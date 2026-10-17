"""Metal family, conversion coats and lacquers: black oxide and blackened
metal, black chrome under a clear coat, bead-blast anodise, and lacquered
metal. The coat is the look; the substrate only shows through as metallic
response.

Calibration per origin component: units.MM_PER_UNIT.
"""
import bpy

from .core import DEFAULT_CTX, base_material, imperfect, material
from .metals_raw import TOGGLE_MM, imperfect_metal_at, mat_plain_metal, rebase
from .units import mm_per_unit

BEZEL_MM = mm_per_unit("button-bezel")
RADIO_MM = mm_per_unit("button-radio")
JACK_MM = mm_per_unit("jack-socket")
VU_MM = mm_per_unit("meter-vu")
HIFI_MM = mm_per_unit("knob-hifi")

_COAT = dict(family="metal", solid=False)

material("steel-blackened-bead-blast", finish="satin",
         params={"color": (0.026, 0.030, 0.036), "rough_lo": 0.42, "rough_hi": 0.58,
                 "bump_strength": 0.022, "grain": 192.0, "anisotropic": 0.30,
                 "name": "bead blasted blackened metal"},
         calib_mm_per_unit=BEZEL_MM, origin="button-bezel:bead blasted blackened metal:213",
         **_COAT)(imperfect_metal_at(BEZEL_MM))
material("black-chrome-coated", finish="satin",
         params={"color": (0.014, 0.018, 0.021), "rough_lo": 0.28, "rough_hi": 0.42,
                 "bump_strength": 0.018, "grain": 798.0, "metallic": 0.16, "coat": 0.22,
                 "name": "modern_ring_black"},
         calib_mm_per_unit=RADIO_MM, origin="button-radio:modern_ring_black:131",
         **_COAT)(imperfect_metal_at(RADIO_MM))
material("brass-blackened", finish="satin",
         params={"color": (0.050, 0.046, 0.041), "rough_lo": 0.52, "rough_hi": 0.72,
                 "bump_strength": 0.03, "grain": 1110.0, "name": "bore_dark"},
         calib_mm_per_unit=JACK_MM, origin="jack-socket:mat_bore_dark:214",
         **_COAT)(imperfect_metal_at(JACK_MM))
material("steel-black-oxide", finish="satin",
         params={"color": (0.040, 0.040, 0.046), "roughness": 0.45, "name": "washerm"},
         calib_mm_per_unit=TOGGLE_MM, origin="toggle-bat:washerm:96", **_COAT)(mat_plain_metal)


# ---------------------------------------------------------------------------
# lacquered metal (meter-vu needle and hub)

_LACQUER = dict(finish="satin", calib_mm_per_unit=VU_MM,
                origin="meter-vu:mat_lacquer:479", **_COAT)


@material("lacquered-metal-black", **_LACQUER)
@material("lacquered-metal-cream", params={"col": (0.80, 0.79, 0.75)}, **_LACQUER)
@material("lacquered-metal-graphite", params={"col": (0.020, 0.020, 0.023), "rough": 0.38},
          **_LACQUER)
def mat_lacquered_metal(col=(0.014, 0.014, 0.016), rough=0.32, coat=0.25, spec=None,
                        name="vu_lacquer", *, ctx=DEFAULT_CTX):
    """Semi-gloss lacquer over thin metal stock (a needle blade, a hub cover):
    dielectric `col` under a clear coat of weight `coat` (coat roughness 0.12),
    imperfect() roughness rough - 0.04 .. rough + 0.10. `spec` sets Specular IOR
    Level when given; a near-black blade over a lit face needs it low (0.13 with
    rough 0.58, coat 0) or its flat top returns the key as mid grey.
    The form reads from a chamfer on the geometry, not from the material."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.12
    if spec is not None:
        b.inputs["Specular IOR Level"].default_value = spec
    imperfect(m, rough - 0.04, rough + 0.10, bump_strength=0.012, scale=1250.0,
              ctx=rebase(ctx, VU_MM))
    return m


# ---------------------------------------------------------------------------
# bead-blast anodise (knob-hifi)


def _math(nt, op, a, b=None):
    node = nt.nodes.new("ShaderNodeMath")
    node.operation = op
    for idx, val in enumerate((a, b)):
        if val is None:
            continue
        if isinstance(val, (int, float)):
            node.inputs[idx].default_value = val
        else:
            nt.links.new(val, node.inputs[idx])
    return node.outputs[0]


def _noise(nt, scale, detail=3.0, roughness=0.55, vector=None):
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = detail
    tex.inputs["Roughness"].default_value = roughness
    if vector is not None:
        nt.links.new(vector, tex.inputs["Vector"])
    return tex.outputs["Fac"]


def _map_range(nt, value, lo, hi, from_lo=0.0, from_hi=1.0):
    node = nt.nodes.new("ShaderNodeMapRange")
    node.inputs["From Min"].default_value = from_lo
    node.inputs["From Max"].default_value = from_hi
    node.inputs["To Min"].default_value = lo
    node.inputs["To Max"].default_value = hi
    nt.links.new(value, node.inputs["Value"])
    return node.outputs["Result"]


def tint(nt, colour, fac, spread):
    """Base colour times a mottle factor in [1 - spread, 1 + spread]."""
    scale = _map_range(nt, fac, 1.0 - spread, 1.0 + spread, 0.3, 0.7)
    rgb = nt.nodes.new("ShaderNodeRGB")
    rgb.outputs[0].default_value = (*colour, 1.0)
    mul = nt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "SCALE"
    nt.links.new(rgb.outputs[0], mul.inputs[0])
    nt.links.new(scale, mul.inputs["Scale"])
    return mul.outputs["Vector"]


HIFI_BODY = {
    "silver": (0.17, 0.172, 0.175),
    "black": (0.0065, 0.0065, 0.0072),
    "champagne": (0.27, 0.175, 0.075),
    "blue": (0.012, 0.016, 0.150),
}
_BLAST = dict(finish="matte", calib_mm_per_unit=HIFI_MM,
              origin="knob-hifi:blasted_anodise:332", **_COAT)


@material("aluminium-bead-blast-anodized-silver", **_BLAST)
@material("aluminium-bead-blast-anodized-black", params={"colour": HIFI_BODY["black"]}, **_BLAST)
@material("aluminium-bead-blast-anodized-champagne", params={"colour": HIFI_BODY["champagne"]},
          **_BLAST)
@material("aluminium-bead-blast-anodized-blue", params={"colour": HIFI_BODY["blue"]}, **_BLAST)
def mat_bead_blast_anodized(colour=HIFI_BODY["silver"], rough=0.58, grain=1.0, metallic=0.6,
                            glints=0.06, name="bead-blasted anodise", *, ctx=DEFAULT_CTX):
    """Bead-blast under anodise: even matte metal built from overlapping shot
    dimples, drawn a few pixels wide at knob size (Object-coordinate F1 Voronoi
    at 190 x `grain`, its distance a concave bump). Each cell carries its own
    small colour (+-4%) and roughness (rough +-0.04) offset, a `glints` share of
    cells are flatter and brighter, and a broad noise drifts roughness +-3%.
    `metallic` < 1 keeps the oxide's diffuse share. Knurled stock takes
    rough 0.34, grain 1.6, metallic 0.78; a blasted top face rough 0.40,
    metallic 0.85."""
    mat, nt, bsdf = base_material(name)
    bsdf.inputs["Metallic"].default_value = metallic
    coord = nt.nodes.new("ShaderNodeTexCoord")
    shot = nt.nodes.new("ShaderNodeTexVoronoi")
    shot.feature = "F1"
    shot.inputs["Scale"].default_value = ctx.freq(190.0 * grain, HIFI_MM)
    shot.inputs["Randomness"].default_value = 1.0
    nt.links.new(coord.outputs["Object"], shot.inputs["Vector"])
    cell = _math(nt, "MULTIPLY", shot.outputs["Color"], 1.0)
    split = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(shot.outputs["Color"], split.inputs["Color"])
    glint = _math(nt, "GREATER_THAN", split.outputs["Red"], 1.0 - glints)
    broad = _noise(nt, ctx.freq(14.0, HIFI_MM), detail=2.0, vector=coord.outputs["Object"])
    base = tint(nt, colour, cell, 0.04)
    lift = nt.nodes.new("ShaderNodeVectorMath")
    lift.operation = "SCALE"
    nt.links.new(base, lift.inputs[0])
    nt.links.new(_math(nt, "ADD", _math(nt, "MULTIPLY", glint, 0.40), 1.0),
                 lift.inputs["Scale"])
    nt.links.new(lift.outputs["Vector"], bsdf.inputs["Base Color"])
    rough_cell = _map_range(nt, cell, rough - 0.04, rough + 0.04, 0.3, 0.7)
    rough_all = _math(nt, "SUBTRACT", _math(
        nt, "MULTIPLY", rough_cell, _map_range(nt, broad, 0.97, 1.03, 0.3, 0.7)),
        _math(nt, "MULTIPLY", glint, 0.07))
    nt.links.new(rough_all, bsdf.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = ctx.length(0.0006, HIFI_MM)
    nt.links.new(shot.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat
