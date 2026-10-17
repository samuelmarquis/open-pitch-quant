"""HardwareScene: the panel-hardware family standard (PLAN 2.9) over ComponentScene.

Members: jack-socket, rack-hardware, vent-grille. Geometry is authored in
millimetres at 25 mm per world unit (the bin standard); a part is mounted on or
through a swatch of family panel.

A generator declares ComponentScene's attributes plus, where its canon differs
from the family defaults:

  FORMS = {}              {form: geometry spec}: the geometry roster (`--form`)
  FORM = None             default --form (required when FORMS is not empty)
  EXTRA_SLOTS = ()        slots beyond face, finish, fastener
  FILL = 0.86             default --fill
  MANIFEST_CONTRACT       name of the sidecar JSON contract ("mate/1", ...)

PRESETS are the component's variant roster: each bundles a `--form` and slot
keys. `--variant` is the preset flag (PRESET_FLAG = "variant"; the receipt key
is `variant`) and `--preset` its plain alias, so `--variant NAME` and `--preset
NAME` are the same flag. DEFAULT_PRESET is the canon tile.

Flags added to the shared vocabulary (SCALE_SUPPORTED is False: parts are
authored at their physical size; RES 512, SAMPLES 256):
  --form NAME          geometry roster entry (members with FORMS)
  --fill F             subject width as a fraction of the frame
  --manifest PATH      write the component's sidecar JSON ('' = none)

Slots: face (the panel), finish (the part's primary hardware finish), fastener
(screw heads), plus EXTRA_SLOTS; SLOTS may declare any subset.

Helpers for build():
  form                          FORMS[--form]
  studio(span, x=0.0)           the house light: rigs.knob_studio at scale `span`
                                (no camera) at rigs.PANEL_STOPS — a swatch of
                                panel is a flat face, lit as panel-board lights
                                its plate — centred over x; returns the rig dict
  dead_on_camera(half, plane_z, tilt_deg=0.0)
                                85 mm camera framing a subject of half-width
                                `half` (world) to --fill at plane z, tilted
                                down about X; returns (camera, distance, half_fov)
  brush_uv_wanted(slot)         the slot's key is one of BRUSH_UV_KEYS (keys whose
                                parts carry a cube-projected `brush` UV layer in
                                the generators' canon meshes; no library builder
                                reads it)
  write_manifest(data)          JSON to --manifest (when set); render() prints
                                `MANIFEST_CONTRACT <json>` after the receipt
"""

import json
import math
from pathlib import Path

from .base import ComponentScene, Flag

FAMILY_SLOTS = ("face", "finish", "fastener")
FAMILY_SLOT_HELP = {
    "face": "panel material the part is mounted on or through",
    "finish": "the part's primary hardware finish",
    "fastener": "screw head material",
}
BRUSH_UV_KEYS = frozenset({"brushed", "worn-steel"})
LENS_MM, SENSOR_MM = 85.0, 36.0


class HardwareScene(ComponentScene):
    FORMS = {}
    FORM = None
    EXTRA_SLOTS = ()
    FILL = 0.86
    MANIFEST_CONTRACT = None
    RES = 512
    SAMPLES = 256
    SCALE_SUPPORTED = False
    PRESET_FLAG = "variant"

    # ------------------------------------------------------------------ schema
    @classmethod
    def family_flags(cls):
        flags = []
        if cls.FORMS:
            flags.append(Flag("--form", str, cls.FORM, choices=tuple(cls.FORMS),
                              help="geometry roster entry"))
        flags.append(Flag("--fill", float, cls.FILL,
                          help="subject width as a fraction of frame"))
        flags.append(Flag("--manifest", str, "",
                          help=f"write the {cls.MANIFEST_CONTRACT or 'sidecar'} JSON here"))
        return flags

    @classmethod
    def slot_help(cls, slot):
        return cls.SLOT_HELP.get(slot, FAMILY_SLOT_HELP.get(slot, f"{slot} material"))

    @classmethod
    def schema(cls):
        stray = sorted(set(cls.SLOTS) - set(FAMILY_SLOTS) - set(cls.EXTRA_SLOTS))
        if stray:
            raise TypeError(f"{cls.__name__}: slots {stray} are not family slots "
                            f"{FAMILY_SLOTS}; declare them in EXTRA_SLOTS")
        if cls.FORMS and cls.FORM not in cls.FORMS:
            raise TypeError(f"{cls.__name__}: FORM {cls.FORM!r} not in FORMS")
        return super().schema()

    @classmethod
    def family_aliases(cls):
        return {"variant": ["--preset"]}

    def validate(self):
        super().validate()
        a = self.args
        if a.fill <= 0.0:
            raise SystemExit(f"{self.COMPONENT}: --fill must be positive")

    # ----------------------------------------------------------------- helpers
    @property
    def form(self):
        return self.FORMS[self.args.form]

    def brush_uv_wanted(self, slot):
        return self.slot_key(slot)[0] in BRUSH_UV_KEYS

    def studio(self, span, x=0.0):
        import rigs

        rig = rigs.knob_studio(self.scene, scale=span, local_dir=self.local_dir, camera=False,
                               stops=rigs.PANEL_STOPS)
        if x:
            for ob in (rig["key"], rig["kicker"], rig["fill"], rig["zenith"], rig["rake"]):
                if ob is not None:
                    ob.location.x += x
        return rig

    def dead_on_camera(self, half, plane_z, tilt_deg=0.0):
        import bpy

        tilt = math.radians(tilt_deg)
        half_fov = math.atan((SENSOR_MM / 2) / LENS_MM)
        dist = plane_z + (half / self.args.fill) / math.tan(half_fov)
        bpy.ops.object.camera_add(location=(0, -dist * math.sin(tilt), dist * math.cos(tilt)),
                                  rotation=(tilt, 0, 0))
        cam = bpy.context.object
        cam.data.lens = LENS_MM
        self.scene.camera = cam
        return cam, dist, half_fov

    def write_manifest(self, data):
        self.manifest = data
        if self.args.manifest:
            path = Path(self.args.manifest)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2) + "\n")

    def render(self):
        line = super().render()
        data = getattr(self, "manifest", None)
        if data is not None and self.MANIFEST_CONTRACT:
            print(f"{self.MANIFEST_CONTRACT} " + json.dumps(data), flush=True)
        return line
