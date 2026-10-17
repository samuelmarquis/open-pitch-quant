"""Paint family, coatings: painted, powder-coated and enamelled surfaces, dark
matte interior coatings, and flat utility cards.

`imperfect()` routes through the core calibration (25 mm/unit); builders hand
it `_imperfect_ctx(ctx, calib)`, which equals `ctx` exactly when `ctx` is at
`calib`.

Calibration per origin component: units.MM_PER_UNIT.
"""
import bpy

from .core import (CALIB_MM_PER_UNIT, DEFAULT_CTX, MaterialContext, _obj_pos, base_material,
                   imperfect, material, sheen)
from .units import mm_per_unit

CAL_RACK = mm_per_unit("rack-hardware")
CAL_VENT = mm_per_unit("vent-grille")
CAL_NIXIE = mm_per_unit("display-nixie")
CAL_HANDWHEEL = mm_per_unit("knob-handwheel")
CAL_RING = mm_per_unit("knob-ring")
CAL_RIBBON = mm_per_unit("conduit-ribbon")
CAL_SMOOTH = mm_per_unit("conduit-smooth")
CAL_CONSOLE = mm_per_unit("button-console")
CAL_FADER = mm_per_unit("fader-desk")
CAL_RADIO = mm_per_unit("button-radio")
CAL_SCREEN = mm_per_unit("screen-monitor")


def _imperfect_ctx(ctx, calib):
    """The context `imperfect()` (calibrated at 25) needs so its constants
    behave as if calibrated at `calib`."""
    if calib == CALIB_MM_PER_UNIT:
        return ctx
    return MaterialContext(CALIB_MM_PER_UNIT * (ctx.mm_per_unit / calib))


def _bump_chain(nt, b, layers, ctx, calib):
    """Stacked Bump nodes (never Mix), linked into the BSDF Normal. Each layer is
    (scale, strength, distance, detail, kind); kind "noise" or Smooth-F1
    Voronoi otherwise. Scales are Object-coordinate frequencies."""
    prev = None
    pos = _obj_pos(nt)
    for scale, strength, dist, detail, kind in layers:
        if kind == "noise":
            n = nt.nodes.new("ShaderNodeTexNoise")
            n.inputs["Scale"].default_value = ctx.freq(scale, calib)
            n.inputs["Detail"].default_value = detail
            src = n.outputs["Fac"]
        else:
            n = nt.nodes.new("ShaderNodeTexVoronoi")
            n.feature = "SMOOTH_F1"
            n.inputs["Scale"].default_value = ctx.freq(scale, calib)
            src = n.outputs["Distance"]
        nt.links.new(pos, n.inputs["Vector"])
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = strength
        bmp.inputs["Distance"].default_value = ctx.length(dist, calib)
        nt.links.new(src, bmp.inputs["Height"])
        if prev is not None:
            nt.links.new(prev.outputs["Normal"], bmp.inputs["Normal"])
        prev = bmp
    nt.links.new(prev.outputs["Normal"], b.inputs["Normal"])


# ---------------------------------------------------------------------------
# rack-hardware finishes


@material("powder-coat", family="paint", finish="satin", solid=False,
          calib_mm_per_unit=CAL_RACK, origin="rack-hardware:mat_powder_black:205")
def mat_powder_coat(color=(0.009, 0.009, 0.010), name="powder_black", *, ctx=DEFAULT_CTX):
    """Powder coat: a thicker film than sprayed panel paint, so a coarser
    orange-peel and a little more sheen, rounding every arris.

    Duplicate candidate: paint-satin-black (same graph shape, other constants)."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.44
    _bump_chain(nt, b, [(32.6, 0.10, 0.012, 2.0, "noise"),
                        (170.0, 0.05, 0.003, 3.0, "noise")], ctx, CAL_RACK)
    imperfect(m, 0.38, 0.54, bump_strength=0.018, scale=142.0,
              ctx=_imperfect_ctx(ctx, CAL_RACK))
    return m


@material("paint-satin-black", family="paint", finish="satin", solid=False,
          calib_mm_per_unit=CAL_RACK, params={"sheen_k": 0.25},
          origin="rack-hardware:mat_rack_black:219")
def mat_paint_satin_black(color=(0.0055, 0.0052, 0.0055), name="rack_black", sheen_k=1.0, *,
                          ctx=DEFAULT_CTX):
    """Sprayed satin black for brackets: slightly warmer and glossier than the
    panel's `black-paint`, with a two-octave orange-peel. Deliberately a
    different paint from `black-paint` (two parts, two shops).

    Duplicate candidate: black-paint, powder-coat."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.36
    sheen(b, sheen_k)
    _bump_chain(nt, b, [(27.5, 0.07, 0.007, 2.0, "noise"),
                        (131.0, 0.035, 0.002, 3.0, "noise")], ctx, CAL_RACK)
    imperfect(m, 0.44, 0.60, bump_strength=0.016, scale=89.4,
              ctx=_imperfect_ctx(ctx, CAL_RACK))
    return m


# charcoal: dark, but its crinkle reads off a black ground (open-conv's crystal
# plate, p177)
@material("enamel-wrinkle-charcoal", family="paint", finish="matte", solid=False,
          calib_mm_per_unit=CAL_RACK, params={"color": (0.022, 0.022, 0.024),
                                              "name": "wrinkle_charcoal"},
          origin="rack-hardware:mat_wrinkle_black:233")
@material("enamel-wrinkle", family="paint", finish="matte", solid=False,
          calib_mm_per_unit=CAL_RACK, origin="rack-hardware:mat_wrinkle_black:233")
def mat_enamel_wrinkle(color=(0.011, 0.010, 0.010), name="wrinkle_black", *,
                       ctx=DEFAULT_CTX):
    """Wrinkle (crinkle) enamel: ~3 mm cells at the calibration unit. The
    relief is the material — it needs raking light to read."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.30
    pos = _obj_pos(nt)
    wr = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, wr.inputs["Vector"])
    wr.inputs["Scale"].default_value = ctx.freq(16.9, CAL_RACK)
    wr.inputs["Detail"].default_value = 5.0
    wr.inputs["Roughness"].default_value = 0.78
    b1 = nt.nodes.new("ShaderNodeBump")
    b1.inputs["Strength"].default_value = 1.0
    b1.inputs["Distance"].default_value = ctx.length(0.055, CAL_RACK)
    nt.links.new(wr.outputs["Fac"], b1.inputs["Height"])
    vo = nt.nodes.new("ShaderNodeTexVoronoi")
    vo.feature = "SMOOTH_F1"
    nt.links.new(pos, vo.inputs["Vector"])
    vo.inputs["Scale"].default_value = ctx.freq(8.47, CAL_RACK)
    b2 = nt.nodes.new("ShaderNodeBump")
    b2.inputs["Strength"].default_value = 0.55
    b2.inputs["Distance"].default_value = ctx.length(0.040, CAL_RACK)
    nt.links.new(vo.outputs["Distance"], b2.inputs["Height"])
    nt.links.new(b1.outputs["Normal"], b2.inputs["Normal"])
    nt.links.new(b2.outputs["Normal"], b.inputs["Normal"])
    imperfect(m, 0.58, 0.76, bump_strength=0.02, scale=162.0,
              ctx=_imperfect_ctx(ctx, CAL_RACK))
    return m


# ---------------------------------------------------------------------------
# enamel over a casting

_ENAMEL = dict(family="paint", finish="gloss", solid=False, calib_mm_per_unit=CAL_HANDWHEEL,
               origin="knob-handwheel:enamel:326")


@material("enamel-cast", **_ENAMEL)
@material("enamel-cast-green", params={"color": (0.006, 0.082, 0.030)}, **_ENAMEL)
@material("enamel-cast-black", params={"color": (0.015, 0.015, 0.017)}, **_ENAMEL)
def mat_enamel_cast(color=(0.32, 0.015, 0.012), name="enamel", *, ctx=DEFAULT_CTX):
    """Coated gloss enamel over a sand casting: roughness mottle plus a
    low-frequency lumpy bump for the cast unevenness under the paint.

    The cast bump REPLACES the micro-bump `imperfect()` links into Normal: those
    two nodes stay in the tree unlinked, and only its roughness mottle reaches
    the BSDF."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    imperfect(m, 0.14, 0.33, bump_strength=0.02, scale=97.2,
              ctx=_imperfect_ctx(ctx, CAL_HANDWHEEL))
    b.inputs["Coat Weight"].default_value = 0.45
    noise = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), noise.inputs["Vector"])
    noise.inputs["Scale"].default_value = ctx.freq(29.2, CAL_HANDWHEEL)
    noise.inputs["Detail"].default_value = 4.0
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.05
    bmp.inputs["Distance"].default_value = ctx.length(bmp.inputs["Distance"].default_value,
                                                      CAL_HANDWHEEL)
    nt.links.new(noise.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


# ---------------------------------------------------------------------------
# near-black matte interiors and fields


def _dark_film(name, color, specular, rough, ctx, calib, coat_zero=True):
    """Near-black dielectric: colour, specular level, and an `imperfect()`
    (lo, hi, bump strength, scale) mottle."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = 0.0
    if coat_zero:
        b.inputs["Coat Weight"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = specular
    lo, hi, strength, scale = rough
    imperfect(m, lo, hi, bump_strength=strength, scale=scale,
              ctx=_imperfect_ctx(ctx, calib))
    return m


@material("paint-matte-dark", family="paint", finish="matte", solid=False,
          calib_mm_per_unit=CAL_RING, origin="knob-ring:plate_material:255")
def mat_paint_matte_dark(color=(0.021, 0.021, 0.022), name="ring plate", *, ctx=DEFAULT_CTX):
    """Matte near-black field for apertures to be cut into. Not a true black:
    an unlit lens's ghost has to survive against it.

    Duplicate candidate: coating-cavity-dark, soot-interior,
    coating-interior-dark, black-paint."""
    return _dark_film(name, color, 0.18, (0.46, 0.62, 0.010, 141.0), ctx, CAL_RING)


@material("coating-interior-dark", family="paint", finish="matte", solid=False,
          calib_mm_per_unit=CAL_RIBBON, origin="conduit-ribbon:mouth:1214")
def mat_coating_interior_dark(color=(0.012, 0.012, 0.014), name="mouth", *,
                              ctx=DEFAULT_CTX):
    """Near-black dielectric for recessed floors (counterbores, liners, bolt
    sockets) that must read as depth rather than a surface.

    Duplicate candidate: soot-interior, coating-cavity-dark, paint-matte-dark."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Specular IOR Level"].default_value = 0.22
    imperfect(m, 0.52, 0.72, bump_strength=0.05, scale=221.0,
              ctx=_imperfect_ctx(ctx, CAL_RIBBON))
    return m


@material("soot-interior", family="paint", finish="matte", solid=False,
          calib_mm_per_unit=CAL_NIXIE, origin="display-nixie:mat_interior:671")
def mat_soot_interior(color=(0.014, 0.012, 0.011), name="interior", *, ctx=DEFAULT_CTX):
    """Discharge-sooted inner face behind an emitter: near-black and very
    rough, so the emitter stays the brightest thing in the object.

    Duplicate candidate: coating-interior-dark, coating-cavity-dark,
    paint-matte-dark."""
    return _dark_film(name, color, 0.22, (0.62, 0.82, 0.03, 399.0), ctx, CAL_NIXIE)


@material("coating-cavity-dark", family="paint", finish="matte", solid=False,
          calib_mm_per_unit=CAL_VENT, origin="vent-grille:mat_cavity:175")
def mat_coating_cavity_dark(color=(0.021, 0.020, 0.019), name="cavity", *, ctx=DEFAULT_CTX):
    """Enclosure interior seen through holes: near-black, matte, non-zero
    albedo so the cavity carries the key's falloff and holes read as deep.

    Duplicate candidate: soot-interior, coating-interior-dark, paint-matte-dark."""
    return _dark_film(name, color, 0.18, (0.62, 0.82, 0.05, 47.9), ctx, CAL_VENT,
                      coat_zero=False)


_WELL = dict(family="paint", finish="matte", solid=False, calib_mm_per_unit=CAL_CONSOLE,
             origin="button-console:wellm:158")


@material("paint-flat-dark", **_WELL)
@material("paint-flat-darker", params={"color": (0.003, 0.003, 0.004), "roughness": 0.9,
                                       "name": "floorm"}, **_WELL)
def mat_paint_flat_dark(color=(0.006, 0.006, 0.007), roughness=0.85, name="wellm", *,
                        ctx=DEFAULT_CTX):
    """Plain dark dielectric at constant roughness, no texture: a panel
    cutout's well walls (`paint-flat-dark`) and its floor (`paint-flat-darker`,
    origin button-console:floorm:164).

    Duplicate candidate: inlay-fill-dark, card-flat-black."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Metallic"].default_value = 0.0
    return m


# fader-desk panel interiors, the same untextured dielectric.
_FADER_INTERIOR = dict(family="paint", solid=False, calib_mm_per_unit=CAL_FADER)
# Screw counterbore floor around a panel screw.
# Duplicate candidate: paint-flat-dark, inlay-fill-dark, coating-interior-dark.
material("coating-counterbore-dark", finish="matte",
         params={"color": (0.012, 0.012, 0.014), "roughness": 0.6, "name": "recessm"},
         origin="fader-desk:recessm:367", **_FADER_INTERIOR)(mat_paint_flat_dark)
# Shadowed drive slot across a screw head.
# Duplicate candidate: coating-counterbore-dark, paint-flat-dark, acetal-black.
material("coating-screw-slot-dark", finish="satin",
         params={"color": (0.008, 0.008, 0.009), "roughness": 0.5, "name": "groovem"},
         origin="fader-desk:groovem:369", **_FADER_INTERIOR)(mat_paint_flat_dark)
# Chassis cavity seen down a fader slot.
# Duplicate candidate: paint-flat-darker, coating-cavity-dark, card-flat-black.
material("coating-cavity-black", finish="matte",
         params={"color": (0.004, 0.004, 0.005), "roughness": 0.9, "name": "cavitym"},
         origin="fader-desk:cavitym:370", **_FADER_INTERIOR)(mat_paint_flat_dark)


@material("paint-board-dark", family="paint", finish="matte", solid=False,
          calib_mm_per_unit=CAL_RADIO, origin="button-radio:review_board:157")
def mat_paint_board_dark(color=(0.045, 0.052, 0.055), name="review_board", *,
                         ctx=DEFAULT_CTX):
    """Neutral dark painted board behind a review plate, default specular."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 0.62
    imperfect(m, 0.56, 0.70, bump_strength=0.014, scale=12.4,
              ctx=_imperfect_ctx(ctx, CAL_RADIO))
    return m


# ---------------------------------------------------------------------------
# flat utility cards

_CARD = dict(family="paint", finish="matte", solid=False, calib_mm_per_unit=CAL_SCREEN,
             origin="screen-monitor:mat_flat:362")


@material("card-flat", **_CARD)
@material("card-flat-black", params={"color": (0.0, 0.0, 0.0)}, **_CARD)
def mat_card_flat(color=(1.0, 1.0, 1.0), emit=False, name="flat", *, ctx=DEFAULT_CTX):
    """Untextured roughness-1 card, optionally self-emitting its colour at
    strength 1: a pass helper (white glass mask, black occluder), not a look.

    Duplicate candidate: card-black-nonspecular, paint-flat-dark."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 1.0
    if emit:
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = 1.0
    return m


@material("card-black-nonspecular", family="paint", finish="matte", solid=False,
          calib_mm_per_unit=CAL_SMOOTH, origin="conduit-smooth:backdrop_black:1675")
def mat_card_black_nonspecular(name="backdrop_black", *, ctx=DEFAULT_CTX):
    """Black, roughness 1, zero specular: a set-dressing card that returns no
    light at all. Visibility flags (e.g. transmission/volume rays only) are the
    caller's object settings, not part of the material.

    Duplicate candidate: card-flat-black."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0, 0, 0, 1)
    b.inputs["Roughness"].default_value = 1.0
    b.inputs["Specular IOR Level"].default_value = 0.0
    return m
