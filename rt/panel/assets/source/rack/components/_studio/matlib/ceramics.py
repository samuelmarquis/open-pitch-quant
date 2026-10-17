"""Ceramics: glazed and raw stoneware bodies, and opal. Solid substances whose
colour depends on local thickness and the object-space field they are cut from."""
import bpy

from .core import DEFAULT_CTX, base_material, imperfect, material
from .nodes import Graph
from .units import mm_per_unit

# Linear albedos, tuned on the knob rig against sampled reference pixels.
# pooled = thick glaze in recesses, broken = thin glaze over edges and high points;
# clay = the raw foot.
GLAZES = {
    "celadon": dict(
        pooled=(0.026, 0.068, 0.052), mid=(0.100, 0.165, 0.115), broken=(0.250, 0.230, 0.155),
        bias=0.0, rough_pooled=0.08, rough_broken=0.22, crackle=1.0, crackle_tint=(0.50, 0.44, 0.34),
        speckle_bleed=0.55, pinholes=0.35, flash=None, sss=0.20,
        clay=(0.28, 0.215, 0.14),
    ),
    "tenmoku": dict(
        pooled=(0.0030, 0.0026, 0.0021), mid=(0.0060, 0.0048, 0.0036), broken=(0.150, 0.060, 0.018),
        bias=0.06, wide_break=0.55, rough_pooled=0.04, rough_broken=0.26, crackle=0.0,
        crackle_tint=(0.2, 0.2, 0.2), speckle_bleed=0.07, pinholes=0.04, flash=None,
        clay=(0.13, 0.075, 0.042),
    ),
    "shino": dict(
        pooled=(0.420, 0.380, 0.200), mid=(0.400, 0.345, 0.175), broken=(0.230, 0.050, 0.012),
        bias=0.0, rough_pooled=0.30, rough_broken=0.40, crackle=0.30, crackle_tint=(0.40, 0.34, 0.28),
        speckle_bleed=0.35, pinholes=1.0, flash=(0.250, 0.052, 0.012), peel=2.2, mottle=2.6,
        clay=(0.30, 0.20, 0.13),
    ),
    "cobalt": dict(
        pooled=(0.004, 0.008, 0.070), mid=(0.012, 0.022, 0.120), broken=(0.250, 0.260, 0.285),
        bias=0.05, rough_pooled=0.05, rough_broken=0.18, crackle=0.0, crackle_tint=(0.2, 0.2, 0.2),
        speckle_bleed=0.18, pinholes=0.30, flash=None,
        clay=(0.27, 0.23, 0.17),
    ),
}


class _G(Graph):
    """Graph with the conventions this family's graphs are authored under:
    single-operand Math writes 0.0 into its second input; smooth(e0, e1, x)
    writes only the From range."""

    def math(self, op, a, b=0.0, c=None, clamp=False):
        return super().math(op, a, b, c, clamp=clamp)

    def add(self, *terms):
        out = terms[0]
        for t in terms[1:]:
            out = self.math("ADD", out, t)
        return out

    def mul(self, a, b):
        return self.math("MULTIPLY", a, b)

    def smooth(self, e0, e1, x):
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP", clamp=True)
        self.feed(n.inputs["Value"], x)
        n.inputs["From Min"].default_value = e0
        n.inputs["From Max"].default_value = e1
        return n.outputs["Result"]

    def separate(self, vector):
        n = self.node("ShaderNodeSeparateXYZ")
        self.link(vector, n.inputs["Vector"])
        return n.outputs

    def gray3(self, value):
        n = self.node("ShaderNodeCombineXYZ")
        for i in range(3):
            self.link(value, n.inputs[i])
        return n.outputs[0]


def _empty_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    g = _G(nt)
    return mat, g, g.node("ShaderNodeOutputMaterial")


def _iron_speckle(g, P, ctx, halo=True):
    """Iron specks in the clay body: (core, soft halo or None)."""
    spk = g.voronoi(P, ctx.freq(58.0))
    spk_sel = g.smooth(0.95, 0.955, g.separate(spk.outputs["Color"])[1])
    spk_core = g.math("SUBTRACT", 1.0, g.smooth(0.15, 0.30, spk.outputs["Distance"]))
    speckle = g.mul(spk_sel, spk_core)
    if not halo:
        return speckle, None
    spk_halo = g.math("SUBTRACT", 1.0, g.smooth(0.18, 0.50, spk.outputs["Distance"]))
    return speckle, g.mul(spk_sel, spk_halo)


def _clay_bsdf(g, P, clay, speckle, ctx):
    """Raw speckled stoneware: grog relief, colour mottle, iron and fine specks."""
    grog = g.noise(P, ctx.freq(160.0), detail=3.0, roughness=0.6)
    clay_mottle = g.map_range(g.noise(P, ctx.freq(18.0), detail=3.0).outputs["Fac"],
                              0.3, 0.7, 0.88, 1.08)
    clay_col = g.mix(1.0, clay, g.gray3(clay_mottle), blend="MULTIPLY")
    clay_col = g.mix(speckle, clay_col, (0.045, 0.028, 0.016))
    fine_spk = g.voronoi(P, ctx.freq(110.0))
    fine_sel = g.smooth(0.86, 0.865, g.separate(fine_spk.outputs["Color"])[2])
    fine_core = g.math("SUBTRACT", 1.0, g.smooth(0.14, 0.26, fine_spk.outputs["Distance"]))
    clay_col = g.mix(g.mul(g.mul(fine_sel, fine_core), 0.8), clay_col, (0.06, 0.04, 0.025))
    clay_bump = g.bump(grog.outputs["Fac"], 0.22, ctx.length(0.002))
    clay = g.node("ShaderNodeBsdfPrincipled")
    g.link(clay_col, clay.inputs["Base Color"])
    clay.inputs["Roughness"].default_value = 0.82
    g.link(clay_bump, clay.inputs["Normal"])
    return clay


_GLAZE = dict(family="ceramic", finish="gloss", solid=True,
              calib_mm_per_unit=mm_per_unit("knob-ceramic"),
              origin="knob-ceramic:glaze_material:397", part_bound={"dip_z": "dip_z"})


@material("glaze-stoneware", **_GLAZE)
@material("glaze-celadon", params={"glaze": "celadon"}, **_GLAZE)
@material("glaze-tenmoku", params={"glaze": "tenmoku"}, **_GLAZE)
@material("glaze-shino", params={"glaze": "shino"}, **_GLAZE)
@material("glaze-cobalt", params={"glaze": "cobalt"}, **_GLAZE)
# Panel plates (pass 45, Nolan's crud_ui rack folders): glazed to the edge — a
# flat plate's whole perimeter reads as an edge to the break probes, which
# rimmed it in raw clay (Sam, p148). The celadon deepened so white legends read.
@material("glaze-celadon-plate", params={"glaze": "celadon", "deepen": 0.58, "edge_break": 0.0},
          **_GLAZE)
@material("glaze-tenmoku-plate", params={"glaze": "tenmoku", "edge_break": 0.0}, **_GLAZE)
def mat_glaze_stoneware(glaze="celadon", dip_z=0.088, name=None, deepen=1.0, edge_break=1.0, *,
                        ctx=DEFAULT_CTX):
    """Dip-glazed stoneware: a fired glaze over a speckled clay body, with the
    raw clay showing below a wandering, dripping dip line.

    Glaze colour follows a THICKNESS proxy built from ray-traced ambient
    occlusion (cavities pool thick and dark, tight and wide edges break thin
    and pale, steep walls run thin), plus orange peel, pinholes, a two-scale
    warped crackle network stained into the glaze, iron specks bleeding
    through thin glaze and, for shino, iron flashing where it runs thin. The
    AO needs the real mesh: on a flat test plane the glaze reads uniformly thin.

      glaze  key of GLAZES (celadon | tenmoku | shino | cobalt); also sets
             the clay tone of the raw foot
      dip_z  object-space height of the dip line above the object origin, in
             the part's own units (NOT ctx-scaled). The dip line's wander,
             drips and rolled edge are object-space geometry too; texture
             frequencies, crackle warp, AO and bump distances and subsurface
             scale are ctx-scaled
      edge_break  how far the glaze thins to raw clay over edges (1 a dipped
             part's; 0 glazed to the edge, as a flat plate)

    The part stands on object XY with Z up."""
    G = GLAZES[glaze]
    mat, g, out = _empty_material(f"{glaze} glaze on stoneware" if name is None else name)

    coord = g.node("ShaderNodeTexCoord")
    P = coord.outputs["Object"]
    Nobj = coord.outputs["Normal"]
    px, _py, pz = g.separate(P)
    nz = g.separate(Nobj)[2]

    # dipping line: glaze stops short of the foot, wanders, drips
    dip_noise = g.noise(P, ctx.freq(2.6), detail=2.0).outputs["Fac"]
    drip_coords = g.vmath("MULTIPLY", P, ctx.freq((14.0, 14.0, 1.2)))
    drip_noise = g.noise(drip_coords, 1.0, detail=1.0).outputs["Fac"]
    drips = g.mul(g.smooth(0.56, 0.72, drip_noise), 0.042)
    tilt = g.mul(px, 0.020)
    zline = g.add(dip_z, g.mul(g.math("SUBTRACT", dip_noise, 0.5), 0.060), tilt)
    zline = g.math("SUBTRACT", zline, drips)
    above = g.math("SUBTRACT", pz, zline)
    glazed = g.smooth(-0.0025, 0.0025, above)
    roll = g.math("EXPONENT", g.mul(g.math("POWER", g.math("SUBTRACT", above, 0.010), 2.0),
                                    -1.0 / (0.008 ** 2)))

    # local thickness proxy from ray-traced occlusion (world-space distances)
    cavity = g.math("SUBTRACT", 1.0, g.ao_thickness(ctx.length(0.045), inside=False, samples=24),
                    clamp=True)
    edge_tight = g.math("SUBTRACT", 1.0, g.ao_thickness(ctx.length(0.022), samples=24), clamp=True)
    edge_wide = g.math("SUBTRACT", 1.0, g.ao_thickness(ctx.length(0.130), samples=24), clamp=True)
    g.math("ADD", edge_tight, edge_wide, clamp=True)  # combined edge probe; unlinked in the canon graph

    # glaze flows off steep upper walls during the melt, and pulls back unevenly
    steep = g.math("SUBTRACT", 1.0, g.math("ABSOLUTE", nz))
    slow = g.noise(P, ctx.freq(5.5), detail=3.0, roughness=0.55).outputs["Fac"]
    break_var = g.map_range(g.noise(P, ctx.freq(11.0), detail=2.0).outputs["Fac"],
                            0.3, 0.7, 0.55, 1.45)

    thickness_raw = g.add(
        0.50 + G["bias"],
        g.mul(cavity, 2.6),
        g.mul(g.mul(edge_tight, break_var), -1.6 * edge_break),
        g.mul(g.mul(edge_wide, break_var), -1.3 * G.get("wide_break", 1.0) * edge_break),
        g.mul(steep, -0.10),
        g.mul(g.math("SUBTRACT", slow, 0.5), 0.35),
        g.mul(roll, 0.30),
    )
    thickness = g.math("ADD", thickness_raw, 0.0, clamp=True)

    # orange peel + pinholes (height)
    peel = g.noise(P, ctx.freq(48.0), detail=2.0, roughness=0.45)
    wave = g.noise(P, ctx.freq(15.0), detail=3.0, roughness=0.50)
    pin_v = g.voronoi(P, ctx.freq(26.0))
    pin_cut = 1.0 - 0.05 * G["pinholes"]
    pin_sel = g.smooth(pin_cut - 0.002, pin_cut, g.separate(pin_v.outputs["Color"])[0])
    pin_core = g.math("SUBTRACT", 1.0, g.smooth(0.16, 0.30, pin_v.outputs["Distance"]))
    pinhole = g.mul(pin_sel, pin_core)

    # crackle: two warped Voronoi edge networks (warp offsets are object-space)
    warp = g.vmath("SUBTRACT", g.noise(P, ctx.freq(2.4), detail=2.0).outputs["Color"], (0.5, 0.5, 0.5))
    warp_mid = g.vmath("SUBTRACT", g.noise(P, ctx.freq(6.5), detail=2.0).outputs["Color"],
                       (0.5, 0.5, 0.5))
    P1 = g.vmath("ADD", g.vmath("ADD", P, g.vmath("SCALE", warp, scale=ctx.length(0.20))),
                 g.vmath("SCALE", warp_mid, scale=ctx.length(0.045)))
    warp2 = g.vmath("SUBTRACT", g.noise(P, ctx.freq(7.0), detail=1.0).outputs["Color"], (0.5, 0.5, 0.5))
    P2 = g.vmath("ADD", P1, g.vmath("SCALE", warp2, scale=ctx.length(0.05)))
    primary = g.voronoi(P1, ctx.freq(4.2), feature="DISTANCE_TO_EDGE")
    secondary = g.voronoi(P2, ctx.freq(10.5), feature="DISTANCE_TO_EDGE")
    # line widths live in each network's cell space
    line1 = g.math("SUBTRACT", 1.0, g.smooth(0.0014 * 4.2, 0.0034 * 4.2, primary.outputs["Distance"]))
    line2 = g.math("SUBTRACT", 1.0, g.smooth(0.0007 * 10.5, 0.0022 * 10.5, secondary.outputs["Distance"]))
    stain_var = g.smooth(0.30, 0.70, g.noise(P, ctx.freq(9.0), detail=1.0).outputs["Fac"])
    crackle = g.add(g.mul(line1, g.map_range(stain_var, 0, 1, 0.55, 1.0)),
                    g.mul(line2, g.map_range(stain_var, 0, 1, 0.15, 0.55)))
    crackle = g.math("MULTIPLY", crackle, G["crackle"], clamp=True)
    crackle = g.mul(crackle, g.map_range(thickness, 0.0, 1.0, 0.45, 1.0))

    speckle, speckle_halo = _iron_speckle(g, P, ctx)

    # glaze colour
    t_lo = g.smooth(0.0, 0.5, thickness)
    t_hi = g.smooth(0.5, 1.0, thickness)
    col = g.mix(t_lo, G["broken"], G["mid"])
    col = g.mix(t_hi, col, G["pooled"])
    if G["flash"] is not None:
        # iron flashing: soft blushes, strongest where the glaze runs thin
        flash_noise = g.smooth(0.46, 0.68, g.noise(P, ctx.freq(3.0), detail=3.0, roughness=0.58,
                                                   distortion=0.30).outputs["Fac"])
        thin = g.math("SUBTRACT", 1.0, g.smooth(0.05, 0.58, thickness))
        flash_amt = g.add(g.mul(flash_noise, g.map_range(thickness, 0.45, 0.95, 0.85, 0.0)),
                          g.mul(thin, 0.85))
        col = g.mix(g.math("MULTIPLY", flash_amt, 1.0, clamp=True), col, G["flash"])
    cloud = g.map_range(g.noise(P, ctx.freq(6.0), detail=3.0).outputs["Fac"], 0.3, 0.7, 0.90, 1.10)
    grain = 0.05 * G.get("mottle", 1.0)
    mottle = g.mul(g.map_range(peel.outputs["Fac"], 0.3, 0.7, 1.0 - grain, 1.0 + grain), cloud)
    col = g.mix(1.0, col, g.gray3(mottle), blend="MULTIPLY")
    bleed = g.mul(speckle_halo, g.mul(G["speckle_bleed"], g.map_range(thickness, 0.0, 1.0, 1.0, 0.35)))
    col = g.mix(bleed, col, (0.10, 0.055, 0.025))
    col = g.mix(g.mul(crackle, 0.72), col, G["crackle_tint"], blend="MULTIPLY")
    col = g.mix(g.mul(pinhole, 0.8), col, (0.05, 0.04, 0.03))

    glaze_rough = g.map_range(thickness, 0.0, 1.0, G["rough_broken"], G["rough_pooled"])
    glaze_rough = g.add(glaze_rough, g.mul(pinhole, 0.5))

    glaze_height = g.add(
        g.mul(peel.outputs["Fac"], 0.35 * G.get("peel", 1.0)),
        g.mul(wave.outputs["Fac"], 1.0),
        g.mul(pinhole, -1.2),
        g.mul(roll, 1.5),
    )
    glaze_bump = g.bump(glaze_height, 0.30, ctx.length(0.0030))

    glaze_bsdf = g.node("ShaderNodeBsdfPrincipled")
    g.link(col, glaze_bsdf.inputs["Base Color"])
    g.link(glaze_rough, glaze_bsdf.inputs["Roughness"])
    glaze_bsdf.inputs["IOR"].default_value = 1.52
    if G.get("sss", 0.0) > 0.0:
        # thick glassy glaze scatters a little light: modest RGB spread
        glaze_bsdf.inputs["Subsurface Weight"].default_value = G["sss"]
        glaze_bsdf.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 0.9)
        glaze_bsdf.inputs["Subsurface Scale"].default_value = ctx.length(0.012)
    g.link(glaze_bump, glaze_bsdf.inputs["Normal"])

    clay = _clay_bsdf(g, P, G["clay"], speckle, ctx)
    g.link(g.mix_shader(glazed, clay.outputs["BSDF"], glaze_bsdf.outputs["BSDF"]),
           out.inputs["Surface"])
    if deepen != 1.0:
        from .finishes import darken

        darken(mat.node_tree, glaze_bsdf, deepen)
    return mat


_CLAY = dict(family="ceramic", finish="matte", solid=True,
             calib_mm_per_unit=mm_per_unit("knob-ceramic"),
             origin="knob-ceramic:glaze_material:538")


@material("stoneware-speckled", **_CLAY)
def mat_stoneware_speckled(clay=(0.28, 0.215, 0.14), name="raw speckled stoneware clay",
                           *, ctx=DEFAULT_CTX):
    """Unglazed speckled stoneware: grog bump, broad colour mottle, sparse iron
    specks and finer dark flecks, matte. The raw-foot branch of the glaze-*
    keys, built by the same function.

      clay  linear body tone (GLAZES[...]["clay"] gives each glaze's body)"""
    mat, g, out = _empty_material(name)
    P = g.node("ShaderNodeTexCoord").outputs["Object"]
    speckle, _ = _iron_speckle(g, P, ctx, halo=False)
    g.link(_clay_bsdf(g, P, clay, speckle, ctx).outputs["BSDF"], out.inputs["Surface"])
    return mat


_OPAL = dict(family="ceramic", finish="gloss", solid=True,
             calib_mm_per_unit=mm_per_unit("knob-heady"),
             origin="knob-heady:opal_material:320")


@material("opal-synthetic", **_OPAL)
@material("opal-crushed", params={"name": "crushed synthetic opal", "fire_scale": 45.0,
                                  "fire": (0.65, 1.0), "milk": (0.62, 0.72, 0.82)}, **_OPAL)
def mat_opal(name="synthetic opal", fire_scale=70.0, fire=(0.40, 0.85),
             milk=(0.86, 0.90, 0.95), *, ctx=DEFAULT_CTX):
    """Synthetic opal: a milky body with cell-wise spectral fire. Each Voronoi
    cell takes one hue off a spectral ramp and one fire strength.

      fire_scale  fire cells per unit at the calibration unit (ctx-scaled)
      fire        (min, max) share of fire over milk per cell
      milk        body colour between the fire

    Near index-matched to borosilicate: specular is kept low so an encased
    interface carries almost none."""
    mat, nt, bsdf = base_material(name)
    g = Graph(nt)
    cells = g.voronoi(g.coord("Object"), ctx.freq(fire_scale))
    split = g.node("ShaderNodeSeparateColor")
    g.link(cells.outputs["Color"], split.inputs["Color"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    stops = [
        (0.00, (0.05, 0.85, 0.30)), (0.22, (0.05, 0.45, 1.00)),
        (0.42, (0.45, 0.15, 1.00)), (0.60, (1.00, 0.30, 0.06)),
        (0.78, (1.00, 0.85, 0.10)), (1.00, (0.10, 0.95, 0.75)),
    ]
    ramp.color_ramp.elements[0].position = stops[0][0]
    ramp.color_ramp.elements[0].color = (*stops[0][1], 1)
    ramp.color_ramp.elements[1].position = stops[-1][0]
    ramp.color_ramp.elements[1].color = (*stops[-1][1], 1)
    for pos, col in stops[1:-1]:
        ramp.color_ramp.elements.new(pos).color = (*col, 1)
    g.link(split.outputs["Red"], ramp.inputs["Fac"])
    amount = g.map_range(split.outputs["Green"], 0.0, 1.0, fire[0], fire[1])
    g.link(g.mix(amount, milk, ramp.outputs["Color"]), bsdf.inputs["Base Color"])
    bsdf.inputs["Subsurface Weight"].default_value = 0.15
    bsdf.inputs["Subsurface Radius"].default_value = (0.8, 0.9, 1.0)
    bsdf.inputs["Subsurface Scale"].default_value = ctx.length(0.006)
    bsdf.inputs["Specular IOR Level"].default_value = 0.08
    return imperfect(mat, 0.10, 0.22, bump_strength=0.006, scale=232.0, ctx=ctx)
