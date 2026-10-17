"""Strand and open-weave textiles: stitching thread and speaker grille cloth."""
import math

from .core import DEFAULT_CTX, base_material, material
from .nodes import Graph
from .units import mm_per_unit

THREAD_COLORS = {
    "cream": (0.40, 0.28, 0.13),
    "black": (0.010, 0.010, 0.011),
    "orange": (0.52, 0.085, 0.004),
}

_THREAD = dict(family="textile", finish="satin", solid=False,
               calib_mm_per_unit=mm_per_unit("knob-leather"),
               origin="knob-leather:thread_material:558")


@material("thread-waxed", **_THREAD)
@material("thread-waxed-cream", params={"colorway": "cream"}, **_THREAD)
@material("thread-waxed-black", params={"colorway": "black"}, **_THREAD)
@material("thread-waxed-orange", params={"colorway": "orange"}, **_THREAD)
def mat_thread_waxed(colorway="cream", color=None, name=None, *, ctx=DEFAULT_CTX):
    """Waxed saddle-stitch thread: fine fibre noise shading the tint, tinted
    sheen, a thin wax coat and fibre relief. The ply twist is geometry, not
    shading.

      colorway  key of THREAD_COLORS; `color` (linear RGB) overrides it"""
    col = THREAD_COLORS[colorway] if color is None else tuple(color)
    mat, nt, bsdf = base_material(f"{colorway} waxed thread" if name is None else name)
    g = Graph(nt)
    fibre = g.noise(g.coord("Object"), ctx.freq(420.0), detail=3.0)
    shade = g.map_range(fibre.outputs["Fac"], 0.3, 0.7, 0.80, 1.0)
    gray = g.node("ShaderNodeCombineColor")
    for ch in ("Red", "Green", "Blue"):
        g.link(shade, gray.inputs[ch])
    g.link(g.mix(1.0, col, gray.outputs["Color"], blend="MULTIPLY"), bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.40
    bsdf.inputs["Specular IOR Level"].default_value = 0.5
    bsdf.inputs["Sheen Weight"].default_value = 0.30
    bsdf.inputs["Sheen Roughness"].default_value = 0.35
    bsdf.inputs["Sheen Tint"].default_value = (*col, 1.0)
    bsdf.inputs["Coat Weight"].default_value = 0.14   # the wax
    bsdf.inputs["Coat Roughness"].default_value = 0.28
    g.link(g.bump(fibre.outputs["Fac"], 0.25, ctx.length(0.002)), bsdf.inputs["Normal"])
    return mat


VENT_MM = mm_per_unit("vent-grille")
_MM = 1.0 / VENT_MM


@material("grille-cloth", family="textile", finish="matte", solid=False, calib_mm_per_unit=VENT_MM,
          origin="vent-grille:mat_grille_cloth:193")
def mat_grille_cloth(pitch_mm=1.05, name="grille_cloth", *, ctx=DEFAULT_CTX):
    """Coarse plain-weave speaker grille cloth, black.

    A real over/under height field, not a stripe pattern: each thread is a
    cosine ridge across its width, modulated along its length by
    cos(pi(u+v)) so the crown alternates crossing by crossing (max(warp, weft)
    gives equal ridges and reads as embossed vinyl). Sheen carries the grazing
    highlight, and the same height field ramps colour to near-black in the
    interstices, which are holes into the cavity behind.

      pitch_mm  thread pitch in millimetres at the calibration unit. Much finer
                than ~1 mm aliases into moire at panel resolutions

    Weave coordinates are object X/Y: lay the cloth in its object XY plane.
    Duplicate candidate: matlib textiles `_weave` (denim / tweed / corduroy),
    a different weave construction."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.26
    b.inputs["Sheen Weight"].default_value = 0.55
    b.inputs["Sheen Roughness"].default_value = 0.30
    b.inputs["Sheen Tint"].default_value = (0.40, 0.38, 0.36, 1)

    g = Graph(nt)
    pitch = pitch_mm * _MM
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(g.mapping(g.coord("Object"), scale=ctx.freq((1.0 / pitch,) * 3)), sep.inputs["Vector"])

    def ridge(ax):
        """0..1 across a thread's width: 0.5 + 0.5 cos(2 pi u), crown at integer u."""
        c = g.math("COSINE", g.math("MULTIPLY", ax, 2.0 * math.pi))
        return g.math("ADD", g.math("MULTIPLY", c, 0.5), 0.5)

    warp = ridge(sep.outputs["X"])
    weft = ridge(sep.outputs["Y"])
    # over/under phase: 1 where the warp rides over, 0 where it dives
    u = g.math("COSINE", g.math("MULTIPLY", g.math("ADD", sep.outputs["X"], sep.outputs["Y"]),
                                math.pi))
    a = g.math("ADD", g.math("MULTIPLY", u, 0.5), 0.5)
    h = g.math("ADD", g.math("MULTIPLY", warp, a),
               g.math("MULTIPLY", weft, g.math("SUBTRACT", 1.0, a)))

    fib = g.noise(None, ctx.freq(536.0), detail=4.0)     # fibre fuzz on the weave
    nrm = g.bump(h, 1.0, ctx.length(0.20 * _MM))
    nrm = g.bump(fib.outputs["Fac"], 0.22, ctx.length(0.012 * _MM), nrm)
    g.link(nrm, b.inputs["Normal"])

    # the interstice (height near zero) is a hole: nearly black
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.004, 0.004, 0.005, 1)
    ramp.color_ramp.elements[0].position = 0.04
    ramp.color_ramp.elements[1].color = (0.052, 0.048, 0.042, 1)
    ramp.color_ramp.elements[1].position = 0.40
    g.link(h, ramp.inputs["Fac"])
    g.link(ramp.outputs["Color"], b.inputs["Base Color"])

    rn = g.noise(None, ctx.freq(155.0), detail=2.0)
    g.link(g.map_range(rn.outputs["Fac"], 0.0, 1.0, 0.72, 0.92, clamp=True), b.inputs["Roughness"])
    return m
