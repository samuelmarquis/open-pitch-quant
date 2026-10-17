"""RailScene: the horizontal-rail family, over ComponentScene.
Members: rail-cross, rail-position, rail-range.

Three commissioned mechanisms that live in the same panel strip and must NOT be
confusable at product scale. They share this layer's slots, scale contract,
engraving and compositing rules; each member supplies only its own mechanism.

A generator declares ComponentScene's attributes plus:

  TRAVEL = 3.20       default --length, the slot travel in world units
  MECHANISM           short name used in the receipt note

Flags this family adds:
  --length L          slot travel, world units at scale 1
  --ticks PATTERN     none | monotonic | bipolar | landmark — BAKED geometry
  --major N           major tick intervals
  --minor N           minor ticks per major interval
  --tick-fill F       auto | white | dark | any matlib key
  --tick-color r,g,b  override the fill pigment, linear 0..1
  --panel KEY|none    the board the rail is cut into; `none` = cut-in
  --cut-in on|off     plate as shadow catcher, backing hidden
  --px-per-unit N     product scale, for the receipt and frame sizing

SCALE — the contract the whole family is sized by
-------------------------------------------------
    1 world unit at the panel plane = 42 logical px at 100% product scale

`PX_PER_UNIT` is that number. It comes from the knob footprint standard
(families.knob.STANDARD_FOOTPRINT: every canonical knob is normalized to an
apparent radius of 0.500 at z = 0, so a standard knob is 1.0 world unit across)
pinned to the product's 42 px standard knob. A rail and a knob rendered at the
same `--px-per-unit` composite with no transform.

MARKINGS — baked geometry, runtime text
---------------------------------------
Tick GEOMETRY is baked and parameterized: positions, major/minor hierarchy, a
zero witness where the domain has one. Semantic text is NOT: endpoint names,
parameter names, values, units and landmark letters are the consumer's, drawn
at runtime over the rendered part. An A/E/I/O/U rail bakes five major ticks; the
letters are composited.

`--tick-fill auto` reads the BUILT panel material's luminance and picks a dark
fill for a pale board, a white one for a dark board — walking the node chain
when the colour is procedural (wood, catalin). In cut-in mode there is no panel
to read, so `auto` is refused and the caller must name the fill: the component
cannot see the board it will be composited onto.

CUT-IN — parts do not paint panels
----------------------------------
`--cut-in on` makes the plate a shadow catcher and hides the backing, so the
render carries the mechanism and the occlusion its cut casts and nothing else.
The consumer composites that over their own panel and the cut reads as a cut
into THEIR material. `--panel KEY` is the standalone/demo path: it builds a
board so the rail can be seen in isolation.
"""

import math

from .base import ComponentScene, Flag
from .knob import PANEL_CAM_Z, STANDARD_FOOTPRINT

# 1 world unit at the panel plane = this many logical px at 100% product scale.
# STANDARD_FOOTPRINT is an apparent RADIUS, so a standard knob is 2x it across.
STANDARD_KNOB_PX = 42.0
PX_PER_UNIT = STANDARD_KNOB_PX / (2.0 * STANDARD_FOOTPRINT)

CAM_LENS, CAM_SENSOR = 85.0, 36.0     # the corpus dead-on panel camera
TICK_PATTERNS = ("none", "monotonic", "bipolar", "landmark")
FILL_WHITE = "engraving-fill-white"
FILL_DARK = "engraving-fill"

FAMILY_SLOTS = ("plate", "cursor", "tick", "bridge", "window")
FAMILY_SLOT_HELP = {
    "plate": "the fixed board the slot is cut into",
    "cursor": "the moving part: cap, carriage or jaws",
    "tick": "engraved-and-filled markings",
    "bridge": "range rail only: the interval span",
    "window": "dark field behind a cursor hairline",
}


def _lum(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def panel_luminance(mat):
    """The board's Base Color luminance, or None if nothing constant can be read.

    Read off the BUILT material, never inferred from the key's name: matlib
    defines `ink-flat` as a LIGHT label ink, so a fill picked by the word in the
    key rendered white where dark was wanted. A flat Base Color is read
    directly; a driven one (catalin's marble, wood's grain — exactly the pale
    boards that need a dark fill) has its chain walked and every constant colour
    averaged, ColorRamp stops included.
    """
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return None
    sock = bsdf.inputs["Base Color"]
    if not sock.is_linked:
        return _lum(sock.default_value[:3])
    seen, stack, cols = set(), [sock.links[0].from_node], []
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        if node.type == "VALTORGB":
            cols += [e.color[:3] for e in node.color_ramp.elements]
        for inp in node.inputs:
            if inp.is_linked:
                stack.append(inp.links[0].from_node)
            elif inp.type == "RGBA":
                cols.append(inp.default_value[:3])
    return sum(_lum(c) for c in cols) / len(cols) if cols else None


class RailScene(ComponentScene):
    FAMILY_SLOTS = FAMILY_SLOTS
    FAMILY_SLOT_HELP = FAMILY_SLOT_HELP
    TRAVEL = 3.20
    MECHANISM = None
    PX_PER_UNIT = PX_PER_UNIT

    @classmethod
    def family_flags(cls):
        return [
            Flag("--length", float, cls.TRAVEL,
                 help="slot travel, world units at scale 1"),
            Flag("--ticks", str, "monotonic", choices=TICK_PATTERNS,
                 help="baked tick pattern; semantic text stays runtime"),
            Flag("--major", int, 4, help="major tick intervals"),
            Flag("--minor", int, 5, help="minor ticks per major interval"),
            Flag("--tick-fill", str, "auto",
                 help="auto (follow the panel) | white | dark | any matlib key"),
            Flag("--tick-color", str, None,
                 help="override the fill pigment, 'r,g,b' linear 0..1"),
            Flag("--panel", str, "none",
                 help="board the rail is cut into; `none` = cut-in compositing"),
            Flag("--cut-in", str, None, choices=("on", "off"),
                 help="plate as shadow catcher; default on when --panel is none"),
            Flag("--px-per-unit", float, PX_PER_UNIT,
                 help="product scale: logical px per world unit at the panel plane"),
        ]

    # ---------------------------------------------------------------- resolve
    def validate(self):
        super().validate()
        a = self.args
        if a.length <= 0:
            raise SystemExit(f"{self.COMPONENT}: --length must be positive")
        if a.major < 0 or a.minor < 1:
            raise SystemExit(f"{self.COMPONENT}: --major >= 0 and --minor >= 1")
        self.cut_in = (a.cut_in == "on") if a.cut_in else (a.panel == "none")
        if self.cut_in and a.panel != "none" and a.cut_in == "on":
            pass                                  # a board that is also a catcher: allowed
        if a.tick_fill == "auto" and a.panel == "none":
            raise SystemExit(
                f"{self.COMPONENT}: --tick-fill auto needs a panel to read. In cut-in mode "
                "the component cannot see the board it will be composited onto — name the "
                "fill explicitly (--tick-fill white|dark|<matlib key>).")
        self.tint = None
        if a.tick_color:
            try:
                self.tint = tuple(float(v) for v in a.tick_color.split(","))
                if len(self.tint) != 3:
                    raise ValueError
            except ValueError:
                raise SystemExit(f"{self.COMPONENT}: --tick-color wants 'r,g,b' linear 0..1")

    def tick_key(self, panel_mat):
        """(matlib key, note) for the engraving fill; see the module docstring."""
        choice = self.args.tick_fill
        if choice == "white":
            return FILL_WHITE, "explicit"
        if choice == "dark":
            return FILL_DARK, "explicit"
        if choice != "auto":
            return choice, "explicit-key"
        lum = panel_luminance(panel_mat)
        if lum is None:
            return FILL_WHITE, "auto-unreadable-panel"
        return (FILL_DARK, f"auto-lum{lum:.3f}-dark") if lum > 0.18 \
            else (FILL_WHITE, f"auto-lum{lum:.3f}-white")

    # ------------------------------------------------------------------ frame
    def frame_size(self):
        """Frame the travel plus a margin, at --px-per-unit. The rail is modelled
        at true product size and the frame is derived from it, so the render can
        never flatter the mechanism's legibility."""
        a = self.args
        scale = max(a.scale, 1.0)
        w = (a.length + self.MARGIN_X * 2) * scale
        h = self.BODY_H * scale
        ppu = a.px_per_unit
        return max(int(round(w * ppu)), 16), max(int(round(h * ppu)), 16)

    MARGIN_X = 0.55          # world units of board either side of the travel
    BODY_H = 152.0 / PX_PER_UNIT    # the product's lower control body, 3.619 wu
    FRAME_BLEED = 1.12       # board built past the frame: a product crop is cut
                             # out of a larger board, never a board on a backdrop

    # ------------------------------------------------------------ shared tail
    def finish_rail(self, parts, apertures, z_top, travel):
        """Board, materials, rig, frame and receipt — the same for every member.

        A member builds only its own mechanism into `parts` (slot -> objects)
        and hands the aperture rects over; everything after that is family
        business, which is what keeps the three visually comparable.
        """
        import bpy  # noqa: F401  (Blender-only; families imports without it)

        import railkit
        import rigs
        from matlib import build as build_mat

        a = self.args
        frame_w = (a.length + self.MARGIN_X * 2) * self.FRAME_BLEED
        frame_h = self.BODY_H * 1.06
        plate = railkit.board(frame_w, frame_h, z_top, 0.16, apertures)
        # a composer with the real host plate in its scene cuts these into it
        # (rack.py) in place of this board
        plate["apertures"] = [v for r in apertures for v in r]
        plate["z_top"] = z_top
        parts.setdefault("plate", []).append(plate)

        # In cut-in mode there is no consumer board here, so the plate carries
        # the family's own default key purely to catch light; it is a shadow
        # catcher and paints nothing.
        panel_key = a.panel if a.panel != "none" else self.SLOTS["plate"]
        panel_mat = build_mat(panel_key)
        tick_key, tick_note = self.tick_key(panel_mat)
        for slot, objs in parts.items():
            if not objs:
                continue
            if slot == "plate":
                mat = panel_mat
            elif slot == "tick":
                mat = build_mat(tick_key, **({"color": self.tint} if self.tint else {}))
            else:
                mat = build_mat(self.SLOTS[slot])
            for ob in objs:
                ob.data.materials.append(mat)

        if self.cut_in:
            railkit.shadow_catcher(parts["plate"])

        # The house rig, scale-invariant, at the board's span: lit as panel-board.
        rig = rigs.knob_studio(self.scene, scale=max(frame_w, frame_h),
                               local_dir=str(self.local_dir), camera=False,
                               stops=rigs.PANEL_STOPS)

        # panel_camera frames a board by its own rule (w to ~80%), which does
        # NOT land on --px-per-unit. The scale contract is the whole point of
        # this family, so the camera is pinned here: sensor fit HORIZONTAL makes
        # the frame WIDTH authoritative and independent of the aspect, and the
        # distance is solved for exactly the world width we mean to show.
        # (No camera when a composer builds the rail into its own scene: its
        # stubbed rig hands back no world.)
        if rig["world"] is not None:
            cam = rigs.panel_camera(self.scene, frame_w, frame_h)
            cam.data.lens, cam.data.sensor_width = CAM_LENS, CAM_SENSOR
            cam.data.sensor_fit = "HORIZONTAL"
            view_w = (a.length + self.MARGIN_X * 2) * max(a.scale, 1.0)
            cam.location = (0.0, 0.0, (view_w / 2.0) / math.tan(
                math.atan((CAM_SENSOR / 2.0) / CAM_LENS)))
            cam.rotation_euler = (0.0, 0.0, 0.0)

        self.scene.render.film_transparent = self.cut_in
        px, py = self.frame_size()
        self.scene.render.resolution_x, self.scene.render.resolution_y = px, py
        self.notes.append(f"[frame:{px}x{py},ppu:{a.px_per_unit:g}]")
        self.notes.append(f"[tick:{tick_key}({tick_note})]")
        # The RESOLVED mode, not the raw flag: --cut-in defaults to None and is
        # decided by --panel, so a receipt showing `cut-in=none` would otherwise
        # read as "off" when the render is in fact a cut-in.
        self.notes.append(f"[cut-in:{'on' if self.cut_in else 'off'}]")
        self.notes.append(f"[mechanism:{self.MECHANISM},travel:{travel:.4f}]")
