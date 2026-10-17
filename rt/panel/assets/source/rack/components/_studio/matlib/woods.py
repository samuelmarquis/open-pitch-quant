"""Wood family: sawn hardwoods and granulated cork.

Species differ in GRAIN CHARACTER, not just colour: ring count and
crookedness (`ring_scale`, `wander`), quarter- vs flat-sawn (`stretch`), how
hard the latewood band lands (`ring_sharp`), pore size (`pore_scale`) and
figure.
"""
from .core import DEFAULT_CTX, _obj_vec, _warp, base_material, material
from .nodes import _mix_rgba
from .textiles import _fibres


@material("cork", family="wood", finish="matte", solid=True, origin="matlib.mat_cork")
def mat_cork(col=(0.55, 0.40, 0.24), name="cork", *, ctx=DEFAULT_CTX):
    """Granulated cork sheet: pressed grains with dark resin between them.
    DISTANCE_TO_EDGE gives the boundaries, two Voronoi scales give big and fine
    granules, and the darkening lives in COLOUR (the resin) not just roughness."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.88
    b.inputs["Diffuse Roughness"].default_value = 0.7
    b.inputs["Specular IOR Level"].default_value = 0.22
    b.inputs["Subsurface Weight"].default_value = 0.10
    b.inputs["Subsurface Radius"].default_value = (0.6, 0.45, 0.3)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.01)
    # Cork is PRESSED SCRAP, so the grains are torn and unequal — an
    # undistorted Voronoi reads as "Voronoi": even cells, straight shared
    # walls. Warping the lookup bends the walls and varies the sizes, which is
    # the whole difference between granulated bark and machine noise.
    cv = _warp(nt, _obj_vec(nt, ctx.freq((1.0, 0.82, 1.0))), 0.55, 16.0)
    edge = nt.nodes.new("ShaderNodeTexVoronoi")
    edge.feature = "DISTANCE_TO_EDGE"
    edge.inputs["Scale"].default_value = 15.0          # bigger, countable grains
    edge.inputs["Randomness"].default_value = 1.0
    nt.links.new(cv, edge.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (col[0] * 0.30, col[1] * 0.26, col[2] * 0.22, 1)
    ramp.color_ramp.elements[1].color = (*col, 1)
    ramp.color_ramp.elements[1].position = 0.26        # thin dark rims
    nt.links.new(edge.outputs["Distance"], ramp.inputs["Fac"])
    # PER-GRANULE TONE is what cork actually looks like: each pressed grain is
    # a different scrap of bark, so they differ in colour, not only at their
    # rims. Voronoi's Color output is a free random value per cell; varying
    # only the edges reads as uniform speckle.
    cells = nt.nodes.new("ShaderNodeTexVoronoi")
    cells.feature = "F1"
    cells.inputs["Scale"].default_value = 15.0
    cells.inputs["Randomness"].default_value = 1.0
    nt.links.new(cv, cells.inputs["Vector"])
    tone = nt.nodes.new("ShaderNodeValToRGB")
    tone.color_ramp.elements[0].color = (0.50, 0.45, 0.38, 1)
    tone.color_ramp.elements[1].color = (1.34, 1.26, 1.12, 1)
    nt.links.new(cells.outputs["Color"], tone.inputs["Fac"])
    _cx, cf, ca, cb2, cres = _mix_rgba(nt, "MULTIPLY")
    cf.default_value = 1.0
    nt.links.new(ramp.outputs["Color"], ca)
    nt.links.new(tone.outputs["Color"], cb2)
    nt.links.new(cres, b.inputs["Base Color"])
    gb = nt.nodes.new("ShaderNodeBump")
    gb.inputs["Strength"].default_value = 0.65
    gb.inputs["Distance"].default_value = ctx.length(0.030)
    nt.links.new(edge.outputs["Distance"], gb.inputs["Height"])
    fine = nt.nodes.new("ShaderNodeTexVoronoi")
    fine.feature = "DISTANCE_TO_EDGE"
    fine.inputs["Scale"].default_value = 44.0
    nt.links.new(_warp(nt, _obj_vec(nt, ctx.freq((1.0, 1.0, 1.0))), 0.4, 45.0),
                 fine.inputs["Vector"])
    fb = nt.nodes.new("ShaderNodeBump")
    fb.inputs["Strength"].default_value = 0.30
    fb.inputs["Distance"].default_value = ctx.length(0.005)
    nt.links.new(fine.outputs["Distance"], fb.inputs["Height"])
    nt.links.new(gb.outputs["Normal"], fb.inputs["Normal"])
    _fibres(nt, b, scales=((89.8, 0.14, 0.006),), prev=fb.outputs["Normal"], ctx=ctx)
    return m


_WOOD = dict(family="wood", finish="satin", solid=True, origin="matlib.mat_wood")


@material("wood-oak", params=dict(
    early=(0.40, 0.27, 0.13), late=(0.20, 0.12, 0.05), ring_scale=5.5, pore=0.95,
    name="wood_oak", wander=7.0, stretch=1.6, pore_scale=46.0,
    ring_sharp=(0.34, 0.50)), **_WOOD)                  # coarse, open, hard bands
@material("wood-walnut", params=dict(
    early=(0.21, 0.12, 0.07), late=(0.08, 0.04, 0.025), ring_scale=9.0, pore=0.5,
    name="wood_walnut", wander=16.0, stretch=2.6, pore_scale=105.0),
    **_WOOD)                                            # wavy; no figure (its bands
                                                        # hatch across the grain, p149)
@material("wood-birch", params=dict(
    early=(0.64, 0.50, 0.32), late=(0.42, 0.30, 0.17), ring_scale=16.0, pore=0.18,
    satin=0.6, name="wood_birch", wander=5.0, stretch=3.4, pore_scale=180.0,
    ring_sharp=(0.40, 0.66)), **_WOOD)
@material("wood-rosewood", params=dict(
    early=(0.25, 0.10, 0.07), late=(0.105, 0.042, 0.032), ring_scale=4.0, pore=0.7,
    satin=0.7, name="wood_rosewood", wander=26.0, stretch=1.3, pore_scale=70.0,
    ring_sharp=(0.30, 0.64)), **_WOOD)                  # streaky, softened
# ebony's coat has to come DOWN, not up: on a near-black base a heavy satin
# is the only thing left to see and the board renders as grey brushed metal.
@material("wood-ebony", params=dict(
    early=(0.058, 0.048, 0.043), late=(0.014, 0.012, 0.012), ring_scale=20.0, pore=0.16,
    satin=0.22, name="wood_ebony", wander=3.0, stretch=4.5, pore_scale=210.0,
    ring_sharp=(0.42, 0.70)), **_WOOD)
@material("wood-greenheart", params=dict(
    early=(0.115, 0.135, 0.040), late=(0.038, 0.050, 0.014), ring_scale=7.0, pore=0.45,
    satin=0.30, name="wood_greenheart", wander=13.0, stretch=2.0, pore_scale=95.0,
    figure=0.8), **_WOOD)                               # interlocked ribbon
def mat_wood(early=(0.36, 0.22, 0.11), late=(0.15, 0.08, 0.04),
             ring_scale=8.0, pore=0.55, satin=0.45, name="wood",
             wander=12.0, stretch=2.2, pore_scale=90.0, figure=0.0,
             ring_sharp=(0.30, 0.62), *, ctx=DEFAULT_CTX):
    """Sawn and finished hardwood. Growth rings from a distorted RINGS wave
    stretched along the grain axis, earlywood/latewood as a two-stop ramp, open
    PORES as stretched bump streaks, and a satin varnish coat over the lot.
    `early`/`late` retune the species; `pore` suits open grain (oak) vs closed
    (maple); `satin` is how much finish is on it."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = satin
    b.inputs["Coat Roughness"].default_value = 0.26
    b.inputs["Specular IOR Level"].default_value = 0.5
    # rings: squashed along Y so the board reads as a flat-sawn plank
    rings = nt.nodes.new("ShaderNodeTexWave")
    rings.wave_type, rings.wave_profile = "RINGS", "SIN"
    rings.inputs["Scale"].default_value = ring_scale
    # `wander` is how crooked the growth rings run and `stretch` how far the
    # board is quarter- vs flat-sawn. Oak is coarse and open, birch tight and
    # quiet, rosewood violently streaked, ebony nearly featureless.
    rings.inputs["Distortion"].default_value = wander
    rings.inputs["Detail"].default_value = 4.0
    rings.inputs["Detail Scale"].default_value = 2.0
    nt.links.new(_obj_vec(nt, ctx.freq((0.18, stretch, 1.0))), rings.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*late, 1)
    ramp.color_ramp.elements[1].color = (*early, 1)
    # tight stops: latewood is a NARROW dark band against wide earlywood. A
    # wide ramp averages the two into one flat tone and the plank vanishes.
    ramp.color_ramp.elements[0].position = ring_sharp[0]
    ramp.color_ramp.elements[1].position = ring_sharp[1]
    nt.links.new(rings.outputs["Factor"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    # latewood is denser => glossier; the ring pattern shows in roughness too
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.32
    rr.inputs["To Max"].default_value = 0.56
    nt.links.new(rings.outputs["Factor"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    # open pores: fine streaks stretched hard along the grain
    pores = nt.nodes.new("ShaderNodeTexNoise")
    pores.inputs["Scale"].default_value = pore_scale
    pores.inputs["Detail"].default_value = 3.0
    nt.links.new(_obj_vec(nt, ctx.freq((1.2, 70.0, 1.0))), pores.inputs["Vector"])
    pb = nt.nodes.new("ShaderNodeBump")
    pb.inputs["Strength"].default_value = pore
    pb.inputs["Distance"].default_value = ctx.length(0.016)
    nt.links.new(pores.outputs["Fac"], pb.inputs["Height"])
    rb = nt.nodes.new("ShaderNodeBump")                 # rings raise a little
    rb.inputs["Strength"].default_value = 0.22
    rb.inputs["Distance"].default_value = ctx.length(0.020)
    nt.links.new(rings.outputs["Factor"], rb.inputs["Height"])
    nt.links.new(pb.outputs["Normal"], rb.inputs["Normal"])
    prev = rb.outputs["Normal"]
    if figure > 0.0:
        # FIGURE: the cross-grain ripple of curly maple or an interlocked
        # tropical ribbon — bands running ACROSS the grain, catching light
        # where the fibres dive. It lives in roughness as much as relief.
        fig = nt.nodes.new("ShaderNodeTexWave")
        fig.wave_type, fig.bands_direction, fig.wave_profile = "BANDS", "X", "SIN"
        fig.inputs["Scale"].default_value = 22.0
        fig.inputs["Distortion"].default_value = 2.5
        fig.inputs["Detail"].default_value = 2.0
        nt.links.new(_obj_vec(nt, ctx.freq((1.0, 0.3, 1.0))), fig.inputs["Vector"])
        fb = nt.nodes.new("ShaderNodeBump")
        fb.inputs["Strength"].default_value = 0.35 * figure
        fb.inputs["Distance"].default_value = ctx.length(0.03)
        nt.links.new(fig.outputs["Factor"], fb.inputs["Height"])
        nt.links.new(prev, fb.inputs["Normal"])
        prev = fb.outputs["Normal"]
        fr = nt.nodes.new("ShaderNodeMapRange")
        fr.inputs["To Min"].default_value = 0.26
        fr.inputs["To Max"].default_value = 0.26 + 0.22 * figure
        nt.links.new(fig.outputs["Factor"], fr.inputs["Value"])
        nt.links.new(fr.outputs["Result"], b.inputs["Roughness"])
    nt.links.new(prev, b.inputs["Normal"])
    return m
