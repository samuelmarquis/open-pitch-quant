"""Leather family: hides and upholstery skins."""
from .core import DEFAULT_CTX, _obj_vec, base_material, material

_LEATHER = dict(family="leather", finish="gloss", solid=False, origin="matlib.mat_leather")


def _warp(nt, vec, amount, scale, detail=2.0):
    """Low-detail warp: bends cell walls without fraying them into cracks."""
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    nt.links.new(vec, n.inputs["Vector"])
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    sc.inputs["Scale"].default_value = amount
    nt.links.new(n.outputs["Color"], sc.inputs[0])
    add = nt.nodes.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    nt.links.new(vec, add.inputs[0])
    nt.links.new(sc.outputs["Vector"], add.inputs[1])
    return add.outputs["Vector"]


def _math(nt, op, a, b, c=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, v in enumerate((a, b, c)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _network(nt, ctx, freq, width, offset=0.0):
    """1 on a crease line, 0 on a cell's crown: thin lines on bent walls."""
    vec = _obj_vec(nt, ctx.freq((freq, freq, freq)))
    if offset:
        add = nt.nodes.new("ShaderNodeVectorMath")
        add.operation = "ADD"
        add.inputs[1].default_value = (offset, offset * 0.61, offset * 1.37)
        nt.links.new(vec, add.inputs[0])
        vec = add.outputs["Vector"]
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Randomness"].default_value = 1.0
    nt.links.new(_warp(nt, vec, 0.30, 0.7), vor.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.interpolation_type = "SMOOTHSTEP"
    mr.inputs["From Max"].default_value = width
    mr.inputs["To Min"].default_value = 1.0
    mr.inputs["To Max"].default_value = 0.0
    nt.links.new(vor.outputs["Distance"], mr.inputs["Value"])
    return mr.outputs["Result"]


@material("leather", **_LEATHER)
@material("leather-oxblood", params={"col": (0.095, 0.012, 0.010), "name": "leather_oxblood"},
          **_LEATHER)
@material("leather-black", params={"col": (0.022, 0.020, 0.020), "name": "leather_black",
                                   "spec": 0.125},
          **_LEATHER)
def mat_leather(col=(0.051, 0.024, 0.010), name="leather", spec=0.5, coat=0.35,
                rough_crown=0.22, rough_crease=0.72, *, ctx=DEFAULT_CTX):
    """Full-grain hide under a glossy top coat (pass 37, from design-lab/refs/
    leather-*). The grain IS a crease network, but a fine irregular one: ~1.8 mm
    cells with thin creases and a subdividing layer, low relief. At panel
    distance the grain barely resolves and TONE reads: broad pull-up patches
    and sparse, loosely directional wrinkles. Gloss is the top coat over the
    same grain (`coat` 0 and `rough_crown` ~0.52 is matte aniline).

    Dead ends, kept out: straight-walled DISTANCE_TO_EDGE cells read as crazy
    paving; smooth-F1 domes as stucco; a detail-4 warp as cracked mud; strongly
    stretched wrinkles comb the panel into wood grain; cloth `_nap` sheen and a
    pink subsurface wash every colour to pastel skin."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["Subsurface Weight"].default_value = 0.02
    b.inputs["Subsurface Radius"].default_value = (0.5, 0.3, 0.25)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.010)
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.12

    main = _network(nt, ctx, 14.0, 0.06)
    fine = _network(nt, ctx, 14.0 * 2.3, 0.066, offset=23.0)
    crease = _math(nt, "MAXIMUM", main, _math(nt, "MULTIPLY", fine, 0.55))

    wn = nt.nodes.new("ShaderNodeTexNoise")                 # sparse wrinkles
    wn.inputs["Detail"].default_value = 3.0
    wn.inputs["Distortion"].default_value = 0.4
    nt.links.new(_warp(nt, _obj_vec(nt, ctx.freq((2.0, 4.5, 1.0))), 0.4, 0.6, detail=1.0),
                 wn.inputs["Vector"])
    wr = nt.nodes.new("ShaderNodeMapRange")
    wr.interpolation_type = "SMOOTHSTEP"
    wr.inputs["From Min"].default_value = 0.38
    wr.inputs["From Max"].default_value = 0.52
    nt.links.new(wn.outputs["Fac"], wr.inputs["Value"])
    fold = wr.outputs["Result"]                             # 0 in a fold

    pn = nt.nodes.new("ShaderNodeTexNoise")                 # pull-up patches
    pn.inputs["Scale"].default_value = ctx.freq(1.2)
    pn.inputs["Detail"].default_value = 3.0
    pn.inputs["Roughness"].default_value = 0.55
    nt.links.new(_obj_vec(nt), pn.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.30
    ramp.color_ramp.elements[1].position = 0.70
    ramp.color_ramp.elements[0].color = (*(c * 0.78 for c in col), 1)
    ramp.color_ramp.elements[1].color = (*(min(1.0, c * 1.22) for c in col), 1)
    nt.links.new(pn.outputs["Fac"], ramp.inputs["Fac"])

    shade = _math(nt, "MULTIPLY",
                  _math(nt, "MULTIPLY_ADD", crease, -0.30, 1.0),      # creases hold dye
                  _math(nt, "MULTIPLY_ADD", fold, 0.075, 0.925))       # folds shade
    comb = nt.nodes.new("ShaderNodeCombineColor")
    for s in ("Red", "Green", "Blue"):
        nt.links.new(shade, comb.inputs[s])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], mix.inputs["A"])
    nt.links.new(comb.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])

    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = rough_crown
    rr.inputs["To Max"].default_value = rough_crease
    nt.links.new(crease, rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])

    gb = nt.nodes.new("ShaderNodeBump")                     # creases sink
    gb.invert = True
    gb.inputs["Distance"].default_value = ctx.length(0.020)
    nt.links.new(crease, gb.inputs["Height"])
    fb = nt.nodes.new("ShaderNodeBump")                     # folds sink broadly
    fb.inputs["Strength"].default_value = 0.15
    fb.inputs["Distance"].default_value = ctx.length(0.05)
    nt.links.new(fold, fb.inputs["Height"])
    nt.links.new(gb.outputs["Normal"], fb.inputs["Normal"])
    nt.links.new(fb.outputs["Normal"], b.inputs["Normal"])
    return m
