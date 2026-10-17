"""Textile family: woven, pressed, knitted and upholstered cloth, plus the
shared cloth mechanisms the leather and paper families also use.

    _weave()        real warp/weft crossing, so cloth catches light in two directions
    _nap()          Principled Sheen = the fibre rim-light that makes felt read fuzzy
    _fibres()       stacked high-frequency bump, the "it has a pile" cue
    _wool()         crossed filament layers (matted fibre)
    _tone_mottle()  broad dye-lot drift

SCALE CALIBRATION: constants are read at PANEL size — a 3x2-unit board at
25 mm/unit filling the frame, under one big soft overhead, dead-on. Anything
finer than ~100 cycles per unit, or shallower than ~0.01 bump distance, is
invisible there; the canon reference is styrofoam's beads at 12.2/26.9 per
unit, distance 0.16/0.05. On a flat dead-on panel the RELIEF has to carry the
cloth.

Ramp stops must follow the driving signal's DISTRIBUTION: a Wave Factor is
arcsine-distributed and `_weave`'s height is a MAX of two, which piles up
near 1.
"""
import bpy

from .core import DEFAULT_CTX, _obj_pos, _obj_vec, base_material, material
from .nodes import _mix_rgba


def _weave(nt, scale=61.2, aspect=1.0, distortion=0.25, detail=2.0, *, ctx=DEFAULT_CTX):
    """Plain warp/weft weave. Two crossed band waves; their MAXIMUM is the
    cloth surface (whichever thread is on top at that point stands proud) and
    their DIFFERENCE says WHICH one it is.

    That second output is the whole point: real cloth changes lustre with
    thread direction, so driving roughness/sheen from the warp mask makes the
    weave catch the key in two directions instead of reading as a printed grid.
    The mask is a subtraction, so it is one-directional: it belongs in
    roughness/lustre, never in pattern (base colour from it paints stripes).

    Returns (height_socket, warp_mask_socket) — mask 1 = warp on top.

    DISTORTION IS A CLIFF: the Wave node's distortion displaces the bands by
    noise, so past ~0.5 the two sets stop being bands at all and the MAX
    degenerates into speckle (burlap at 1.8 renders as sand, tweed at 1.1 as
    stripes). Keep it low; irregularity belongs in the fibre octaves on top,
    where it does not eat the weave."""
    pos = _obj_pos(nt)
    warp = nt.nodes.new("ShaderNodeTexWave")
    warp.wave_type, warp.bands_direction, warp.wave_profile = "BANDS", "X", "SIN"
    nt.links.new(pos, warp.inputs["Vector"])
    warp.inputs["Scale"].default_value = ctx.freq(scale)
    warp.inputs["Distortion"].default_value = distortion
    warp.inputs["Detail"].default_value = detail
    weft = nt.nodes.new("ShaderNodeTexWave")
    weft.wave_type, weft.bands_direction, weft.wave_profile = "BANDS", "Y", "SIN"
    nt.links.new(pos, weft.inputs["Vector"])
    weft.inputs["Scale"].default_value = ctx.freq(scale * aspect)
    weft.inputs["Distortion"].default_value = distortion
    weft.inputs["Detail"].default_value = detail
    hi = nt.nodes.new("ShaderNodeMath")
    hi.operation = "MAXIMUM"
    nt.links.new(warp.outputs["Factor"], hi.inputs[0])
    nt.links.new(weft.outputs["Factor"], hi.inputs[1])
    df = nt.nodes.new("ShaderNodeMath")
    df.operation = "SUBTRACT"
    nt.links.new(warp.outputs["Factor"], df.inputs[0])
    nt.links.new(weft.outputs["Factor"], df.inputs[1])
    mask = nt.nodes.new("ShaderNodeMapRange")
    mask.inputs["From Min"].default_value = -0.15
    mask.inputs["From Max"].default_value = 0.15
    nt.links.new(df.outputs["Value"], mask.inputs["Value"])
    return hi.outputs["Value"], mask.outputs["Result"]


def _nap(b, weight=1.0, rough=0.30, tint=(1, 1, 1, 1)):
    """Principled Sheen — the retroreflective rim a fibre pile throws at
    grazing angles. Without it a high-roughness diffuse just reads as chalk;
    with it, as cloth."""
    b.inputs["Sheen Weight"].default_value = weight
    b.inputs["Sheen Roughness"].default_value = rough
    b.inputs["Sheen Tint"].default_value = tint


def _wool(nt, b, layers=((0.25, 1.0, 15.0, 0.95, 0.105),
                         (1.05, 1.0, 13.0, 0.95, 0.098),
                         (1.95, 1.0, 16.0, 0.88, 0.090),
                         (2.70, 1.0, 14.0, 0.82, 0.082),
                         (0.65, 1.0, 46.0, 0.45, 0.030),
                         (0.0, 55.0, 55.0, 0.35, 0.020)),
          prev=None, *, ctx=DEFAULT_CTX):
    """MATTED WOOL: crossed layers of FILAMENTS, not a field of blobs.

    Each layer is a noise lookup stretched ~30:1 and rotated, so it resolves
    into long thin threads lying at that angle; several angles laid over each
    other is what felting physically is. Isotropic noise octaves cannot get
    here — they give rounded lumps and read as suede or styrofoam. Layers are
    (rotation_rad, across, along, strength, distance); across/along are the
    chain frequency, distance a length.
    """
    for rot, across, along, strength, dist in layers:
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = 1.0
        n.inputs["Detail"].default_value = 4.0
        n.inputs["Roughness"].default_value = 0.62
        nt.links.new(_obj_vec(nt, ctx.freq((across, along, 1.0)), rot), n.inputs["Vector"])
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = strength
        bmp.inputs["Distance"].default_value = ctx.length(dist)
        nt.links.new(n.outputs["Fac"], bmp.inputs["Height"])
        if prev is not None:
            nt.links.new(prev, bmp.inputs["Normal"])
        prev = bmp.outputs["Normal"]
    if b is not None:
        nt.links.new(prev, b.inputs["Normal"])
    return prev


def _fibres(nt, b, scales=((36.7, 0.30, 0.030), (98.0, 0.16, 0.010)),
            stretch=None, prev=None, *, ctx=DEFAULT_CTX):
    """Stacked bump octaves = the pile. `stretch` gives the fibres a lie
    direction (nap), which is what separates felt from velvet. Scales are
    Object-coordinate frequencies, unless `stretch` puts the octave on a
    scaled Object chain, in which case the stretch carries the frequency.

    Calibrated at PANEL size (see the module docstring). Sheen is kept for
    bezels and tilted shots, but on a flat dead-on panel the RELIEF has to
    carry the cloth by itself."""
    for scale, strength, dist in scales:
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale if stretch is not None else ctx.freq(scale)
        n.inputs["Detail"].default_value = 4.0
        nt.links.new(_obj_pos(nt) if stretch is None else _obj_vec(nt, ctx.freq(stretch)),
                     n.inputs["Vector"])
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = strength
        bmp.inputs["Distance"].default_value = ctx.length(dist)
        nt.links.new(n.outputs["Fac"], bmp.inputs["Height"])
        if prev is not None:
            nt.links.new(prev, bmp.inputs["Normal"])
        prev = bmp.outputs["Normal"]
    if b is not None:
        nt.links.new(prev, b.inputs["Normal"])
    return prev


def _tone_mottle(nt, b, col, amount=0.10, scale=3.67, *, ctx=DEFAULT_CTX):
    """Broad dye/lot variation. Flat cloth colour is the giveaway that a
    textile is a fill; real bolts drift a little across a panel's width.
    Returns the ramp node so callers can multiply a second field into it."""
    n = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), n.inputs["Vector"])
    n.inputs["Scale"].default_value = ctx.freq(scale)
    n.inputs["Detail"].default_value = 3.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    lo = tuple(c * (1.0 - amount) for c in col)
    hi = tuple(min(1.0, c * (1.0 + amount)) for c in col)
    ramp.color_ramp.elements[0].color = (*lo, 1)
    ramp.color_ramp.elements[1].color = (*hi, 1)
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return ramp


# Cloth under the house rig (pass 38): the sheen, spec and coat above were
# tuned under panel_studio's matte tier, which hid the world from glossy rays
# and lit from one overhead. Under knob_studio at -1.3 stops (Sam's pick, p116)
# a sheen at weight ~1 and tight roughness images as a glassy rim on every
# curve — felt and knit "too shiny". Measured on the mosaic: these factors take
# felt-crimson's highlight p99 106 -> 71 and knit's 124 -> 95 while the flat
# colour moves 1-6 levels and texture holds or grows. Vinyl (tolex) keeps its
# own spec: it is not cloth.
CLOTH_SHEEN_K, CLOTH_SPEC_K, CLOTH_COAT_K = 0.15, 0.5, 0.5


def _cloth_finish(nt):
    """Apply the cloth factors to every Principled BSDF in the graph (damask
    has two faces). Call last."""
    for n in nt.nodes:
        if n.type != "BSDF_PRINCIPLED":
            continue
        for sock, k in (("Sheen Weight", CLOTH_SHEEN_K), ("Specular IOR Level", CLOTH_SPEC_K),
                        ("Coat Weight", CLOTH_COAT_K)):
            if not n.inputs[sock].is_linked:
                n.inputs[sock].default_value *= k


_FELT = dict(family="textile", finish="matte", solid=False, origin="matlib.mat_felt")


@material("felt", **_FELT)
@material("felt-crimson", params={"col": (0.34, 0.05, 0.06), "name": "felt_crimson"}, **_FELT)
@material("felt-mustard", params={"col": (0.46, 0.31, 0.05), "name": "felt_mustard"}, **_FELT)
@material("felt-ink", params={"col": (0.05, 0.07, 0.11), "name": "felt_ink"}, **_FELT)
@material("felt-baize", params={"col": (0.035, 0.175, 0.075), "name": "felt_baize"}, **_FELT)
def mat_felt(col=(0.30, 0.34, 0.31), name="felt", *, ctx=DEFAULT_CTX):
    """Pressed wool felt: no weave at all — matted fibre, so the read is pure
    PILE. Dead-matte Oren-Nayar body, strong sheen for the nap rim, a shallow
    SSS so light creeps a millimetre into the mat, and two bump octaves of
    fibre. The one material here with no directionality whatsoever."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.95
    b.inputs["Diffuse Roughness"].default_value = 0.85   # Oren-Nayar: flat, powdery
    b.inputs["Specular IOR Level"].default_value = 0.18
    b.inputs["Subsurface Weight"].default_value = 0.16
    b.inputs["Subsurface Radius"].default_value = (0.5, 0.45, 0.42)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.012)
    _nap(b, weight=1.0, rough=0.26)
    mot = _tone_mottle(nt, b, col, amount=0.11, scale=2.86, ctx=ctx)
    # PRESSED, not woven: a broad low-frequency undulation from the rolling,
    # under the fibre octaves. Fibre alone reads as even suede — felt is never
    # flat, it has soft hills where the mat compacted unevenly.
    press = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), press.inputs["Vector"])
    press.inputs["Scale"].default_value = ctx.freq(4.49)
    press.inputs["Detail"].default_value = 3.0
    pb = nt.nodes.new("ShaderNodeBump")
    pb.inputs["Strength"].default_value = 0.40
    pb.inputs["Distance"].default_value = ctx.length(0.09)
    nt.links.new(press.outputs["Fac"], pb.inputs["Height"])
    _wool(nt, b, prev=pb.outputs["Normal"], ctx=ctx)
    # deeper pile sits in its own shadow: darken along the fibre lie, so the
    # tonal depth is THREADED too rather than blotchy
    shade = nt.nodes.new("ShaderNodeTexNoise")
    shade.inputs["Scale"].default_value = 1.0
    shade.inputs["Detail"].default_value = 4.0
    nt.links.new(_obj_vec(nt, ctx.freq((0.9, 14.0, 1.0)), 0.25), shade.inputs["Vector"])
    sr = nt.nodes.new("ShaderNodeMapRange")
    sr.inputs["To Min"].default_value = 0.68
    sr.inputs["To Max"].default_value = 1.0
    nt.links.new(shade.outputs["Fac"], sr.inputs["Value"])
    _mx, mf, ma, mb2, mres = _mix_rgba(nt, "MULTIPLY")
    mf.default_value = 1.0
    nt.links.new(mot.outputs["Color"], ma)
    nt.links.new(sr.outputs["Result"], mb2)
    nt.links.new(mres, b.inputs["Base Color"])
    _cloth_finish(nt)
    return m


_DAMASK = dict(family="textile", finish="satin", solid=False, origin="matlib.mat_damask")


@material("damask", **_DAMASK)
@material("damask-teal", params={"ground": (0.05, 0.16, 0.17), "motif": (0.09, 0.25, 0.25),
                                 "name": "damask_teal"}, **_DAMASK)
def mat_damask(ground=(0.20, 0.06, 0.10), motif=(0.30, 0.11, 0.15),
               name="damask", *, ctx=DEFAULT_CTX):
    """Woven silk damask. The motif is NOT printed: ground and figure are the
    same yarn woven with opposite faces — warp-satin against weft-satin — so
    the pattern appears and disappears as the light moves. Two BSDFs through a
    Mix Shader, differing in roughness, sheen and anisotropy direction, sharing
    one weave; the colour difference is deliberately tiny, because lustre is
    what actually carries a damask."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    out = nt.nodes["Material Output"]
    fig = nt.nodes["Principled BSDF"]

    # --- the ogee lattice: two diagonal band waves crossed, times a ring
    # rosette, thresholded hard. Distortion is what stops it reading as tartan.
    d1 = nt.nodes.new("ShaderNodeTexWave")
    d1.wave_type, d1.bands_direction, d1.wave_profile = "BANDS", "DIAGONAL", "SIN"
    d1.inputs["Scale"].default_value = 4.0
    # DISTORTION CLIFF: the ogee only exists while the two diagonals are still
    # bands (4.5 is noise).
    d1.inputs["Distortion"].default_value = 0.22
    d1.inputs["Detail"].default_value = 2.0
    # BOTH legs must come from the same space or they never cross — one leg on
    # generated coords against the other on object coords gives horizontal
    # streaking, not a lattice.
    nt.links.new(_obj_vec(nt, ctx.freq((1.0, 1.0, 1.0))), d1.inputs["Vector"])
    d2 = nt.nodes.new("ShaderNodeTexWave")
    d2.wave_type, d2.bands_direction, d2.wave_profile = "BANDS", "DIAGONAL", "SIN"
    d2.inputs["Scale"].default_value = 4.0
    d2.inputs["Distortion"].default_value = 0.22
    d2.inputs["Phase Offset"].default_value = 3.14159
    nt.links.new(_obj_vec(nt, ctx.freq((-1.0, 1.0, 1.0))), d2.inputs["Vector"])
    ros = nt.nodes.new("ShaderNodeTexWave")
    ros.wave_type, ros.wave_profile = "RINGS", "SIN"
    ros.inputs["Scale"].default_value = 9.0
    ros.inputs["Distortion"].default_value = 0.6      # a rosette, not a storm
    ros.inputs["Detail"].default_value = 2.0
    nt.links.new(_obj_vec(nt, ctx.freq((1.0, 1.4, 1.0))), ros.inputs["Vector"])
    # The LATTICE is the product of the two diagonals: two crossed band sets
    # multiplied give the pointed-arch grid an ogee is built on. The rosette
    # rides inside each cell, at a fraction of the weight, so it decorates the
    # lattice instead of drowning it (added 1:1 it gives soft waves).
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(d1.outputs["Factor"], mul.inputs[0])
    nt.links.new(d2.outputs["Factor"], mul.inputs[1])
    rw = nt.nodes.new("ShaderNodeMath")
    rw.operation = "MULTIPLY"
    rw.inputs[1].default_value = 0.35
    nt.links.new(ros.outputs["Factor"], rw.inputs[0])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(mul.outputs["Value"], add.inputs[0])
    nt.links.new(rw.outputs["Value"], add.inputs[1])
    pat = nt.nodes.new("ShaderNodeMapRange")
    pat.inputs["From Min"].default_value = 0.30      # narrow band = crisp figure
    pat.inputs["From Max"].default_value = 0.46
    nt.links.new(add.outputs["Value"], pat.inputs["Value"])

    height, warp = _weave(nt, scale=28.6, distortion=0.18, ctx=ctx)

    def face(bsdf, base, rough, sheen, aniso, rot):
        bsdf.inputs["Metallic"].default_value = 0.0
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Anisotropic"].default_value = aniso
        bsdf.inputs["Anisotropic Rotation"].default_value = rot
        bsdf.inputs["Specular IOR Level"].default_value = 0.45
        _nap(bsdf, weight=sheen, rough=0.22)
        _tone_mottle(nt, bsdf, base, amount=0.07, scale=2.45, ctx=ctx)
        wb = nt.nodes.new("ShaderNodeBump")
        wb.inputs["Strength"].default_value = 0.30
        wb.inputs["Distance"].default_value = ctx.length(0.004)
        nt.links.new(height, wb.inputs["Height"])
        nt.links.new(wb.outputs["Normal"], bsdf.inputs["Normal"])

    # figure = warp-faced satin (lustrous, grain one way); ground = weft-faced
    # (duller, grain across). Rotating anisotropy 90 deg is the whole trick.
    face(fig, motif, 0.26, 0.55, 0.80, 0.0)
    gnd = nt.nodes.new("ShaderNodeBsdfPrincipled")
    face(gnd, ground, 0.44, 0.95, 0.80, 0.25)

    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(pat.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(gnd.outputs["BSDF"], mix.inputs[1])
    nt.links.new(fig.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    _cloth_finish(nt)
    return m


@material("corduroy", family="textile", finish="matte", solid=False,
          origin="matlib.mat_corduroy")
def mat_corduroy(col=(0.32, 0.18, 0.09), name="corduroy", *, ctx=DEFAULT_CTX):
    """Cotton corduroy: cut-pile WALES running the panel's long axis. The wale
    crowns are the only thing that catches the key, so roughness is driven from
    the same wave as the height and the sheen does the rest."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Diffuse Roughness"].default_value = 0.7
    b.inputs["Specular IOR Level"].default_value = 0.22
    _nap(b, weight=1.0, rough=0.24)
    _tone_mottle(nt, b, col, amount=0.08, scale=3.27, ctx=ctx)
    pos = _obj_pos(nt)
    wale = nt.nodes.new("ShaderNodeTexWave")
    wale.wave_type, wale.bands_direction, wale.wave_profile = "BANDS", "Y", "SIN"
    nt.links.new(pos, wale.inputs["Vector"])
    wale.inputs["Scale"].default_value = ctx.freq(8.16)   # fat wales, countable
    wale.inputs["Distortion"].default_value = 0.25     # wales wander slightly
    wale.inputs["Detail"].default_value = 2.0
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.62           # crown: tighter pile
    rr.inputs["To Max"].default_value = 0.95           # valley: dead matte
    nt.links.new(wale.outputs["Factor"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    # CRUSH: worn corduroy has patches where the pile has been flattened and
    # lies the wrong way, which is most of what makes it look used rather than
    # printed. Broad, soft, and it reaches colour as well as relief.
    crush = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, crush.inputs["Vector"])
    crush.inputs["Scale"].default_value = ctx.freq(1.47)
    crush.inputs["Detail"].default_value = 6.0
    crush.inputs["Roughness"].default_value = 0.6
    cr = nt.nodes.new("ShaderNodeMapRange")
    cr.inputs["To Min"].default_value = 0.80
    cr.inputs["To Max"].default_value = 1.16
    nt.links.new(crush.outputs["Fac"], cr.inputs["Value"])
    _cx, cf, ca, cb2, cres = _mix_rgba(nt, "MULTIPLY")
    cf.default_value = 1.0
    nt.links.new(b.inputs["Base Color"].links[0].from_socket, ca)
    nt.links.new(cr.outputs["Result"], cb2)
    nt.links.new(cres, b.inputs["Base Color"])
    wb = nt.nodes.new("ShaderNodeBump")
    wb.inputs["Strength"].default_value = 1.0
    wb.inputs["Distance"].default_value = ctx.length(0.055)   # wales must cast on each other
    nt.links.new(wale.outputs["Factor"], wb.inputs["Height"])
    _fibres(nt, b, scales=((49.0, 0.26, 0.016), (131.0, 0.14, 0.006)),
            prev=wb.outputs["Normal"], ctx=ctx)
    _cloth_finish(nt)
    return m


@material("denim", family="textile", finish="matte", solid=False,
          origin="matlib.mat_denim")
def mat_denim(col=(0.055, 0.085, 0.175), name="denim", *, ctx=DEFAULT_CTX):
    """Indigo denim: 3/1 right-hand TWILL, so the diagonal is the identity.
    Indigo dyes only the warp, which is why the white weft flecks through —
    that flecking is driven off the weave's own warp mask, not painted on."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.80
    b.inputs["Diffuse Roughness"].default_value = 0.6
    b.inputs["Specular IOR Level"].default_value = 0.25
    _nap(b, weight=0.55, rough=0.32)
    pos = _obj_pos(nt)
    twill = nt.nodes.new("ShaderNodeTexWave")
    twill.wave_type, twill.bands_direction, twill.wave_profile = "BANDS", "DIAGONAL", "SAW"
    nt.links.new(pos, twill.inputs["Vector"])
    twill.inputs["Scale"].default_value = ctx.freq(10.6)      # coarse enough to READ
    twill.inputs["Distortion"].default_value = 0.35
    twill.inputs["Detail"].default_value = 2.0
    # warp (indigo) vs weft (undyed) — the fleck. Both stops are pushed LATE:
    # a ramp running 0 -> 0.78 leaves most of the cloth blended toward the
    # undyed weft and reads as pale denim-effect blue instead of indigo.
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*col, 1)
    ramp.color_ramp.elements[1].color = (min(1.0, col[0] * 2.1 + 0.20),
                                         min(1.0, col[1] * 1.9 + 0.20),
                                         min(1.0, col[2] * 1.4 + 0.16), 1)
    ramp.color_ramp.elements[0].position = 0.58
    ramp.color_ramp.elements[1].position = 0.90     # weft is the MINORITY face
    # The Wave's own distribution is not uniform once Detail is on, so the
    # factor is CONTRAST-STRETCHED before the ramp reads it. The raw factor
    # parks the whole cloth at the pale weft end (measured std 7.5, against
    # ~15 for a texture that reads) — denim-effect, not denim.
    tstretch = nt.nodes.new("ShaderNodeMapRange")
    tstretch.inputs["From Min"].default_value = 0.30
    tstretch.inputs["From Max"].default_value = 0.70
    nt.links.new(twill.outputs["Factor"], tstretch.inputs["Value"])
    nt.links.new(tstretch.outputs["Result"], ramp.inputs["Fac"])
    # WEAR, not just a wash. Indigo sits on the outside of the yarn and rubs
    # off where the cloth is handled, so a real bolt has soft pale whiskers and
    # darker unwashed pockets over the twill. Two scales: broad lot variation
    # and a finer, stretched abrasion that follows the weft.
    fade = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, fade.inputs["Vector"])
    fade.inputs["Scale"].default_value = ctx.freq(1.22)
    fade.inputs["Detail"].default_value = 6.0
    fade.inputs["Roughness"].default_value = 0.65
    whisk = nt.nodes.new("ShaderNodeTexNoise")
    whisk.inputs["Scale"].default_value = 14.0
    whisk.inputs["Detail"].default_value = 4.0
    nt.links.new(_obj_vec(nt, ctx.freq((0.55, 9.0, 1.0))), whisk.inputs["Vector"])
    wsum = nt.nodes.new("ShaderNodeMath")
    wsum.operation = "MULTIPLY_ADD"
    wsum.inputs[1].default_value = 0.62
    nt.links.new(fade.outputs["Fac"], wsum.inputs[0])
    wmul = nt.nodes.new("ShaderNodeMath")
    wmul.operation = "MULTIPLY"
    wmul.inputs[1].default_value = 0.38
    nt.links.new(whisk.outputs["Fac"], wmul.inputs[0])
    nt.links.new(wmul.outputs["Value"], wsum.inputs[2])
    fmr = nt.nodes.new("ShaderNodeMapRange")
    fmr.inputs["To Min"].default_value = 0.74
    fmr.inputs["To Max"].default_value = 1.26
    nt.links.new(wsum.outputs["Value"], fmr.inputs["Value"])
    _mx, mfac, ma, mb, mres = _mix_rgba(nt, "MULTIPLY")
    mfac.default_value = 1.0
    nt.links.new(ramp.outputs["Color"], ma)
    nt.links.new(fmr.outputs["Result"], mb)
    nt.links.new(mres, b.inputs["Base Color"])
    tb = nt.nodes.new("ShaderNodeBump")
    tb.inputs["Strength"].default_value = 0.65
    tb.inputs["Distance"].default_value = ctx.length(0.022)
    nt.links.new(twill.outputs["Factor"], tb.inputs["Height"])
    # SLUBS: cotton yarn is uneven, so the twill wanders in thickness. Without
    # them the diagonal is a printed graphic — perfectly regular, which is the
    # one thing denim never is.
    slub = nt.nodes.new("ShaderNodeTexNoise")
    slub.inputs["Scale"].default_value = 22.0
    slub.inputs["Detail"].default_value = 6.0
    nt.links.new(_obj_vec(nt, ctx.freq((0.8, 14.0, 1.0))), slub.inputs["Vector"])
    sb = nt.nodes.new("ShaderNodeBump")
    sb.inputs["Strength"].default_value = 0.45
    sb.inputs["Distance"].default_value = ctx.length(0.030)
    nt.links.new(slub.outputs["Fac"], sb.inputs["Height"])
    nt.links.new(tb.outputs["Normal"], sb.inputs["Normal"])
    _fibres(nt, b, scales=((57.2, 0.24, 0.012), (155.0, 0.12, 0.004)),
            prev=sb.outputs["Normal"], ctx=ctx)
    _cloth_finish(nt)
    return m


@material("burlap", family="textile", finish="matte", solid=False,
          origin="matlib.mat_burlap")
def mat_burlap(col=(0.44, 0.33, 0.17), name="burlap", *, ctx=DEFAULT_CTX):
    """Jute hessian: the coarsest weave in the bin. Big slubby threads with
    real gaps, high distortion so no two crossings match, and enough bump that
    the weave shadows itself."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Diffuse Roughness"].default_value = 0.8
    b.inputs["Specular IOR Level"].default_value = 0.20
    _nap(b, weight=0.8, rough=0.36)
    height, warp = _weave(nt, scale=12.2, distortion=0.45, detail=3.0, ctx=ctx)
    _tone_mottle(nt, b, col, amount=0.16, scale=5.72, ctx=ctx)
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.70
    rr.inputs["To Max"].default_value = 0.96
    nt.links.new(warp, rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    hb = nt.nodes.new("ShaderNodeBump")
    hb.inputs["Strength"].default_value = 1.0
    hb.inputs["Distance"].default_value = ctx.length(0.095)   # coarsest weave in the bin
    nt.links.new(height, hb.inputs["Height"])
    _fibres(nt, b, scales=((36.7, 0.40, 0.032), (98.0, 0.20, 0.011)),
            prev=hb.outputs["Normal"], ctx=ctx)
    _cloth_finish(nt)
    return m


_KNIT = dict(family="textile", finish="matte", solid=False, origin="matlib.mat_knit")


@material("knit", **_KNIT)
@material("knit-cream", params={"col": (0.62, 0.56, 0.43), "name": "knit_cream"}, **_KNIT)
@material("knit-chunky", params={"col": (0.42, 0.33, 0.22), "name": "knit_chunky", "chunk": 2.1},
          **_KNIT)
def mat_knit(col=(0.55, 0.20, 0.18), name="knit", chunk=1.0, *, ctx=DEFAULT_CTX):
    """Stockinette wool. Each stitch is a V: two opposed diagonal waves MAXed
    together give the chevron, a row wave separates the courses, and the yarn
    gets its own twist bump on top. Sheen high — the fuzziest thing in the
    roster after felt. `chunk` scales the needle size: 1.0 is a fine jersey,
    ~2 is hand-knitted aran, and the stitch relief grows with it because a
    fatter yarn genuinely stands prouder."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.92
    b.inputs["Diffuse Roughness"].default_value = 0.8
    b.inputs["Specular IOR Level"].default_value = 0.16
    b.inputs["Subsurface Weight"].default_value = 0.12
    b.inputs["Subsurface Radius"].default_value = (0.6, 0.5, 0.45)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.02)
    _nap(b, weight=1.0, rough=0.28)
    _tone_mottle(nt, b, col, amount=0.10, scale=3.67, ctx=ctx)

    # THE YARN IS A ROPE. Each leg of the V is a fat round strand, so the legs
    # are built as SIN bands pushed through a power curve — that is what turns
    # a soft sinusoid into a tube with a crown and a deep valley beside it.
    # Chunky knitwear is ropes lying against ropes; a plain MAX of two gentle
    # waves gives a ribbed surface with no strand in it.
    def leg(sx, rot):
        w = nt.nodes.new("ShaderNodeTexWave")
        w.wave_type, w.bands_direction, w.wave_profile = "BANDS", "DIAGONAL", "SIN"
        w.inputs["Scale"].default_value = 11.0 / chunk
        w.inputs["Distortion"].default_value = 0.22
        w.inputs["Detail"].default_value = 1.0
        nt.links.new(_obj_vec(nt, ctx.freq((sx, 1.0, 1.0)), rot), w.inputs["Vector"])
        rope = nt.nodes.new("ShaderNodeMath")        # crown the strand
        rope.operation = "POWER"
        rope.inputs[1].default_value = 0.45
        nt.links.new(w.outputs["Factor"], rope.inputs[0])
        return rope.outputs["Value"]

    chev = nt.nodes.new("ShaderNodeMath")
    chev.operation = "MAXIMUM"
    nt.links.new(leg(1.0, 0.10), chev.inputs[0])
    nt.links.new(leg(-1.0, -0.10), chev.inputs[1])
    # courses: rows of stitches, with a deep gap between rows so the knit reads
    # as stacked bands of loops rather than one continuous mesh
    course = nt.nodes.new("ShaderNodeTexWave")
    course.wave_type, course.bands_direction, course.wave_profile = "BANDS", "Y", "SIN"
    nt.links.new(_obj_pos(nt), course.inputs["Vector"])
    course.inputs["Scale"].default_value = ctx.freq(2.86 / chunk)
    course.inputs["Distortion"].default_value = 0.20
    crow = nt.nodes.new("ShaderNodeMapRange")
    crow.inputs["To Min"].default_value = 0.30       # the gutter between courses
    crow.inputs["To Max"].default_value = 1.0
    nt.links.new(course.outputs["Factor"], crow.inputs["Value"])
    st = nt.nodes.new("ShaderNodeMath")
    st.operation = "MULTIPLY"
    nt.links.new(chev.outputs["Value"], st.inputs[0])
    nt.links.new(crow.outputs["Result"], st.inputs[1])
    sb = nt.nodes.new("ShaderNodeBump")
    sb.inputs["Strength"].default_value = 1.0
    sb.inputs["Distance"].default_value = ctx.length(0.20 * chunk)   # fatter yarn, prouder
    nt.links.new(st.outputs["Value"], sb.inputs["Height"])
    # stitch shadow: the gutters go darker, which is what sells depth at a
    # glance far more than relief does on a flat dead-on panel
    shr = nt.nodes.new("ShaderNodeMapRange")
    shr.inputs["To Min"].default_value = 0.52
    shr.inputs["To Max"].default_value = 1.06
    nt.links.new(st.outputs["Value"], shr.inputs["Value"])
    _kx, kf, ka, kb2, kres = _mix_rgba(nt, "MULTIPLY")
    kf.default_value = 1.0
    nt.links.new(b.inputs["Base Color"].links[0].from_socket, ka)
    nt.links.new(shr.outputs["Result"], kb2)
    nt.links.new(kres, b.inputs["Base Color"])
    # TWIST: the ply spiralling along each strand, at a steep angle to it
    twist = nt.nodes.new("ShaderNodeTexWave")
    twist.wave_type, twist.bands_direction, twist.wave_profile = "BANDS", "DIAGONAL", "SIN"
    twist.inputs["Scale"].default_value = 60.0 / chunk
    twist.inputs["Distortion"].default_value = 0.6
    nt.links.new(_obj_vec(nt, ctx.freq((1.0, 2.6, 1.0)), 1.1), twist.inputs["Vector"])
    tb = nt.nodes.new("ShaderNodeBump")
    tb.inputs["Strength"].default_value = 0.45
    tb.inputs["Distance"].default_value = ctx.length(0.030 * chunk)
    nt.links.new(twist.outputs["Factor"], tb.inputs["Height"])
    nt.links.new(sb.outputs["Normal"], tb.inputs["Normal"])
    _wool(nt, b, layers=((0.4, 1.0, 26.0, 0.30 * chunk, 0.022 * chunk),
                         (2.2, 1.0, 30.0, 0.24 * chunk, 0.016 * chunk),
                         (1.2, 1.0, 80.0, 0.16, 0.007)),
          prev=tb.outputs["Normal"], ctx=ctx)
    _cloth_finish(nt)
    return m


@material("tweed", family="textile", finish="satin", solid=False,
          origin="matlib.mat_tweed")
def mat_tweed(col_a=(0.52, 0.42, 0.20), col_b=(0.26, 0.19, 0.09), name="tweed",
              *, ctx=DEFAULT_CTX):
    """Lacquered amp tweed: a coarse two-yarn twill under yellowed nitrocellulose.
    The audio-historical one — this is a 1950s combo cabinet. The lacquer coat
    is what separates it from burlap: cloth texture under a hard gloss."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Coat Weight"].default_value = 0.22      # the nitro
    b.inputs["Coat Roughness"].default_value = 0.45   # a crisp coat flattens the cloth
    b.inputs["Coat Tint"].default_value = (0.85, 0.66, 0.34, 1)   # ambered
    _nap(b, weight=0.5, rough=0.32)
    # TWEED IS A DIAGONAL TWILL, not a plain weave. The 1950s cabinet cloth is
    # a coarse two-yarn twill whose cream and brown bands march across the
    # diagonal — that stripe IS the identity, and a plain warp/weft cross
    # (_weave) has no diagonal in it at all. This is denim's mechanism, with
    # the two yarns pushed far apart in tone.
    pos = _obj_pos(nt)
    twill = nt.nodes.new("ShaderNodeTexWave")
    twill.wave_type, twill.bands_direction, twill.wave_profile = "BANDS", "DIAGONAL", "SAW"
    nt.links.new(pos, twill.inputs["Vector"])
    twill.inputs["Scale"].default_value = ctx.freq(7.76)
    twill.inputs["Distortion"].default_value = 0.55
    twill.inputs["Detail"].default_value = 3.0
    stretch = nt.nodes.new("ShaderNodeMapRange")
    stretch.inputs["From Min"].default_value = 0.34
    stretch.inputs["From Max"].default_value = 0.66
    nt.links.new(twill.outputs["Factor"], stretch.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*col_b, 1)
    ramp.color_ramp.elements[1].color = (*col_a, 1)
    ramp.color_ramp.elements[0].position = 0.34
    ramp.color_ramp.elements[1].position = 0.56
    nt.links.new(stretch.outputs["Result"], ramp.inputs["Fac"])
    # slub: the yarn is hand-spun uneven, so the bands breathe
    slub = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, slub.inputs["Vector"])
    slub.inputs["Scale"].default_value = ctx.freq(12.2)
    slub.inputs["Detail"].default_value = 6.0
    sr = nt.nodes.new("ShaderNodeMapRange")
    sr.inputs["To Min"].default_value = 0.74
    sr.inputs["To Max"].default_value = 1.14
    nt.links.new(slub.outputs["Fac"], sr.inputs["Value"])
    _tx, tf, ta, tb2, tres = _mix_rgba(nt, "MULTIPLY")
    tf.default_value = 1.0
    nt.links.new(ramp.outputs["Color"], ta)
    nt.links.new(sr.outputs["Result"], tb2)
    nt.links.new(tres, b.inputs["Base Color"])
    # lustre follows the bands: the two yarns take the lacquer differently
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.34
    rr.inputs["To Max"].default_value = 0.66
    nt.links.new(stretch.outputs["Result"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    hb = nt.nodes.new("ShaderNodeBump")               # the twill ridge
    hb.inputs["Strength"].default_value = 1.0
    hb.inputs["Distance"].default_value = ctx.length(0.075)
    nt.links.new(twill.outputs["Factor"], hb.inputs["Height"])
    sb = nt.nodes.new("ShaderNodeBump")               # yarn thickness
    sb.inputs["Strength"].default_value = 0.5
    sb.inputs["Distance"].default_value = ctx.length(0.040)
    nt.links.new(slub.outputs["Fac"], sb.inputs["Height"])
    nt.links.new(hb.outputs["Normal"], sb.inputs["Normal"])
    _fibres(nt, b, scales=((61.2, 0.22, 0.012),), prev=sb.outputs["Normal"], ctx=ctx)
    _cloth_finish(nt)
    return m


_TOLEX = dict(family="textile", finish="satin", solid=False, origin="matlib.mat_tolex")


@material("tolex", **_TOLEX)
@material("tolex-red", params={"col": (0.26, 0.030, 0.030), "name": "tolex_red"}, **_TOLEX)
@material("tolex-cream", params={"col": (0.60, 0.53, 0.36), "name": "tolex_cream"}, **_TOLEX)
def mat_tolex(col=(0.035, 0.035, 0.038), name="tolex", *, ctx=DEFAULT_CTX):
    """Amp-covering vinyl. The one every guitar amplifier on earth is wrapped
    in: a coarse embossed pebble grain under a slightly rubbery satin, over a
    cloth-backed sheet. Voronoi crowns plus their edge creases, roughness
    driven from the creases so the grain glints on top and goes dead in the
    valleys. Black is the default because black is the default."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.45
    b.inputs["Coat Weight"].default_value = 0.18
    b.inputs["Coat Roughness"].default_value = 0.34
    _tone_mottle(nt, b, col, amount=0.14, scale=1.84, ctx=ctx)
    pos = _obj_pos(nt)
    peb = nt.nodes.new("ShaderNodeTexVoronoi")
    peb.feature = "SMOOTH_F1"
    nt.links.new(pos, peb.inputs["Vector"])
    peb.inputs["Scale"].default_value = ctx.freq(23.7)
    peb.inputs["Smoothness"].default_value = 0.4
    crease = nt.nodes.new("ShaderNodeTexVoronoi")
    crease.feature = "DISTANCE_TO_EDGE"
    nt.links.new(pos, crease.inputs["Vector"])
    crease.inputs["Scale"].default_value = ctx.freq(23.7)
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["From Max"].default_value = 0.3
    rr.inputs["To Min"].default_value = 0.82
    rr.inputs["To Max"].default_value = 0.40
    nt.links.new(crease.outputs["Distance"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    pb = nt.nodes.new("ShaderNodeBump")
    pb.inputs["Strength"].default_value = 0.7
    pb.inputs["Distance"].default_value = ctx.length(0.016)
    nt.links.new(peb.outputs["Distance"], pb.inputs["Height"])
    cb = nt.nodes.new("ShaderNodeBump")
    cb.inputs["Strength"].default_value = 0.5
    cb.inputs["Distance"].default_value = ctx.length(0.010)
    nt.links.new(crease.outputs["Distance"], cb.inputs["Height"])
    nt.links.new(pb.outputs["Normal"], cb.inputs["Normal"])
    # the cloth backing reads faintly through the vinyl
    weave_h, _ = _weave(nt, scale=122.0, distortion=0.4, ctx=ctx)
    wb = nt.nodes.new("ShaderNodeBump")
    wb.inputs["Strength"].default_value = 0.10
    wb.inputs["Distance"].default_value = ctx.length(0.002)
    nt.links.new(weave_h, wb.inputs["Height"])
    nt.links.new(cb.outputs["Normal"], wb.inputs["Normal"])
    nt.links.new(wb.outputs["Normal"], b.inputs["Normal"])
    return m
