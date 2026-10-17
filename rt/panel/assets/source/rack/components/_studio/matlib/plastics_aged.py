"""Plastic family, aged plastics: yellowed, grimed and hand-polished moulded
plastic whose wear follows the part's own relief.
"""
import math

import bpy

from .core import DEFAULT_CTX, base_material, imperfect, material
from .units import mm_per_unit

WITCHHAT_MM = mm_per_unit("knob-witchhat")


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


def _mix_rgb(nt, fac, a, b):
    node = nt.nodes.new("ShaderNodeMix")
    node.data_type = "RGBA"
    _feed(nt, _sock(node, "Factor_Float"), fac)
    _feed(nt, _sock(node, "A_Color"), a)
    _feed(nt, _sock(node, "B_Color"), b)
    return _sock(node, "Result_Color", outputs=True)


def _mix_float(nt, fac, a, b):
    node = nt.nodes.new("ShaderNodeMix")
    node.data_type = "FLOAT"
    _feed(nt, _sock(node, "Factor_Float"), fac)
    _feed(nt, _sock(node, "A_Float"), a)
    _feed(nt, _sock(node, "B_Float"), b)
    return _sock(node, "Result_Float", outputs=True)


def _noise(nt, vec, scale, detail=3.0, rough=0.55):
    node = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(vec, node.inputs["Vector"])
    node.inputs["Scale"].default_value = scale
    node.inputs["Detail"].default_value = detail
    node.inputs["Roughness"].default_value = rough
    return node.outputs["Fac"]


def _polar(nt):
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Object"], sep.inputs["Vector"])
    x, y, z = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]
    r = _m(nt, "SQRT", _m(nt, "ADD", _m(nt, "MULTIPLY", x, x), _m(nt, "MULTIPLY", y, y)))
    th = _m(nt, "ARCTAN2", y, x)
    return coord.outputs["Object"], r, th, z


def _image(image):
    if not isinstance(image, str):
        return image
    img = bpy.data.images.get(image)
    if img is None:
        img = bpy.data.images.new(image, 1, 1, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
    return img


_AGED = dict(family="plastic", finish="satin", solid=False, calib_mm_per_unit=WITCHHAT_MM,
             origin="knob-witchhat:aged_plastic_material:518",
             part_bound={"radius": "outer_radius"})


@material("aged-plastic", **_AGED)
@material("aged-plastic-black", params={
    "body_a": (0.010, 0.0095, 0.009), "body_b": (0.013, 0.011, 0.009),
    "grime": (0.060, 0.054, 0.046), "grime_gain": 0.40, "tide": (0.045, 0.042, 0.037),
    "tide_gain": 0.35, "polish": (0.006, 0.006, 0.006), "rough_lo": 0.30, "rough_hi": 0.44,
    "polish_rough": 0.16, "coat": 0.55, "coat_rough": 0.24, "sss": 0.0,
    "name": "aged black plastic"}, **_AGED)
def mat_aged_plastic(body_a=(0.80, 0.585, 0.165), body_b=(0.66, 0.455, 0.095),
                     grime=(0.060, 0.036, 0.024), grime_gain=1.0, tide=(0.30, 0.19, 0.075),
                     tide_gain=0.75, polish=(0.86, 0.68, 0.28), rough_lo=0.36, rough_hi=0.50,
                     polish_rough=0.22, coat=0.45, coat_rough=0.30, sss=0.10,
                     halo_image="numeral grime halo", radius=0.55, flutes=80,
                     flute_width=0.38, junction_r=0.530, grime_r_lo=0.58, grime_r_hi=0.93,
                     name="aged cream plastic", *, ctx=DEFAULT_CTX):
    """Aged satin plastic on a fluted witch-hat knob (skirt + cap): uneven
    yellowing between `body_a` and `body_b` (stronger on up-facing surfaces),
    grime packed into the flute grooves, the cap/skirt step and occluded
    corners (AO, distance 0.035 x radius), dirt tidemarks along stamped
    numerals, and hand polish on the rim roll, top lip and flute ridges
    (lighter toward `polish`, roughness toward `polish_rough`).

    The wear masks are keyed to the part's own geometry in Object space, all
    component-supplied and not scaled by ctx: a body of revolution about local
    Z with `radius`, `flutes` grooves each `flute_width` of a pitch, the cap
    meeting the skirt at `junction_r` x radius, and the zone fractions of
    radius built into the masks (cap edge 0.545-0.56, cap floor 0.30-0.33,
    lip 0.43-0.46, top 0.985-0.995, rim 0.962-0.995).

    `halo_image` is the numeral-footprint map: an Image, or the name of one,
    sampled at (theta / 2pi + 0.5, (r - grime_r_lo R) / ((grime_r_hi -
    grime_r_lo) R)); red is the blurred edge halo. A name with no image makes a
    black 1x1 placeholder (no tidemark).

    Colourways: cream (default) and black; knob-witchhat's gold colourway
    builds the black graph. `sss` > 0 adds scatter (radius 1.0/0.72/0.38,
    scale 0.006)."""
    R = radius
    m, nt, b = base_material(name)
    obj, r, th, z = _polar(nt)
    imperfect(m, rough_lo, rough_hi, bump_strength=0.012, scale=145.0, ctx=ctx)
    mottled = b.inputs["Roughness"].links[0].from_socket

    u = _m(nt, "ADD", _m(nt, "DIVIDE", th, 2 * math.pi), 0.5)
    v = _m(nt, "DIVIDE", _m(nt, "SUBTRACT", r, grime_r_lo * R), (grime_r_hi - grime_r_lo) * R)
    uv = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(u, uv.inputs["X"])
    nt.links.new(v, uv.inputs["Y"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = _image(halo_image)
    tex.extension = "CLIP"
    tex.interpolation = "Cubic"
    nt.links.new(uv.outputs["Vector"], tex.inputs["Vector"])
    rgb = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tex.outputs["Color"], rgb.inputs["Color"])
    halo = rgb.outputs["Red"]

    on_cap = _m(nt, "MULTIPLY", _remap(nt, r, 0.545 * R, 0.56 * R, 1.0, 0.0),
                _remap(nt, z, 0.30 * R, 0.33 * R))
    phase = _m(nt, "FRACT", _m(nt, "MULTIPLY", th, flutes / (2 * math.pi)))
    dist = _m(nt, "ABSOLUTE", _m(nt, "SUBTRACT", phase, 0.5))
    groove_m = _remap(nt, dist, 0.0, 0.5 * flute_width, 1.0, 0.0)
    groove_low = _m(nt, "MULTIPLY", groove_m, _remap(nt, z, 0.35 * R, 0.98 * R, 1.0, 0.35))
    lip_fade = _remap(nt, r, 0.43 * R, 0.46 * R, 0.0, 1.0)
    cap_top = _remap(nt, z, 0.985 * R, 0.995 * R)
    groove_grime = _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", groove_low, on_cap),
                      _m(nt, "SUBTRACT", 1.0,
                         _m(nt, "MULTIPLY", cap_top, _m(nt, "SUBTRACT", 1.0, lip_fade))))

    step = _m(nt, "MULTIPLY", _remap(nt, r, junction_r * R, (junction_r + 0.075) * R, 1.0, 0.0),
              _remap(nt, z, 0.31 * R, 0.42 * R, 1.0, 0.0))
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.only_local = True
    ao.samples = 8
    ao.inputs["Distance"].default_value = ctx.length(0.035 * R)
    occl = _m(nt, "SUBTRACT", 1.0, ao.outputs["AO"])

    dirt_var = _remap(nt, _noise(nt, obj, ctx.freq(7.0), 4.0, 0.6), 0.35, 0.70, 0.45, 1.15,
                      smooth_step=False)
    speck = _remap(nt, _noise(nt, obj, ctx.freq(260.0), 2.0, 0.5), 0.62, 0.75, 0.0, 0.35)
    grime_f = _m(nt, "MULTIPLY", step, 1.1)
    grime_f = _m(nt, "ADD", grime_f, _m(nt, "MULTIPLY", groove_grime, 0.75))
    grime_f = _m(nt, "ADD", grime_f, _m(nt, "MULTIPLY", occl, 0.55))
    grime_f = _m(nt, "MULTIPLY", grime_f, dirt_var)
    grime_f = _m(nt, "ADD", grime_f, speck)
    grime_f = _m(nt, "MINIMUM", _m(nt, "MULTIPLY", grime_f, grime_gain), 0.88)

    rim = _remap(nt, r, 0.962 * R, 0.995 * R)
    ridges = _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", on_cap, _m(nt, "SUBTRACT", 1.0, groove_m)),
                _remap(nt, z, 0.45 * R, 0.98 * R, 0.15, 0.55))
    polish_f = _m(nt, "MAXIMUM", _m(nt, "MAXIMUM", rim, _m(nt, "MULTIPLY", cap_top, 0.9)), ridges)
    polish_f = _m(nt, "MULTIPLY", polish_f,
                  _remap(nt, _noise(nt, obj, ctx.freq(22.0), 3.0, 0.6), 0.35, 0.65, 0.55, 1.0,
                         smooth_step=False))

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    nsep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], nsep.inputs["Vector"])
    age = _m(nt, "ADD", _m(nt, "MULTIPLY", _noise(nt, obj, ctx.freq(3.2), 3.0, 0.5), 0.9),
             _m(nt, "MULTIPLY", nsep.outputs["Z"], 0.25))
    age = _remap(nt, age, 0.45, 1.05)
    col = _mix_rgb(nt, age, (*body_a, 1), (*body_b, 1))
    col = _mix_rgb(nt, _m(nt, "MULTIPLY", polish_f, 0.55), col, (*polish, 1))
    col = _mix_rgb(nt, grime_f, col, (*grime, 1))
    tide_f = _m(nt, "MINIMUM", _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", halo, dirt_var), tide_gain),
                0.8)
    col = _mix_rgb(nt, tide_f, col, (*tide, 1))
    nt.links.new(col, b.inputs["Base Color"])

    rough = _mix_float(nt, polish_f, mottled, polish_rough)
    rough_v = _m(nt, "ADD", rough, _m(nt, "MULTIPLY", grime_f, 0.30))
    rough_v = _m(nt, "ADD", rough_v,
                 _remap(nt, _noise(nt, obj, ctx.freq(4.5), 2.0, 0.5), 0.35, 0.65, -0.09, 0.07))
    nt.links.new(rough_v, b.inputs["Roughness"])

    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = coat_rough
    if sss > 0:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.72, 0.38)
        b.inputs["Subsurface Scale"].default_value = ctx.length(0.006)
    return m
