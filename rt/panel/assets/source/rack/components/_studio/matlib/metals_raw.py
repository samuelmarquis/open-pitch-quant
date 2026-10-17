"""Metal family, bare stock: wrought, drawn, cast and machined steel, brass,
bronze and aluminium with no plating or conversion coat, plus the generic
builders the other metals_* modules share (`mat_imperfect_metal`,
`mat_plain_metal`, `rebase`).

Calibration per origin component: units.MM_PER_UNIT.
"""
import bpy

from .core import (CALIB_MM_PER_UNIT, DEFAULT_CTX, MaterialContext, _obj_pos, base_material,
                   imperfect, material, sheet_ripple)
from .metals import steel_hw

from .units import mm_per_unit

CORRUGATED_MM = mm_per_unit("conduit-corrugated")
SMOOTH_MM = mm_per_unit("conduit-smooth")
PIPING_MM = mm_per_unit("conduit-piping")
RIBBON_MM = mm_per_unit("conduit-ribbon")
TOGGLE_MM = mm_per_unit("toggle-bat")
FADER_MM = mm_per_unit("fader-desk")
HANDWHEEL_MM = mm_per_unit("knob-handwheel")
JACK_MM = mm_per_unit("jack-socket")
RACK_MM = mm_per_unit("rack-hardware")


def rebase(ctx, calib):
    """The context under which a calib-25 helper (`imperfect`) scales exactly as
    a builder calibrated at `calib` does: identical to DEFAULT_CTX at calib."""
    if ctx.mm_per_unit == calib:
        return DEFAULT_CTX
    return MaterialContext(ctx.mm_per_unit * CALIB_MM_PER_UNIT / calib)


# ---------------------------------------------------------------------------
# shared builders


def _imperfect_metal(color, rough_lo, rough_hi, bump_strength, grain, metallic,
                     anisotropic, coat, coat_roughness, name, ctx, calib, ripple=0.0):
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Anisotropic"].default_value = anisotropic
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = coat_roughness
    imperfect(m, rough_lo, rough_hi, bump_strength=bump_strength, scale=grain,
              ctx=rebase(ctx, calib))
    if ripple > 0:
        sheet_ripple(nt, b, ripple, ctx=ctx)    # a rolled sheet's slow waves (p134)
    return m


def imperfect_metal_at(calib):
    """A builder for the commonest local metal: one Principled with a colour,
    metallic, optional anisotropy / coat, and `imperfect()` roughness mottle +
    micro-bump at `grain` (cycles per world unit). One function per
    calibration unit, because `ctx` does not carry the key's calibration."""
    def mat_imperfect_metal(color=(0.62, 0.63, 0.64), rough_lo=0.24, rough_hi=0.38,
                            bump_strength=0.01, grain=2730.0, metallic=1.0,
                            anisotropic=0.0, coat=0.0, coat_roughness=0.03,
                            ripple=0.0, name="metal", *, ctx=DEFAULT_CTX):
        """Imperfect metal: Principled colour/metallic (+ anisotropy, coat) and
        `imperfect()` roughness mottle between rough_lo and rough_hi with a
        micro-bump at 3x `grain`, and a rolled sheet's `ripple` (core.sheet_ripple
        strength; 0 = none). Any Tangent is Principled's default (no UV map read)."""
        return _imperfect_metal(color, rough_lo, rough_hi, bump_strength, grain, metallic,
                                anisotropic, coat, coat_roughness, name, ctx, calib, ripple)
    mat_imperfect_metal.__name__ = f"mat_imperfect_metal_{calib:g}"
    return mat_imperfect_metal


def mat_plain_metal(color=(0.30, 0.31, 0.34), roughness=0.30, metallic=1.0, name="metal",
                    *, ctx=DEFAULT_CTX):
    """Untextured metal: one Principled with colour, roughness and metallic. No
    spatial constant, so the context changes nothing."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Metallic"].default_value = metallic
    return m


_im_jack = imperfect_metal_at(JACK_MM)
_im_handwheel = imperfect_metal_at(HANDWHEEL_MM)


# ---------------------------------------------------------------------------
# imperfect-metal keys


material("brass-bare", family="metal", finish="satin", solid=True,
         params={"color": (0.58, 0.42, 0.17), "rough_lo": 0.26, "rough_hi": 0.42,
                 "bump_strength": 0.018, "grain": 1690.0, "name": "brass"},
         calib_mm_per_unit=JACK_MM, origin="jack-socket:mat_brass:152")(_im_jack)
material("phosphor-bronze", family="metal", finish="satin", solid=True,
         params={"color": (0.55, 0.40, 0.24), "rough_lo": 0.24, "rough_hi": 0.40,
                 "bump_strength": 0.02, "grain": 7150.0, "name": "bronze"},
         calib_mm_per_unit=JACK_MM, origin="jack-socket:mat_bronze:162")(_im_jack)
# Duplicate candidate: brass-bare (darker, rougher band, matlib imperfect defaults).
material("brass-aged", family="metal", finish="satin", solid=True,
         params={"color": (0.44, 0.29, 0.09), "rough_lo": 0.18, "rough_hi": 0.42,
                 "bump_strength": 0.04, "grain": 2260.0, "name": "brassm"},
         calib_mm_per_unit=HANDWHEEL_MM, origin="knob-handwheel:brassm:313")(_im_handwheel)


# ---------------------------------------------------------------------------
# plain keys (toggle-bat, fader-desk)

material("steel-bare", family="metal", finish="satin", solid=True,
         params={"color": (0.30, 0.31, 0.34), "roughness": 0.30, "name": "nutm"},
         calib_mm_per_unit=TOGGLE_MM, origin="toggle-bat:nutm:101")(mat_plain_metal)
# fader-desk:screwm:364 is steel-dark@roughness=0.24.
material("steel-dark", family="metal", finish="satin", solid=True,
         params={"color": (0.22, 0.22, 0.25), "roughness": 0.28, "name": "bushm"},
         calib_mm_per_unit=TOGGLE_MM, origin="toggle-bat:bushm:103")(mat_plain_metal)


# ---------------------------------------------------------------------------
# conduit workshop steel


def _workshop_steel(nt, b, gain, ctx, calib):
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Base Color"].default_value = (*(c * gain for c in (0.30, 0.31, 0.34)), 1)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), noise.inputs["Vector"])
    noise.inputs["Scale"].default_value = ctx.freq(85.8, calib)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.35
    mr.inputs["From Max"].default_value = 0.75
    mr.inputs["To Min"].default_value = 0.26
    mr.inputs["To Max"].default_value = 0.52
    nt.links.new(noise.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.06
    bmp.inputs["Distance"].default_value = ctx.length(bmp.inputs["Distance"].default_value, calib)
    nt.links.new(noise.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return bmp


@material("steel-workshop", family="metal", finish="satin", solid=True,
          params={"gain": 0.36}, calib_mm_per_unit=CORRUGATED_MM,
          origin="conduit-corrugated:steel:1295")
def mat_steel_workshop(gain=0.36, name="steel", *, ctx=DEFAULT_CTX):
    """Workshop steel for fittings and bolts: isotropic, the richness in a
    noise driving roughness 0.26-0.52 and a grain bump.

    `gain` multiplies the base reflectance (0.30, 0.31, 0.34) only; the
    roughness map and bump are independent of it. 0.36 is conduit-corrugated's
    studio-rig look, 1.0 its canon-rig look.

    Duplicate candidate: steel-workshop-shell (the same front face);
    matlib worn-steel (anisotropic, UV-tangent)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    _workshop_steel(m.node_tree, m.node_tree.nodes["Principled BSDF"], gain, ctx, CORRUGATED_MM)
    return m


@material("steel-workshop-shell", family="metal", finish="satin", solid=False,
          params={"gain": 1.0}, calib_mm_per_unit=SMOOTH_MM,
          origin="conduit-smooth:steel:1483")
def mat_steel_workshop_shell(gain=1.0, name="steel", *, ctx=DEFAULT_CTX):
    """steel-workshop on a zero-thickness shell: BACK faces take a machined-bore
    shader instead (base (0.66, 0.67, 0.69) x gain, metallic 0.30, roughness
    0.55, the same grain bump), so a sealed metal tunnel seen from inside
    returns light instead of mirroring nothing. Needs geometry whose inside is a
    back face; front faces are identical to steel-workshop.

    Duplicate candidate: steel-workshop, steel-machined-bore."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    st = m.node_tree
    sb = st.nodes["Principled BSDF"]
    bmp = _workshop_steel(st, sb, gain, ctx, SMOOTH_MM)
    bore_sh = st.nodes.new("ShaderNodeBsdfPrincipled")
    bore_sh.inputs["Base Color"].default_value = (*(c * gain for c in (0.66, 0.67, 0.69)), 1)
    bore_sh.inputs["Metallic"].default_value = 0.30
    bore_sh.inputs["Roughness"].default_value = 0.55
    st.links.new(bmp.outputs["Normal"], bore_sh.inputs["Normal"])
    geo = st.nodes.new("ShaderNodeNewGeometry")
    mixsh = st.nodes.new("ShaderNodeMixShader")
    st.links.new(geo.outputs["Backfacing"], mixsh.inputs["Fac"])
    st.links.new(sb.outputs["BSDF"], mixsh.inputs[1])
    st.links.new(bore_sh.outputs["BSDF"], mixsh.inputs[2])
    st.links.new(mixsh.outputs["Shader"], st.nodes["Material Output"].inputs["Surface"])
    return m


@material("steel-machined-bore", family="metal", finish="satin", solid=False,
          params={"gain": 0.36}, calib_mm_per_unit=CORRUGATED_MM,
          origin="conduit-corrugated:bore:1369")
def mat_steel_machined_bore(gain=0.36, name="bore", *, ctx=DEFAULT_CTX):
    """Machined bore / counterbore inside a steel fitting: lighter, rougher and
    mostly dielectric (base (0.66, 0.67, 0.69) x gain, metallic 0.30, roughness
    0.45-0.62 from a noise at 349 per unit), so a recess reads as a lit pocket
    rather than a black mirror tunnel. `gain` tracks the fitting's steel-workshop
    gain.

    conduit-smooth:bore_material:1566 builds the same graph (gain 1.0 there).
    Duplicate candidate: steel-workshop-shell's back-face branch."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*(c * gain for c in (0.66, 0.67, 0.69)), 1)
    b.inputs["Metallic"].default_value = 0.30
    n = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), n.inputs["Vector"])
    n.inputs["Scale"].default_value = ctx.freq(349.0, CORRUGATED_MM)
    m2 = nt.nodes.new("ShaderNodeMapRange")
    m2.inputs["From Min"].default_value = 0.35
    m2.inputs["From Max"].default_value = 0.75
    m2.inputs["To Min"].default_value = 0.45
    m2.inputs["To Max"].default_value = 0.62
    nt.links.new(n.outputs["Fac"], m2.inputs["Value"])
    nt.links.new(m2.outputs["Result"], b.inputs["Roughness"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.05
    bp.inputs["Distance"].default_value = ctx.length(bp.inputs["Distance"].default_value, CORRUGATED_MM)
    nt.links.new(n.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


# ---------------------------------------------------------------------------
# conduit-ribbon


@material("steel-milled", family="metal", finish="satin", solid=True,
          calib_mm_per_unit=RIBBON_MM, origin="conduit-ribbon:header_steel:1114")
def mat_steel_milled(rough_lo=0.32, rough_hi=0.58, base=(0.215, 0.225, 0.245),
                     name="header_steel", *, ctx=DEFAULT_CTX):
    """Milled steel block: a dark base, a directional MACHINING grain (Object
    noise stretched 220:7 along Y) driving roughness rough_lo..rough_hi, broad
    worn tonal zones added on top (clamped), and a fine grain bump. Grooves run
    along the part's object Y axis.

    Defaults are conduit-ribbon --matver 2; --matver 1 is rough 0.22-0.46, base
    (0.235, 0.245, 0.265).

    Duplicate candidate: matlib worn-steel (adds anisotropy, UV tangent, rust)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    st = m.node_tree
    sb = st.nodes["Principled BSDF"]
    sb.inputs["Metallic"].default_value = 1.0
    sb.inputs["Base Color"].default_value = (*base, 1)
    tc = st.nodes.new("ShaderNodeTexCoord")
    mp = st.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = ctx.freq((7.0, 220.0, 7.0), RIBBON_MM)
    st.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    n = st.nodes.new("ShaderNodeTexNoise")
    n.inputs["Detail"].default_value = 3.0
    n.inputs["Roughness"].default_value = 0.72
    st.links.new(mp.outputs["Vector"], n.inputs["Vector"])
    mr = st.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = rough_lo
    mr.inputs["To Max"].default_value = rough_hi
    st.links.new(n.outputs["Fac"], mr.inputs["Value"])
    wz = st.nodes.new("ShaderNodeTexNoise")
    st.links.new(tc.outputs["Object"], wz.inputs["Vector"])
    wz.inputs["Scale"].default_value = ctx.freq(10.4, RIBBON_MM)
    wz.inputs["Detail"].default_value = 6.0
    wr = st.nodes.new("ShaderNodeMapRange")
    wr.inputs["To Min"].default_value = -0.07
    wr.inputs["To Max"].default_value = 0.11
    st.links.new(wz.outputs["Fac"], wr.inputs["Value"])
    ad = st.nodes.new("ShaderNodeMath")
    ad.operation = "ADD"
    ad.use_clamp = True
    st.links.new(mr.outputs["Result"], ad.inputs[0])
    st.links.new(wr.outputs["Result"], ad.inputs[1])
    st.links.new(ad.outputs["Value"], sb.inputs["Roughness"])
    bp = st.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.045
    bp.inputs["Distance"].default_value = ctx.length(0.0016, RIBBON_MM)
    st.links.new(n.outputs["Fac"], bp.inputs["Height"])
    st.links.new(bp.outputs["Normal"], sb.inputs["Normal"])
    return m


@material("steel-hw-dull", family="metal", finish="satin", solid=True,
          params={"dull": 0.10}, calib_mm_per_unit=mm_per_unit("default"),
          origin="conduit-ribbon:steel_hw:1201")
def mat_steel_hw_dull(dull=0.10, *, ctx=DEFAULT_CTX):
    """The steel-hw fastener with every roughness Map Range raised by `dull`
    (each end clamped to 1.0). dull=0 is steel-hw exactly. Calibrated where
    steel-hw is (the bin default unit), because it IS steel-hw."""
    m = steel_hw(ctx=ctx)
    if dull <= 0:
        return m
    for n in m.node_tree.nodes:
        if n.type == "MAP_RANGE":
            for s in ("To Min", "To Max"):
                n.inputs[s].default_value = min(1.0, n.inputs[s].default_value + dull)
    return m


# ---------------------------------------------------------------------------
# fader-desk


@material("gunmetal-brushed", family="metal", finish="satin", solid=False,
          calib_mm_per_unit=FADER_MM, origin="fader-desk:panel_metal:308")
def mat_gunmetal_brushed(dark=(0.045, 0.048, 0.055), light=(0.085, 0.088, 0.096),
                         name="panelmetal", *, ctx=DEFAULT_CTX):
    """Dark gunmetal plate: a mottled base colour between `dark` and `light`
    (broad noise), and a grain streaked along object Y (noise
    stretched 45:1.1) driving roughness 0.26-0.52 and a bump."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Metallic"].default_value = 1.0
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = ctx.freq((45.0, 1.1, 45.0), FADER_MM)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 22.0
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.26
    mr.inputs["To Max"].default_value = 0.52
    nt.links.new(noise.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.05
    bmp.inputs["Distance"].default_value = ctx.length(bmp.inputs["Distance"].default_value, FADER_MM)
    nt.links.new(noise.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    mot = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(tc.outputs["Object"], mot.inputs["Vector"])
    mot.inputs["Scale"].default_value = ctx.freq(1.5, FADER_MM)

    def sock(node, ident, outputs=False):
        return next(sk for sk in (node.outputs if outputs else node.inputs)
                    if sk.identifier == ident)
    mix1 = nt.nodes.new("ShaderNodeMix")
    mix1.data_type = "RGBA"
    sock(mix1, "A_Color").default_value = (*dark, 1)
    sock(mix1, "B_Color").default_value = (*light, 1)
    nt.links.new(mot.outputs["Fac"], sock(mix1, "Factor_Float"))
    nt.links.new(sock(mix1, "Result_Color", True), b.inputs["Base Color"])
    return m


# ---------------------------------------------------------------------------
# rack-hardware


def _bump_chain(nt, b, layers, ctx, calib):
    prev = None
    pos = _obj_pos(nt)
    for scale, strength, dist, detail, kind in layers:
        if kind == "noise":
            n = nt.nodes.new("ShaderNodeTexNoise")
            n.inputs["Scale"].default_value = ctx.freq(scale, calib)
            n.inputs["Detail"].default_value = detail
            src = n.outputs["Fac"]
        else:
            n = nt.nodes.new("ShaderNodeTexVoronoi")
            n.feature = "SMOOTH_F1"
            n.inputs["Scale"].default_value = ctx.freq(scale, calib)
            src = n.outputs["Distance"]
        nt.links.new(pos, n.inputs["Vector"])
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = strength
        bmp.inputs["Distance"].default_value = ctx.length(dist, calib)
        nt.links.new(src, bmp.inputs["Height"])
        if prev is not None:
            nt.links.new(prev.outputs["Normal"], bmp.inputs["Normal"])
        prev = bmp
    nt.links.new(prev.outputs["Normal"], b.inputs["Normal"])


@material("aluminium-sand-cast", family="metal", finish="satin", solid=True,
          calib_mm_per_unit=RACK_MM, origin="rack-hardware:mat_cast_alu:263")
def mat_aluminium_sand_cast(name="cast_alu", *, ctx=DEFAULT_CTX):
    """Sand-cast aluminium: a pebbled casting skin at three scales (noise 15.5,
    smooth-F1 Voronoi 67, noise 283, chained bumps) under imperfect() roughness
    0.30-0.50. Base 0.34, below aluminium's chart value, so a rough metal under
    a big source stays metal. Not anisotropic: reads the same on any bend.

    Duplicate candidate: steel-cast / copper-cast (conduit-piping)."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.34, 0.34, 0.35, 1)
    b.inputs["Metallic"].default_value = 1.0
    _bump_chain(nt, b, [(15.5, 0.20, 0.020, 4.0, "noise"),
                        (67.0, 0.42, 0.013, 2.0, "voronoi"),
                        (283.0, 0.16, 0.003, 3.0, "noise")], ctx, RACK_MM)
    imperfect(m, 0.30, 0.50, bump_strength=0.03, scale=206.0, ctx=rebase(ctx, RACK_MM))
    return m


# ---------------------------------------------------------------------------
# conduit-piping: one metal, three manufacturing processes

PIPE_BASE = {"copper": (0.71, 0.44, 0.24, 1), "steel": (0.30, 0.31, 0.34, 1)}


def _chain_bump(nt, b, height_socket, strength, dist):
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = strength
    bmp.inputs["Distance"].default_value = dist
    nt.links.new(height_socket, bmp.inputs["Height"])
    if b.inputs["Normal"].links:
        nt.links.new(b.inputs["Normal"].links[0].from_socket, bmp.inputs["Normal"])
    nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return bmp


def _add_rough(nt, b, socket):
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    add.use_clamp = True
    nt.links.new(b.inputs["Roughness"].links[0].from_socket, add.inputs[0])
    nt.links.new(socket, add.inputs[1])
    nt.links.new(add.outputs["Value"], b.inputs["Roughness"])


def _map(nt, socket, lo, hi, frm=(0.0, 1.0)):
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = frm[0]
    mr.inputs["From Max"].default_value = frm[1]
    mr.inputs["To Min"].default_value = lo
    mr.inputs["To Max"].default_value = hi
    nt.links.new(socket, mr.inputs["Value"])
    return mr.outputs["Result"]


def _noise(nt, scale, detail=6.0, rough=0.5, vector=None):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    nt.links.new(_obj_pos(nt) if vector is None else vector, n.inputs["Vector"])
    return n.outputs["Fac"]


def _voronoi(nt, scale):
    v = nt.nodes.new("ShaderNodeTexVoronoi")
    v.feature = "F1"
    v.inputs["Scale"].default_value = scale
    nt.links.new(_obj_pos(nt), v.inputs["Vector"])
    return v.outputs["Distance"]


# Per finish, the frequencies of the isotropic layers (cycles per world unit at
# PIPING_MM), calibrated on the finish's own part (drawn: a run; cast: an
# elbow; turned: a flange): imperfect() mottle, tonal roughness, sand grain,
# fine grain, and the dings' Voronoi x R.
_PIPE_FREQ = {"drawn": (35.1, 2.04, None, None, None),
              "cast": (57.8, 9.45, 11.6, 42.0, 0.735),
              "turned": (82.4, 13.5, 16.5, 59.9, 1.05)}


def _dir_noise(nt, tc, freq, detail=3.0, rough=0.72):
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = freq
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    return _noise(nt, 1.0, detail, rough, mp.outputs["Vector"])


def mat_pipe_metal(finish="drawn", metal="steel", pipe_radius=0.18, name=None, *,
                   ctx=DEFAULT_CTX):
    """Pipe-assembly metal, `metal` steel | copper, `finish`:

      drawn   pipe barrels: directional grain along object +X driving roughness
              and bump, anisotropy 0.38 on a built-in RADIAL tangent about X
              (circumferential), sparse ring scuffs.
      cast    fitting bodies: sand grain at two scales, crisscross wear
              scratches in object space, sparse Voronoi dings, and POINTINESS
              edge wear, which only reads on small-faceted (voxel-remeshed)
              geometry; a low-poly barrel reads convex everywhere.
      turned  flanges and bolts: concentric tool rings around object +X, grain
              and dings as cast, no pointiness.

    Parts are expected to be built along their own local +X. `pipe_radius` is
    the pipe radius in calibration units (world units x mm_per_unit / calib):
    every grain frequency and bump distance is proportional to it. Every
    roughness term is near zero-mean around the imperfect() band."""
    cast = finish != "drawn"
    R = pipe_radius
    L = PIPING_MM
    m, nt, b = base_material(name or f"{metal}_{finish}")
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Base Color"].default_value = PIPE_BASE[metal]
    if metal == "copper":
        lo, hi = (0.30, 0.60) if cast else (0.24, 0.50)
    else:
        lo, hi = (0.32, 0.62) if cast else (0.26, 0.52)
    f_imp, f_tone, f_grain, f_fine, f_ding = _PIPE_FREQ[finish]
    imperfect(m, lo, hi, bump_strength=0.05 if cast else 0.035, scale=f_imp,
              ctx=rebase(ctx, L))
    tc = nt.nodes.new("ShaderNodeTexCoord")
    _add_rough(nt, b, _map(nt, _noise(nt, ctx.freq(f_tone, L), 6.0, vector=tc.outputs["Object"]),
                           -0.09, 0.13 if cast else 0.11))
    if finish == "drawn":
        b.inputs["Anisotropic"].default_value = 0.38
        tan = nt.nodes.new("ShaderNodeTangent")
        tan.direction_type = "RADIAL"
        tan.axis = "X"
        nt.links.new(tan.outputs["Tangent"], b.inputs["Tangent"])
        brush = _dir_noise(nt, tc, ctx.freq((0.18 / R, 7.0 / R, 7.0 / R), L),
                           detail=3.0, rough=0.62)
        _add_rough(nt, b, _map(nt, brush, -0.08, 0.08))
        _chain_bump(nt, b, brush, 0.18, ctx.length(0.008 * R, L))
        hair = _dir_noise(nt, tc, ctx.freq((0.25 / R, 13.0 / R, 13.0 / R), L), detail=2.0)
        _chain_bump(nt, b, hair, 0.08, ctx.length(0.0025 * R, L))
        ring = _map(nt, _dir_noise(nt, tc, ctx.freq((3.0 / R, 0.4 / R, 0.4 / R), L),
                                   detail=3.0),
                    0.0, 1.0, frm=(0.58, 0.80))
        _add_rough(nt, b, _map(nt, ring, -0.02, 0.08))
        _chain_bump(nt, b, ring, 0.12, ctx.length(0.005 * R, L))
    else:
        grain = _noise(nt, ctx.freq(f_grain, L), 6.0, vector=tc.outputs["Object"])
        _chain_bump(nt, b, grain, 0.22, ctx.length(0.014 * R, L))
        _chain_bump(nt, b, _noise(nt, ctx.freq(f_fine, L), 4.0, vector=tc.outputs["Object"]),
                    0.10, ctx.length(0.004 * R, L))
        if finish == "turned":
            rings = _dir_noise(nt, tc, ctx.freq((9.0 / R, 0.35 / R, 0.35 / R), L), detail=2.0)
            _add_rough(nt, b, _map(nt, rings, -0.05, 0.09))
            _chain_bump(nt, b, rings, 0.11, ctx.length(0.005 * R, L))
        else:
            _chain_bump(nt, b, _dir_noise(nt, tc, ctx.freq((0.55 / R, 9.0 / R, 9.0 / R), L),
                                          detail=2.0),
                        0.16, ctx.length(0.009 * R, L))
            _chain_bump(nt, b, _dir_noise(nt, tc, ctx.freq((9.0 / R, 0.55 / R, 0.55 / R), L),
                                          detail=2.0),
                        0.13, ctx.length(0.008 * R, L))
        # the ding threshold is in Voronoi cell space, not a spatial constant
        ding = _map(nt, _voronoi(nt, ctx.freq(f_ding / R, L)), 1.0, 0.0, frm=(0.0, 0.20 * R))
        _chain_bump(nt, b, ding, -0.22, ctx.length(0.020 * R, L))
        _add_rough(nt, b, _map(nt, ding, 0.0, 0.09))
    if finish == "cast":
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        _add_rough(nt, b, _map(nt, geo.outputs["Pointiness"], 0.0, -0.11, frm=(0.52, 0.64)))
    return m


_PIPE = dict(family="metal", finish="satin", calib_mm_per_unit=PIPING_MM)

# Duplicate candidate (drawn): matlib brushed / worn-steel (UV tangent instead of RADIAL).
material("steel-drawn", solid=False, params={"finish": "drawn", "metal": "steel"},
         origin="conduit-piping:metal(METAL,'drawn'):728", **_PIPE)(mat_pipe_metal)
material("copper-drawn", solid=False, params={"finish": "drawn", "metal": "copper"},
         origin="conduit-piping:metal(METAL,'drawn'):728", **_PIPE)(mat_pipe_metal)
# Duplicate candidate (cast): aluminium-sand-cast; matlib worn-steel's scratches.
material("steel-cast", solid=True, params={"finish": "cast", "metal": "steel"},
         origin="conduit-piping:metal(METAL,'cast'):729", **_PIPE)(mat_pipe_metal)
material("copper-cast", solid=True, params={"finish": "cast", "metal": "copper"},
         origin="conduit-piping:metal(METAL,'cast'):729", **_PIPE)(mat_pipe_metal)
material("steel-turned", solid=False, params={"finish": "turned", "metal": "steel"},
         origin="conduit-piping:metal(METAL,'turned'):730", **_PIPE)(mat_pipe_metal)
material("copper-turned", solid=False, params={"finish": "turned", "metal": "copper"},
         origin="conduit-piping:metal(METAL,'turned'):730", **_PIPE)(mat_pipe_metal)
