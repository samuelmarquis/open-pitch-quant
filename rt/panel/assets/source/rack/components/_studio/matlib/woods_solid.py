"""Solid woods: turned and carved hardwood evaluated as ONE 3-D function of
object space, so end grain, long grain and every cut between them agree."""
import math

from .core import DEFAULT_CTX, base_material, material
from .nodes import Graph
from .units import mm_per_unit


def _srgb(r, g, b):
    """8-bit sRGB triplet -> linear RGBA for node defaults."""
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b), 1.0)


# Species. Colours are 8-bit sRGB albedo for an oiled finish under the knob
# family rig (which renders ~1.6x brighter than albedo). Lengths are world
# units at 25 mm/unit (0.04 = 1 mm).
#   ramp        earlywood -> latewood colour stops over one growth ring
#   spacing     mean growth-ring width; pith = grain axis (x, y) off the part axis
#   ring_var    per-year darkness; fine / mottle / streak / ray = figure layers
#   pore_*      vessel tubes along the grain: cell scale, size, darkness, how
#               strongly size follows earlywood (1 ring-porous, 0 diffuse),
#               roughness they add, stretch along the grain
#   rough/spec  long-grain satin finish; end_* = extra roughness, spec factor
#               and darkening where end grain drinks the oil
TURNED_SPECIES = {
    "walnut": dict(
        ramp=[(0.00, (52, 36, 28)), (0.07, (71, 51, 39)), (0.55, (66, 47, 36)),
              (0.88, (55, 38, 30)), (0.96, (41, 29, 22)), (1.00, (41, 29, 22))],
        spacing=0.17, ring_var=0.20, warp=0.035, pith=(-0.50, 0.37),
        fine=0.18, mottle=0.14,
        pore_scale=110.0, pore_size=0.25, pore_dark=0.42, pore_ring=0.85,
        pore_rough=0.1, pore_stretch=9.0, streak=0.35, streak_col=(44, 32, 26),
        rough=0.32, coat=0.0, spec=0.40, end_dark=0.90, ray=0.04,
        end_rough=0.22, end_spec=0.30,
    ),
    "maple": dict(
        ramp=[(0.00, (152, 118, 70)), (0.06, (164, 129, 78)), (0.70, (160, 125, 75)),
              (0.92, (150, 115, 68)), (1.00, (138, 104, 61))],
        fine=0.06, mottle=0.08,
        spacing=0.14, ring_var=0.14, warp=0.030, pith=(-0.55, 0.36),
        pore_scale=150.0, pore_size=0.16, pore_dark=0.18, pore_ring=0.10,
        pore_rough=0.06, pore_stretch=7.0, streak=0.08, streak_col=(140, 108, 70),
        end_rough=0.18, end_spec=0.35,
        rough=0.34, coat=0.0, spec=0.40, end_dark=0.92, ray=0.16,
    ),
    "cherry": dict(
        ramp=[(0.00, (104, 60, 36)), (0.06, (122, 73, 45)), (0.64, (116, 68, 41)),
              (0.92, (98, 57, 34)), (1.00, (88, 50, 30))],
        fine=0.10, mottle=0.12,
        spacing=0.16, ring_var=0.22, warp=0.035, pith=(-0.52, 0.40),
        pore_scale=130.0, pore_size=0.18, pore_dark=0.28, pore_ring=0.30,
        pore_rough=0.08, pore_stretch=8.0, streak=0.22, streak_col=(76, 42, 26),
        end_rough=0.18, end_spec=0.35,
        rough=0.34, coat=0.0, spec=0.40, end_dark=0.90, ray=0.07,
    ),
    "ebony": dict(
        ramp=[(0.00, (14, 12, 11)), (0.45, (12, 11, 10)), (0.70, (40, 30, 21)),
              (0.90, (34, 26, 18)), (1.00, (11, 10, 9))],
        fine=0.10, mottle=0.18,
        spacing=0.25, ring_var=0.30, warp=0.060, pith=(-0.62, 0.30),
        pore_scale=200.0, pore_size=0.10, pore_dark=0.35, pore_ring=0.0,
        pore_rough=0.0, pore_stretch=10.0, streak=0.35, streak_col=(6, 6, 6),
        end_rough=0.14, end_spec=0.22,
        rough=0.24, coat=0.0, spec=0.45, end_dark=0.92, ray=0.0,
    ),
}


class _K:
    """Graph calls with the input-writing conventions this builder's graph was
    authored under: single-operand Math writes 0.0 into its second input,
    Vector Math always writes its second operand."""

    def __init__(self, nt):
        self.g = Graph(nt)
        self.nt = nt

    def math(self, op, a, b=0.0, clamp=False):
        return self.g.math(op, a, b, clamp=clamp)

    def vmath(self, op, a, b=(0.0, 0.0, 0.0)):
        return self.g.vmath(op, a, b)

    def mapping(self, vec, rot=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)):
        return self.g.mapping(vec, scale=scale, rotation=rot, location=(0.0, 0.0, 0.0))

    def noise(self, vec, scale, detail=2.0, rough=0.5):
        return self.g.noise(vec, scale, detail=detail, roughness=rough)

    def noise1d(self, w, scale, detail=1.0):
        n = self.g.node("ShaderNodeTexNoise", noise_dimensions="1D")
        self.g.link(w, n.inputs["W"])
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        return n.outputs["Fac"]

    def white1d(self, w):
        n = self.g.node("ShaderNodeTexWhiteNoise", noise_dimensions="1D")
        self.g.link(w, n.inputs["W"])
        return n.outputs["Value"]

    def separate(self, vec):
        n = self.g.node("ShaderNodeSeparateXYZ")
        self.g.feed(n.inputs["Vector"], vec)
        return n.outputs["X"], n.outputs["Y"], n.outputs["Z"]

    def combine(self, x, y, z):
        n = self.g.node("ShaderNodeCombineXYZ")
        for ident, v in (("X", x), ("Y", y), ("Z", z)):
            self.g.feed(n.inputs[ident], v)
        return n.outputs["Vector"]

    def ramp(self, fac, stops):
        """Stops are (position, 8-bit sRGB). Elements are added at 0.5 and then
        written in collection order; the resulting ramp is part of the look."""
        n = self.nt.nodes.new("ShaderNodeValToRGB")
        cr = n.color_ramp
        cr.interpolation = "LINEAR"
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for el, (pos, col) in zip(cr.elements, stops):
            el.position = pos
            el.color = _srgb(*col)
        self.g.link(fac, n.inputs["Fac"])
        return n.outputs["Color"]


def lathe_sanding(k, coord, density, ctx):
    """Concentric tooling / abrasive scratches about the Z axis of `coord`:
    circles on a horizontal face, horizontal lines on a flank. `density` is
    scratches per unit radius at the calibration unit; the angular term is not
    spatial."""
    x, y, _z = k.separate(coord)
    rk = k.vmath("LENGTH", k.combine(x, y, 0.0))
    theta = k.math("ARCTAN2", y, x)
    v = k.combine(k.math("MULTIPLY", rk, ctx.freq(density)), k.math("MULTIPLY", theta, 2.5), 0.0)
    return k.noise(v, 1.0, detail=3.0, rough=0.6).outputs["Fac"]


_TURNED = dict(family="wood", finish="satin", solid=True,
               calib_mm_per_unit=mm_per_unit("knob-wood"),
               origin="knob-wood:turned_wood_material:388", part_bound={"top_z": "top_z"})


@material("wood-turned", **_TURNED)
@material("wood-turned-walnut", params={"species": "walnut"}, **_TURNED)
@material("wood-turned-maple", params={"species": "maple"}, **_TURNED)
@material("wood-turned-cherry", params={"species": "cherry"}, **_TURNED)
@material("wood-turned-ebony", params={"species": "ebony"}, **_TURNED)
def mat_wood_turned(species="walnut", pith=None, spacing=None, top_z=0.680, name=None,
                    *, ctx=DEFAULT_CTX):
    """Spindle-turned hardwood: ONE 3-D wood function in object space.

    Rings are the distance from a grain axis parallel to object Z that sits OFF
    the part's axis, so a horizontal cut (a knob top) shows arcs around that
    pith and a vertical cut (the flank) shows the same rings as stripes.
    Vessels are tubes stretched along Z (dots on end grain, dashes on long
    grain) sized by ring phase; rays are thin plates radiating from the pith;
    end grain (surface normal along Z) is darker, rougher and less specular.

    The part must be modelled with its turning axis on object Z through the
    object origin.

      species  key of TURNED_SPECIES (walnut | maple | cherry | ebony)
      pith     (x, y) grain-axis offset from the part axis, calibration units
               (ctx-scaled); None = the species value
      spacing  mean growth-ring width, calibration units (ctx-scaled); None =
               the species value
      top_z    object-space height of the part's flat top in the part's own
               units (NOT ctx-scaled): the burnished shoulder band sits
               0.03-0.16 below it

    Grain tilt, warp and figure amplitudes are the species' design constants.
    Duplicate candidate: matlib `wood-walnut` / `wood-ebony` (mat_wood, a
    surface-oriented panel wood; different graph)."""
    sp = TURNED_SPECIES[species]
    pith = sp["pith"] if pith is None else pith
    spacing = sp["spacing"] if spacing is None else spacing
    mat, nt, bsdf = base_material(f"turned {species}" if name is None else name)
    k = _K(nt)
    g = k.g
    coord = g.coord("Object")
    # a turning blank is never exactly on the grain: tilt the grain axis
    p = k.mapping(coord, rot=(math.radians(2.5), math.radians(-1.5), 0.0))
    warp_col = k.noise(k.mapping(p, scale=ctx.freq((1.0, 1.0, 0.35))), 1.3, detail=1.0,
                       rough=0.5).outputs["Color"]
    warp = k.vmath("SUBTRACT", warp_col, (0.5, 0.5, 0.5))
    warp = k.vmath("MULTIPLY", warp, ctx.length((sp["warp"] * 2.0, sp["warp"] * 2.0, 0.0)))
    pw = k.vmath("ADD", p, warp)
    q = k.vmath("SUBTRACT", pw, ctx.length((pith[0], pith[1], 0.0)))
    qx, qy, _qz = k.separate(q)
    d = k.vmath("LENGTH", k.combine(qx, qy, 0.0))
    wobble = k.noise(k.mapping(pw, scale=ctx.freq((1.0, 1.0, 0.5))), 2.2, detail=1.0,
                     rough=0.5).outputs["Fac"]
    d = k.math("ADD", d, k.math("MULTIPLY", k.math("SUBTRACT", wobble, 0.5),
                                ctx.length(spacing * 0.45)))
    u = k.math("DIVIDE", d, ctx.length(spacing))
    u = k.math("ADD", u, k.math("MULTIPLY", k.math("SUBTRACT", k.noise1d(d, ctx.freq(2.4), 2.0),
                                                   0.5), 1.6))
    ring_id = k.math("FLOOR", u)
    t = k.math("SUBTRACT", u, ring_id)  # ring phase: 0 earlywood -> 1 latewood

    base = k.ramp(t, sp["ramp"])
    ring_rand = k.white1d(ring_id)
    base = g.mix(k.math("MULTIPLY", ring_rand, sp["ring_var"]), base,
                 _srgb(*[c * 0.70 for c in sp["ramp"][-1][1]]))
    streak = k.noise(k.mapping(pw, scale=ctx.freq((1.0, 1.0, 0.22))), 4.5, detail=2.0,
                     rough=0.5).outputs["Fac"]
    streak_f = g.smoothstep(streak, 0.48, 0.70, 0.0, sp["streak"])
    base = g.mix(streak_f, base, _srgb(*sp["streak_col"]))
    wob2 = k.noise(k.mapping(pw, scale=ctx.freq((1.0, 1.0, 0.4))), 7.0, detail=1.0).outputs["Fac"]
    u2 = k.math("ADD", k.math("MULTIPLY", u, 3.3), k.math("MULTIPLY", wob2, 1.2))
    t2 = k.math("FRACT", u2)
    fine = g.smoothstep(k.math("ABSOLUTE", k.math("SUBTRACT", t2, 0.5)), 0.36, 0.5, 0.0, sp["fine"])
    base = g.mix(fine, base, _srgb(*[c * 0.6 for c in sp["ramp"][-1][1]]))
    mot = k.noise(k.mapping(pw, scale=ctx.freq((1.0, 1.0, 0.3))), 9.0, detail=3.0,
                  rough=0.6).outputs["Fac"]
    mot_dark = g.smoothstep(mot, 0.5, 0.75, 0.0, sp["mottle"])
    base = g.mix(mot_dark, base, _srgb(*[c * 0.55 for c in sp["ramp"][1][1]]))
    mot_light = g.smoothstep(mot, 0.5, 0.25, 0.0, sp["mottle"] * 0.6)
    base = g.mix(mot_light, base, _srgb(*[min(255, c * 1.3) for c in sp["ramp"][1][1]]))

    # rays: (arc, radius, height) -> fine across the arc, long along radius and Z
    theta = k.math("ARCTAN2", qy, qx)
    arc = k.math("MULTIPLY", theta, 0.9)
    ray_in = k.combine(k.math("MULTIPLY", arc, 150.0), k.math("MULTIPLY", d, ctx.freq(6.0)),
                       k.math("MULTIPLY", k.separate(pw)[2], ctx.freq(10.0)))
    ray_n = k.noise(ray_in, 1.0, detail=0.0, rough=0.5).outputs["Fac"]
    rays = g.smoothstep(ray_n, 0.63, 0.74, 0.0, sp["ray"])
    base = g.mix(rays, base, _srgb(*[min(255, c * 1.25) for c in sp["ramp"][0][1]]))

    # vessels: tubes along the grain; F1 distance is 0 AT the feature point
    v_in = k.mapping(pw, scale=ctx.freq((1.0, 1.0, 1.0 / sp["pore_stretch"])))
    vd = g.voronoi(v_in, sp["pore_scale"], randomness=1.0).outputs["Distance"]
    early = k.math("SUBTRACT", 1.0, t)
    size = g.mix(sp["pore_ring"], 1.0, g.smoothstep(early, 0.10, 0.80, 0.35, 1.30),
                 data_type="FLOAT")
    size = k.math("MULTIPLY", size, sp["pore_size"])
    pore = k.math("SUBTRACT", 1.0, g.smoothstep(k.math("DIVIDE", vd, size), 0.55, 1.0))

    geo = g.node("ShaderNodeNewGeometry")
    _nx, _ny, nz = k.separate(geo.outputs["Normal"])
    endness = g.smoothstep(k.math("ABSOLUTE", nz), 0.55, 0.97)
    col = g.mix(k.math("MULTIPLY", endness, 1.0 - sp["end_dark"]), base,
                _srgb(*[c * 0.35 for c in sp["ramp"][-1][1]]))
    col = g.mix(k.math("MULTIPLY", pore, sp["pore_dark"]), col, (0.0, 0.0, 0.0, 1.0))
    g.link(col, bsdf.inputs["Base Color"])

    # oiled satin; burnished on the high shoulder
    _ox, _oy, oz = k.separate(coord)
    shoulder = k.math("MULTIPLY", g.smoothstep(oz, top_z - 0.16, top_z - 0.03),
                      k.math("SUBTRACT", 1.0, g.smoothstep(k.math("ABSOLUTE", nz), 0.80, 0.99)))
    rough_n = k.noise(coord, ctx.freq(38.0), detail=4.0).outputs["Fac"]
    rough = g.map_range(rough_n, 0.3, 0.7, sp["rough"] - 0.05, sp["rough"] + 0.05)
    rough = k.math("ADD", rough, k.math("MULTIPLY", endness, sp["end_rough"]))
    rough = k.math("SUBTRACT", rough, k.math("MULTIPLY", shoulder, 0.16))
    rough = k.math("ADD", rough, k.math("MULTIPLY", pore, sp["pore_rough"]))
    sand = lathe_sanding(k, coord, 900.0, ctx)
    rough = k.math("ADD", rough, k.math("MULTIPLY", k.math("SUBTRACT", sand, 0.5), 0.10), clamp=True)
    g.link(rough, bsdf.inputs["Roughness"])
    spec = g.mix(endness, sp["spec"], sp["spec"] * sp["end_spec"], data_type="FLOAT")
    g.link(spec, bsdf.inputs["Specular IOR Level"])
    bsdf.inputs["Coat Weight"].default_value = sp["coat"]
    bsdf.inputs["Coat Roughness"].default_value = 0.30

    # relief: vessels sink, latewood stands a hair proud, sanding marks
    nrm = g.bump(pore, -0.35, ctx.length(0.0015))
    nrm = g.bump(t, 0.03, ctx.length(0.002), nrm)
    nrm = g.bump(sand, 0.035, ctx.length(0.001), nrm)
    g.link(nrm, bsdf.inputs["Normal"])
    return mat
