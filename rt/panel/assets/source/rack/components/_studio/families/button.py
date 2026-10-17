"""ButtonScene: the push-button / switch family standard (PLAN 2.9) over
ControlScene. Members: button-bezel, button-console, button-radio, button-stage,
toggle-bat, toggle-guard, toggle-key, toggle-rocker, toggle-slide, toggle-tab.

A generator declares ControlScene's attributes plus, where its canon differs
from the family defaults:

  STATES = ("up", "down")  --state choices; None = free text the generator's
                           validate() checks (button-radio: an index or none)
  STATE = "up"             default --state
  HUE = None               default --hue; None = the part has no emitter and
                           gets neither --hue nor --level
  LEVEL = 1.0              default --level
  LEVEL_RANGE = (0.0, 8.0) inclusive --level range
  LEVEL_HELP               what --level drives on this member
  TEXT = None              default --text; None = no legend, no --text / --font
  FONT = "mono"            default --font
  FONTS = ("sans", "mono") --font choices
  FOOTPRINT = None         default --footprint; None = the member has no
                           --footprint and frames itself (native only)

Flags added to the shared vocabulary:
  --state S          the switch position the part is rendered in
  --hue COLOUR       emitter colour, RRGGBB or r,g,b in 0..1 (members with HUE)
  --level L          emitter level (members with HUE)
  --text T           legend text (members with TEXT)
  --font F           legend face (members with TEXT)
  --footprint R|native
                     (members with FOOTPRINT) the knob family's footprint
                     contract: R scales the part so its apparent radius at the
                     panel plane (scaffold.footprint_normalize's measure,
                     iterated to the size it renders at, max over every pose
                     in footprint_poses(), so all states share one framing) is
                     R, renders a square --res frame through the
                     knob camera (85 mm, 0, 0, 0.29s + 4max(s, 1)) under the
                     house rig at span 2R*s; a knob and a switch at the same R
                     fill the same circle. native: the member's own size,
                     frame, rig and camera

stage(objects, span, cam_z) is the member's last build step: part_root, then
either the native rig (house_rig(span * s), camera(cam_z)) or the footprint
contract above. footprint_poses() is a generator hook: yield once per pose the
framing must cover (default: the built pose only); a member whose extent moves
with --state poses each state, yields, and restores the requested state.
Receipt note `[footprint:native=A,factor=F]` when normalized.

Slots: cap (the key or lever you press), body (housing / receiver), bezel (trim
or escutcheon around the key), legend (printed label), lens (emitter lens);
SLOTS declares any subset plus EXTRA_SLOTS.

Old names a member aliases onto the family flags:
  --pos, --selected                -> --state
  --led-color, --light-color       -> --hue
  --led-level, --light-level       -> --level
  --led-glow                       -> --bloom-strength (scaffold.bloom_flags)

host_cut(name, w, h, depth, above): a through-mounted member's cut in its
host, z = 0 the host's face: a closed box w x h from z = -depth to `above`,
invisible to every ray, tagged "rack_hole" for a composer to cut into the
host under it (rack.py); alone it draws nothing (button-bezel, button-stage).

hue_rgb() -> (r, g, b) of --hue, as parsed (button-radio's convention).

Colour flags: `RRGGBB` hex is sRGB (what a designer's picker gives) and is
decoded to linear; `r,g,b` is linear 0..1 and passes through. linear_rgb(text)
is that conversion; button-bezel and button-stage read every colour flag
through it.

legend_fit(ob, max_w, max_h, cap) scales a size-1 legend text object: cap None
= the largest that fits max_w x max_h; cap = the face's cap height ('H') in
world units, so a row of keys shares one cap height whatever the label length.
A cap that does not fit is clamped to fit, with receipt note
`[cap-height:clamped=MM]`.

Glow is member-specific (button-bezel: compositor bloom on the emission pass;
button-radio: a point light in the lit well); led-indicator bakes a halo into
alpha (families.indicator.halo).
"""

from .control import ControlScene, Flag, color_value, parse_color
from .knob import PANEL_CAM_Z, footprint_value

FAMILY_SLOTS = ("cap", "body", "bezel", "legend", "lens")
FAMILY_SLOT_HELP = {
    "cap": "the key or lever you press",
    "body": "housing / receiver",
    "bezel": "trim or escutcheon around the key",
    "legend": "printed label",
    "lens": "emitter lens",
}


class ButtonScene(ControlScene):
    FAMILY_SLOTS = FAMILY_SLOTS
    FAMILY_SLOT_HELP = FAMILY_SLOT_HELP
    STATES = ("up", "down")
    STATE = "up"
    HUE = None
    LEVEL = 1.0
    LEVEL_RANGE = (0.0, 8.0)
    LEVEL_HELP = "emitter level"
    TEXT = None
    FONT = "mono"
    FONTS = ("sans", "mono")
    FOOTPRINT = None

    @classmethod
    def family_flags(cls):
        states = cls.STATES
        flags = [Flag("--state", str, cls.STATE, choices=states,
                      help="switch position rendered" if states else
                      "switch position rendered (member-validated)")]
        if cls.HUE is not None:
            lo, hi = cls.LEVEL_RANGE
            flags += [Flag("--hue", color_value, cls.HUE, help="emitter colour, RRGGBB or r,g,b in 0..1"),
                      Flag("--level", float, cls.LEVEL, help=f"{cls.LEVEL_HELP}, {lo:g}..{hi:g}")]
        if cls.TEXT is not None:
            flags += [Flag("--text", str, cls.TEXT, help="legend text"),
                      Flag("--font", str, cls.FONT, choices=cls.FONTS, help="legend face")]
        if cls.FOOTPRINT is not None:
            flags += [Flag("--footprint", footprint_value, cls.FOOTPRINT,
                           help="apparent radius at the panel plane in the knob camera "
                                "(square frame, every state one framing), or native")]
        return flags

    # ------------------------------------------------------- footprint contract
    def footprinted(self):
        return self.FOOTPRINT is not None and self.args.footprint != "native"

    def frame_size(self):
        if self.footprinted() and "x" not in self.args.res and self.args.res != "auto":
            n = int(self.args.res)
            return n, n
        return super().frame_size()

    def footprint_poses(self):
        yield

    def stage(self, objects, span, cam_z):
        import bpy
        import scaffold

        a = self.args
        root = self.part_root(objects)
        if not self.footprinted():
            self.house_rig(span * a.scale)
            self.camera(cam_z)
            return root
        target = float(a.footprint)
        factor = None
        for _ in self.footprint_poses():
            # the apparent radius AT the normalized size: a tall part (a bat
            # lever) grows faster than linearly under perspective, so the scale
            # is iterated to its fixed point instead of measured once at 1
            root.scale = (1.0, 1.0, 1.0)
            for _i in range(24):
                _app, step = scaffold.footprint_normalize(root, target=target,
                                                          cam_z=PANEL_CAM_Z)
                if abs(step - 1.0) < 1e-7:
                    break
            pose_factor = root.scale[0]
            factor = pose_factor if factor is None else min(factor, pose_factor)
        native = target / factor
        root.scale = (factor * a.scale,) * 3
        bpy.context.view_layer.update()
        self.notes.append(f"[footprint:native={native:.6g},factor={factor:.6g}]")
        self.house_rig(2.0 * target * a.scale)
        # the knob camera (rigs.knob_studio): 85 mm / 36 mm, dead on
        bpy.ops.object.camera_add(location=(0, 0, 0.29 * a.scale + 4.0 * max(a.scale, 1.0)),
                                  rotation=(0, 0, 0))
        cam = bpy.context.object
        cam.data.lens = 85
        cam.data.sensor_width = 36
        self.scene.camera = cam
        return root

    def validate(self):
        super().validate()
        if self.HUE is not None:
            lo, hi = self.LEVEL_RANGE
            if not lo <= self.args.level <= hi:
                raise SystemExit(f"{self.COMPONENT}: --level must be in {lo:g}..{hi:g}")

    def host_cut(self, name, w, h, depth, above):
        """The cut a through-mounted part needs in its host (module docstring)."""
        import bmesh
        import bpy

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = (v.co.x * w, v.co.y * h, above if v.co.z > 0 else -depth)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(ob)
        ob.visible_camera = False
        for k in ("diffuse", "glossy", "transmission", "volume_scatter", "shadow"):
            setattr(ob, "visible_" + k, False)
        ob["rack_hole"] = True
        return ob

    def hue_rgb(self):
        return parse_color(self.args.hue)

    @staticmethod
    def linear_rgb(text):
        rgb = parse_color(text)
        if "," in str(text):
            return rgb
        return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)

    def legend_fit(self, ob, max_w, max_h, cap=None, mm=None):
        import bpy

        bpy.context.view_layer.update()
        if ob.dimensions.x <= 0 or ob.dimensions.y <= 0:
            raise SystemExit(f"{self.COMPONENT}: the legend produced no geometry")
        fit = min(max_w / ob.dimensions.x, max_h / ob.dimensions.y)
        if cap is not None:
            ref = bpy.data.curves.new("legend cap probe", "FONT")
            ref.body, ref.size, ref.font = "H", ob.data.size, ob.data.font
            probe = bpy.data.objects.new("legend cap probe", ref)
            bpy.context.collection.objects.link(probe)
            bpy.context.view_layer.update()
            want = cap / probe.dimensions.y
            bpy.data.objects.remove(probe, do_unlink=True)
            bpy.data.curves.remove(ref)
            if want > fit:
                got = fit * cap / want / (mm or 1.0)
                self.notes.append(f"[cap-height:clamped={got:.3g}]")
            else:
                fit = want
        ob.scale = (fit, fit, fit)
        bpy.context.view_layer.update()
        return fit
