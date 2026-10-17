"""KnobScene: the knob family standard (PLAN 2.8) over ComponentScene.

A knob generator declares ComponentScene's attributes plus, where its canon
differs from the family defaults:

  VALUE = 0.62            default --value
  START_DEG = -135.0      default --start-deg
  END_DEG = -45.0         default --end-deg
  DETENTS = 0             default --detents
  FOOTPRINT = 0.5         default --footprint (STANDARD_FOOTPRINT)
  EXTRA_SLOTS = ()        slot names beyond body, cap, indicator, accent

and implements `build_knob(self) -> [objects]`: the part modelled at scale 1,
centred on the object Z axis, standing on z = 0, pointer along local +X, with
every slot bound. SLOTS may declare any subset of the standard slots; only
declared slots become flags.

Flags added to the shared vocabulary:
  --value 0..1       position within the throw
  --start-deg/--end-deg
                     pointer angle at value 0 / 1, degrees counter-clockwise from
                     image +X (3 o'clock); the throw runs CLOCKWISE from start to
                     end; equal values = a full 360
  --detents N        0 = continuous; N >= 1 quantizes to N positions (a throw
                     short of 360 includes both ends; a 360 throw spaces N
                     positions 360/N apart)
  --footprint R|native
                     R (default 0.5): scale the part so its apparent radius at
                     the panel plane z = 0 (max over evaluated vertices of
                     r*4.29/(4.29 - z), at scale 1) is R; native: the modelled
                     size. Every knob at the default fills the same circle, so
                     one knob-ring default fits them all

Throw: a continuous knob keeps the family throw (-135 -> -45, 270 deg). A
detented selector is a different product (a 5-position selector over 120 deg is
not a 270 deg pot) and keeps its own START_DEG / END_DEG / DETENTS.

build(): a "knob root" empty is created first; build_knob's objects are
parented to it; the root turns to throw_angle(...); footprint normalization (if
any) multiplies the root scale at scale 1, then the root scale is multiplied by
--scale; `self.rig = self.studio()` lights and frames it. Receipt notes:
`[footprint:native=A,factor=F]` when normalized.

studio() -> dict with at least "world" and "camera": the rig hook, called once
after the part is posed and scaled. Default rigs.knob_studio(scene, --scale,
local_dir, stops=rigs.PANEL_STOPS) — the same light panel-board ships, so a
knob and its panel share one rig; a knob with its own rig overrides it (world,
lights and camera keyed to --scale).
"""

import math

from .base import ComponentScene, Flag

FAMILY_SLOTS = ("body", "cap", "indicator", "accent")
FAMILY_SLOT_HELP = {
    "body": "body (skirt / bell) material",
    "cap": "cap / top material",
    "indicator": "pointer line or pin material",
    "accent": "trim material",
}
PANEL_CAM_Z = 4.29
STANDARD_FOOTPRINT = 0.5     # apparent radius at z = 0, world units at scale 1


def throw_sweep(start_deg, end_deg):
    """Clockwise sweep in degrees from start to end, in (0, 360]."""
    sweep = start_deg - end_deg
    if sweep <= 0.0:
        sweep += 360.0
    return sweep


def throw_angle(value, start_deg=-135.0, end_deg=-45.0, detents=0):
    """Pointer angle in degrees (counter-clockwise from +X) at `value`."""
    sweep = throw_sweep(start_deg, end_deg)
    if detents:
        steps = detents if sweep >= 360.0 else detents - 1
        if steps <= 0:
            return start_deg
        k = math.floor(value * steps + 0.5)
        value = (k % detents if sweep >= 360.0 else k) / steps
    return start_deg - sweep * value


def footprint_value(raw):
    if raw == "native":
        return raw
    try:
        v = float(raw)
    except (TypeError, ValueError):
        raise SystemExit(f"--footprint: {raw!r} is neither `native` nor a radius")
    if v <= 0.0:
        raise SystemExit("--footprint must be positive")
    return v


footprint_value.__name__ = "radius|native"


class KnobScene(ComponentScene):
    VALUE = 0.62
    START_DEG = -135.0
    END_DEG = -45.0
    DETENTS = 0
    FOOTPRINT = STANDARD_FOOTPRINT
    EXTRA_SLOTS = ()
    RES = 640
    SAMPLES = 220

    @classmethod
    def family_flags(cls):
        return [
            Flag("--value", float, cls.VALUE, help="position within the throw, 0..1"),
            Flag("--start-deg", float, cls.START_DEG,
                 help="pointer angle at value 0, deg CCW from 3 o'clock"),
            Flag("--end-deg", float, cls.END_DEG,
                 help="pointer angle at value 1; the throw runs clockwise; equal = 360"),
            Flag("--detents", int, cls.DETENTS, help="0 = continuous; N quantizes to N positions"),
            Flag("--footprint", footprint_value, cls.FOOTPRINT,
                 help="apparent radius at the panel plane, or native"),
        ]

    @classmethod
    def slot_help(cls, slot):
        return cls.SLOT_HELP.get(slot, FAMILY_SLOT_HELP.get(slot, f"{slot} material"))

    @classmethod
    def schema(cls):
        stray = sorted(set(cls.SLOTS) - set(FAMILY_SLOTS) - set(cls.EXTRA_SLOTS))
        if stray:
            raise TypeError(f"{cls.__name__}: slots {stray} are not family slots "
                            f"{FAMILY_SLOTS}; declare them in EXTRA_SLOTS")
        return super().schema()

    def validate(self):
        super().validate()
        a = self.args
        if not 0.0 <= a.value <= 1.0:
            raise SystemExit(f"{self.COMPONENT}: --value must be in 0..1")
        if a.detents < 0:
            raise SystemExit(f"{self.COMPONENT}: --detents must be >= 0")

    def angle_deg(self):
        a = self.args
        return throw_angle(a.value, a.start_deg, a.end_deg, a.detents)

    def build_knob(self):
        raise NotImplementedError

    def build(self):
        import bpy
        import scaffold

        a = self.args
        root = bpy.data.objects.new("knob root", None)
        bpy.context.collection.objects.link(root)
        self.root = root
        self.parts = list(self.build_knob())
        for ob in self.parts:
            if ob.parent is None:
                ob.parent = root
        root.rotation_euler.z = math.radians(self.angle_deg())
        if a.footprint != "native":
            native, factor = scaffold.footprint_normalize(root, target=float(a.footprint),
                                                          cam_z=PANEL_CAM_Z)
            self.notes.append(f"[footprint:native={native:.6g},factor={factor:.6g}]")
        root.scale = tuple(s * a.scale for s in root.scale)
        self.rig = self.studio()
        return root

    def studio(self):
        import rigs

        # the panel light: one rig for panel and knob alike (pass 38, p120 —
        # Sam: "panel light looks fine or better across the board")
        return rigs.knob_studio(self.scene, self.args.scale, local_dir=self.local_dir,
                                stops=rigs.PANEL_STOPS)
