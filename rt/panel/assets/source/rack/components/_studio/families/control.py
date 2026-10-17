"""ControlScene: the layer the control families (button.py, fader.py,
indicator.py) share, over ComponentScene.

A generator declares ComponentScene's attributes plus:

  RES                 default --res: `N` (frame height in px; width is
                      round(N * frame_aspect())), `WxH`, or `auto` (canon_frame())
  FAMILY_SLOTS        set by the family: its standard slot names
  EXTRA_SLOTS = ()    slot names beyond FAMILY_SLOTS
  SCALE_HELP, RES_HELP
                      --scale / --res help text (default: SCALE_LAW and the
                      frame-height contract)

and may override the frame hooks:

  frame_aspect()      width / height of the frame for `--res N` (default 1.0)
  canon_frame()       (w, h) for `--res auto`
  frame_size()        (w, h) from --res; the resolved frame is `self.frame` and
                      the receipt note `[frame:WxH]`

Slots bind through ComponentScene.bind (derived colours and levels as `params`;
legend text objects bind like meshes).

Scale law for members whose geometry does not carry --scale itself:
  part_root(objects)  parents the objects to a `part root` empty scaled by --scale
  camera(z, lens=85)  dead-on camera at (0, 0, z * max(scale, 1)): the canon
                      frame holds a smaller part; a larger one pulls back

Light: house_rig(span) is the house rig, rigs.knob_studio at `span` (the part's
footprint in world units, after --scale) and PANEL_STOPS, no camera — the
light the knob families and panel-board ship. The rig is scale-invariant, so
the part is lit the same at every --scale.

parse_color(text) -> (r, g, b): `RRGGBB` (per channel /255) or `r,g,b` in 0..1.

run(): factory-empty scene -> scaffold.setup_render at the frame -> build ->
render -> receipt.
"""

from .base import ComponentScene, Flag, scaffold

AUTO = "auto"
SCALE_LAW = ("physical size: part and house rig zoom (lit the same at every scale); the camera "
             "holds the canon frame up to 1 and pulls back above")


def parse_color(text):
    value = str(text).strip().lstrip("#")
    if "," in value:
        try:
            rgb = tuple(float(part) for part in value.split(","))
        except ValueError:
            raise SystemExit(f"colour {text!r}: r,g,b must be numbers in 0..1")
        if len(rgb) != 3 or any(c < 0.0 or c > 1.0 for c in rgb):
            raise SystemExit(f"colour {text!r}: r,g,b must be three values in 0..1")
        return rgb
    if len(value) != 6:
        raise SystemExit(f"colour {text!r} is not RRGGBB or r,g,b")
    try:
        return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        raise SystemExit(f"colour {text!r} is not RRGGBB or r,g,b")


def color_value(text):
    parse_color(text)
    return str(text)


color_value.__name__ = "RRGGBB|r,g,b"


def res_value(text):
    """`N`, `WxH` or `auto`, kept as given."""
    value = str(text).strip().lower()
    if value == AUTO:
        return value
    try:
        dims = [int(v) for v in value.split("x")]
    except ValueError:
        raise SystemExit(f"--res {text!r} is not N, WxH or auto")
    if len(dims) not in (1, 2) or min(dims) < 16:
        raise SystemExit(f"--res {text!r}: N or WxH, each at least 16")
    return value


res_value.__name__ = "N|WxH|auto"


class ControlScene(ComponentScene):
    FAMILY_SLOTS = ()
    FAMILY_SLOT_HELP = {}
    EXTRA_SLOTS = ()
    SCALE_HELP = SCALE_LAW
    RES_HELP = None

    # ------------------------------------------------------------------ schema
    @classmethod
    def slot_help(cls, slot):
        return cls.SLOT_HELP.get(slot, cls.FAMILY_SLOT_HELP.get(slot, f"{slot} material"))

    @classmethod
    def schema(cls):
        stray = sorted(set(cls.SLOTS) - set(cls.FAMILY_SLOTS) - set(cls.EXTRA_SLOTS))
        if stray:
            raise TypeError(f"{cls.__name__}: slots {stray} are not family slots "
                            f"{cls.FAMILY_SLOTS}; declare them in EXTRA_SLOTS")
        schema = super().schema()
        res = schema.flags["--res"]
        res.type = res_value
        res.default = str(cls.RES)
        res.help = cls.RES_HELP or ("frame height px (width from the part's aspect), or WxH"
                                    + (", or auto (the part's canon frame)"
                                       if str(cls.RES) == AUTO else ""))
        schema.flags["--scale"].help = cls.SCALE_HELP
        return schema

    # ------------------------------------------------------------------- frame
    def frame_aspect(self):
        return 1.0

    def canon_frame(self):
        raise SystemExit(f"{self.COMPONENT}: --res auto has no canon frame")

    def frame_size(self):
        value = self.args.res
        if value == AUTO:
            return tuple(self.canon_frame())
        dims = [int(v) for v in value.split("x")]
        if len(dims) == 2:
            return dims[0], dims[1]
        return round(dims[0] * self.frame_aspect()), dims[0]

    def validate(self):
        values = self.args.values
        given = values["res"]
        self.frame = self.frame_size()
        if min(self.frame) < 16:
            raise SystemExit(f"{self.COMPONENT}: frame {self.frame} is under 16 px")
        values["res"] = min(self.frame)          # ComponentScene.validate compares an int
        try:
            super().validate()
        finally:
            values["res"] = given

    # ------------------------------------------------------------- scale + rig
    def part_root(self, objects):
        import bpy

        root = bpy.data.objects.new("part root", None)
        bpy.context.collection.objects.link(root)
        for ob in objects:
            if ob.parent is None:
                ob.parent = root
        s = self.args.scale
        root.scale = (s, s, s)
        return root

    def house_rig(self, span):
        import rigs

        return rigs.knob_studio(self.scene, scale=span, local_dir=self.local_dir,
                                camera=False, stops=rigs.PANEL_STOPS)

    def camera(self, z, lens=85):
        import bpy

        bpy.ops.object.camera_add(location=(0, 0, z * max(self.args.scale, 1.0)),
                                  rotation=(0, 0, 0))
        cam = bpy.context.object
        cam.data.lens = lens
        self.scene.camera = cam
        return cam

    # ------------------------------------------------------------------ render
    def run(self):
        import bpy

        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        w, h = self.frame
        self.device = scaffold.setup_render(self.scene, self.args, size=self.frame, **self.RENDER)
        self.notes.append(f"[frame:{w}x{h}]")
        self.build()
        return self.render()


__all__ = ["AUTO", "SCALE_LAW", "ControlScene", "Flag", "color_value", "parse_color", "res_value"]
