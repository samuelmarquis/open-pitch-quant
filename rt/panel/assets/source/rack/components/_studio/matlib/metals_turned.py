"""Metal family, lathe finishes: spun, turned, faced and diamond-cut metal
whose grain circles or radiates from a part's own Z axis.

Every key here builds its anisotropy tangent and its polar texture from OBJECT
coordinates about the object's Z axis, so the part must be modelled centred on
that axis. Tangents are carried to world space as noted per builder. Angular
multipliers (streaks per radian) are not spatial; radial ones are, and go
through ctx.freq.

Calibration per origin component: units.MM_PER_UNIT.
"""
import math

import bpy

from .core import DEFAULT_CTX, base_material, imperfect, material
from .metals_coated import _map_range, _math, _noise, tint
from .units import mm_per_unit

BOSS_MM = mm_per_unit("knob-boss")
WITCHHAT_MM = mm_per_unit("knob-witchhat")
DAVIES_MM = mm_per_unit("knob-davies")
HIFI_MM = mm_per_unit("knob-hifi")
LEATHER_MM = mm_per_unit("knob-leather")
WOOD_MM = mm_per_unit("knob-wood")
_TURNED = dict(family="metal", solid=False)


# ---------------------------------------------------------------------------
# knob-boss


@material("aluminium-spun", finish="satin", calib_mm_per_unit=BOSS_MM,
          origin="knob-boss:spun_metal_material:278", **_TURNED)
def mat_aluminium_spun(tone=1.0, name="spun aluminium", *, ctx=DEFAULT_CTX):
    """Spun aluminium disc: true radial anisotropy 0.72 (object XY radial,
    transformed Object -> World), irregular hairlines from a fine polar noise
    (68 per radian around, 0.42 per unit out), slow pressure variation from a
    broad polar noise scaling that roughness 0.86-1.14, fine ring grooves
    concentric about object Z (wave 320), and imperfect() mottle blended in at
    20%.
    `tone` scales the base colour (0.42, 0.46, 0.50).

    Duplicate candidate: aluminium-spun-satin, aluminium-fine-turned-*."""
    mat, nt, bsdf = base_material(name)
    bsdf.inputs["Base Color"].default_value = (0.42 * tone, 0.46 * tone, 0.50 * tone, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.38
    bsdf.inputs["Anisotropic"].default_value = 0.72
    imperfect(mat, 0.30, 0.48, bump_strength=0.003, scale=306.0, ctx=ctx)
    previous_normal = bsdf.inputs["Normal"].links[0].from_socket if bsdf.inputs["Normal"].is_linked else None
    previous_roughness = bsdf.inputs["Roughness"].links[0].from_socket if bsdf.inputs["Roughness"].is_linked else None

    coord = nt.nodes.new("ShaderNodeTexCoord")
    separate = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Object"], separate.inputs["Vector"])
    plane = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(separate.outputs["X"], plane.inputs["X"])
    nt.links.new(separate.outputs["Y"], plane.inputs["Y"])
    to_world = nt.nodes.new("ShaderNodeVectorTransform")
    to_world.vector_type = "VECTOR"
    to_world.convert_from = "OBJECT"
    to_world.convert_to = "WORLD"
    nt.links.new(plane.outputs["Vector"], to_world.inputs["Vector"])
    radial_tangent = nt.nodes.new("ShaderNodeVectorMath")
    radial_tangent.operation = "NORMALIZE"
    nt.links.new(to_world.outputs["Vector"], radial_tangent.inputs[0])
    nt.links.new(radial_tangent.outputs["Vector"], bsdf.inputs["Tangent"])

    angle = nt.nodes.new("ShaderNodeMath")
    angle.operation = "ARCTAN2"
    nt.links.new(separate.outputs["Y"], angle.inputs[0])
    nt.links.new(separate.outputs["X"], angle.inputs[1])
    x_square = nt.nodes.new("ShaderNodeMath")
    x_square.operation = "MULTIPLY"
    nt.links.new(separate.outputs["X"], x_square.inputs[0])
    nt.links.new(separate.outputs["X"], x_square.inputs[1])
    y_square = nt.nodes.new("ShaderNodeMath")
    y_square.operation = "MULTIPLY"
    nt.links.new(separate.outputs["Y"], y_square.inputs[0])
    nt.links.new(separate.outputs["Y"], y_square.inputs[1])
    radius_squared = nt.nodes.new("ShaderNodeMath")
    radius_squared.operation = "ADD"
    nt.links.new(x_square.outputs[0], radius_squared.inputs[0])
    nt.links.new(y_square.outputs[0], radius_squared.inputs[1])
    radius = nt.nodes.new("ShaderNodeMath")
    radius.operation = "SQRT"
    nt.links.new(radius_squared.outputs[0], radius.inputs[0])

    fine_angle = nt.nodes.new("ShaderNodeMath")
    fine_angle.operation = "MULTIPLY"
    fine_angle.inputs[1].default_value = 68.0
    nt.links.new(angle.outputs[0], fine_angle.inputs[0])
    fine_radius = nt.nodes.new("ShaderNodeMath")
    fine_radius.operation = "MULTIPLY"
    fine_radius.inputs[1].default_value = ctx.freq(0.42, BOSS_MM)
    nt.links.new(radius.outputs[0], fine_radius.inputs[0])
    fine_polar = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(fine_angle.outputs[0], fine_polar.inputs["X"])
    nt.links.new(fine_radius.outputs[0], fine_polar.inputs["Y"])
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 1.0
    fine.inputs["Detail"].default_value = 2.2
    fine.inputs["Roughness"].default_value = 0.68
    fine.inputs["Distortion"].default_value = 0.025
    nt.links.new(fine_polar.outputs["Vector"], fine.inputs["Vector"])

    broad_angle = nt.nodes.new("ShaderNodeMath")
    broad_angle.operation = "MULTIPLY"
    broad_angle.inputs[1].default_value = 13.0
    nt.links.new(angle.outputs[0], broad_angle.inputs[0])
    broad_radius = nt.nodes.new("ShaderNodeMath")
    broad_radius.operation = "MULTIPLY"
    broad_radius.inputs[1].default_value = ctx.freq(1.4, BOSS_MM)
    nt.links.new(radius.outputs[0], broad_radius.inputs[0])
    broad_polar = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(broad_angle.outputs[0], broad_polar.inputs["X"])
    nt.links.new(broad_radius.outputs[0], broad_polar.inputs["Y"])
    broad = nt.nodes.new("ShaderNodeTexNoise")
    broad.inputs["Scale"].default_value = 0.72
    broad.inputs["Detail"].default_value = 3.0
    broad.inputs["Roughness"].default_value = 0.62
    broad.inputs["Distortion"].default_value = 0.08
    nt.links.new(broad_polar.outputs["Vector"], broad.inputs["Vector"])

    ring_wave = nt.nodes.new("ShaderNodeTexWave")
    ring_wave.wave_type = "RINGS"
    ring_wave.rings_direction = "Z"
    nt.links.new(coord.outputs["Object"], ring_wave.inputs["Vector"])
    ring_wave.inputs["Scale"].default_value = ctx.freq(320.0, BOSS_MM)
    ring_wave.inputs["Distortion"].default_value = 0.22
    ring_wave.inputs["Detail"].default_value = 1.0
    ring_bump = nt.nodes.new("ShaderNodeBump")
    ring_bump.inputs["Strength"].default_value = 0.004
    ring_bump.inputs["Distance"].default_value = ctx.length(0.0012, BOSS_MM)
    nt.links.new(ring_wave.outputs["Color"], ring_bump.inputs["Height"])
    if previous_normal:
        nt.links.new(previous_normal, ring_bump.inputs["Normal"])

    brush_bump = nt.nodes.new("ShaderNodeBump")
    brush_bump.inputs["Strength"].default_value = 0.09
    brush_bump.inputs["Distance"].default_value = ctx.length(0.0012, BOSS_MM)
    nt.links.new(fine.outputs["Fac"], brush_bump.inputs["Height"])
    nt.links.new(ring_bump.outputs["Normal"], brush_bump.inputs["Normal"])
    nt.links.new(brush_bump.outputs["Normal"], bsdf.inputs["Normal"])

    fine_roughness = nt.nodes.new("ShaderNodeMapRange")
    fine_roughness.inputs["To Min"].default_value = 0.24
    fine_roughness.inputs["To Max"].default_value = 0.52
    nt.links.new(fine.outputs["Fac"], fine_roughness.inputs["Value"])
    broad_pressure = nt.nodes.new("ShaderNodeMapRange")
    broad_pressure.inputs["To Min"].default_value = 0.86
    broad_pressure.inputs["To Max"].default_value = 1.14
    nt.links.new(broad.outputs["Fac"], broad_pressure.inputs["Value"])
    brushed_roughness = nt.nodes.new("ShaderNodeMath")
    brushed_roughness.operation = "MULTIPLY"
    nt.links.new(fine_roughness.outputs["Result"], brushed_roughness.inputs[0])
    nt.links.new(broad_pressure.outputs["Result"], brushed_roughness.inputs[1])
    if previous_roughness:
        old_weight = nt.nodes.new("ShaderNodeMath")
        old_weight.operation = "MULTIPLY"
        old_weight.inputs[1].default_value = 0.20
        nt.links.new(previous_roughness, old_weight.inputs[0])
        brush_weight = nt.nodes.new("ShaderNodeMath")
        brush_weight.operation = "MULTIPLY"
        brush_weight.inputs[1].default_value = 0.80
        nt.links.new(brushed_roughness.outputs[0], brush_weight.inputs[0])
        combined = nt.nodes.new("ShaderNodeMath")
        combined.operation = "ADD"
        nt.links.new(old_weight.outputs[0], combined.inputs[0])
        nt.links.new(brush_weight.outputs[0], combined.inputs[1])
        nt.links.new(combined.outputs[0], bsdf.inputs["Roughness"])
    else:
        nt.links.new(brushed_roughness.outputs[0], bsdf.inputs["Roughness"])
    return mat


# ---------------------------------------------------------------------------
# knob-witchhat


def _sock(node, ident, outputs=False):
    for s in (node.outputs if outputs else node.inputs):
        if s.identifier == ident:
            return s
    raise KeyError(ident)


def _feed(nt, target, value):
    if isinstance(value, bpy.types.NodeSocket):
        nt.links.new(value, target)
    else:
        target.default_value = value


def _m(nt, op, a, b=0.0, clamp=False):
    node = nt.nodes.new("ShaderNodeMath")
    node.operation = op
    node.use_clamp = clamp
    _feed(nt, node.inputs[0], a)
    _feed(nt, node.inputs[1], b)
    return node.outputs[0]


def _remap(nt, value, f0, f1, t0=0.0, t1=1.0, smooth_step=True):
    node = nt.nodes.new("ShaderNodeMapRange")
    if smooth_step:
        node.interpolation_type = "SMOOTHSTEP"
    _feed(nt, node.inputs["Value"], value)
    node.inputs["From Min"].default_value = f0
    node.inputs["From Max"].default_value = f1
    node.inputs["To Min"].default_value = t0
    node.inputs["To Max"].default_value = t1
    return node.outputs["Result"]


def _vnoise(nt, vec, scale, detail=3.0, rough=0.55):
    node = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(vec, node.inputs["Vector"])
    node.inputs["Scale"].default_value = scale
    node.inputs["Detail"].default_value = detail
    node.inputs["Roughness"].default_value = rough
    return node.outputs["Fac"]


_SPUN_SATIN = dict(finish="satin", calib_mm_per_unit=WITCHHAT_MM,
                   origin="knob-witchhat:spun_metal_material:618", **_TURNED)


@material("aluminium-spun-satin", **_SPUN_SATIN)
@material("aluminium-spun-satin-gold", params={"tint": (0.74, 0.52, 0.22)}, **_SPUN_SATIN)
def mat_aluminium_spun_satin(tint=(0.42, 0.46, 0.50), name="spun insert", *, ctx=DEFAULT_CTX):
    """Spun metal insert, smoother and more anisotropic (0.85) than
    aluminium-spun: radial tangent (object XY, Object -> World), a fine polar
    noise (68 per radian, 0.42 per unit) driving a brush bump and roughness
    0.14-0.34 blended 75% over imperfect() mottle, fine ring grooves concentric
    about object Z (wave 533). `tint` is the base colour.

    Duplicate candidate: aluminium-spun."""
    mat, nt, bsdf = base_material(name)
    bsdf.inputs["Base Color"].default_value = (*tint, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Anisotropic"].default_value = 0.85
    imperfect(mat, 0.16, 0.30, bump_strength=0.003, scale=511.0, ctx=ctx)
    previous_normal = bsdf.inputs["Normal"].links[0].from_socket
    previous_rough = bsdf.inputs["Roughness"].links[0].from_socket

    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Object"], sep.inputs["Vector"])
    plane = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["X"], plane.inputs["X"])
    nt.links.new(sep.outputs["Y"], plane.inputs["Y"])
    to_world = nt.nodes.new("ShaderNodeVectorTransform")
    to_world.vector_type = "VECTOR"
    to_world.convert_from = "OBJECT"
    to_world.convert_to = "WORLD"
    nt.links.new(plane.outputs["Vector"], to_world.inputs["Vector"])
    tangent = nt.nodes.new("ShaderNodeVectorMath")
    tangent.operation = "NORMALIZE"
    nt.links.new(to_world.outputs["Vector"], tangent.inputs[0])
    nt.links.new(tangent.outputs["Vector"], bsdf.inputs["Tangent"])

    th = _m(nt, "ARCTAN2", sep.outputs["Y"], sep.outputs["X"])
    rad = _m(nt, "SQRT", _m(nt, "ADD", _m(nt, "MULTIPLY", sep.outputs["X"], sep.outputs["X"]),
                            _m(nt, "MULTIPLY", sep.outputs["Y"], sep.outputs["Y"])))
    fine_p = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(_m(nt, "MULTIPLY", th, 68.0), fine_p.inputs["X"])
    nt.links.new(_m(nt, "MULTIPLY", rad, ctx.freq(0.42, WITCHHAT_MM)), fine_p.inputs["Y"])
    fine = _vnoise(nt, fine_p.outputs["Vector"], 1.0, 2.2, 0.68)
    ring = nt.nodes.new("ShaderNodeTexWave")
    ring.wave_type = "RINGS"
    ring.rings_direction = "Z"
    nt.links.new(coord.outputs["Object"], ring.inputs["Vector"])
    ring.inputs["Scale"].default_value = ctx.freq(533.0, WITCHHAT_MM)
    ring.inputs["Distortion"].default_value = 0.22
    ring_bump = nt.nodes.new("ShaderNodeBump")
    ring_bump.inputs["Strength"].default_value = 0.004
    ring_bump.inputs["Distance"].default_value = ctx.length(0.0012, WITCHHAT_MM)
    nt.links.new(ring.outputs["Color"], ring_bump.inputs["Height"])
    nt.links.new(previous_normal, ring_bump.inputs["Normal"])
    brush = nt.nodes.new("ShaderNodeBump")
    brush.inputs["Strength"].default_value = 0.03
    brush.inputs["Distance"].default_value = ctx.length(0.0012, WITCHHAT_MM)
    nt.links.new(fine, brush.inputs["Height"])
    nt.links.new(ring_bump.outputs["Normal"], brush.inputs["Normal"])
    nt.links.new(brush.outputs["Normal"], bsdf.inputs["Normal"])
    brushed = _remap(nt, fine, 0.0, 1.0, 0.14, 0.34, smooth_step=False)
    nt.links.new(_m(nt, "ADD", _m(nt, "MULTIPLY", previous_rough, 0.25),
                    _m(nt, "MULTIPLY", brushed, 0.75)), bsdf.inputs["Roughness"])
    return mat


# ---------------------------------------------------------------------------
# knob-davies

DAVIES_CAPS = {
    "gold": ((0.95, 0.52, 0.13), 0.20, 0.32, 0.78),
    "silver": ((0.80, 0.81, 0.82), 0.20, 0.32, 0.78),
    "black": ((0.030, 0.030, 0.034), 0.18, 0.28, 0.70),
}
_DAVIES = dict(finish="satin", calib_mm_per_unit=DAVIES_MM,
               origin="knob-davies:turned_anodised:362", **_TURNED)


def _davies(cap):
    t, lo, hi, an = DAVIES_CAPS[cap]
    return {"tint": t, "rough_lo": lo, "rough_hi": hi, "aniso": an,
            "name": f"turned {cap} anodised"}


@material("aluminium-turned-anodized-gold", params=_davies("gold"), **_DAVIES)
@material("aluminium-turned-anodized-silver", params=_davies("silver"), **_DAVIES)
@material("aluminium-turned-anodized-black", params=_davies("black"), **_DAVIES)
def mat_aluminium_turned_anodized(tint=(0.95, 0.52, 0.13), rough_lo=0.20, rough_hi=0.32,
                                  aniso=0.78, name="turned anodised", *, ctx=DEFAULT_CTX):
    """Turned anodised-aluminium cap: concentric turning grooves (ring wave on
    object XY, 2 pi / 0.2 per unit, wandering pitch), irregular radial hairlines
    (noise fast in radius, slow around) modulating roughness 0.88-1.12 over
    imperfect() mottle rough_lo..rough_hi, and an uneven dye take-up (Object
    noise) drifting the `tint` density 0.90-1.06.

    The anisotropy tangent is RADIAL IN WORLD SPACE from the Geometry Position,
    about the world Z axis: the part must sit centred on the world origin.

    Duplicate candidate: aluminium-fine-turned-*, aluminium-spun."""
    mat, nt, bsdf = base_material(name)
    bsdf.inputs["Base Color"].default_value = (*tint, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Anisotropic"].default_value = aniso
    imperfect(mat, rough_lo, rough_hi, bump_strength=0.004, scale=242.0, ctx=ctx)
    mottled = bsdf.inputs["Roughness"].links[0].from_socket
    micro_normal = bsdf.inputs["Normal"].links[0].from_socket

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep_w = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep_w.inputs["Vector"])
    plane_w = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep_w.outputs["X"], plane_w.inputs["X"])
    nt.links.new(sep_w.outputs["Y"], plane_w.inputs["Y"])
    radial = nt.nodes.new("ShaderNodeVectorMath")
    radial.operation = "NORMALIZE"
    nt.links.new(plane_w.outputs["Vector"], radial.inputs[0])
    nt.links.new(radial.outputs["Vector"], bsdf.inputs["Tangent"])

    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Object"], sep.inputs["Vector"])
    plane = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["X"], plane.inputs["X"])
    nt.links.new(sep.outputs["Y"], plane.inputs["Y"])
    rad = nt.nodes.new("ShaderNodeVectorMath")
    rad.operation = "LENGTH"
    nt.links.new(plane.outputs["Vector"], rad.inputs[0])

    rings = nt.nodes.new("ShaderNodeTexWave")
    rings.wave_type = "RINGS"
    rings.rings_direction = "Z"
    rings.wave_profile = "SIN"
    rings.inputs["Scale"].default_value = ctx.freq(2.0 * math.pi / (20.0 * 0.0100), DAVIES_MM)
    rings.inputs["Distortion"].default_value = 0.6
    rings.inputs["Detail"].default_value = 1.5
    rings.inputs["Detail Scale"].default_value = 0.4
    nt.links.new(plane.outputs["Vector"], rings.inputs["Vector"])

    hair_vec = nt.nodes.new("ShaderNodeCombineXYZ")
    hx = nt.nodes.new("ShaderNodeMath")
    hx.operation = "MULTIPLY"
    hx.inputs[1].default_value = ctx.freq(3.0, DAVIES_MM)
    nt.links.new(sep.outputs["X"], hx.inputs[0])
    hy = nt.nodes.new("ShaderNodeMath")
    hy.operation = "MULTIPLY"
    hy.inputs[1].default_value = ctx.freq(3.0, DAVIES_MM)
    nt.links.new(sep.outputs["Y"], hy.inputs[0])
    hz = nt.nodes.new("ShaderNodeMath")
    hz.operation = "MULTIPLY"
    hz.inputs[1].default_value = ctx.freq(900.0, DAVIES_MM)
    nt.links.new(rad.outputs["Value"], hz.inputs[0])
    nt.links.new(hx.outputs[0], hair_vec.inputs["X"])
    nt.links.new(hy.outputs[0], hair_vec.inputs["Y"])
    nt.links.new(hz.outputs[0], hair_vec.inputs["Z"])
    hair = nt.nodes.new("ShaderNodeTexNoise")
    hair.inputs["Scale"].default_value = 1.0
    hair.inputs["Detail"].default_value = 3.0
    hair.inputs["Roughness"].default_value = 0.6
    nt.links.new(hair_vec.outputs["Vector"], hair.inputs["Vector"])

    ring_bump = nt.nodes.new("ShaderNodeBump")
    ring_bump.inputs["Strength"].default_value = 0.16
    ring_bump.inputs["Distance"].default_value = ctx.length(0.0015, DAVIES_MM)
    nt.links.new(rings.outputs["Fac"], ring_bump.inputs["Height"])
    nt.links.new(micro_normal, ring_bump.inputs["Normal"])
    hair_bump = nt.nodes.new("ShaderNodeBump")
    hair_bump.inputs["Strength"].default_value = 0.06
    hair_bump.inputs["Distance"].default_value = ctx.length(0.001, DAVIES_MM)
    nt.links.new(hair.outputs["Fac"], hair_bump.inputs["Height"])
    nt.links.new(ring_bump.outputs["Normal"], hair_bump.inputs["Normal"])
    nt.links.new(hair_bump.outputs["Normal"], bsdf.inputs["Normal"])

    dye = nt.nodes.new("ShaderNodeTexNoise")
    dye.inputs["Scale"].default_value = ctx.freq(3.5, DAVIES_MM)
    dye.inputs["Detail"].default_value = 2.0
    nt.links.new(coord.outputs["Object"], dye.inputs["Vector"])
    dye_level = nt.nodes.new("ShaderNodeMapRange")
    dye_level.inputs["To Min"].default_value = 0.90
    dye_level.inputs["To Max"].default_value = 1.06
    nt.links.new(dye.outputs["Fac"], dye_level.inputs["Value"])
    dye_grey = nt.nodes.new("ShaderNodeCombineColor")
    for channel in ("Red", "Green", "Blue"):
        nt.links.new(dye_level.outputs["Result"], dye_grey.inputs[channel])
    dye_mix = nt.nodes.new("ShaderNodeMix")
    dye_mix.data_type = "RGBA"
    dye_mix.blend_type = "MULTIPLY"
    _sock(dye_mix, "Factor_Float").default_value = 1.0
    _sock(dye_mix, "A_Color").default_value = (*tint, 1)
    nt.links.new(dye_grey.outputs["Color"], _sock(dye_mix, "B_Color"))
    nt.links.new(_sock(dye_mix, "Result_Color", True), bsdf.inputs["Base Color"])

    hair_rough = nt.nodes.new("ShaderNodeMapRange")
    hair_rough.inputs["To Min"].default_value = 0.88
    hair_rough.inputs["To Max"].default_value = 1.12
    nt.links.new(hair.outputs["Fac"], hair_rough.inputs["Value"])
    rough_mix = nt.nodes.new("ShaderNodeMath")
    rough_mix.operation = "MULTIPLY"
    nt.links.new(mottled, rough_mix.inputs[0])
    nt.links.new(hair_rough.outputs["Result"], rough_mix.inputs[1])
    nt.links.new(rough_mix.outputs[0], bsdf.inputs["Roughness"])
    return mat


# ---------------------------------------------------------------------------
# knob-hifi


def _obj_radial(nt):
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Object"], sep.inputs["Vector"])
    return coord, sep


def _world_radial_tangent(nt, sep):
    plane = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["X"], plane.inputs["X"])
    nt.links.new(sep.outputs["Y"], plane.inputs["Y"])
    to_world = nt.nodes.new("ShaderNodeVectorTransform")
    to_world.vector_type = "VECTOR"
    to_world.convert_from = "OBJECT"
    to_world.convert_to = "WORLD"
    nt.links.new(plane.outputs["Vector"], to_world.inputs["Vector"])
    norm = nt.nodes.new("ShaderNodeVectorMath")
    norm.operation = "NORMALIZE"
    nt.links.new(to_world.outputs["Vector"], norm.inputs[0])
    return norm.outputs["Vector"]


HIFI_TOP = {
    "silver": (0.47, 0.475, 0.48),
    "black": (0.022, 0.022, 0.024),
    "champagne": (0.64, 0.49, 0.28),
    "blue": (0.026, 0.036, 0.34),
}
_FINE = dict(finish="satin", calib_mm_per_unit=HIFI_MM, origin="knob-hifi:turned_face:373",
             **_TURNED)


@material("aluminium-fine-turned-silver", **_FINE)
@material("aluminium-fine-turned-black", params={"colour": HIFI_TOP["black"]}, **_FINE)
@material("aluminium-fine-turned-champagne", params={"colour": HIFI_TOP["champagne"]}, **_FINE)
@material("aluminium-fine-turned-blue", params={"colour": HIFI_TOP["blue"]}, **_FINE)
def mat_aluminium_fine_turned(colour=HIFI_TOP["silver"], name="turned top face", *,
                              ctx=DEFAULT_CTX):
    """Fine concentric turning under a dye: radial anisotropy 0.70 (object XY,
    Object -> World) throws the fan sheen, a polar streak noise (120 per radian,
    1.2 per unit) holds roughness in 0.24-0.28, an Object mottle tints `colour`
    +-5%, and a faint Object ring wave (160) gives the tool marks.

    Duplicate candidate: aluminium-turned-anodized-*, aluminium-spun."""
    mat, nt, bsdf = base_material(name)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Anisotropic"].default_value = 0.70
    coord, sep = _obj_radial(nt)
    nt.links.new(_world_radial_tangent(nt, sep), bsdf.inputs["Tangent"])
    radius = _math(nt, "SQRT", _math(
        nt, "ADD",
        _math(nt, "MULTIPLY", sep.outputs["X"], sep.outputs["X"]),
        _math(nt, "MULTIPLY", sep.outputs["Y"], sep.outputs["Y"])))
    angle = _math(nt, "ARCTAN2", sep.outputs["Y"], sep.outputs["X"])
    polar = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(_math(nt, "MULTIPLY", angle, 120.0), polar.inputs["X"])
    nt.links.new(_math(nt, "MULTIPLY", radius, ctx.freq(1.2, HIFI_MM)), polar.inputs["Y"])
    streak = _noise(nt, 1.0, detail=2.5, roughness=0.6, vector=polar.outputs["Vector"])
    mottle = _noise(nt, ctx.freq(60.0, HIFI_MM), detail=2.0, vector=coord.outputs["Object"])
    nt.links.new(tint(nt, colour, mottle, 0.05), bsdf.inputs["Base Color"])
    nt.links.new(_map_range(nt, streak, 0.24, 0.28, 0.25, 0.75), bsdf.inputs["Roughness"])
    rings = nt.nodes.new("ShaderNodeTexWave")
    rings.wave_type = "RINGS"
    rings.rings_direction = "Z"
    rings.inputs["Scale"].default_value = ctx.freq(160.0, HIFI_MM)
    rings.inputs["Distortion"].default_value = 0.6
    rings.inputs["Detail"].default_value = 1.0
    nt.links.new(coord.outputs["Object"], rings.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.03
    bump.inputs["Distance"].default_value = ctx.length(0.0008, HIFI_MM)
    nt.links.new(rings.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


_CUT = dict(finish="mirror", calib_mm_per_unit=HIFI_MM, origin="knob-hifi:diamond_cut:408",
            **_TURNED)


@material("aluminium-diamond-cut", **_CUT)
@material("aluminium-diamond-cut-champagne", params={"colour": (0.94, 0.92, 0.88)}, **_CUT)
def mat_aluminium_diamond_cut(colour=(0.93, 0.93, 0.94), name="diamond-cut chamfer", *,
                              ctx=DEFAULT_CTX):
    """Diamond-turned bright cut: near-mirror bare aluminium (roughness
    0.09-0.12 from an Object mottle), faint radial anisotropy 0.55 (object XY,
    Object -> World) so a reflected light bar stretches into a ring segment."""
    mat, nt, bsdf = base_material(name)
    bsdf.inputs["Base Color"].default_value = (*colour, 1.0)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Anisotropic"].default_value = 0.55
    coord, sep = _obj_radial(nt)
    nt.links.new(_world_radial_tangent(nt, sep), bsdf.inputs["Tangent"])
    mottle = _noise(nt, ctx.freq(40.0, HIFI_MM), detail=2.0, vector=coord.outputs["Object"])
    nt.links.new(_map_range(nt, mottle, 0.09, 0.12, 0.3, 0.7), bsdf.inputs["Roughness"])
    return mat


# ---------------------------------------------------------------------------
# knob-leather


def _lmap(nt, src, fmin, fmax, tmin, tmax, clamp=True):
    node = nt.nodes.new("ShaderNodeMapRange")
    node.clamp = clamp
    node.inputs["From Min"].default_value = fmin
    node.inputs["From Max"].default_value = fmax
    node.inputs["To Min"].default_value = tmin
    node.inputs["To Max"].default_value = tmax
    nt.links.new(src, node.inputs["Value"])
    return node.outputs["Result"]


def _lbump(nt, height, strength, distance, normal=None, invert=False):
    node = nt.nodes.new("ShaderNodeBump")
    node.invert = invert
    node.inputs["Strength"].default_value = strength
    node.inputs["Distance"].default_value = distance
    nt.links.new(height, node.inputs["Height"])
    if normal is not None:
        nt.links.new(normal, node.inputs["Normal"])
    return node.outputs["Normal"]


_BRASS = dict(calib_mm_per_unit=LEATHER_MM, origin="knob-leather:brass_material:580", **_TURNED)


@material("brass-turned-satin", finish="satin", **_BRASS)
@material("brass-turned-blasted", finish="matte",
          params={"rough_lo": 0.42, "rough_hi": 0.52, "aniso": 0.15,
                  "name": "bead-blasted brass collar"}, **_BRASS)
@material("brass-turned-polished", finish="gloss",
          params={"rough_lo": 0.08, "rough_hi": 0.13, "aniso": 0.0, "polished": True,
                  "name": "polished brass pin"}, **_BRASS)
def mat_brass_turned(rough_lo=0.17, rough_hi=0.30, aniso=0.70, polished=False,
                     name="satin turned brass", *, ctx=DEFAULT_CTX):
    """Lathe-turned brass (0.62, 0.43, 0.16): circumferential tangent (object
    Z x P, Object -> World), hairlines along height + radius from a noise at 520,
    slow patches (Object noise 6) nudging roughness -0.03..+0.04 over
    rough_lo..rough_hi, and a hairline bump unless `polished`.

    The hairline lookup mixes radius (spatial, scaled at the texture) with angle
    x 0.004 (per radian); the angle multiplier takes ctx.length so the angular
    rate is unchanged at any scale.

    Duplicate candidate: brass-bare, aluminium-spun."""
    mat, nt, bsdf = base_material(name)
    bsdf.inputs["Base Color"].default_value = (0.62, 0.43, 0.16, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Anisotropic"].default_value = aniso
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Object"], sep.inputs["Vector"])
    circ = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(_math(nt, "MULTIPLY", sep.outputs["Y"], -1.0), circ.inputs["X"])
    nt.links.new(sep.outputs["X"], circ.inputs["Y"])
    to_world = nt.nodes.new("ShaderNodeVectorTransform")
    to_world.vector_type = "VECTOR"
    to_world.convert_from = "OBJECT"
    to_world.convert_to = "WORLD"
    nt.links.new(circ.outputs["Vector"], to_world.inputs["Vector"])
    norm = nt.nodes.new("ShaderNodeVectorMath")
    norm.operation = "NORMALIZE"
    nt.links.new(to_world.outputs["Vector"], norm.inputs[0])
    nt.links.new(norm.outputs["Vector"], bsdf.inputs["Tangent"])

    radius = _math(nt, "SQRT", _math(nt, "ADD",
                   _math(nt, "MULTIPLY", sep.outputs["X"], sep.outputs["X"]),
                   _math(nt, "MULTIPLY", sep.outputs["Y"], sep.outputs["Y"])))
    angle = _math(nt, "ARCTAN2", sep.outputs["Y"], sep.outputs["X"])
    lines = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(_math(nt, "ADD", radius, sep.outputs["Z"]), lines.inputs["X"])
    nt.links.new(_math(nt, "MULTIPLY", angle, ctx.length(0.004, LEATHER_MM)), lines.inputs["Y"])
    hair = nt.nodes.new("ShaderNodeTexNoise")
    hair.inputs["Scale"].default_value = ctx.freq(520.0, LEATHER_MM)
    hair.inputs["Detail"].default_value = 3.0
    hair.inputs["Roughness"].default_value = 0.7
    nt.links.new(lines.outputs["Vector"], hair.inputs["Vector"])
    patch = nt.nodes.new("ShaderNodeTexNoise")
    patch.inputs["Scale"].default_value = ctx.freq(6.0, LEATHER_MM)
    patch.inputs["Detail"].default_value = 3.0
    nt.links.new(coord.outputs["Object"], patch.inputs["Vector"])
    rough = _math(nt, "ADD", _lmap(nt, hair.outputs["Fac"], 0.3, 0.7, rough_lo, rough_hi),
                  _lmap(nt, patch.outputs["Fac"], 0.3, 0.7, -0.03, 0.04))
    nt.links.new(rough, bsdf.inputs["Roughness"])
    if not polished:
        nt.links.new(_lbump(nt, hair.outputs["Fac"], 0.06, ctx.length(0.001, LEATHER_MM)),
                     bsdf.inputs["Normal"])
    return mat


# ---------------------------------------------------------------------------
# knob-wood flush pointer pin


def srgb(r, g, b):
    """8-bit sRGB triplet -> linear RGBA."""
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b), 1.0)


class _Nodes:
    def __init__(self, nt):
        self.nt = nt

    def _feed(self, sock, v):
        if hasattr(v, "is_output"):
            self.nt.links.new(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=0.0, clamp=False):
        n = self.nt.nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        self._feed(n.inputs[0], a)
        self._feed(n.inputs[1], b)
        return n.outputs[0]

    def vmath(self, op, a, b=(0.0, 0.0, 0.0)):
        n = self.nt.nodes.new("ShaderNodeVectorMath")
        n.operation = op
        self._feed(n.inputs[0], a)
        self._feed(n.inputs[1], b)
        return n.outputs["Value"] if op in ("LENGTH", "DOT_PRODUCT", "DISTANCE") else n.outputs["Vector"]

    def smooth(self, x, lo, hi, out_lo=0.0, out_hi=1.0):
        n = self.nt.nodes.new("ShaderNodeMapRange")
        n.interpolation_type = "SMOOTHSTEP"
        n.clamp = True
        self._feed(n.inputs["Value"], x)
        n.inputs["From Min"].default_value = lo
        n.inputs["From Max"].default_value = hi
        n.inputs["To Min"].default_value = out_lo
        n.inputs["To Max"].default_value = out_hi
        return n.outputs["Result"]

    def remap(self, x, lo, hi, out_lo, out_hi):
        n = self.nt.nodes.new("ShaderNodeMapRange")
        n.clamp = True
        self._feed(n.inputs["Value"], x)
        n.inputs["From Min"].default_value = lo
        n.inputs["From Max"].default_value = hi
        n.inputs["To Min"].default_value = out_lo
        n.inputs["To Max"].default_value = out_hi
        return n.outputs["Result"]

    def mix_col(self, fac, a, b):
        n = self.nt.nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        ins = {s.identifier: s for s in n.inputs}
        self._feed(ins["Factor_Float"], fac)
        self._feed(ins["A_Color"], a)
        self._feed(ins["B_Color"], b)
        return {s.identifier: s for s in n.outputs}["Result_Color"]

    def noise(self, vec, scale, detail=2.0, rough=0.5, distortion=0.0):
        n = self.nt.nodes.new("ShaderNodeTexNoise")
        n.noise_dimensions = "3D"
        self._feed(n.inputs["Vector"], vec)
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = distortion
        return n.outputs["Fac"], n.outputs["Color"]

    def separate(self, vec):
        n = self.nt.nodes.new("ShaderNodeSeparateXYZ")
        self._feed(n.inputs["Vector"], vec)
        return n.outputs["X"], n.outputs["Y"], n.outputs["Z"]

    def combine(self, x, y, z):
        n = self.nt.nodes.new("ShaderNodeCombineXYZ")
        self._feed(n.inputs["X"], x)
        self._feed(n.inputs["Y"], y)
        self._feed(n.inputs["Z"], z)
        return n.outputs["Vector"]

    def bump(self, height, strength, distance, normal=None):
        n = self.nt.nodes.new("ShaderNodeBump")
        n.inputs["Strength"].default_value = strength
        n.inputs["Distance"].default_value = distance
        self._feed(n.inputs["Height"], height)
        if normal is not None:
            self.nt.links.new(normal, n.inputs["Normal"])
        return n.outputs["Normal"]


def _lathe_sanding(k, coord, density):
    x, y, _z = k.separate(coord)
    rk = k.vmath("LENGTH", k.combine(x, y, 0.0))
    theta = k.math("ARCTAN2", y, x)
    v = k.combine(k.math("MULTIPLY", rk, density), k.math("MULTIPLY", theta, 2.5), 0.0)
    n, _c = k.noise(v, 1.0, detail=3.0, rough=0.6)
    return n


INLAY_LOOKS = {
    "brass": dict(tint=(128, 98, 42), margin=(84, 63, 29), metallic=1.0, rough=(0.44, 0.62),
                  name="satin inlay brass"),
    "nickel": dict(tint=(196, 198, 200), margin=(128, 130, 132), metallic=1.0,
                   rough=(0.24, 0.36), name="satin inlay nickel"),
    "copper": dict(tint=(183, 96, 60), margin=(118, 62, 40), metallic=1.0, rough=(0.36, 0.52),
                   name="satin inlay copper"),
    "black": dict(tint=(11, 11, 12), margin=(6, 6, 7), metallic=1.0, rough=(0.24, 0.36),
                  name="lacquered inlay black"),
    "bone": dict(tint=(208, 195, 167), margin=(162, 148, 118), metallic=0.0,
                 rough=(0.40, 0.56), name="inlay bone"),
}


def _inlay(kind):
    lk = INLAY_LOOKS[kind]
    return {"tint": lk["tint"], "margin": lk["margin"], "metallic": lk["metallic"],
            "rough_lo": lk["rough"][0], "rough_hi": lk["rough"][1], "name": lk["name"]}


_PIN = dict(solid=True, calib_mm_per_unit=WOOD_MM, origin="knob-wood:inlay_material:522")


@material("inlay-pin-brass", family="metal", finish="satin", params=_inlay("brass"), **_PIN)
@material("inlay-pin-nickel", family="metal", finish="satin", params=_inlay("nickel"), **_PIN)
@material("inlay-pin-copper", family="metal", finish="satin", params=_inlay("copper"), **_PIN)
@material("inlay-pin-black", family="metal", finish="satin", params=_inlay("black"), **_PIN)
@material("inlay-pin-bone", family="bone", finish="satin", params=_inlay("bone"), **_PIN)
def mat_inlay_pin(tint=(128, 98, 42), margin=(84, 63, 29), metallic=1.0, rough_lo=0.44,
                  rough_hi=0.62, pin_x=0.220, pin_r=0.062, name="satin inlay brass", *,
                  ctx=DEFAULT_CTX):
    """Flush pointer pin faced on a lathe and sanded flush with its host: a
    tarnish margin toward the pin rim (glue line) plus broad polish drift
    blending 8-bit sRGB `tint` toward `margin`, roughness rough_lo..rough_hi
    plus concentric sanding scratches about the PIN's axis, a sanding bump, and
    a built-in RADIAL tangent about Z (the mesh's bounding-box centre), so the
    pin must be its own object. `metallic` 0 is bone: anisotropy 0.15 and a
    faint warm subsurface instead of 0.65.

    `pin_x` (the pin axis's object X offset; it sits on object Y = 0) and
    `pin_r` (its radius) are the host part's geometry in calibration units
    (world units x mm_per_unit / calib), lengths routed through ctx."""
    mat, nt, bsdf = base_material(name)
    k = _Nodes(nt)
    coord = nt.nodes.new("ShaderNodeTexCoord").outputs["Object"]
    bsdf.inputs["Metallic"].default_value = metallic
    axis = (ctx.length(pin_x, WOOD_MM), 0.0, 0.0)
    radius = ctx.length(pin_r, WOOD_MM)
    rim = k.vmath("LENGTH", k.vmath("MULTIPLY", k.vmath("SUBTRACT", coord, axis),
                                    (1.0, 1.0, 0.0)))
    edge = k.smooth(rim, radius * 0.80, radius * 1.0, 0.0, 0.6)
    broad, _c = k.noise(coord, ctx.freq(14.0, WOOD_MM), detail=2.0)
    tarnish = k.math("ADD", k.math("MULTIPLY", edge, 0.75),
                     k.smooth(broad, 0.45, 0.75, 0.0, 0.35), clamp=True)
    col = k.mix_col(tarnish, srgb(*tint), srgb(*margin))
    nt.links.new(col, bsdf.inputs["Base Color"])
    sand = _lathe_sanding(k, k.vmath("SUBTRACT", coord, axis),
                          ctx.freq(1400.0, WOOD_MM))
    rough = k.math("ADD", k.remap(tarnish, 0.0, 1.0, rough_lo, rough_hi),
                   k.math("MULTIPLY", k.math("SUBTRACT", sand, 0.5), 0.16), clamp=True)
    nt.links.new(rough, bsdf.inputs["Roughness"])
    nt.links.new(k.bump(sand, 0.10, ctx.length(0.0008, WOOD_MM)), bsdf.inputs["Normal"])
    tangent = nt.nodes.new("ShaderNodeTangent")
    tangent.direction_type = "RADIAL"
    tangent.axis = "Z"
    nt.links.new(tangent.outputs["Tangent"], bsdf.inputs["Tangent"])
    bsdf.inputs["Anisotropic"].default_value = 0.65 if metallic else 0.15
    if not metallic:
        bsdf.inputs["Subsurface Weight"].default_value = 0.18
        bsdf.inputs["Subsurface Radius"].default_value = (0.6, 0.5, 0.35)
        bsdf.inputs["Subsurface Scale"].default_value = ctx.length(0.05, WOOD_MM)
    return mat
