"""Metal family, thin metal films in glass: colloidal metal fume and dichroic
interference coating, as fused into art glass. Both are sheets (solid=False)
seen through or against surrounding glass.

Calibration per origin component: units.MM_PER_UNIT.
"""
import bpy  # noqa: F401

from .core import DEFAULT_CTX, base_material, imperfect, material
from .units import mm_per_unit

KNOB_MM = mm_per_unit("knob-heady")
_FILM = dict(family="metal", solid=False, calib_mm_per_unit=KNOB_MM)
_FUME = dict(finish="satin", origin="knob-heady:fume_material:361", **_FILM)


@material("colloidal-silver-fume", **_FUME)
@material("colloidal-gold-fume",
          params={"reflect": (0.95, 0.62, 0.16), "transmit": (0.92, 0.20, 0.52),
                  "weight": 0.38, "name": "gold fume"}, **_FUME)
def mat_colloidal_fume(reflect=(0.06, 0.45, 0.92), transmit=(1.0, 0.55, 0.10), weight=0.42,
                       name="silver fume", *, ctx=DEFAULT_CTX):
    """Colloidal metal fume: a metallic film reflecting `reflect` mixed with a
    Transparent BSDF passing its complement `transmit`. The film's density is
    streaky (Object noise 9, detail 6), weight x 0.55 .. min(weight x 1.35,
    0.95) metal, over imperfect() roughness 0.16-0.32. Silver fumes reflect blue
    and pass amber; gold reflects gold and passes magenta."""
    mat, nt, bsdf = base_material(name)
    bsdf.inputs["Base Color"].default_value = (*reflect, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    imperfect(mat, 0.16, 0.32, bump_strength=0.006, scale=68.2, ctx=ctx)
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    clear.inputs["Color"].default_value = (*transmit, 1)
    coords = nt.nodes.new("ShaderNodeTexCoord")
    streak = nt.nodes.new("ShaderNodeTexNoise")
    streak.inputs["Scale"].default_value = ctx.freq(9.0, KNOB_MM)
    streak.inputs["Detail"].default_value = 6.0
    nt.links.new(coords.outputs["Object"], streak.inputs["Vector"])
    density = nt.nodes.new("ShaderNodeMapRange")
    density.inputs["To Min"].default_value = weight * 0.55
    density.inputs["To Max"].default_value = min(weight * 1.35, 0.95)
    nt.links.new(streak.outputs["Fac"], density.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(density.outputs["Result"], mix.inputs[0])
    nt.links.new(clear.outputs["BSDF"], mix.inputs[1])
    nt.links.new(bsdf.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], nt.nodes["Material Output"].inputs["Surface"])
    return mat


@material("dichroic-coating", finish="gloss", origin="knob-heady:dichro_material:386", **_FILM)
def mat_dichroic_coating(name="dichroic flake", *, ctx=DEFAULT_CTX):
    """Narrow-band interference coating on flakes: each Object Voronoi cell (24)
    picks a hue from a cyclic cyan-blue-magenta-amber ramp, and the hue slides
    with view tilt (Layer Weight facing x 0.35 added before wrapping), over
    imperfect() roughness 0.06-0.16."""
    mat, nt, bsdf = base_material(name)
    bsdf.inputs["Metallic"].default_value = 1.0
    coords = nt.nodes.new("ShaderNodeTexCoord")
    shard = nt.nodes.new("ShaderNodeTexVoronoi")
    shard.inputs["Scale"].default_value = ctx.freq(24.0, KNOB_MM)
    nt.links.new(coords.outputs["Object"], shard.inputs["Vector"])
    split = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(shard.outputs["Color"], split.inputs["Color"])
    tilt = nt.nodes.new("ShaderNodeLayerWeight")
    tilt.inputs["Blend"].default_value = 0.45
    shift = nt.nodes.new("ShaderNodeMath")
    shift.operation = "MULTIPLY_ADD"
    shift.inputs[1].default_value = 0.35
    nt.links.new(tilt.outputs["Facing"], shift.inputs[0])
    nt.links.new(split.outputs["Red"], shift.inputs[2])
    wrap = nt.nodes.new("ShaderNodeMath")
    wrap.operation = "FRACT"
    nt.links.new(shift.outputs["Value"], wrap.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    stops = [(0.00, (0.00, 0.80, 0.85)), (0.25, (0.20, 0.25, 1.00)),
             (0.50, (0.95, 0.08, 0.70)), (0.75, (1.00, 0.62, 0.02)),
             (1.00, (0.00, 0.80, 0.85))]
    ramp.color_ramp.elements[0].color = (*stops[0][1], 1)
    ramp.color_ramp.elements[1].color = (*stops[-1][1], 1)
    for pos, col in stops[1:-1]:
        ramp.color_ramp.elements.new(pos).color = (*col, 1)
    nt.links.new(wrap.outputs["Value"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return imperfect(mat, 0.06, 0.16, bump_strength=0.004, scale=316.0, ctx=ctx)
