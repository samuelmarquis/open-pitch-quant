"""Emissive family: light sources a part carries — LED lenses and dies, light
pipes, backlit wells, luminous ink, VFD phosphor and filament, gas discharge.

Surface emission strength and colour are NOT spatial and never pass through
ctx. Volume quantities per unit of path (volume emission strength, absorption
density) are per world unit, i.e. frequencies: they pass through ctx.freq.

Lit/unlit is a parameter of the one builder, never a second key.

Calibration per origin component: units.MM_PER_UNIT.
"""
import math

import bpy

from .core import (CALIB_MM_PER_UNIT, DEFAULT_CTX, MaterialContext, _obj_pos, base_material,
                   imperfect, material)
from .units import mm_per_unit

CONDUIT_MM = mm_per_unit("conduit-corrugated")
RADIO_MM = mm_per_unit("button-radio")
LED_INDICATOR_MM = mm_per_unit("led-indicator")
BEZEL_MM = mm_per_unit("button-bezel")
KNOB_MM = mm_per_unit("knob-led")
NIXIE_MM = mm_per_unit("display-nixie")
SEGMENT_MM = mm_per_unit("display-segment")


def _imperfect_ctx(ctx, calib):
    """The context for core.imperfect (calibrated at 25 mm/unit) that scales its
    constants as if they were calibrated at `calib`; exactly the 25 mm/unit
    context when ctx.mm_per_unit == calib."""
    return MaterialContext(ctx.mm_per_unit / calib * CALIB_MM_PER_UNIT)


# --------------------------------------------------------------- glow cores

_CORE = dict(family="emissive", finish="matte", solid=True, calib_mm_per_unit=CONDUIT_MM,
             origin="conduit-corrugated:core:1285")


@material("glow-core", **_CORE)
@material("glow-core-amber", params={"glow": (1.00, 0.45, 0.12)}, **_CORE)
def glow_core(glow=(0.20, 0.90, 1.00), strength=16.0, *, ctx=DEFAULT_CTX):
    """A pure surface emitter: the lit core running inside a translucent tube.
    One Emission on Surface; the default Principled stays in the tree, unlinked.
    `glow` is the linear emission colour, `strength` the emission strength.

    Duplicate candidate: conduit-smooth:core:1473 builds this identical graph
    (same default glow and strength)."""
    m, nt, _b = base_material("core")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*glow, 1)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    return m


@material("nixie-neon", family="emissive", finish="matte", solid=True,
          calib_mm_per_unit=NIXIE_MM, origin="display-nixie:mat_glow:389")
@material("nixie-mercury", family="emissive", finish="matte", solid=True,
          params={"col": (0.10, 0.22, 1.00), "strength": 220.0 * 0.55},
          calib_mm_per_unit=NIXIE_MM, origin="display-nixie:mat_glow:389")
def nixie_glow(col=(1.00, 0.150, 0.025), strength=220.0, *, ctx=DEFAULT_CTX):
    """Gas discharge as a VOLUME: no surface closure (the Principled node is
    removed), an Emission on the Volume socket. Radiance along a ray is
    strength x path length through the mesh, so the falloff comes from the
    sleeve geometry it is assigned to (closed, non-self-intersecting sleeves);
    the mesh must not cast shadows.

    `col` is the gas colour (neon / Hg-doped presets), `strength` the volume
    emission per world unit of path at the calibration unit (routed through
    ctx.freq) — the inner sheath takes the preset, the outer halo is the same
    builder at a lower strength (the component passes it)."""
    m = bpy.data.materials.new("glow")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*col, 1)
    em.inputs["Strength"].default_value = ctx.freq(strength, NIXIE_MM)
    nt.links.new(em.outputs["Emission"], nt.nodes["Material Output"].inputs["Volume"])
    return m


# ------------------------------------------------------------ LED lenses

@material("acrylic-led-lens", family="emissive", finish="satin", solid=True,
          calib_mm_per_unit=BEZEL_MM, origin="button-bezel:tinted LED lens:277")
def acrylic_led_lens(color=(1.0, 1.0, 0.0), level=2.6, *, ctx=DEFAULT_CTX):
    """Tinted moulded acrylic (IOR 1.49) lens over an LED, near-opaque, with a
    fine moulding bump. `level` > 0 is lit: dormant tint 0.003 + 0.14 x color,
    emission 0.05 + 0.09 sqrt(level); `level` 0 is unlit: darker, rougher, no
    transmission, no emission. `color` is the emitter colour as the component
    resolves it (button-bezel saturates it when lit)."""
    m, nt, b = base_material("tinted LED lens")
    if level > 0:
        dormant = tuple(0.003 + 0.14 * c for c in color)
        roughness, transmission, coat, specular = 0.36, 0.01, 0.02, 0.12
    else:
        dormant = tuple(0.002 + 0.035 * c for c in color)
        roughness, transmission, coat, specular = 0.58, 0.0, 0.01, 0.10
    b.inputs["Base Color"].default_value = (*dormant, 1)
    b.inputs["Roughness"].default_value = roughness
    b.inputs["IOR"].default_value = 1.49
    b.inputs["Specular IOR Level"].default_value = specular
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = 0.05 + 0.09 * math.sqrt(level) if level > 0 else 0.0
    noise = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), noise.inputs["Vector"])
    noise.inputs["Scale"].default_value = ctx.freq(333.0, BEZEL_MM)
    noise.inputs["Detail"].default_value = 2.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.035
    bump.inputs["Distance"].default_value = ctx.length(0.002, BEZEL_MM)
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


_DOME = dict(family="emissive", finish="gloss", solid=True, calib_mm_per_unit=LED_INDICATOR_MM,
             origin="led-indicator:lensm:138")


@material("led-dome", **_DOME)
@material("led-dome-amber", params={"glow": (1.00, 0.52, 0.07), "body": (0.058, 0.024, 0.004)},
          **_DOME)
@material("led-dome-green", params={"glow": (0.10, 1.00, 0.25), "body": (0.010, 0.048, 0.014)},
          **_DOME)
@material("led-dome-mcblue", params={"glow": (0.08, 0.60, 1.00), "body": (0.004, 0.024, 0.044)},
          **_DOME)
@material("led-dome-white", params={"glow": (1.00, 0.95, 0.85), "body": (0.048, 0.048, 0.048)},
          **_DOME)
def led_dome(glow=(1.00, 0.11, 0.05), body=(0.052, 0.006, 0.004), level=15, *, ctx=DEFAULT_CTX):
    """Translucent tinted indicator dome: glossy coated plastic with shallow
    subsurface. `level` is the 0..15 brightness index; the base colour warms
    from `body` toward `glow` by (level/15)^2 x 0.30 and emission is
    3.6 (level/15)^2.3, capped there so AgX keeps the hue. The halo is not in
    the material (led-indicator composites it).

    Duplicate candidate: acrylic-led-lens and backlit-lens are the other two
    ways the bin builds a lit LED lens."""
    lvl = level / 15.0
    m, nt, b = base_material("lensm")
    warm = [body[i] + (glow[i] - body[i]) * (lvl ** 2.0) * 0.30 for i in range(3)]
    b.inputs["Base Color"].default_value = (*warm, 1)
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Coat Weight"].default_value = 0.6
    b.inputs["Subsurface Weight"].default_value = 0.4
    b.inputs["Subsurface Radius"].default_value = (0.6, 0.6, 0.6)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.02, LED_INDICATOR_MM)
    b.inputs["Emission Color"].default_value = (*glow, 1)
    b.inputs["Emission Strength"].default_value = 3.6 * (lvl ** 2.3)
    return m


@material("backlit-lens", family="emissive", finish="satin", solid=True,
          calib_mm_per_unit=RADIO_MM, origin="button-radio:illuminated_center_well:147")
def backlit_lens(color=(82 / 255.0, 217 / 255.0, 255 / 255.0), level=2.8, *, ctx=DEFAULT_CTX):
    """Backlit translucent plastic well: base colour 0.26 x `color`, light
    transmission and coat, emission `color` at min(level, 5), roughness mottle
    and micro-bump. The unlit state is a different material in its component
    (not this key). Any point light behind it belongs to the component.

    Duplicate candidate: led-dome, acrylic-led-lens (lit LED lens built another way)."""
    m, _nt, b = base_material("illuminated_center_well")
    b.inputs["Base Color"].default_value = (*tuple(c * 0.26 for c in color), 1)
    b.inputs["Roughness"].default_value = 0.30
    b.inputs["Transmission Weight"].default_value = 0.22
    b.inputs["Coat Weight"].default_value = 0.18
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = min(level, 5.0)
    imperfect(m, 0.24, 0.37, bump_strength=0.018, scale=1210.0, ctx=_imperfect_ctx(ctx, RADIO_MM))
    return m


@material("light-pipe", family="emissive", finish="gloss", solid=True,
          calib_mm_per_unit=KNOB_MM, origin="knob-led:clear_pipe_material:162")
def light_pipe(color=(1.0, 0.055, 0.002), level=1.0, *, ctx=DEFAULT_CTX):
    """Solid transmissive light pipe (IOR 1.49) tinted 0.04 + 0.32 x `color`,
    emitting `color` at 1.8 level^1.5, with a Volume Absorption of `color` on
    the Volume socket. `level` 0..1 is the illumination; 0 is unlit.

    The absorption Density (0.22 per world unit at the calibration unit) is a
    frequency and goes through ctx.freq. The mesh must be closed for the volume
    to be bounded."""
    m, nt, b = base_material("translucent LED angle strip")
    tint = tuple(0.04 + 0.32 * c for c in color)
    b.inputs["Base Color"].default_value = (*tint, 1)
    b.inputs["Roughness"].default_value = 0.22
    b.inputs["IOR"].default_value = 1.49
    b.inputs["Transmission Weight"].default_value = 0.32
    b.inputs["Coat Weight"].default_value = 0.16
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = 1.8 * (level ** 1.5)
    absorption = nt.nodes.new("ShaderNodeVolumeAbsorption")
    absorption.inputs["Color"].default_value = (*color, 1)
    absorption.inputs["Density"].default_value = ctx.freq(0.22, KNOB_MM)
    nt.links.new(absorption.outputs["Volume"], nt.nodes["Material Output"].inputs["Volume"])
    return imperfect(m, 0.10, 0.19, bump_strength=0.010, scale=3150.0, ctx=ctx)


# ------------------------------------------------------------------ dies

@material("led-emitter", family="emissive", finish="satin", solid=True,
          calib_mm_per_unit=KNOB_MM, origin="knob-led:emitter_material:179")
def led_emitter(color=(1.0, 0.055, 0.002), level=1.0, *, ctx=DEFAULT_CTX):
    """Concealed LED emitter block behind a light pipe: near-black
    (0.008 + 0.015 x `color`) diffuse body emitting `color` at 5.2 level^1.5.
    `level` 0..1; 0 is unlit.

    Duplicate candidate: led-die (buried die, different ramp and body)."""
    m, _nt, b = base_material("concealed LED diffuser")
    dark = tuple(0.008 + c * 0.015 for c in color)
    b.inputs["Base Color"].default_value = (*dark, 1)
    b.inputs["Roughness"].default_value = 0.38
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = 5.2 * (level ** 1.5)
    return imperfect(m, 0.32, 0.44, bump_strength=0.010, scale=3460.0, ctx=ctx)


_DIE = dict(family="emissive", finish="satin", solid=True, calib_mm_per_unit=SEGMENT_MM,
            origin="display-segment:mat_die:655")


@material("led-die", **_DIE)
@material("led-die-amber", params={"em": (1.00, 0.520, 0.070)}, **_DIE)
@material("led-die-green", params={"em": (0.045, 1.00, 0.150)}, **_DIE)
def led_die(em=(1.00, 0.110, 0.050), emit=1.4, lit=True, *, ctx=DEFAULT_CTX):
    """Semiconductor die buried under a diffusant lens: cool near-black chip,
    emitting `em` at 0.8 x `emit` when `lit` (0 when not), so the core stays
    below its lens's own emission. `emit` is the lens emission strength the
    component uses for the diffusant over it.

    Duplicate candidate: led-emitter (concealed die, different body and ramp);
    the red and amber `em` presets equal led-dome's glow colours."""
    m, _nt, b = base_material("die_lit" if lit else "die_dark")
    b.inputs["Base Color"].default_value = (0.028, 0.026, 0.036, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.42
    b.inputs["Specular IOR Level"].default_value = 0.60
    b.inputs["Emission Color"].default_value = (*em, 1)
    b.inputs["Emission Strength"].default_value = emit * 0.8 if lit else 0.0
    return m


# ------------------------------------------------------------------- VFD

@material("vfd-phosphor", family="emissive", finish="matte", solid=False,
          calib_mm_per_unit=SEGMENT_MM, origin="display-segment:mat_phosphor:673")
def vfd_phosphor(tint=(0.210, 0.235, 0.200), em=(0.100, 1.00, 0.720), emit=1.4, lit=True,
                 *, ctx=DEFAULT_CTX):
    """Stencilled ZnO:Zn phosphor pad on a VFD anode: an opaque pale coating
    (`tint` is its unlit colour, readable when off), emitting `em` at
    0.9 x `emit` when `lit`, with roughness mottle and micro-bump. No
    transmission, no diffusant."""
    m, _nt, b = base_material("phosphor_lit" if lit else "phosphor_dark")
    b.inputs["Base Color"].default_value = (*tint, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.72
    b.inputs["Specular IOR Level"].default_value = 0.22
    b.inputs["Emission Color"].default_value = (*em, 1)
    b.inputs["Emission Strength"].default_value = emit * 0.90 if lit else 0.0
    imperfect(m, 0.66, 0.80, bump_strength=0.02, scale=2910.0, ctx=ctx)
    return m


@material("vfd-filament", family="emissive", finish="satin", solid=True,
          calib_mm_per_unit=SEGMENT_MM, origin="display-segment:mat_filament:691")
def vfd_filament(dark=False, *, ctx=DEFAULT_CTX):
    """Directly heated tungsten VFD cathode wire: dull metal, barely emissive
    (dull orange at 0.30). It glows whenever the tube is powered, so `dark`
    (every always-on source off, for additive bake layers) is its only off
    switch."""
    m, _nt, b = base_material("filament")
    b.inputs["Base Color"].default_value = (0.42, 0.38, 0.34, 1)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.34
    b.inputs["Emission Color"].default_value = (1.0, 0.42, 0.14, 1)
    b.inputs["Emission Strength"].default_value = 0.0 if dark else 0.30
    return m


# --------------------------------------------------------- backlit lettering

TITLE_MM = mm_per_unit("panel-board")
_LETTER = dict(family="emissive", finish="satin", solid=True, calib_mm_per_unit=TITLE_MM,
               origin="panel-board --title")


@material("acrylic-opal", **_LETTER)
@material("acrylic-opal-grey", params={"body": (0.15, 0.15, 0.15), "rough": 0.34, "coat": 0.30},
          **_LETTER)
@material("acrylic-smoke", params={"body": (0.035, 0.036, 0.038), "rough": 0.16,
                                   "transmission": 0.30, "coat": 0.55}, **_LETTER)
def acrylic_letter(body=(0.60, 0.60, 0.58), rough=0.40, transmission=0.0, coat=0.22,
                   level=0.0, *, ctx=DEFAULT_CTX):
    """Cast acrylic (IOR 1.49) for backlit lettering: opal (milky, frosted
    face), opal-grey (a grey diffuser: light plastic unlit, the backlight's
    colour dominant lit) or smoke (dark clear, glossy). `level` is the backlight: WHITE emission at
    that strength, the only input that differs between lit and unlit, so a
    lit letter is exactly the unlit render plus its own light (additive bake
    layers). The consumer tints a letter by scaling its layer."""
    m, nt, b = base_material("backlit acrylic")
    b.inputs["Base Color"].default_value = (*body, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["IOR"].default_value = 1.49
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.06
    b.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1)
    b.inputs["Emission Strength"].default_value = level
    noise = nt.nodes.new("ShaderNodeTexNoise")               # the frosting's grain
    nt.links.new(_obj_pos(nt), noise.inputs["Vector"])
    noise.inputs["Scale"].default_value = ctx.freq(6490.0, TITLE_MM)
    noise.inputs["Detail"].default_value = 2.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.03
    bump.inputs["Distance"].default_value = ctx.length(0.002, TITLE_MM)
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


# ------------------------------------------------------------------- ink

@material("deposited-ink", family="emissive", finish="satin", solid=False,
          calib_mm_per_unit=BEZEL_MM, origin="button-bezel:deposited label ink:240")
def deposited_ink(color=(237 / 255.0, 240 / 255.0, 238 / 255.0), *, ctx=DEFAULT_CTX):
    """Raised deposited legend ink: flat `color` at roughness 0.42 with a faint
    self-emission (0.12) of the same colour, so the legend stays legible in the
    dark. The relief is the text geometry's, not the material's."""
    m, _nt, b = base_material("deposited label ink")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 0.42
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = 0.12
    return m
