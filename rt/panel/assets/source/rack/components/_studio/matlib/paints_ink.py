"""Paint family, inks and fills: printed and stamped legends, engraving and
inlay fills, and printed scale cards.

`imperfect()` routes through the core calibration (25 mm/unit); builders hand
it `_imperfect_ctx(ctx, calib)`, which equals `ctx` exactly when `ctx` is at
`calib`.

Calibration per origin component: units.MM_PER_UNIT.
"""
import bpy

from .core import CALIB_MM_PER_UNIT, DEFAULT_CTX, MaterialContext, base_material, imperfect, material
from .nodes import sock
from .units import mm_per_unit

CAL_WITCHHAT = mm_per_unit("knob-witchhat")
CAL_DAVIES = mm_per_unit("knob-davies")
CAL_HIFI = mm_per_unit("knob-hifi")
CAL_BEZEL = mm_per_unit("button-bezel")
CAL_RADIO = mm_per_unit("button-radio")
CAL_FADER = mm_per_unit("fader-desk")
CAL_VU = mm_per_unit("meter-vu")


def _imperfect_ctx(ctx, calib):
    """The context `imperfect()` (calibrated at 25) needs so its constants
    behave as if calibrated at `calib`."""
    if calib == CALIB_MM_PER_UNIT:
        return ctx
    return MaterialContext(CALIB_MM_PER_UNIT * (ctx.mm_per_unit / calib))


# ---------------------------------------------------------------------------
# printed legends


@material("ink-screen-print", family="paint", finish="matte", solid=False,
          calib_mm_per_unit=CAL_BEZEL,
          origin="button-bezel:screen printed label paint:246")
def mat_ink_screen_print(color=(237 / 255, 240 / 255, 238 / 255),
                         name="screen printed label paint", *, ctx=DEFAULT_CTX):
    """Flush, rough screen-printed label paint. `color` is the nominal legend
    colour; the ink lays down at half of it (a thin, rough print never reaches
    its nominal value)."""
    paint = tuple(0.50 * c for c in color)
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*paint, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.72
    b.inputs["Specular IOR Level"].default_value = 0.18
    b.inputs["Coat Weight"].default_value = 0.0
    imperfect(m, 0.64, 0.78, bump_strength=0.006, scale=1090.0,
              ctx=_imperfect_ctx(ctx, CAL_BEZEL))
    return m


@material("ink-flat", family="paint", finish="matte", solid=False,
          calib_mm_per_unit=CAL_RADIO, origin="button-radio:plate_ink:157")
def mat_ink_flat(color=(0.70, 0.73, 0.72), roughness=0.72, name="plate_ink", *,
                 ctx=DEFAULT_CTX):
    """Untextured light label ink at constant roughness, for plate annotations.

    Duplicate candidate: inlay-fill, engraving-fill-flat-light."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = roughness
    return m


# Printed scale ticks and numerals beside a fader slot.
# Duplicate candidate: ink-flat, inlay-fill.
material("ink-legend-grey", family="paint", finish="satin", solid=False,
         params={"color": (0.60, 0.61, 0.63), "roughness": 0.42, "name": "paint"},
         calib_mm_per_unit=CAL_FADER, origin="fader-desk:paint:371")(mat_ink_flat)


_STAMPED = dict(family="paint", finish="satin", solid=False, calib_mm_per_unit=CAL_WITCHHAT,
                origin="knob-witchhat:{color} stamped numeral fill:607")
_BODY_DARK = (0.013, 0.011, 0.009)


@material("ink-stamped", **_STAMPED)
@material("ink-stamped-light", params={
    "ink": (0.70, 0.67, 0.58), "rough": (0.40, 0.55), "substrate": _BODY_DARK,
    "name": "black stamped numeral fill"}, **_STAMPED)
@material("ink-stamped-gold", params={
    "ink": (0.74, 0.45, 0.11), "metallic": 0.55, "substrate": _BODY_DARK,
    "name": "gold stamped numeral fill"}, **_STAMPED)
def mat_ink_stamped(ink=(0.014, 0.011, 0.009), metallic=0.0, rough=(0.36, 0.50),
                    substrate=(0.66, 0.455, 0.095), name="cream stamped numeral fill", *,
                    ctx=DEFAULT_CTX):
    """Ink filling stamped glyphs, worn through to `substrate` (the moulding's
    colour) in object-space patches. Built for glyph geometry that owns this
    material; the wear lookup is Object coordinates, so it rides the part."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = metallic
    imperfect(m, rough[0], rough[1], bump_strength=0.02, scale=247.0,
              ctx=_imperfect_ctx(ctx, CAL_WITCHHAT))
    coord = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    noise.inputs["Scale"].default_value = ctx.freq(55.0, CAL_WITCHHAT)
    noise.inputs["Detail"].default_value = 4.0
    noise.inputs["Roughness"].default_value = 0.62
    wear = nt.nodes.new("ShaderNodeMapRange")
    wear.interpolation_type = "SMOOTHSTEP"
    nt.links.new(noise.outputs["Fac"], wear.inputs["Value"])
    wear.inputs["From Min"].default_value = 0.66
    wear.inputs["From Max"].default_value = 0.74
    wear.inputs["To Min"].default_value = 0.0
    wear.inputs["To Max"].default_value = 0.55
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(wear.outputs["Result"], sock(mix, "Factor_Float"))
    sock(mix, "A_Color").default_value = (*ink, 1)
    sock(mix, "B_Color").default_value = (*substrate, 1)
    nt.links.new(sock(mix, "Result_Color"), b.inputs["Base Color"])
    return m


# ---------------------------------------------------------------------------
# engraving and inlay fills

_ENGRAVE = dict(family="paint", solid=False, calib_mm_per_unit=CAL_DAVIES,
                origin="knob-davies:paint_fill:347")


@material("engraving-fill", finish="matte", **_ENGRAVE)
@material("engraving-fill-neutral", finish="matte",
          params={"color": (0.008, 0.008, 0.009)}, **_ENGRAVE)
@material("engraving-fill-white", finish="satin",
          params={"color": (0.78, 0.78, 0.76), "rough": (0.40, 0.55)}, **_ENGRAVE)
def mat_engraving_fill(color=(0.011, 0.0075, 0.0045), rough=(0.48, 0.64),
                       name="engraving fill", *, ctx=DEFAULT_CTX):
    """Paint filling an engraved slot: low specular, fine roughness mottle and
    micro-bump. Presets: warm near-black (`engraving-fill`), neutral near-black
    (`-neutral`), off-white (`-white`).

    Duplicate candidate: engraving-fill-flat."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Specular IOR Level"].default_value = 0.12
    imperfect(m, rough[0], rough[1], bump_strength=0.02, scale=5460.0,
              ctx=_imperfect_ctx(ctx, CAL_DAVIES))
    return m


_ENGRAVE_FLAT = dict(family="paint", finish="matte", solid=False, calib_mm_per_unit=CAL_HIFI,
                     origin="knob-hifi:indicator fill:422")


@material("engraving-fill-flat", **_ENGRAVE_FLAT)
@material("engraving-fill-flat-light", params={"color": (0.80, 0.80, 0.78)}, **_ENGRAVE_FLAT)
def mat_engraving_fill_flat(color=(0.0012, 0.0012, 0.0014), name="indicator fill", *,
                            ctx=DEFAULT_CTX):
    """Untextured paint filling an engraved slot: constant roughness 0.55, low
    specular, no bump.

    Duplicate candidate: engraving-fill."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Specular IOR Level"].default_value = 0.12
    return m


_INLAY = dict(family="paint", finish="matte", solid=False, calib_mm_per_unit=CAL_FADER,
              origin="fader-desk:strip_material:286")


@material("inlay-fill", **_INLAY)
@material("inlay-fill-dark", params={"color": (0.004, 0.004, 0.0045), "roughness": 0.72},
          **_INLAY)
def mat_inlay_fill(color=(0.42, 0.40, 0.345), roughness=0.60, name="strip", *,
                   ctx=DEFAULT_CTX):
    """Untextured matte fill for an inset strip at default specular: aged cream
    (`inlay-fill`) or near-black (`inlay-fill-dark`).

    Duplicate candidate: ink-flat, paint-flat-dark."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = roughness
    return m


# ---------------------------------------------------------------------------
# printed scale card

_CARD = dict(family="paint", finish="matte", solid=False, calib_mm_per_unit=CAL_VU,
             origin="meter-vu:mat_face:402")


@material("print-card", **_CARD)
@material("print-card-reversed", params={"ink_dark": False}, **_CARD)
@material("print-film-backlit", params={"backlit": True}, **_CARD)
def mat_print_card(image=None, ink_dark=True, backlit=False, albedo=0.085, specular=0.12,
                   level=0.32, name="vu_face", *, ctx=DEFAULT_CTX):
    """A printed card whose print is a component-supplied raster.

    `image`: a bpy Image, the name of a loaded image, or a file path (loaded);
    None leaves the Image Texture empty. It is sampled on Generated
    coordinates with cubic interpolation and extended edges, so the card's
    bounding box is the print's extent (the library's one bounding-box lookup,
    selftest IMAGE_FIT_KEYS); the paper's mottle, warp and grain are Object
    coordinates.

    `ink_dark`: True when the ink is darker than the stock (print-card); False
    for light ink on a dark card (print-card-reversed). It sets which way the
    print's luminance drives roughness, and the non-backlit specular and coat.

    `backlit`: light-through-film (print-film-backlit). The print drives
    Emission Color at `level`, the albedo is the print scaled by `albedo`, and
    specular is `specular` with no coat. `albedo`, `specular`, `level` are
    ignored when not backlit."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    if isinstance(image, str):
        image = bpy.data.images.get(image) or bpy.data.images.load(image)
    if image is not None:
        tex.image = image
    tex.interpolation = "Cubic"
    tex.extension = "EXTEND"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["Generated"], tex.inputs["Vector"])
    if backlit:
        nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = level
        dim = nt.nodes.new("ShaderNodeVectorMath")
        dim.operation = "SCALE"
        dim.inputs["Scale"].default_value = albedo
        nt.links.new(tex.outputs["Color"], dim.inputs[0])
        nt.links.new(dim.outputs["Vector"], b.inputs["Base Color"])
    else:
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = (
        specular if backlit else (0.30 if ink_dark else 0.20))
    b.inputs["Coat Weight"].default_value = 0.0 if backlit else (0.05 if ink_dark else 0.0)
    b.inputs["Coat Roughness"].default_value = 0.35
    lum = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(tex.outputs["Color"], lum.inputs["Color"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.05
    mr.inputs["From Max"].default_value = 0.55
    mr.inputs["To Min"].default_value = 0.47 if ink_dark else 0.68
    mr.inputs["To Max"].default_value = 0.63 if ink_dark else 0.56
    nt.links.new(lum.outputs["Val"], mr.inputs["Value"])
    mot = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(tc.outputs["Object"], mot.inputs["Vector"])
    mot.inputs["Scale"].default_value = ctx.freq(41.9, CAL_VU)
    mmr = nt.nodes.new("ShaderNodeMapRange")
    mmr.inputs["To Min"].default_value = -0.05
    mmr.inputs["To Max"].default_value = 0.05
    nt.links.new(mot.outputs["Fac"], mmr.inputs["Value"])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation, add.use_clamp = "ADD", True
    nt.links.new(mr.outputs["Result"], add.inputs[0])
    nt.links.new(mmr.outputs["Result"], add.inputs[1])
    nt.links.new(add.outputs["Value"], b.inputs["Roughness"])
    warp = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(tc.outputs["Object"], warp.inputs["Vector"])
    warp.inputs["Scale"].default_value = ctx.freq(1.86, CAL_VU)
    wb = nt.nodes.new("ShaderNodeBump")
    wb.inputs["Strength"].default_value = 0.03
    wb.inputs["Distance"].default_value = ctx.length(0.01, CAL_VU)
    nt.links.new(warp.outputs["Fac"], wb.inputs["Height"])
    grain = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(tc.outputs["Object"], grain.inputs["Vector"])
    grain.inputs["Scale"].default_value = ctx.freq(288.0, CAL_VU)
    grain.inputs["Detail"].default_value = 3.0
    gb = nt.nodes.new("ShaderNodeBump")
    gb.inputs["Strength"].default_value = 0.035
    gb.inputs["Distance"].default_value = ctx.length(0.0008, CAL_VU)
    nt.links.new(grain.outputs["Fac"], gb.inputs["Height"])
    nt.links.new(wb.outputs["Normal"], gb.inputs["Normal"])
    nt.links.new(gb.outputs["Normal"], b.inputs["Normal"])
    return m
