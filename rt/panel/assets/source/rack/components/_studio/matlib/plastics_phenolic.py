"""Plastic family, moulded phenolics: compression-moulded bakelite — solid-colour
knob bodies, dark recess wells, jack collars and tube bases with flow marks.
(Cast phenolic resin, catalin, is in `resins`; the marbled `bakelite` panel key
is in `plastics`.)

`imperfect()` routes through the core calibration (25 mm/unit); builders
calibrated elsewhere hand it `_imp_ctx(ctx, calib)`.

Calibration per origin component: units.MM_PER_UNIT.
"""
from .core import (CALIB_MM_PER_UNIT, DEFAULT_CTX, MaterialContext, _obj_pos, base_material,
                   imperfect, material)
from .units import mm_per_unit

CHICKENHEAD_MM = mm_per_unit("knob-chickenhead")
JACK_MM = mm_per_unit("jack-socket")
NIXIE_MM = mm_per_unit("display-nixie")
RADIO_MM = mm_per_unit("button-radio")


def _imp_ctx(ctx, calib):
    """The context `imperfect()` (calibrated at 25) needs so its constants
    scale as if calibrated at `calib`."""
    if calib == CALIB_MM_PER_UNIT:
        return ctx
    return MaterialContext(CALIB_MM_PER_UNIT * (ctx.mm_per_unit / calib))


_SOLID = dict(family="plastic", finish="satin", solid=True, calib_mm_per_unit=CHICKENHEAD_MM,
              origin="knob-chickenhead:bakelite:162")


@material("bakelite-solid", **_SOLID)
@material("bakelite-solid-cream", params={"color": (0.55, 0.47, 0.33), "subsurface": 0.3},
          **_SOLID)
@material("bakelite-solid-red", params={"color": (0.26, 0.016, 0.012), "roughness": 0.30},
          **_SOLID)
@material("bakelite-solid-grey", params={"color": (0.16, 0.165, 0.17)}, **_SOLID)
def mat_bakelite_solid(color=(0.012, 0.012, 0.013), roughness=0.32, subsurface=0.0,
                       name="bakelite", *, ctx=DEFAULT_CTX):
    """Solid-colour moulded bakelite: flat pigment, a 0.12 coat, flat
    roughness, no relief and no imperfect(). `subsurface` > 0 adds the cream
    colourway's scatter (radius 0.9/0.8/0.6, scale 0.03).
    Duplicate candidate: gloss-cap, bakelite."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Coat Weight"].default_value = 0.12
    if subsurface > 0:
        b.inputs["Subsurface Weight"].default_value = subsurface
        b.inputs["Subsurface Radius"].default_value = (0.9, 0.8, 0.6)
        b.inputs["Subsurface Scale"].default_value = ctx.length(0.03)
    return m


@material("phenolic-dull", family="plastic", finish="matte", solid=True,
          calib_mm_per_unit=RADIO_MM, origin="button-radio:recess_bakelite:124")
def mat_phenolic_dull(name="recess_bakelite", *, ctx=DEFAULT_CTX):
    """Dull brown-black phenolic for recess wells: roughness 0.58-0.76, no
    coat. Duplicate candidate: bakelite-black."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.009, 0.006, 0.005, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.68
    imperfect(m, 0.58, 0.76, bump_strength=0.025, scale=273.0, ctx=_imp_ctx(ctx, RADIO_MM))
    return m


@material("bakelite-black", family="plastic", finish="satin", solid=True,
          calib_mm_per_unit=JACK_MM, origin="jack-socket:mat_bakelite:172")
def mat_bakelite_black(name="bakelite", *, ctx=DEFAULT_CTX):
    """Moulded phenolic fascia part: near-black with a warm brown core, a thin
    aged coat (0.55 at 0.20), the mould's orange-peel (noise 181) over a slow
    flow ripple (noise 9.9) as a two-layer bump chain.
    Duplicate candidate: phenolic-moulded."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.035, 0.019, 0.013, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.55
    b.inputs["Coat Roughness"].default_value = 0.20
    prev = None
    pos = _obj_pos(nt)
    for scale, strength, dist in ((9.87, 0.06, 0.02), (181.0, 0.05, 0.005)):
        n = nt.nodes.new("ShaderNodeTexNoise")
        nt.links.new(pos, n.inputs["Vector"])
        n.inputs["Scale"].default_value = ctx.freq(scale)
        n.inputs["Detail"].default_value = 3.0
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = strength
        bmp.inputs["Distance"].default_value = ctx.length(dist)
        nt.links.new(n.outputs["Fac"], bmp.inputs["Height"])
        if prev is not None:
            nt.links.new(prev.outputs["Normal"], bmp.inputs["Normal"])
        prev = bmp
    nt.links.new(prev.outputs["Normal"], b.inputs["Normal"])
    imperfect(m, 0.28, 0.42, bump_strength=0.012, scale=428.0, ctx=ctx)
    return m


@material("phenolic-moulded", family="plastic", finish="satin", solid=True,
          calib_mm_per_unit=NIXIE_MM, origin="display-nixie:mat_phenolic:477")
def mat_phenolic_moulded(name="phenolic", *, ctx=DEFAULT_CTX):
    """Coarse brown-black phenolic moulding (a tube base or socket body), with
    four kinds of variation:

      1. flow marks in the colour: two heavily distorted diagonal wave bands in
         Object space through a two-brown ramp;
      2. roughness and coat that follow the same flow (resin-rich streaks take
         a sheen, filler-rich ones stay dull);
      3. turning marks and pits: a RINGS wave about local Z plus a BANDS wave
         along Z (the part must be a lathe about its local Z axis), and
         Voronoi porosity pits, in the bump chain and in the specular;
      4. edge wear: Pointiness lightens and polishes convex rims.

    imperfect()'s Roughness link is replaced by the flow-driven roughness; its
    micro-bump stays at the end of the chain.
    Duplicate candidate: bakelite-black."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Roughness"].default_value = 0.42
    tc = nt.nodes.new("ShaderNodeTexCoord")
    geo = nt.nodes.new("ShaderNodeNewGeometry")

    flow = nt.nodes.new("ShaderNodeTexWave")
    flow.wave_type = "BANDS"
    flow.bands_direction = "DIAGONAL"
    flow.wave_profile = "SIN"
    flow.inputs["Scale"].default_value = ctx.freq(1.8)
    flow.inputs["Distortion"].default_value = 14.0
    flow.inputs["Detail"].default_value = 3.0
    flow.inputs["Detail Scale"].default_value = 1.6
    flow.inputs["Detail Roughness"].default_value = 0.62
    nt.links.new(tc.outputs["Object"], flow.inputs["Vector"])
    fine = nt.nodes.new("ShaderNodeTexWave")
    fine.wave_type = "BANDS"
    fine.bands_direction = "DIAGONAL"
    fine.wave_profile = "SIN"
    fine.inputs["Scale"].default_value = ctx.freq(8.5)
    fine.inputs["Distortion"].default_value = 7.0
    fine.inputs["Detail"].default_value = 3.0
    fine.inputs["Detail Scale"].default_value = 2.2
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    swirl = nt.nodes.new("ShaderNodeMath")
    swirl.operation = "MULTIPLY_ADD"
    swirl.inputs[1].default_value = 0.34
    swirl.use_clamp = True
    nt.links.new(fine.outputs["Fac"], swirl.inputs[0])
    mflow = nt.nodes.new("ShaderNodeMath")
    mflow.operation = "MULTIPLY"
    mflow.inputs[1].default_value = 0.70
    nt.links.new(flow.outputs["Fac"], mflow.inputs[0])
    nt.links.new(mflow.outputs[0], swirl.inputs[2])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    e0, e1 = ramp.color_ramp.elements[0], ramp.color_ramp.elements[1]
    e0.position, e0.color = 0.12, (0.017, 0.0088, 0.0060, 1)
    e1.position, e1.color = 0.90, (0.062, 0.031, 0.019, 1)
    nt.links.new(swirl.outputs[0], ramp.inputs[0])

    wear = nt.nodes.new("ShaderNodeMapRange")
    wear.inputs["From Min"].default_value = 0.50
    wear.inputs["From Max"].default_value = 0.62
    nt.links.new(geo.outputs["Pointiness"], wear.inputs["Value"])
    worn = nt.nodes.new("ShaderNodeMixRGB")
    worn.blend_type = "MIX"
    worn.inputs[2].default_value = (0.088, 0.054, 0.038, 1)
    nt.links.new(wear.outputs["Result"], worn.inputs[0])
    nt.links.new(ramp.outputs[0], worn.inputs[1])
    nt.links.new(worn.outputs[0], b.inputs["Base Color"])

    rings = nt.nodes.new("ShaderNodeTexWave")
    rings.wave_type = "RINGS"
    rings.rings_direction = "Z"
    rings.wave_profile = "SAW"
    rings.inputs["Scale"].default_value = ctx.freq(18.0)
    rings.inputs["Distortion"].default_value = 1.1
    rings.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], rings.inputs["Vector"])
    walls = nt.nodes.new("ShaderNodeTexWave")
    walls.wave_type = "BANDS"
    walls.bands_direction = "Z"
    walls.wave_profile = "SAW"
    walls.inputs["Scale"].default_value = ctx.freq(18.0)
    walls.inputs["Distortion"].default_value = 0.7
    walls.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], walls.inputs["Vector"])
    turn = nt.nodes.new("ShaderNodeMath")
    turn.operation = "MULTIPLY_ADD"
    turn.inputs[1].default_value = 0.5
    nt.links.new(rings.outputs["Fac"], turn.inputs[0])
    tw = nt.nodes.new("ShaderNodeMath")
    tw.operation = "MULTIPLY"
    tw.inputs[1].default_value = 0.5
    nt.links.new(walls.outputs["Fac"], tw.inputs[0])
    nt.links.new(tw.outputs[0], turn.inputs[2])
    pits = nt.nodes.new("ShaderNodeTexVoronoi")
    pits.feature = "F1"
    pits.inputs["Scale"].default_value = ctx.freq(190.0)
    nt.links.new(tc.outputs["Object"], pits.inputs["Vector"])

    prev = None
    for src, strength, dist in (
            (None, 0.07, 0.02),
            (None, 0.05, 0.005),
            (turn.outputs[0], 0.11, 0.006),
            (pits.outputs["Distance"], 0.22, 0.006)):
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = strength
        bmp.inputs["Distance"].default_value = ctx.length(dist)
        if src is None:
            n = nt.nodes.new("ShaderNodeTexNoise")
            nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
            n.inputs["Scale"].default_value = ctx.freq(5.12 if prev is None else 95.0)
            n.inputs["Detail"].default_value = 3.0
            src = n.outputs["Fac"]
        nt.links.new(src, bmp.inputs["Height"])
        if prev is not None:
            nt.links.new(prev.outputs["Normal"], bmp.inputs["Normal"])
        prev = bmp
    nt.links.new(prev.outputs["Normal"], b.inputs["Normal"])

    imperfect(m, 0.36, 0.52, bump_strength=0.012, scale=175.0, ctx=ctx)

    rn = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(tc.outputs["Object"], rn.inputs["Vector"])
    rn.inputs["Scale"].default_value = ctx.freq(19.0)
    rn.inputs["Detail"].default_value = 4.0
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 0.50
    nt.links.new(rn.outputs["Fac"], mul.inputs[0])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.inputs[1].default_value = 0.34
    nt.links.new(swirl.outputs[0], add.inputs[0])
    nt.links.new(mul.outputs[0], add.inputs[2])
    add2 = nt.nodes.new("ShaderNodeMath")
    add2.operation = "MULTIPLY_ADD"
    add2.inputs[1].default_value = 0.16
    add2.use_clamp = True
    nt.links.new(turn.outputs[0], add2.inputs[0])
    nt.links.new(add.outputs[0], add2.inputs[2])
    rmr = nt.nodes.new("ShaderNodeMapRange")
    rmr.inputs["To Min"].default_value = 0.26
    rmr.inputs["To Max"].default_value = 0.72
    nt.links.new(add2.outputs[0], rmr.inputs["Value"])
    pol = nt.nodes.new("ShaderNodeMath")
    pol.operation = "MULTIPLY_ADD"
    pol.inputs[1].default_value = -0.20
    pol.use_clamp = True
    nt.links.new(wear.outputs["Result"], pol.inputs[0])
    nt.links.new(rmr.outputs["Result"], pol.inputs[2])
    nt.links.new(pol.outputs[0], b.inputs["Roughness"])
    cmr = nt.nodes.new("ShaderNodeMapRange")
    cmr.inputs["To Min"].default_value = 0.07
    cmr.inputs["To Max"].default_value = 0.30
    nt.links.new(add2.outputs[0], cmr.inputs["Value"])
    nt.links.new(cmr.outputs["Result"], b.inputs["Coat Weight"])
    return m
