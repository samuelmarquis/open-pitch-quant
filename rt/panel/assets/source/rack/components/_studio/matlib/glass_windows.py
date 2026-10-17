"""Glass family, windows: tube envelopes, display filter windows and dark
faceplate glass — thin dielectric sheets and shells a part is seen through or
that mirror the room over a display.

IOR, transmission, tint and roughness are not spatial and never pass through
ctx; only texture frequencies and bump distances do.

Calibration per origin component: units.MM_PER_UNIT.
"""
from .core import DEFAULT_CTX, _obj_pos, base_material, material
from .units import mm_per_unit

NIXIE_MM = mm_per_unit("display-nixie")
SEGMENT_MM = mm_per_unit("display-segment")
METER_MM = mm_per_unit("meter-vu")
SCREEN_MM = mm_per_unit("screen-monitor")

_ENVELOPE = dict(family="glass", finish="gloss", solid=True, calib_mm_per_unit=NIXIE_MM,
                 origin="display-nixie:mat_glass:344")


@material("soda-lime-envelope", **_ENVELOPE)
@material("soda-lime-envelope-smoked", params={"col": (0.40, 0.41, 0.44), "name": "glass_smoked"},
          **_ENVELOPE)
def soda_lime_envelope(col=(0.97, 0.98, 0.98), name="glass_clear", *, ctx=DEFAULT_CTX):
    """Drawn soda-lime tube envelope (IOR 1.474), full transmission, tinted by
    `col` (Base Color is the transmission tint: smoked darkens what is seen
    through it, not its reflection). Draw-mark roughness mottle 0.035-0.075 and
    a broad shallow wave bump, both in object space. Needs real wall
    thickness in the mesh and deep transmission bounces in the scene.

    Duplicate candidate: filter-window, window-dark (hand-rolled dielectric
    windows in other displays)."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.474
    b.inputs["Roughness"].default_value = 0.055
    pos = _obj_pos(nt)
    rn = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, rn.inputs["Vector"])
    rn.inputs["Scale"].default_value = ctx.freq(5.29, NIXIE_MM)
    rn.inputs["Detail"].default_value = 2.0
    rmr = nt.nodes.new("ShaderNodeMapRange")
    rmr.inputs["To Min"].default_value = 0.035
    rmr.inputs["To Max"].default_value = 0.075
    nt.links.new(rn.outputs["Fac"], rmr.inputs["Value"])
    nt.links.new(rmr.outputs["Result"], b.inputs["Roughness"])
    wav = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, wav.inputs["Vector"])
    wav.inputs["Scale"].default_value = ctx.freq(2.50, NIXIE_MM)
    wav.inputs["Detail"].default_value = 1.0
    wb = nt.nodes.new("ShaderNodeBump")
    wb.inputs["Strength"].default_value = 0.014
    wb.inputs["Distance"].default_value = ctx.length(0.02, NIXIE_MM)
    nt.links.new(wav.outputs["Fac"], wb.inputs["Height"])
    nt.links.new(wb.outputs["Normal"], b.inputs["Normal"])
    return m


_FILTER = dict(family="glass", finish="gloss", solid=True, calib_mm_per_unit=SEGMENT_MM,
               origin="display-segment:mat_window:736")


@material("window-smoked", **_FILTER)
@material("window-clear", params={"col": (0.950, 0.960, 0.970), "rough": 0.030,
                                  "name": "window_clear"}, **_FILTER)
@material("window-green", params={"col": (0.300, 0.520, 0.420), "rough": 0.030,
                                  "name": "window_green"}, **_FILTER)
def filter_window(col=(0.300, 0.270, 0.290), rough=0.045, ar=0.14, name="window_smoked",
                  *, ctx=DEFAULT_CTX):
    """Contrast-enhancement display window: an absorbing filter plate (IOR
    1.52, full transmission, Base Color `col` is the filter's transmission)
    with an anti-reflective coating modelled as `ar` = Specular IOR Level
    (0.5 is bare glass). Low roughness `rough` — a rough transmissive plate
    frosts the glyph. Presets: smoked (LED), clear, green (VFD faceplate).

    Duplicate candidate: soda-lime-envelope, window-dark."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = rough
    b.inputs["IOR"].default_value = 1.52
    b.inputs["Specular IOR Level"].default_value = ar
    b.inputs["Transmission Weight"].default_value = 1.0
    return m


@material("window-dark", family="glass", finish="gloss", solid=True,
          calib_mm_per_unit=SCREEN_MM, origin="screen-monitor:mat_glass_dark:348")
@material("window-dark-soft", family="glass", finish="gloss", solid=True,
          params={"coat_rough": 0.10}, calib_mm_per_unit=METER_MM,
          origin="meter-vu:mat_glass_dark:627")
def window_dark(coat_rough=0.05, *, ctx=DEFAULT_CTX):
    """Dark glossy faceplate glass over an unlit display: near-black opaque
    dielectric (roughness 0.12) under a full clear coat of roughness
    `coat_rough`, so it reads only as a mirror of the aimed room. Meant for a
    separate reflection pass composited over the display, not for seeing
    through.

    Duplicate candidate: the two keys are one graph differing only in
    coat_rough (screen-monitor 0.05, meter-vu 0.10)."""
    m, _nt, b = base_material("glass_dark")
    b.inputs["Base Color"].default_value = (0.008, 0.010, 0.009, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.12
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = coat_rough
    return m
