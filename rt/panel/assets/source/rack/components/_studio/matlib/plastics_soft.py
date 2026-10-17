"""Plastic family, soft-touch coatings: elastomer-coated moulded parts with a
velvet sheen, grippy grain, caught dust and finger burnish.
"""
from .core import DEFAULT_CTX, base_material, imperfect, material
from .units import mm_per_unit

DIMPLE_MM = mm_per_unit("knob-dimple")


def _sock(sockets, identifier):
    return next(x for x in sockets if x.identifier == identifier)


_SOFT = dict(family="plastic", finish="matte", solid=False, calib_mm_per_unit=DIMPLE_MM,
             origin="knob-dimple:soft_touch_material:208")


@material("soft-touch", **_SOFT)
@material("soft-touch-teal", params={
    "base": (0.0015, 0.052, 0.048), "sheen": (0.45, 0.80, 0.78), "sss": (0.02, 0.35, 0.33),
    "dust": (0.060, 0.105, 0.100), "name": "soft-touch elastomer teal"}, **_SOFT)
@material("soft-touch-coral", params={
    "base": (0.30, 0.026, 0.011), "sheen": (1.00, 0.62, 0.52), "sss": (0.90, 0.25, 0.14),
    "dust": (0.36, 0.13, 0.09), "name": "soft-touch elastomer coral"}, **_SOFT)
@material("soft-touch-cream", params={
    "base": (0.26, 0.205, 0.120), "sheen": (1.00, 0.96, 0.88), "sss": (0.75, 0.66, 0.50),
    "dust": (0.17, 0.15, 0.11), "name": "soft-touch elastomer cream"}, **_SOFT)
def mat_soft_touch(base=(0.016, 0.0165, 0.0185), sheen=(0.60, 0.62, 0.66),
                   sss=(0.05, 0.05, 0.055), dust=(0.075, 0.072, 0.068), lip_attribute="lip",
                   name="soft-touch elastomer graphite", *, ctx=DEFAULT_CTX):
    """Soft-touch elastomer coating: a diffuse body with a weak, very broad
    specular (0.16, IOR 1.48) and a velvet sheen (0.28 at 0.40 tinted
    `sheen`); a concave dish focuses any real gloss into a ball-like hotspot,
    so the gloss stays low.

    Relief: a fine pebble (Object noise 150) over a slower orange peel (45),
    then imperfect() roughness 0.60-0.80. Albedo: `base` mottled +-10 % by the
    pebble, with sparse pale `dust` specks (Voronoi 38 in Object space; F1
    distance under a per-cell radius). Subsurface 0.05 with radius `sss`,
    scale 0.010.

    Finger oil burnishes the roughness (to 0.55 x) where a broad Object noise
    or the float point attribute `lip_attribute` (0..1, the component's worn
    rim mask) is high, and the lip also loses the coating's specular
    suppression (0.16 -> 0.42). Without the attribute the lip term reads 0.
    Colourways: graphite (default), teal, coral, cream."""
    m, nt, b = base_material(name)
    b.inputs["Specular IOR Level"].default_value = 0.16
    b.inputs["IOR"].default_value = 1.48
    b.inputs["Sheen Weight"].default_value = 0.28
    b.inputs["Sheen Roughness"].default_value = 0.40
    b.inputs["Sheen Tint"].default_value = (*sheen, 1.0)
    b.inputs["Subsurface Weight"].default_value = 0.05
    b.inputs["Subsurface Radius"].default_value = sss
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.010)

    coord = nt.nodes.new("ShaderNodeTexCoord")
    previous = None
    pebble = None
    for scale, strength, distance in ((150.0, 0.45, 0.0006), (45.0, 0.12, 0.0010)):
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = ctx.freq(scale)
        tex.inputs["Detail"].default_value = 3.0
        nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = strength
        bump.inputs["Distance"].default_value = ctx.length(distance)
        nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
        pebble = pebble or tex
        if previous is not None:
            nt.links.new(previous.outputs["Normal"], bump.inputs["Normal"])
        previous = bump
    nt.links.new(previous.outputs["Normal"], b.inputs["Normal"])

    imperfect(m, 0.60, 0.80, bump_strength=0.012, scale=102.0, ctx=ctx)

    speckle = nt.nodes.new("ShaderNodeTexVoronoi")
    speckle.inputs["Scale"].default_value = ctx.freq(38.0)
    speckle.inputs["Randomness"].default_value = 1.0
    nt.links.new(coord.outputs["Object"], speckle.inputs["Vector"])
    dust_rgb = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(speckle.outputs["Color"], dust_rgb.inputs["Color"])
    dust_pick = nt.nodes.new("ShaderNodeMath")
    dust_pick.operation = "GREATER_THAN"
    dust_pick.inputs[1].default_value = 0.972
    nt.links.new(dust_rgb.outputs["Red"], dust_pick.inputs[0])
    dust_size = nt.nodes.new("ShaderNodeMapRange")
    dust_size.inputs["To Min"].default_value = 0.10
    dust_size.inputs["To Max"].default_value = 0.22
    nt.links.new(dust_rgb.outputs["Green"], dust_size.inputs["Value"])
    dust_in = nt.nodes.new("ShaderNodeMath")
    dust_in.operation = "LESS_THAN"
    nt.links.new(speckle.outputs["Distance"], dust_in.inputs[0])
    nt.links.new(dust_size.outputs["Result"], dust_in.inputs[1])
    speck = nt.nodes.new("ShaderNodeMath")
    speck.operation = "MULTIPLY"
    nt.links.new(dust_pick.outputs[0], speck.inputs[0])
    nt.links.new(dust_in.outputs[0], speck.inputs[1])

    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    _sock(tint.inputs, "A_Color").default_value = (*base, 1.0)
    _sock(tint.inputs, "B_Color").default_value = (*dust, 1.0)
    nt.links.new(speck.outputs[0], _sock(tint.inputs, "Factor_Float"))
    mottle = nt.nodes.new("ShaderNodeMapRange")
    mottle.inputs["From Min"].default_value = 0.30
    mottle.inputs["From Max"].default_value = 0.70
    mottle.inputs["To Min"].default_value = 0.90
    mottle.inputs["To Max"].default_value = 1.10
    nt.links.new(pebble.outputs["Fac"], mottle.inputs["Value"])
    mottled = nt.nodes.new("ShaderNodeMix")
    mottled.data_type = "RGBA"
    mottled.blend_type = "MULTIPLY"
    _sock(mottled.inputs, "Factor_Float").default_value = 1.0
    nt.links.new(_sock(tint.outputs, "Result_Color"), _sock(mottled.inputs, "A_Color"))
    nt.links.new(mottle.outputs["Result"], _sock(mottled.inputs, "B_Color"))
    nt.links.new(_sock(mottled.outputs, "Result_Color"), b.inputs["Base Color"])

    rough_src = b.inputs["Roughness"].links[0].from_socket
    lip_attr = nt.nodes.new("ShaderNodeAttribute")
    lip_attr.attribute_name = lip_attribute
    oil = nt.nodes.new("ShaderNodeTexNoise")
    oil.inputs["Scale"].default_value = ctx.freq(3.2)
    oil.inputs["Detail"].default_value = 4.0
    nt.links.new(coord.outputs["Object"], oil.inputs["Vector"])
    oil_ramp = nt.nodes.new("ShaderNodeMapRange")
    oil_ramp.inputs["From Min"].default_value = 0.48
    oil_ramp.inputs["From Max"].default_value = 0.68
    oil_ramp.inputs["To Max"].default_value = 0.55
    nt.links.new(oil.outputs["Fac"], oil_ramp.inputs["Value"])
    oil_lip = nt.nodes.new("ShaderNodeMath")
    oil_lip.operation = "MAXIMUM"
    nt.links.new(oil_ramp.outputs["Result"], oil_lip.inputs[0])
    lip_scale = nt.nodes.new("ShaderNodeMath")
    lip_scale.operation = "MULTIPLY"
    lip_scale.inputs[1].default_value = 1.0
    nt.links.new(lip_attr.outputs["Fac"], lip_scale.inputs[0])
    nt.links.new(lip_scale.outputs[0], oil_lip.inputs[1])
    burnish = nt.nodes.new("ShaderNodeMapRange")
    burnish.inputs["To Min"].default_value = 1.0
    burnish.inputs["To Max"].default_value = 0.55
    lip_spec = nt.nodes.new("ShaderNodeMapRange")
    lip_spec.inputs["To Min"].default_value = 0.16
    lip_spec.inputs["To Max"].default_value = 0.42
    nt.links.new(lip_attr.outputs["Fac"], lip_spec.inputs["Value"])
    nt.links.new(lip_spec.outputs["Result"], b.inputs["Specular IOR Level"])
    nt.links.new(oil_lip.outputs[0], burnish.inputs["Value"])
    rough = nt.nodes.new("ShaderNodeMath")
    rough.operation = "MULTIPLY"
    nt.links.new(rough_src, rough.inputs[0])
    nt.links.new(burnish.outputs["Result"], rough.inputs[1])
    speck_rough = nt.nodes.new("ShaderNodeMath")
    speck_rough.operation = "MAXIMUM"
    nt.links.new(rough.outputs[0], speck_rough.inputs[0])
    nt.links.new(speck.outputs[0], speck_rough.inputs[1])
    nt.links.new(speck_rough.outputs[0], b.inputs["Roughness"])
    return m
