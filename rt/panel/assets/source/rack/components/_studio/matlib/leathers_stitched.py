"""Stitched leathers: dyed hide cut, grooved and saddle-stitched onto a part."""
from .core import DEFAULT_CTX, base_material, material
from .nodes import Graph
from .units import mm_per_unit

# Linear albedos, steeper than sampled reference sRGB because the knob rig reads
# albedo bright and AgX desaturates.
#             base albedo              crease / dye pool         edge paint
LEATHER_DYES = {
    "tan": ((0.265, 0.068, 0.014), (0.095, 0.021, 0.0045), (0.045, 0.014, 0.006)),
    "black": ((0.0110, 0.0104, 0.0104), (0.0035, 0.0033, 0.0034), (0.005, 0.005, 0.005)),
    "oxblood": ((0.048, 0.0062, 0.0060), (0.017, 0.0022, 0.0021), (0.012, 0.0025, 0.0025)),
}


def gray(g, value):
    """A scalar socket as an RGB colour (Combine Color, all three channels)."""
    node = g.node("ShaderNodeCombineColor")
    for name in ("Red", "Green", "Blue"):
        g.link(value, node.inputs[name])
    return node.outputs["Color"]


_DYED = dict(family="leather", finish="satin", solid=False,
             calib_mm_per_unit=mm_per_unit("knob-leather"),
             origin="knob-leather:leather_material:396",
             part_bound={"r_stitch": "stitch_radius", "r_edge": "outer_radius",
                         "z_flange": "flange_z", "h_dome": "dome_rise"})


@material("leather-dyed", **_DYED)
@material("leather-dyed-tan", params={"colorway": "tan"}, **_DYED)
@material("leather-dyed-black", params={"colorway": "black"}, **_DYED)
@material("leather-dyed-oxblood", params={"colorway": "oxblood"}, **_DYED)
def mat_leather_dyed(colorway="tan", base=None, pool=None, edge=None,
                     hole_attribute="stitch_hole", r_stitch=0.362, r_edge=0.430,
                     z_flange=0.571, h_dome=0.120, name=None, *, ctx=DEFAULT_CTX):
    """Saddle-stitched dyed leather on a round padded face: warped pebble grain
    with coarser belly patches, ONE dye-density scalar lerped once from dye
    pool to base, a darker compressed stitch channel, handling patina and
    creases on the crown, punctures that hold dirt, and a burnished,
    edge-painted cut edge.

    The face must be axisymmetric about object Z through the object origin.

      colorway        key of LEATHER_DYES; base / pool / edge (linear RGB)
                      override its three colours when given
      hole_attribute  name of a point FLOAT attribute, 0..1, marking stitch
                      slits and seats (punctures darken and roughen). The
                      component computes it from its stitch geometry; a mesh
                      without it renders with no punctures
      r_stitch        radius of the stitch line
      r_edge          radius of the cut leather edge
      z_flange        height of the flat flange
      h_dome          rise of the padded crown above the flange

    The four placement parameters and the band widths measured from them are
    object-space geometry in the part's own units and are NOT ctx-scaled; grain
    frequencies, grain warp, relief depths and subsurface scale are.
    Duplicate candidate: matlib `leather` (mat_leather, a flat upholstery hide;
    same concept, independent graph)."""
    d_base, d_pool, d_edge = LEATHER_DYES[colorway]
    base_col = d_base if base is None else tuple(base)
    pool_col = d_pool if pool is None else tuple(pool)
    edge_col = d_edge if edge is None else tuple(edge)
    mat, nt, bsdf = base_material(f"{colorway} leather" if name is None else name)
    g = Graph(nt)
    obj = g.coord("Object")
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(obj, sep.inputs["Vector"])
    radius = g.math("SQRT", g.math("ADD",
                                   g.math("MULTIPLY", sep.outputs["X"], sep.outputs["X"]),
                                   g.math("MULTIPLY", sep.outputs["Y"], sep.outputs["Y"])))

    # grain lookup: object space pushed around by a slow noise (object-space offset)
    warp = g.noise(obj, ctx.freq(9.0), detail=2.0)
    centred = g.vmath("SUBTRACT", warp.outputs["Color"], (0.5, 0.5, 0.5))
    gvec = g.vmath("ADD", obj, g.vmath("SCALE", centred, scale=ctx.length(0.010)))

    pebble = g.voronoi(gvec, ctx.freq(46.0), feature="SMOOTH_F1", randomness=0.95,
                       smoothness=0.6)
    crease = g.voronoi(gvec, ctx.freq(46.0), feature="DISTANCE_TO_EDGE", randomness=0.95)
    fine = g.voronoi(gvec, ctx.freq(95.0))                           # pores

    # pebble grain is rounded crowns with narrow, shallow valleys
    crease_open = g.map_range(crease.outputs["Distance"], 0.0, 0.26, 0.0, 1.0)
    crease_open = g.math("POWER", crease_open, 0.8)
    fine_open = g.map_range(fine.outputs["Distance"], 0.1, 0.6, 1.0, 0.0)
    crown_cell = g.map_range(pebble.outputs["Distance"], 0.05, 0.62, 1.0, 0.0)
    # patches of coarser pebble wander through the fine field
    coarse = g.voronoi(gvec, ctx.freq(29.0), feature="SMOOTH_F1", smoothness=0.6)
    size_patch = g.noise(obj, ctx.freq(4.5), detail=1.0)
    coarse_f = g.map_range(size_patch.outputs["Fac"], 0.545, 0.565, 0.0, 1.0)
    coarse_cell = g.map_range(coarse.outputs["Distance"], 0.05, 0.62, 1.0, 0.0)
    crown_cell = g.math("ADD", g.math("MULTIPLY", crown_cell, g.math("SUBTRACT", 1.0, coarse_f)),
                        g.math("MULTIPLY", coarse_cell, coarse_f))

    mottle = g.noise(obj, ctx.freq(3.2), detail=4.0, roughness=0.55)
    mottle_f = g.map_range(mottle.outputs["Fac"], 0.30, 0.70, 0.0, 1.0)

    # handling patina on the crown: darker, glossier
    crown = g.map_range(sep.outputs["Z"], z_flange + 0.035, z_flange + h_dome, 0.0, 1.0)
    hide = g.noise(gvec, ctx.freq(11.0), detail=2.0)
    hide_f = g.map_range(hide.outputs["Fac"], 0.35, 0.65, 0.0, 1.0)
    # the groover compresses and darkens a band under the thread
    channel = g.math("EXPONENT", g.math("MULTIPLY", -1.0, g.math(
        "POWER", g.math("DIVIDE", g.math("SUBTRACT", radius, r_stitch), 0.016), 2.0)))
    # handling creases: wandering iso-lines of a low-frequency noise
    wrinkle = g.noise(gvec, ctx.freq(6.0), detail=3.0, roughness=0.5)
    iso = g.math("ABSOLUTE", g.math("SUBTRACT", wrinkle.outputs["Fac"], 0.5))
    crease_line = g.map_range(iso, 0.0, 0.030, 1.0, 0.0)
    crease_line = g.math("MULTIPLY", crease_line, g.map_range(crown, 0.0, 0.6, 0.0, 1.0))
    edge_band = g.map_range(radius, r_edge - 0.045, r_edge - 0.012, 0.0, 1.0)
    hole = g.node("ShaderNodeAttribute", attribute_name=hole_attribute).outputs["Fac"]

    col = g.dye_density((
        (g.math("SUBTRACT", 1.0, crown_cell), 0.72),
        (g.math("SUBTRACT", 1.0, crease_open), 0.18),
        (fine_open, 0.22),
        (g.math("SUBTRACT", 1.0, mottle_f), 0.20),
        (g.math("SUBTRACT", 1.0, hide_f), 0.14),
        (crown, 0.22),
        (channel, 0.30),
        (crease_line, 0.22),
        (edge_band, 0.40),
    ), pool_col, base_col, lo=0.30, hi=1.40)
    # punctures: the awl slit and the pin seat hold shadow and dirt
    col = g.mix(g.math("MULTIPLY", hole, 0.75), col, tuple(0.25 * c for c in pool_col))

    rough = g.map_range(crease_open, 0.0, 1.0, 0.66, 0.42)
    rough = g.math("SUBTRACT", rough, g.map_range(crown, 0.0, 1.0, 0.0, 0.10))
    rough = g.math("ADD", rough, g.map_range(mottle_f, 0.0, 1.0, 0.06, -0.04))
    rough = g.math("SUBTRACT", rough, g.map_range(channel, 0.0, 1.0, 0.0, 0.08))
    rough = g.math("ADD", rough, g.math("MULTIPLY", hole, 0.25))

    n = g.bump(crown_cell, 0.22, ctx.length(0.006))
    n = g.bump(crease_open, 0.08, ctx.length(0.003), normal=n)
    n = g.bump(fine_open, 0.10, ctx.length(0.0015), normal=n)
    n = g.bump(crease_line, 0.12, ctx.length(0.002), normal=n, invert=True)

    bsdf.inputs["Specular IOR Level"].default_value = 0.18
    bsdf.inputs["Sheen Weight"].default_value = 0.10
    bsdf.inputs["Sheen Roughness"].default_value = 0.45
    bsdf.inputs["Sheen Tint"].default_value = (*base_col, 1.0)
    bsdf.inputs["Coat Weight"].default_value = 0.0
    bsdf.inputs["Subsurface Weight"].default_value = 0.06
    bsdf.inputs["Subsurface Radius"].default_value = (0.6, 0.3, 0.2)
    bsdf.inputs["Subsurface Scale"].default_value = ctx.length(0.004)

    # burnished, edge-painted cut edge beyond the crease line
    edge_f = g.map_range(radius, r_edge - 0.0135, r_edge - 0.0105, 0.0, 1.0)
    g.link(g.mix(edge_f, col, edge_col), bsdf.inputs["Base Color"])
    g.link(g.mix(edge_f, gray(g, rough), (0.30, 0.30, 0.30)), bsdf.inputs["Roughness"])
    g.link(n, bsdf.inputs["Normal"])
    return mat
