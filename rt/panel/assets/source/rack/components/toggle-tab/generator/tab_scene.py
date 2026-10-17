"""toggle-tab: flat aluminium lever in a panel slot, 2-pos and 3-pos.

  blender -b -P tab_scene.py -- OUT [flags]        flag table: ../README.md

The lever switch of 1970s hi-fi receivers: a solid machined tab standing out
of a rectangular slot, hinged just behind the panel face. z = 0 is the host's
face; the slot is the family's host_cut (a composer cuts the host under it)
lined by a dark tray. No nut, no washer. `center` is the 3-way's rest
position, the tab pointing straight at the camera. families.ButtonScene owns
flags, slots, frame, scale law and receipt. Blender exits 0 after a script
exception: callers check OUT and the receipt line.
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
import meshlib  # noqa: E402
from families.base import Flag  # noqa: E402
from families.button import ButtonScene  # noqa: E402
from families.knob import STANDARD_FOOTPRINT  # noqa: E402

MM = 0.04                   # the bin standard: 1 world unit = 25 mm
TILT = {"up": -25.0, "center": 0.0, "down": 25.0}
TAB_W, TAB_T = 7.0, 3.6     # tab width (x) and thickness (y), mm
TAB_LEN = 14.0              # tab standing out of the panel at center, mm
TAIL = 3.0                  # tab below the panel face, mm
PIVOT = 1.5                 # hinge depth behind the panel face, mm
TIP_R, EDGE_R = 1.0, 0.45   # tip corner radius, long-edge radius, mm
GROOVE = (3.2, 0.3, 3.4)    # finger groove: chord, depth, centre below the tip, mm
SLOT_W, SLOT_H = 8.2, 6.2   # the cut, mm
SLOT_DEPTH = 6.0            # tray depth, mm
TRAY_INSET = 0.05           # tray wall inside the cut wall, mm
TRIM_H = 0.3                # slot trim height on the face, mm
SPAN = 0.68                 # tip reach up to down: the footprint the house rig takes


def tab_profile():
    """(y, z) mm outline of the tab's thickness section, counter-clockwise from
    the tail's -y corner: straight flanks with a shallow finger groove under
    the tip on each, rounded tip corners."""
    h, top = TAB_T / 2, TAB_LEN
    chord, depth, below = GROOVE
    rad = (chord * chord / 4 + depth * depth) / (2 * depth)
    half = math.asin(chord / 2 / rad)
    zc = top - below

    def groove(side, up):
        # arc of the scallop on the flank y = side * h, centre outside the tab
        steps = [-half + 2 * half * k / 10 for k in range(11)]
        pts = [(side * (h + rad - depth - rad * math.cos(a)) , zc + rad * math.sin(a)) for a in steps]
        return pts if up else pts[::-1]

    def corner(side, up):
        steps = [math.pi / 2 * k / 8 for k in range(9)]
        pts = [(side * (h - TIP_R + TIP_R * math.cos(a)), top - TIP_R + TIP_R * math.sin(a))
               for a in steps]
        return pts if up else pts[::-1]

    return ([(-h, -TAIL), (h, -TAIL)] + groove(1, True) + corner(1, True)
            + corner(-1, False) + groove(-1, False))


def extrude_x(name, profile, width):
    """A (y, z) outline extruded along x, centred."""
    bm = bmesh.new()
    a = [bm.verts.new((-width / 2, y, z)) for y, z in profile]
    b = [bm.verts.new((width / 2, y, z)) for y, z in profile]
    n = len(profile)
    bm.faces.new(a)
    bm.faces.new(b[::-1])
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[j], a[i], b[i], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return meshlib.link_bmesh(name, bm)


def open_tray(name, w, h, depth):
    """A box w x h from z = -depth to 0 without its top face."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = (v.co.x * w, v.co.y * h, (v.co.z - 0.5) * depth)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z > 0.5], context="FACES_ONLY")
    return meshlib.link_bmesh(name, bm)


def frame(name, w, h, band, height):
    """A flat frame on the face, z 0 to height, `band` wide round a w x h opening."""
    bm = bmesh.new()
    loops = []
    for z in (0.0, height):
        for grow in (0.0, band):
            hx, hy = w / 2 + grow, h / 2 + grow
            loops.append([bm.verts.new(p + (z,)) for p in
                          ((hx, hy), (-hx, hy), (-hx, -hy), (hx, -hy))])
    in0, out0, in1, out1 = loops
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((in1[i], in1[j], out1[j], out1[i]))      # top
        bm.faces.new((out1[i], out1[j], out0[j], out0[i]))    # outer wall
        bm.faces.new((in0[i], in0[j], in1[j], in1[i]))        # inner wall
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return meshlib.link_bmesh(name, bm)


class ToggleTab(ButtonScene):
    COMPONENT = "toggle-tab"
    DEFAULT_OUT = "/tmp/toggle-tab.png"
    RES = 640
    SAMPLES = 240
    STATES = tuple(TILT)
    STATE = "up"
    FOOTPRINT = STANDARD_FOOTPRINT
    SLOTS = {
        "cap": "brushed@rough_lo=0.22,rough_hi=0.42,aniso=0.6",
        "body": "coating-cavity-dark",
        "bezel": "steel-black-oxide",
    }
    SLOT_HELP = {
        "cap": "the tab",
        "body": "slot interior",
        "bezel": "slot trim (with --trim)",
    }
    FLAGS = [Flag("--trim", float, 0.0,
                  help="slot trim band on the host face, mm; 0 = none (a bare slot)")]

    def frame_aspect(self):
        return 0.75

    def validate(self):
        super().validate()
        if not 0.0 <= self.args.trim <= 3.0:
            raise SystemExit(f"{self.COMPONENT}: --trim must be in 0..3 mm")

    def build(self):
        a = self.args
        parts = []
        tray = open_tray("slot tray", (SLOT_W - 2 * TRAY_INSET) * MM,
                         (SLOT_H - 2 * TRAY_INSET) * MM, SLOT_DEPTH * MM)
        self.bind("body", [tray])
        parts.append(tray)
        parts.append(self.host_cut("slot cut", SLOT_W * MM, SLOT_H * MM, (SLOT_DEPTH + 0.2) * MM,
                                   (TRIM_H if a.trim else 0.1) * MM))
        if a.trim:
            trim = frame("slot trim", SLOT_W * MM, SLOT_H * MM, a.trim * MM, TRIM_H * MM)
            meshlib.bevel(trim, 0.08 * MM, segments=2)
            self.bind("bezel", [trim])
            parts.append(trim)

        self.tab = extrude_x("tab", [(y * MM, z * MM) for y, z in tab_profile()], TAB_W * MM)
        meshlib.bevel(self.tab, EDGE_R * MM, segments=5, angle_deg=40.0)
        meshlib.smooth(self.tab)
        self.tab.modifiers.new("flat faces", "WEIGHTED_NORMAL").keep_sharp = True
        self.bind("cap", [self.tab])
        parts.append(self.tab)
        self.pose(a.state)
        self.stage(parts, SPAN, 2.6)

    def pose(self, state):
        piv = Matrix.Translation(Vector((0, 0, -PIVOT * MM)))
        self.tab.matrix_basis = (piv @ Matrix.Rotation(math.radians(TILT[state]), 4, "X")
                                 @ piv.inverted())

    def footprint_poses(self):
        # one framing for every position: the tip's reach at up/down sets it
        for state in self.STATES:
            self.pose(state)
            yield
        self.pose(self.args.state)


if __name__ == "__main__":
    ToggleTab.main()
