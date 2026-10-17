"""Resin family: cast and moulded thermoset resins — marbled cast phenolic
(catalin), glass-filled epoxy packages, pigmented diffusant lenses.
"""
from .core import DEFAULT_CTX, _obj_pos, base_material, imperfect, material
from .nodes import deep as _deep
from .units import mm_per_unit

CATALIN_MM = mm_per_unit("knob-catalin")
RING_MM = mm_per_unit("knob-ring")
SEGMENT_MM = mm_per_unit("display-segment")


# ---------------------------------------------------------------------------
# catalin


def _math(nt, op, a=None, b=None, value_b=None, value_a=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    if a is not None:
        nt.links.new(a, n.inputs[0])
    elif value_a is not None:
        n.inputs[0].default_value = value_a
    if b is not None:
        nt.links.new(b, n.inputs[1])
    elif value_b is not None:
        n.inputs[1].default_value = value_b
    return n.outputs[0]


def _vmath(nt, op, a=None, b=None, value_b=None, scale=None):
    n = nt.nodes.new("ShaderNodeVectorMath")
    n.operation = op
    if a is not None:
        nt.links.new(a, n.inputs[0])
    if b is not None:
        nt.links.new(b, n.inputs[1])
    elif value_b is not None:
        n.inputs[1].default_value = value_b
    if scale is not None:
        n.inputs["Scale"].default_value = scale
    out = "Value" if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else "Vector"
    return n.outputs[out]


def _noise(nt, vec, scale, detail=2.0, rough=0.5, distortion=0.0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.noise_dimensions = "3D"
    nt.links.new(vec, n.inputs["Vector"])
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    n.inputs["Distortion"].default_value = distortion
    return n


def _mix_rgb(nt, fac, a, b):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = "MIX"
    ins = {s.identifier: s for s in n.inputs}
    outs = {s.identifier: s for s in n.outputs}
    if isinstance(fac, float):
        ins["Factor_Float"].default_value = fac
    else:
        nt.links.new(fac, ins["Factor_Float"])
    for key, val in (("A_Color", a), ("B_Color", b)):
        if isinstance(val, tuple):
            ins[key].default_value = (*val, 1.0)
        else:
            nt.links.new(val, ins[key])
    return outs["Result_Color"]


def _warp(nt, vec, scale, amount, detail=2.0):
    """Domain warp: vec + (noise colour - 0.5) * amount, both in vec's space."""
    n = _noise(nt, vec, scale, detail=detail, rough=0.55)
    centred = _vmath(nt, "SUBTRACT", n.outputs["Color"], value_b=(0.5, 0.5, 0.5))
    push = _vmath(nt, "SCALE", centred, scale=amount)
    return _vmath(nt, "ADD", vec, push)


def _marble_fields(nt, pos, seed, marble_freq, soft=False):
    """Folded, domain-warped laminar marbling. `pos` is scaled by `marble_freq`
    and offset by `seed`; every constant after that lives in the scaled space.
    Returns (swirl 0..1, vein 0..1)."""
    p = _vmath(nt, "ADD", _vmath(nt, "SCALE", pos, scale=marble_freq), value_b=seed)
    p1 = _warp(nt, p, 1.15, 1.35, detail=1.0)
    p2 = _warp(nt, p1, 3.1, 0.42, detail=2.0)
    axis = _vmath(nt, "DOT_PRODUCT", p2, value_b=(0.62, 0.34, 0.71))
    fbm = _noise(nt, p2, 2.2, detail=3.0, rough=0.55)
    t = _math(nt, "ADD", _math(nt, "MULTIPLY", axis, value_b=11.0),
              _math(nt, "MULTIPLY", fbm.outputs["Fac"], value_b=7.0))
    s = _math(nt, "ABSOLUTE", _math(nt, "SINE", t))
    band = _math(nt, "POWER", _math(nt, "SUBTRACT", value_a=1.0, b=s), value_b=3.2)
    cloud = _noise(nt, p1, 1.9, detail=2.0, rough=0.5)
    cloud_ramp = nt.nodes.new("ShaderNodeMapRange")
    cloud_ramp.inputs["From Min"].default_value = 0.63
    cloud_ramp.inputs["From Max"].default_value = 0.80
    nt.links.new(cloud.outputs["Fac"], cloud_ramp.inputs["Value"])
    cloud_w = _math(nt, "MULTIPLY", cloud_ramp.outputs["Result"], value_b=0.30)
    swirl = _math(nt, "MAXIMUM", band, cloud_w)
    swirl = _math(nt, "MULTIPLY", _math(nt, "MINIMUM", swirl, value_b=1.0), value_b=0.62)
    t2 = _math(nt, "ADD", _math(nt, "MULTIPLY", t, value_b=0.5), value_b=1.3)
    s2 = _math(nt, "ABSOLUTE", _math(nt, "SINE", t2))
    vein = _math(nt, "POWER", _math(nt, "SUBTRACT", value_a=1.0, b=s2), value_b=9.0)
    if soft:
        return swirl, vein
    t3 = _math(nt, "MULTIPLY", t, value_b=4.0)
    fine_noise = _noise(nt, p2, 9.0, detail=2.0, rough=0.5)
    t3 = _math(nt, "ADD", t3, _math(nt, "MULTIPLY", fine_noise.outputs["Fac"], value_b=3.0))
    s3 = _math(nt, "ABSOLUTE", _math(nt, "SINE", t3))
    streak = _math(nt, "POWER", _math(nt, "SUBTRACT", value_a=1.0, b=s3), value_b=6.0)
    gate = _noise(nt, p1, 2.6, detail=1.0)
    gate_r = nt.nodes.new("ShaderNodeMapRange")
    gate_r.inputs["From Min"].default_value = 0.45
    gate_r.inputs["From Max"].default_value = 0.62
    nt.links.new(gate.outputs["Fac"], gate_r.inputs["Value"])
    streak = _math(nt, "MULTIPLY", streak,
                   _math(nt, "MULTIPLY", gate_r.outputs["Result"], value_b=0.45))
    swirl = _math(nt, "MINIMUM", _math(nt, "ADD", swirl, streak), value_b=1.0)
    return swirl, vein


def _pointer_mask(nt, pos, pointer_w, pointer_r0, pointer_zmin):
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(pos, sep.inputs["Vector"])
    x, y, z = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]
    lateral = _math(nt, "ABSOLUTE", y)
    across = _math(nt, "LESS_THAN", lateral, value_b=pointer_w * 0.36)
    in0 = _math(nt, "GREATER_THAN", x, value_b=pointer_r0 + 0.002)
    in1 = _math(nt, "GREATER_THAN", z, value_b=pointer_zmin + 0.006)
    high = _math(nt, "GREATER_THAN", x, value_b=0.0)
    m = _math(nt, "MULTIPLY", across, in0)
    m = _math(nt, "MULTIPLY", m, in1)
    return _math(nt, "MULTIPLY", m, high)


_CATALIN = dict(family="resin", finish="gloss", solid=True, calib_mm_per_unit=CATALIN_MM,
                origin="knob-catalin:catalin_material:445",
                part_bound={"pointer_w": "pointer_width", "pointer_r0": "pointer_start",
                            "pointer_zmin": "pointer_floor_z"})


_CHERRY = {
    "base": (0.30, 0.003, 0.008), "deep": (0.10, 0.0008, 0.003),
    "glow": (0.55, 0.018, 0.012), "seed": (3.7, -1.9, 2.3), "swirl": (0.78, 0.24, 0.12),
    "vein": (0.045, 0.0005, 0.002), "sss": (1.0, 0.10, 0.10), "age": (0.30, 0.02, 0.01),
    "inlay": (0.66, 0.34, 0.025)}
_JADE = {
    "base": (0.002, 0.24, 0.135), "deep": (0.0005, 0.065, 0.042),
    "glow": (0.012, 0.40, 0.25), "seed": (-2.6, 4.1, -0.7), "swirl": (0.12, 0.54, 0.36),
    "vein": (0.001, 0.030, 0.020), "sss": (0.20, 1.0, 0.70), "age": (0.06, 0.22, 0.12),
    "inlay": (0.72, 0.64, 0.46)}
# Polished catalin plates (Nolan's crud_ui rack folders): an even wall, no
# pointer, the polish on the body itself (no coat), shallow subsurface, and
# _plate_inks' tiered marbling. AgX skews saturated red toward orange: the
# cherry reds carry a little blue against it.
_PLATE = {"polished": True, "deepen": 0.33}
_JADE_POLISHED = {
    **_JADE, **_PLATE, "base": (0.030, 0.250, 0.060), "deep": (0.012, 0.120, 0.030),
    "glow": (0.090, 0.400, 0.100), "ink": (0.527, 0.479, 0.080), "sss": (0.6, 1.0, 0.25),
    "age": (0.24, 0.26, 0.04), "spec_tint": (0.7, 1.0, 0.4), "marble": (1.0, 0.55, 0.45, 0.3)}
_CHERRY_POLISHED = {
    **_CHERRY, **_PLATE, "base": (0.360, 0.0, 0.020), "deep": (0.130, 0.0, 0.016),
    "glow": (0.500, 0.010, 0.016), "ink": (0.620, 0.060, 0.010), "ink2": (0.791, 0.130, 0.004),
    "sss": (1.0, 0.06, 0.04), "age": (0.30, 0.006, 0.008), "spec_tint": (1.0, 0.10, 0.10),
    "marble": (0.8, 0.5, 0.75, 0.4)}


@material("catalin", **_CATALIN)
@material("catalin-cherry", params=_CHERRY, **_CATALIN)
@material("catalin-jade", params=_JADE, **_CATALIN)
@material("catalin-cherry-polished", params=_CHERRY_POLISHED, **_CATALIN)
@material("catalin-jade-polished", params=_JADE_POLISHED, **_CATALIN)
def mat_catalin(base=(0.54, 0.22, 0.0012), deep=(0.25, 0.048, 0.0006),
                glow=(0.70, 0.155, 0.0003), seed=(0.0, 0.0, 0.0), swirl=(0.76, 0.42, 0.10),
                vein=(0.15, 0.022, 0.0015), sss=(1.0, 0.64, 0.22), age=(0.55, 0.36, 0.05),
                inlay=(0.050, 0.006, 0.005), pointer_w=0.034, pointer_r0=0.070,
                pointer_zmin=0.165, name="cast catalin", polished=False, deepen=1.0,
                ink=None, ink2=None, marble=(0.8, 0.5, 0.5, 0.6), spec_tint=None,
                *, ctx=DEFAULT_CTX):
    """Cast catalin (see _mat_catalin); `deepen` scales its colour.

    `polished` makes a plate: an even wall, no pointer, no coat (the polish is
    the body's own), subsurface 0.35, the face reflection tinted `spec_tint`,
    and the knob's swirl swapped for _plate_inks: `deep`..`base` masses with
    `ink` in tiers weighed by `marble` (mass, cloud, wisp, crisp) and
    optional `ink2` flame tongues."""
    if polished:
        # a plate carries no pointer: the inlay's floor far above any part
        # (pointer_zmin is part-bound, so a measured value would bring it back)
        pointer_zmin = 1.0e3
    m = _mat_catalin(base, deep, glow, seed, swirl, vein, sss, age, inlay, pointer_w,
                     pointer_r0, pointer_zmin, name,
                     ink=ink if polished else None, ink2=ink2, marble=marble, ctx=ctx)
    if polished or deepen != 1.0:
        from .finishes import darken, even_wall, principled

        if polished:
            even_wall(m)
        # the body: the BSDF that already scatters (the pointer inlay does not)
        for b in [b for b in principled(m) if b.inputs["Subsurface Weight"].default_value > 0]:
            if polished:
                b.inputs["Coat Weight"].default_value = 0.0
                b.inputs["Subsurface Weight"].default_value = 0.35
                if spec_tint is not None:
                    # a dyed body's face reflection keeps its hue, so a
                    # highlight goes to its own colour rather than white
                    b.inputs["Specular Tint"].default_value = (*spec_tint, 1.0)
            if deepen != 1.0:
                darken(m.node_tree, b, deepen)
    return m


def _iso(nt, field, level, width, soft, drag=None):
    """1 within `width` of `field` == `level`, falling to 0 over `soft` (over
    `drag` on the low side, when given): a filament along one isoline of a
    noise field, crisp at its leading edge and dragged out at its trailing."""
    d = _math(nt, "SUBTRACT", field, value_b=level)
    lead = _ramp(nt, d, width + soft, width)
    trail = _ramp(nt, d, -width - (soft if drag is None else drag), -width)
    return _math(nt, "MINIMUM", lead, trail)


def _flow(nt, pos, seed, ctx):
    """The stirred flow of poured phenolic: one flow direction (object x, the
    plate's length), 1-3 cm eddies and S-folds from three warp octaves.
    Returns (q, layers): the warped coordinate, and layers(freq, drift, off,
    detail) -> a noise field 0..1 laid along the folded layer coordinate."""
    p = _vmath(nt, "MULTIPLY", pos, value_b=ctx.freq((0.8, 1.05, 1.05)))
    p = _vmath(nt, "ADD", p, value_b=seed)
    q = _warp(nt, p, 0.7, 2.8, detail=2.0)
    q = _warp(nt, q, 2.2, 0.55, detail=2.0)
    q = _warp(nt, q, 7.0, 0.07, detail=1.0)
    t = _vmath(nt, "DOT_PRODUCT", q, value_b=(0.10, 1.0, 0.25))
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(q, sep.inputs["Vector"])

    def layers(freq, drift, off, detail):
        v = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(_math(nt, "MULTIPLY", t, value_b=freq), v.inputs["X"])
        nt.links.new(_math(nt, "MULTIPLY", sep.outputs["X"], value_b=drift), v.inputs["Y"])
        v.inputs["Z"].default_value = off
        return _noise(nt, v.outputs["Vector"], 1.0, detail=detail, rough=0.55).outputs["Fac"]

    return q, layers


def _ramp(nt, v, lo, hi):
    r = nt.nodes.new("ShaderNodeMapRange")
    r.inputs["From Min"].default_value = lo
    r.inputs["From Max"].default_value = hi
    nt.links.new(v, r.inputs["Value"])
    return r.outputs["Result"]


def _gate(nt, q, scale, lo, hi, off):
    """A slow patch mask on the flow: where a structure occurs at all."""
    shifted = _vmath(nt, "ADD", q, value_b=(off, -off, 0.5 * off))
    return _ramp(nt, _noise(nt, shifted, scale, detail=2.0).outputs["Fac"], lo, hi)


def _plate_inks(nt, pos, below, seed, base, deep, glow, ink, ink2, marble, ctx):
    """A catalin plate's colour, by scale and by depth (`marble` weighs the
    tiers: mass, cloud, wisp, crisp):
      mass   large soft masses of `deep`..`base` carry most of the area
      cloud  smoky ink a few mm down (sampled `below`), feathered, diluted
      wisp   mid streaks along the folds, soft-edged, in patches
      crisp  a few sharp filaments at the skin, rarer still
    `ink2` adds feathered flame tongues with a brighter core; the bevels
    saturate toward `glow` where the wall is thin."""
    w_mass, w_cloud, w_wisp, w_crisp = marble
    q, layers = _flow(nt, pos, seed, ctx)
    qd, layers_d = _flow(nt, below, seed, ctx)
    mass = _noise(nt, q, 0.8, detail=8.0, rough=0.62).outputs["Fac"]
    col = _mix_rgb(nt, _math(nt, "MULTIPLY", _ramp(nt, mass, 0.36, 0.64), value_b=w_mass),
                   base, deep)
    # smoke: blurred wisps along the folds, a few mm down, everywhere; ink
    # thinned into the lit body
    diluted = tuple(0.35 * i + 0.65 * g for i, g in zip(ink, glow))
    smoke = _math(nt, "MAXIMUM", _iso(nt, layers_d(1.2, 0.6, 21.7, 4.0), 0.5, 0.01, 0.08),
                  _iso(nt, layers_d(2.8, 1.0, 27.1, 4.0), 0.5, 0.004, 0.04))
    smoke = _math(nt, "MULTIPLY", smoke, _gate(nt, qd, 0.7, 0.36, 0.56, 8.3))
    # everything poured is drawn into fibres along the flow: feathered, not filled
    fib =_ramp(nt, layers(24.0, 2.5, 19.9, 2.0), 0.30, 0.70)
    fib = _math(nt, "ADD", _math(nt, "MULTIPLY", fib, value_b=0.6), value_b=0.4)
    smoke = _math(nt, "MULTIPLY", smoke, fib)
    col = _mix_rgb(nt, _math(nt, "MULTIPLY", smoke, value_b=w_cloud), col, diluted)
    if ink2 is not None:
        # flames: tongues 1-3 cm streaming with the flow, combed into fibres,
        # translucent amber at the edge, orange, then a yellow core
        flame = _noise(nt, _vmath(nt, "MULTIPLY", qd, value_b=(0.85, 1.15, 1.0)), 1.1, detail=6.0,
                       rough=0.64).outputs["Fac"]
        comb = _math(nt, "MAXIMUM", _ramp(nt, layers(18.0, 2.0, 37.1, 2.0), 0.40, 0.62),
                     _ramp(nt, layers(40.0, 3.0, 41.3, 1.0), 0.45, 0.58))
        comb = _math(nt, "ADD", _math(nt, "MULTIPLY", comb, value_b=0.8), value_b=0.2)
        amber = tuple(c * k for c, k in zip(ink2, (0.95, 0.75, 1.0)))
        core = (min(3.0, 1.4 * ink2[0]), min(3.0, 4.8 * ink2[1]), 5.0 * ink2[2])
        # the amber body of a tongue is continuous; its brighter fibres combed
        for lo, hi, k, c, combed in ((0.50, 0.62, 0.75, amber, False),
                                     (0.54, 0.65, 0.9, ink2, True),
                                     (0.59, 0.69, 0.95, core, True)):
            heat = _ramp(nt, flame, lo, hi)
            if combed:
                heat = _math(nt, "MULTIPLY", heat, comb)
            col = _mix_rgb(nt, _math(nt, "MULTIPLY", heat, value_b=k), col, c)
    # wisps: feathered clusters of fine strands where the ink was drawn out
    strands = _math(nt, "MAXIMUM", _iso(nt, layers(4.0, 1.2, 7.7, 3.0), 0.5, 0.001, 0.016,
                                        drag=0.05),
                    _iso(nt, layers(11.0, 2.2, 31.3, 2.0), 0.5, 0.001, 0.010))
    wisp = _math(nt, "MULTIPLY", strands, _gate(nt, q, 1.1, 0.52, 0.64, 2.3))
    wisp = _math(nt, "MULTIPLY", wisp, fib)
    col = _mix_rgb(nt, _math(nt, "MULTIPLY", wisp, value_b=w_wisp), col, ink)
    crisp = _iso(nt, layers(9.0, 2.0, 13.3, 2.0), 0.5, 0.0022, 0.0015)
    crisp = _math(nt, "MULTIPLY", crisp, _gate(nt, q, 1.4, 0.60, 0.67, 5.9))
    col = _mix_rgb(nt, _math(nt, "MULTIPLY", crisp, value_b=w_crisp), col, ink)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.3
    return _mix_rgb(nt, _math(nt, "MULTIPLY", lw.outputs["Facing"], value_b=0.4), col, glow)


def _mat_catalin(base, deep, glow, seed, swirl, vein, sss, age, inlay, pointer_w, pointer_r0,
                 pointer_zmin, name, ink=None, ink2=None, marble=None, *, ctx=DEFAULT_CTX):
    """Cast catalin (phenolic resin poured and folded while casting): full
    random-walk subsurface (IOR 1.55) under a thin 1.52 coat, the colour
    deepening with path length, over folded domain-warped laminar marbling.

    - Marbling in Object space: two warp octaves fold one laminar direction
      into whorls, |sin| folds give thin bright bands, dark veins run at half
      frequency; a second, softer fold is sampled 0.06 below the skin along the
      object-space normal.
    - Thickness: AO cast INTO the solid (distance 0.22) is the wall-thickness
      proxy, thick -> `deep`, mid -> `base`, thin -> `glow`.
    - Ageing: patchy crazing hairlines (warped Voronoi distance-to-edge, broken
      into open segments, inverted bump) and faint yellowing toward `age`.
    - Pointer: a paint-filled engraved line mixed in as a second BSDF
      (`inlay`, roughness 0.34) where |y| < 0.36 `pointer_w`, x >
      `pointer_r0` + 0.002 and z > `pointer_zmin` + 0.006 — object-space
      geometry of the component's pointer groove, not scaled by ctx.

    `seed` offsets the marbling in its already-scaled space (a phase). The
    colourways are butterscotch (default), cherry and jade.
    Duplicate candidate: bakelite, bakelite-butterscotch."""
    m, nt, b = base_material(name)
    b.subsurface_method = "RANDOM_WALK"
    b.inputs["Subsurface Weight"].default_value = 1.0
    b.inputs["Subsurface Radius"].default_value = sss
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.045)
    b.inputs["IOR"].default_value = 1.55
    b.inputs["Coat Weight"].default_value = 0.12
    b.inputs["Coat Roughness"].default_value = 0.06
    b.inputs["Coat IOR"].default_value = 1.52
    imperfect(m, 0.055, 0.13, bump_strength=0.004, scale=55.0, ctx=ctx)
    rough_src = b.inputs["Roughness"].links[0].from_socket
    normal_src = b.inputs["Normal"].links[0].from_socket

    coord = nt.nodes.new("ShaderNodeTexCoord")
    pos = coord.outputs["Object"]
    marble_freq = ctx.freq(0.50)
    if ink is None:
        swirl_f, vein_f = _marble_fields(nt, pos, seed, marble_freq)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    to_obj = nt.nodes.new("ShaderNodeVectorTransform")
    to_obj.vector_type = "NORMAL"
    to_obj.convert_from = "WORLD"
    to_obj.convert_to = "OBJECT"
    nt.links.new(geo.outputs["Normal"], to_obj.inputs["Vector"])
    below = _vmath(nt, "SUBTRACT", pos,
                   _vmath(nt, "SCALE", to_obj.outputs["Vector"], scale=ctx.length(0.06)))
    below = _vmath(nt, "ADD", below, value_b=ctx.length((0.21, -0.13, 0.08)))
    if ink is None:
        deep_swirl, _deep_vein = _marble_fields(nt, below, seed, marble_freq, soft=True)

    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.inside = True
    ao.samples = 8
    ao.inputs["Distance"].default_value = ctx.length(0.22)
    thin_ramp = nt.nodes.new("ShaderNodeMapRange")
    thin_ramp.inputs["From Min"].default_value = 0.30
    thin_ramp.inputs["From Max"].default_value = 0.62
    nt.links.new(_math(nt, "SUBTRACT", value_a=1.0, b=ao.outputs["AO"]), thin_ramp.inputs["Value"])
    thin = thin_ramp.outputs["Result"]

    lo = _math(nt, "MINIMUM", _math(nt, "MULTIPLY", thin, value_b=2.0), value_b=1.0)
    hi = _math(nt, "MAXIMUM", _math(nt, "SUBTRACT", _math(nt, "MULTIPLY", thin, value_b=2.0),
                                    value_b=1.0), value_b=0.0)
    if ink is None:
        body = _mix_rgb(nt, lo, deep, base)
        body = _mix_rgb(nt, _math(nt, "MULTIPLY", hi, value_b=0.65), body, glow)
        body = _mix_rgb(nt, _math(nt, "MULTIPLY", deep_swirl, value_b=0.38), body,
                        tuple(0.55 * sw + 0.45 * ba for sw, ba in zip(swirl, base)))
        body = _mix_rgb(nt, swirl_f, body, swirl)
        body = _mix_rgb(nt, _math(nt, "MULTIPLY", vein_f, value_b=0.55), body, vein)
    else:
        body = _plate_inks(nt, pos, below, seed, base, deep, glow, ink, ink2, marble, ctx)
        # a cast face is never optically flat: a slow wave in the reflections
        swell = _noise(nt, pos, ctx.freq(0.8), detail=1.0)
        wave = nt.nodes.new("ShaderNodeBump")
        wave.inputs["Strength"].default_value = 0.12
        wave.inputs["Distance"].default_value = ctx.length(0.02)
        nt.links.new(swell.outputs["Fac"], wave.inputs["Height"])
        nt.links.new(normal_src, wave.inputs["Normal"])
        normal_src = wave.outputs["Normal"]
        # a hard polish on the body itself
        rough_src.node.inputs["To Min"].default_value = 0.025
        rough_src.node.inputs["To Max"].default_value = 0.055
    craze = nt.nodes.new("ShaderNodeTexVoronoi")
    craze.feature = "DISTANCE_TO_EDGE"
    craze.inputs["Scale"].default_value = ctx.freq(26.0)
    craze.inputs["Randomness"].default_value = 1.0
    nt.links.new(_warp(nt, pos, ctx.freq(4.0), ctx.length(0.12), detail=1.0),
                 craze.inputs["Vector"])
    line = nt.nodes.new("ShaderNodeMapRange")
    line.inputs["From Min"].default_value = 0.035
    line.inputs["From Max"].default_value = 0.0
    nt.links.new(craze.outputs["Distance"], line.inputs["Value"])
    patch = _noise(nt, pos, ctx.freq(3.2), detail=2.0)
    patch_r = nt.nodes.new("ShaderNodeMapRange")
    patch_r.inputs["From Min"].default_value = 0.47
    patch_r.inputs["From Max"].default_value = 0.62
    nt.links.new(patch.outputs["Fac"], patch_r.inputs["Value"])
    seg = _noise(nt, pos, ctx.freq(38.0), detail=1.0)
    seg_r = nt.nodes.new("ShaderNodeMapRange")
    seg_r.inputs["From Min"].default_value = 0.52
    seg_r.inputs["From Max"].default_value = 0.60
    nt.links.new(seg.outputs["Fac"], seg_r.inputs["Value"])
    crazing = _math(nt, "MULTIPLY", line.outputs["Result"], patch_r.outputs["Result"])
    crazing = _math(nt, "MULTIPLY", crazing, seg_r.outputs["Result"])
    body = _mix_rgb(nt, _math(nt, "MULTIPLY", crazing, value_b=0.16), body, glow)
    body = _mix_rgb(nt, 0.06, body, age)
    nt.links.new(body, b.inputs["Base Color"])
    craze_bump = nt.nodes.new("ShaderNodeBump")
    craze_bump.invert = True
    craze_bump.inputs["Strength"].default_value = 0.05
    craze_bump.inputs["Distance"].default_value = ctx.length(0.0015)
    nt.links.new(crazing, craze_bump.inputs["Height"])
    nt.links.new(normal_src, craze_bump.inputs["Normal"])
    nt.links.new(craze_bump.outputs["Normal"], b.inputs["Normal"])
    rough = _math(nt, "ADD", rough_src, _math(nt, "MULTIPLY", crazing, value_b=0.10))
    rough = _math(nt, "ADD", rough, _math(nt, "MULTIPLY", hi, value_b=0.06))
    nt.links.new(rough, b.inputs["Roughness"])

    paint = nt.nodes.new("ShaderNodeBsdfPrincipled")
    paint.inputs["Base Color"].default_value = (*inlay, 1.0)
    paint.inputs["Roughness"].default_value = 0.34
    mask = _pointer_mask(nt, pos, pointer_w, pointer_r0, pointer_zmin)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(mask, mix.inputs["Fac"])
    nt.links.new(b.outputs["BSDF"], mix.inputs[1])
    nt.links.new(paint.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], nt.nodes["Material Output"].inputs["Surface"])
    return m


# ---------------------------------------------------------------------------
# epoxy packages


@material("epoxy-package", family="resin", finish="matte", solid=True,
          calib_mm_per_unit=SEGMENT_MM, origin="display-segment:mat_epoxy:592")
def mat_epoxy_package(name="epoxy", *, ctx=DEFAULT_CTX):
    """Black moulded glass-filled epoxy (a display package face): a shade
    lighter than true black so dark lenses set in it still read, carrying the
    fill's speckle (Smooth-F1 Voronoi at 271 per unit into a 0.0018 bump), no coat.
    Duplicate candidate: glass-filled-nylon, epoxy-package-rim."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.0225, 0.0215, 0.0235, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.36
    fill = nt.nodes.new("ShaderNodeTexVoronoi")
    fill.feature = "SMOOTH_F1"
    nt.links.new(_obj_pos(nt), fill.inputs["Vector"])
    fill.inputs["Scale"].default_value = ctx.freq(271.0)
    fb = nt.nodes.new("ShaderNodeBump")
    fb.inputs["Strength"].default_value = 0.045
    fb.inputs["Distance"].default_value = ctx.length(0.0018)
    nt.links.new(fill.outputs["Distance"], fb.inputs["Height"])
    nt.links.new(fb.outputs["Normal"], b.inputs["Normal"])
    imperfect(m, 0.50, 0.66, bump_strength=0.012, scale=160.0, ctx=ctx)
    return m


@material("epoxy-package-rim", family="resin", finish="satin", solid=True,
          calib_mm_per_unit=SEGMENT_MM, origin="display-segment:mat_rim:758")
def mat_epoxy_package_rim(name="rim", *, ctx=DEFAULT_CTX):
    """The package epoxy where the mould's land met it: a shade darker, a thin
    coat (0.12 at 0.38) and no fill speckle. More coat turns a moulded rim into
    a glossy frame that competes with what it holds.
    Duplicate candidate: epoxy-package."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.0195, 0.0190, 0.0210, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.12
    b.inputs["Coat Roughness"].default_value = 0.38
    imperfect(m, 0.44, 0.60, bump_strength=0.018, scale=191.0, ctx=ctx)
    return m


# ---------------------------------------------------------------------------
# diffusant lenses


_FROSTED = dict(family="resin", finish="satin", solid=True, calib_mm_per_unit=SEGMENT_MM,
                origin="display-segment:mat_diffusant:614")


@material("diffusant-frosted", **_FROSTED)
@material("diffusant-frosted-amber",
          params={"tint": (0.145, 0.058, 0.010), "emission_color": (1.00, 0.520, 0.070)},
          **_FROSTED)
@material("diffusant-frosted-green",
          params={"tint": (0.028, 0.120, 0.038), "emission_color": (0.045, 1.00, 0.150)},
          **_FROSTED)
def mat_diffusant_frosted(tint=(0.135, 0.016, 0.010), emission_color=(1.00, 0.110, 0.050),
                          emission=1.4, name="diffusant_lit", *, ctx=DEFAULT_CTX):
    """Pigmented frosted epoxy diffusant (a segment lens): tint, IOR 1.52,
    roughness 0.36, a thin coat, and transmission 0.25 — a ceiling: a lens in a
    dark pocket that transmits more becomes a light trap and renders darker
    than the package around it.

    One material for both states: `emission` 0 is the unlit GHOST (a faintly
    visible tinted shape), > 0 lights it. Under AgX emission is a saturation
    control, so the hue is hit at a moderate strength. The tint is the unlit
    pigment set against the package epoxy (~3x its albedo). Colourways: red
    (default), amber, green. No spatial constants."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*tint, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.36
    b.inputs["IOR"].default_value = 1.52
    b.inputs["Transmission Weight"].default_value = 0.25
    b.inputs["Coat Weight"].default_value = 0.16
    b.inputs["Coat Roughness"].default_value = 0.22
    b.inputs["Emission Color"].default_value = (*emission_color, 1)
    b.inputs["Emission Strength"].default_value = emission
    return m


_MATTE = dict(family="resin", finish="matte", solid=True, calib_mm_per_unit=RING_MM,
              origin="knob-ring:lens_material:270")


@material("diffusant-matte", **_MATTE)
@material("diffusant-matte-amber", params={"hue": (1.00, 0.52, 0.07)}, **_MATTE)
@material("diffusant-matte-green", params={"hue": (0.10, 1.00, 0.25)}, **_MATTE)
@material("diffusant-matte-mcblue", params={"hue": (0.08, 0.60, 1.00)}, **_MATTE)
@material("diffusant-matte-white", params={"hue": (1.00, 0.95, 0.85)}, **_MATTE)
def mat_diffusant_matte(hue=(1.00, 0.11, 0.05), ghost=0.036, emission=1.45, name="lens lit",
                        *, ctx=DEFAULT_CTX):
    """Pigmented matte diffusant block (an LED ring lens): unlit it is a dark
    tinted block that still catches the key (base = deep(hue, 3) x `ghost`),
    lit the same block emits deep(hue, 2) at `emission`. Lit and unlit differ in
    emission strength and nothing else, which keeps layer bakes exact
    (radiance is linear in the set of emitters).

    Matte and nearly specular-free (0.03, coat 0.04 at 0.34): any gloss on a
    horizontal lens face staring into the key turns a dark lens into a pale
    chip. Subsurface 0.14 with a hue-shaped radius, scale 0.015; imperfect()
    sets roughness 0.54-0.68. Hues are led-indicator's glow roster.
    Duplicate candidate: diffusant-frosted."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*(c * ghost for c in _deep(hue, 3)), 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.60
    b.inputs["Specular IOR Level"].default_value = 0.03
    b.inputs["Coat Weight"].default_value = 0.04
    b.inputs["Coat Roughness"].default_value = 0.34
    b.inputs["Subsurface Weight"].default_value = 0.14
    b.inputs["Subsurface Radius"].default_value = tuple(max(c, 0.02) for c in hue)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.015)
    b.inputs["Emission Color"].default_value = (*_deep(hue, 2), 1)
    b.inputs["Emission Strength"].default_value = emission
    imperfect(m, 0.54, 0.68, bump_strength=0.006, scale=2260.0, ctx=ctx)
    return m
