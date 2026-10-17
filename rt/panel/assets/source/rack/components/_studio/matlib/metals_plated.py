"""Metal family, plated and deposited finishes: chrome, nickel and zinc
electroplate, galvanised wire, sputtered tube nickel and the barium getter
flash. Every key here is a surface film over some substrate (solid=False).

Calibration per origin component: units.MM_PER_UNIT.
"""
import bpy

from .core import DEFAULT_CTX, _obj_pos, material
from .metals_raw import (
    HANDWHEEL_MM, TOGGLE_MM, _imperfect_metal, imperfect_metal_at, mat_plain_metal,
)
from .units import mm_per_unit
from .metals import mat_brushed  # TEMP p159

NIXIE_MM = mm_per_unit("display-nixie")
JACK_MM = mm_per_unit("jack-socket")
VENT_MM = mm_per_unit("vent-grille")
RADIO_MM = mm_per_unit("button-radio")
LED_MM = mm_per_unit("led-indicator")

_PLATE = dict(family="metal", solid=False)
_im_radio = imperfect_metal_at(RADIO_MM)
_im_jack = imperfect_metal_at(JACK_MM)
_im_nixie = imperfect_metal_at(NIXIE_MM)
_im_vent = imperfect_metal_at(VENT_MM)
_im_handwheel = imperfect_metal_at(HANDWHEEL_MM)


material("chrome-plate-coated", finish="gloss",
         params={"color": (0.58, 0.62, 0.68), "rough_lo": 0.08, "rough_hi": 0.18,
                 "bump_strength": 0.008, "grain": 1370.0, "coat": 0.24,
                 "coat_roughness": 0.08, "name": "classic_chrome"},
         calib_mm_per_unit=RADIO_MM, origin="button-radio:classic_chrome:115",
         **_PLATE)(_im_radio)
material("nickel-plate-satin", finish="satin",
         params={"color": (0.75, 0.74, 0.71), "rough_lo": 0.17, "rough_hi": 0.29,
                 "bump_strength": 0.014, "grain": 337.0, "name": "nickel"},
         calib_mm_per_unit=JACK_MM, origin="jack-socket:mat_nickel:141", **_PLATE)(_im_jack)
# TEMP p159 candidates (pitch strip), not canon.
material("nickel-plate-satin-cand-diag", finish="satin",
         params={"color": (0.75, 0.74, 0.71), "rough_lo": 0.02, "rough_hi": 0.05,
                 "bump_strength": 0.014, "grain": 337.0, "name": "nickel"},
         calib_mm_per_unit=JACK_MM, origin="jack-socket:mat_nickel:141", **_PLATE)(_im_jack)
material("nickel-plate-satin-cand-b", finish="satin",
         params={"color": (0.75, 0.74, 0.71), "rough_lo": 0.07, "rough_hi": 0.15,
                 "bump_strength": 0.014, "grain": 337.0, "name": "nickel"},
         calib_mm_per_unit=JACK_MM, origin="jack-socket:mat_nickel:141", **_PLATE)(_im_jack)
material("nickel-plate-satin-cand-c", finish="satin", solid=False, family="metal",
         params={"tint": (1.34, 1.32, 1.22), "grain": (0.72, 21.6)},
         origin="matlib.mat_brushed")(mat_brushed)
material("nickel-plate-satin-cand-d", finish="satin", solid=False, family="metal",
         params={"tint": (1.18, 1.18, 1.12), "grain": (0.72, 21.6)},
         origin="matlib.mat_brushed")(mat_brushed)
# Duplicate candidate: nickel-plate-satin (same recipe, whiter and a hair smoother).
material("chrome-plate-satin", finish="satin",
         params={"color": (0.77, 0.77, 0.75), "rough_lo": 0.13, "rough_hi": 0.26,
                 "bump_strength": 0.014, "grain": 289.0, "name": "collar"},
         calib_mm_per_unit=NIXIE_MM, origin="display-nixie:mat_chrome_ring:717",
         **_PLATE)(_im_nixie)
material("nickel-mesh-sooted", finish="satin",
         params={"color": (0.19, 0.185, 0.175), "rough_lo": 0.44, "rough_hi": 0.62,
                 "bump_strength": 0.02, "grain": 1270.0, "name": "anode"},
         calib_mm_per_unit=NIXIE_MM, origin="display-nixie:mat_anode:457", **_PLATE)(_im_nixie)
material("barium-getter", finish="gloss",
         params={"color": (0.62, 0.61, 0.58), "rough_lo": 0.10, "rough_hi": 0.55,
                 "bump_strength": 0.05, "grain": 93.1, "name": "getter"},
         calib_mm_per_unit=NIXIE_MM, origin="display-nixie:mat_getter:685", **_PLATE)(_im_nixie)
# Duplicate candidate: steel-hw (brighter, smoother fastener band).
material("galvanised-steel-wire", finish="satin",
         params={"color": (0.52, 0.53, 0.54), "rough_lo": 0.31, "rough_hi": 0.46,
                 "bump_strength": 0.02, "grain": 327.0, "name": "wire"},
         calib_mm_per_unit=VENT_MM, origin="vent-grille:mat_wire:290", **_PLATE)(_im_vent)
material("zinc-plate-bright", finish="satin",
         params={"color": (0.66, 0.67, 0.70), "rough_lo": 0.10, "rough_hi": 0.30,
                 "bump_strength": 0.04, "grain": 897.0, "ripple": 0.35, "name": "washm"},
         calib_mm_per_unit=HANDWHEEL_MM, origin="knob-handwheel:washm:285", **_PLATE)(_im_handwheel)
# Duplicate candidate: zinc-plate-bright.
material("zinc-plate-grey", finish="satin",
         params={"color": (0.52, 0.53, 0.56), "rough_lo": 0.12, "rough_hi": 0.34,
                 "bump_strength": 0.04, "grain": 1150.0, "name": "nutm2"},
         calib_mm_per_unit=HANDWHEEL_MM, origin="knob-handwheel:nutm2:301", **_PLATE)(_im_handwheel)
# Duplicate candidate: matlib chrome (procedural waviness and scratches).
material("chrome-plain", finish="mirror",
         params={"color": (0.88, 0.90, 0.93), "roughness": 0.08, "name": "batm"},
         calib_mm_per_unit=TOGGLE_MM, origin="toggle-bat:batm:112", **_PLATE)(mat_plain_metal)


@material("nickel-wire-sputtered", finish="satin", calib_mm_per_unit=NIXIE_MM,
          origin="display-nixie:mat_cathode:418", **_PLATE)
def mat_nickel_wire_sputtered(reflectance=0.19, rough_floor=0.50, name="cathode", *,
                              ctx=DEFAULT_CTX):
    """Used tube-cathode nickel: dark and rough because the tube sputters its own
    metal over it. Base (r, 0.969 r, 0.915 r) at `reflectance`, roughness
    rough_floor..rough_floor + 0.20, micro-bump at grain 2170. Reads as a
    silhouette against a discharge only while it stays this dark."""
    return _imperfect_metal((reflectance, reflectance * 0.969, reflectance * 0.915),
                            rough_floor, rough_floor + 0.20, 0.02, 2170.0, 1.0,
                            0.0, 0.0, 0.03, name, ctx, NIXIE_MM)


@material("chrome-plate-dull", finish="satin", calib_mm_per_unit=LED_MM,
          origin="led-indicator:collarm:121", **_PLATE)
def mat_chrome_plate_dull(color=(0.50, 0.51, 0.54), rough_lo=0.14, rough_hi=0.36,
                          bump_strength=0.03, grain=870.0, name="collarm", *,
                          ctx=DEFAULT_CTX):
    """Dull chrome bezel ring: metallic `color`, a noise at `grain`
    (default detail) mapping roughness rough_lo..rough_hi, and a micro-bump
    from a second noise at 3x `grain` that REPLACES any existing Normal link.

    Duplicate candidate: chrome-plate-satin (imperfect() with detail 5 and a
    chained bump)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Base Color"].default_value = (*color, 1)
    pos = _obj_pos(nt)
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, n1.inputs["Vector"])
    n1.inputs["Scale"].default_value = ctx.freq(grain, LED_MM)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = rough_lo
    mr.inputs["To Max"].default_value = rough_hi
    nt.links.new(n1.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, n2.inputs["Vector"])
    n2.inputs["Scale"].default_value = ctx.freq(grain * 3, LED_MM)
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump_strength
    bmp.inputs["Distance"].default_value = ctx.length(bmp.inputs["Distance"].default_value, LED_MM)
    nt.links.new(n2.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m
