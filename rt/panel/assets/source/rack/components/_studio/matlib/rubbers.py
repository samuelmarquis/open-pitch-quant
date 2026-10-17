"""Rubber family: elastomers and soft PVC — gummy translucent tube walls, wire
insulation, EPDM grommets, grip sleeves and seam inserts.

`imperfect()` routes through the core calibration (25 mm/unit); builders
calibrated elsewhere hand it `_imp_ctx(ctx, calib)`.

Calibration per origin component: units.MM_PER_UNIT.
"""
from .core import (CALIB_MM_PER_UNIT, DEFAULT_CTX, MaterialContext, _obj_pos, base_material,
                   imperfect, material)
from .units import mm_per_unit

CORRUGATED_MM = mm_per_unit("conduit-corrugated")
SMOOTH_MM = mm_per_unit("conduit-smooth")
RIBBON_MM = mm_per_unit("conduit-ribbon")
BEZEL_MM = mm_per_unit("button-bezel")
NIXIE_MM = mm_per_unit("display-nixie")
RACK_MM = mm_per_unit("rack-hardware")


def _imp_ctx(ctx, calib):
    """The context `imperfect()` (calibrated at 25) needs so its constants
    scale as if calibrated at `calib`."""
    if calib == CALIB_MM_PER_UNIT:
        return ctx
    return MaterialContext(CALIB_MM_PER_UNIT * (ctx.mm_per_unit / calib))


def _set(b, socket, value):
    if socket in b.inputs:
        b.inputs[socket].default_value = value


def _gummy_body(name, color, radius, sss_radius, ctx, calib):
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Subsurface Weight"].default_value = 0.85
    b.inputs["Subsurface Radius"].default_value = sss_radius
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.9 * radius, calib)
    b.inputs["Roughness"].default_value = 0.07
    b.inputs["Coat Weight"].default_value = 0.6
    b.inputs["IOR"].default_value = 1.42
    return m, nt, b


def _longitudinal_streak(nt, b, strength, dist, ctx, calib):
    """Extrusion die-lines along the tube: Object coords stretched (2.5, 240,
    240), at an amplitude that only shows in the specular ridge."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = ctx.freq((2.5, 240.0, 240.0), calib)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Detail"].default_value = 2.0
    nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = strength
    bmp.inputs["Distance"].default_value = ctx.length(dist, calib)
    nt.links.new(n.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])


_CYAN, _AMBER, _VIOLET = (0.01, 0.50, 0.68), (0.62, 0.30, 0.05), (0.33, 0.14, 0.55)
_GUMMY = dict(family="rubber", finish="gloss", solid=True, calib_mm_per_unit=CORRUGATED_MM,
              origin="conduit-corrugated:wall:1266")


@material("gummy-rubber", **_GUMMY)
@material("gummy-rubber-amber", params={"color": _AMBER}, **_GUMMY)
@material("gummy-rubber-violet", params={"color": _VIOLET}, **_GUMMY)
def mat_gummy_rubber(color=_CYAN, radius=0.16, sss_radius=(0.15, 0.85, 1.0), name="wall",
                     *, ctx=DEFAULT_CTX):
    """Solid gummy tube wall: random-walk subsurface 0.85 tinted by `color`,
    coat 0.6 at roughness 0.07, IOR 1.42, no relief.

    `radius` is the tube radius (a length at the calibration unit): the scatter
    scale is 0.9 x radius, so the wall reads the same at every tube size.
    `sss_radius` is the scatter profile; the default carries blue furthest,
    which suits the cyan body (a component deriving it from the body colour
    passes it in). Duplicate candidate: gummy-rubber-extruded."""
    m, _nt, _b = _gummy_body(name, color, radius, sss_radius, ctx, CORRUGATED_MM)
    return m


_GUMMY_X = dict(family="rubber", finish="gloss", solid=True, calib_mm_per_unit=SMOOTH_MM,
                origin="conduit-smooth:wall_gummy:1459")


@material("gummy-rubber-extruded", **_GUMMY_X)
@material("gummy-rubber-extruded-amber", params={"color": _AMBER}, **_GUMMY_X)
@material("gummy-rubber-extruded-violet", params={"color": _VIOLET}, **_GUMMY_X)
def mat_gummy_rubber_extruded(color=_CYAN, radius=0.16, name="wall_gummy",
                              *, ctx=DEFAULT_CTX):
    """The gummy tube wall (`gummy-rubber`) as an extrusion: faint die-lines
    along the tube's local Y axis (Object-space noise stretched 2.5 x 240 x
    240), then imperfect()'s roughness 0.055-0.11 and micro-bump chained on
    top. `radius` is the tube radius (scatter scale 0.9 x radius).
    Duplicate candidate: gummy-rubber."""
    m, nt, b = _gummy_body(name, color, radius, (0.15, 0.85, 1.0), ctx, SMOOTH_MM)
    _longitudinal_streak(nt, b, 0.016, 0.0022, ctx, SMOOTH_MM)
    imperfect(m, 0.055, 0.11, bump_strength=0.014, scale=45.3, ctx=_imp_ctx(ctx, SMOOTH_MM))
    return m


def _srgb_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


@material("pvc-insulation", family="rubber", finish="satin", solid=True,
          calib_mm_per_unit=RIBBON_MM, origin="conduit-ribbon:pvc:1072")
def mat_pvc_insulation(color=tuple(_srgb_lin(int(h, 16) / 255.0) for h in ("7c", "4a", "24")),
                       sss_scale=0.9 * 0.06, glow=0.0, rough_lo=0.13, rough_hi=0.21,
                       coat=0.20, coat_k=0.15, coat_rough=0.16, specular=0.38,
                       name="wire00", *, ctx=DEFAULT_CTX):
    """Soft PVC wire insulation: random-walk scatter with a radius profile
    taken from `color`, IOR 1.42, satin coat, imperfect() roughness.

    Carbon-loaded black PVC neither scatters nor coats like a pigment: below
    ~5 % linear luminance a factor k ramps subsurface weight (0.85 x (0.30 +
    0.70 k)) and coat (coat + coat_k x k) down; k is exactly 1 above it.
    `glow` 0..1 lifts the insulation with emission in its own colour
    (strength min(1.6, 1.5 x glow)).

    Component-supplied: `color` (linear RGB per conductor; the default is the
    IDC brown of wire 0) and `sss_scale`, a length at the calibration unit
    (canon 0.9 x the insulation radius 0.06 for a conductor, 0.5 x for the
    fused web between conductors, whose colour is the band's mean x 0.45).
    The roughness / coat / specular defaults are the ribbon's duller material
    set 2; set 1 is rough 0.05-0.11, coat 0.34 + 0.26 k, coat roughness 0.03,
    specular 0.5."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    luma = 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]
    k = min(1.0, luma / 0.05)
    b.inputs["Subsurface Weight"].default_value = 0.85 * (0.30 + 0.70 * k)
    mx = max(color) or 1.0
    b.inputs["Subsurface Radius"].default_value = tuple(0.15 + 0.85 * (c / mx) for c in color)
    b.inputs["Subsurface Scale"].default_value = ctx.length(sss_scale, RIBBON_MM)
    b.inputs["Coat Weight"].default_value = coat + coat_k * k
    _set(b, "Coat Roughness", coat_rough)
    _set(b, "Specular IOR Level", specular)
    b.inputs["IOR"].default_value = 1.42
    if glow > 0:
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = min(1.6, 1.5 * glow)
    imperfect(m, rough_lo, rough_hi, bump_strength=0.03, scale=101.0,
              ctx=_imp_ctx(ctx, RIBBON_MM))
    return m


@material("rubber-seam", family="rubber", finish="matte", solid=True,
          calib_mm_per_unit=BEZEL_MM, origin="button-bezel:rubber reveal:533")
def mat_rubber_seam(name="rubber reveal", *, ctx=DEFAULT_CTX):
    """Dark rubber seam insert: flat near-black at roughness 0.78, no relief.
    Duplicate candidate: epdm."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.0025, 0.003, 0.0035, 1)
    b.inputs["Roughness"].default_value = 0.78
    b.inputs["Metallic"].default_value = 0.0
    return m


@material("epdm", family="rubber", finish="matte", solid=True,
          calib_mm_per_unit=NIXIE_MM, origin="display-nixie:mat_rubber:696")
def mat_epdm(name="rubber", *, ctx=DEFAULT_CTX):
    """EPDM grommet: dead matte, no coat, specular 0.30, a fine moulded pebble
    (Smooth-F1 Voronoi at 225 per unit into a 0.004 bump).
    Duplicate candidate: rubber-grip."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.020, 0.020, 0.021, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.30
    peb = nt.nodes.new("ShaderNodeTexVoronoi")
    peb.feature = "SMOOTH_F1"
    nt.links.new(_obj_pos(nt), peb.inputs["Vector"])
    peb.inputs["Scale"].default_value = ctx.freq(225.0)
    pb = nt.nodes.new("ShaderNodeBump")
    pb.inputs["Strength"].default_value = 0.06
    pb.inputs["Distance"].default_value = ctx.length(0.004)
    nt.links.new(peb.outputs["Distance"], pb.inputs["Height"])
    nt.links.new(pb.outputs["Normal"], b.inputs["Normal"])
    imperfect(m, 0.62, 0.78, bump_strength=0.02, scale=150.0, ctx=ctx)
    return m


@material("rubber-grip", family="rubber", finish="matte", solid=True,
          calib_mm_per_unit=RACK_MM, origin="rack-hardware:mat_rubber:282")
def mat_rubber_grip(name="rubber", *, ctx=DEFAULT_CTX):
    """Grip rubber: dead matte near-black (specular 0.16, roughness 0.80-0.94)
    with a hair of subsurface so it reads as rubber rather than paint, and a
    fine moulded-knurl micro-texture (Smooth-F1 Voronoi at 598 per unit). Ribs
    belong in geometry: a bump rib vanishes when the key grazes along it.
    Duplicate candidate: epdm."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.020, 0.020, 0.022, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.16
    b.inputs["Subsurface Weight"].default_value = 0.06
    b.inputs["Subsurface Radius"].default_value = (0.4, 0.4, 0.4)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.01)
    n = nt.nodes.new("ShaderNodeTexVoronoi")
    n.feature = "SMOOTH_F1"
    nt.links.new(_obj_pos(nt), n.inputs["Vector"])
    n.inputs["Scale"].default_value = ctx.freq(598.0)
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.07
    bmp.inputs["Distance"].default_value = ctx.length(0.0025)
    nt.links.new(n.outputs["Distance"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    imperfect(m, 0.80, 0.94, bump_strength=0.025, scale=683.0, ctx=ctx)
    return m
