"""knob-chickenhead: bakelite chickenhead selector (drum + keeled pointer fin) at one position.

  blender -b -P knob_scene.py -- OUT [flags]        flag table: ../README.md

The drum and the lofted fin are modelled at scale 1 on the object Z axis with
the fin nose along object +Y; both objects are turned -90 deg so the nose lies
on local +X, families.KnobScene's pointer axis. The selector is a 5-detent
throw from 150 to 30 deg (counter-clockwise from 3 o'clock), i.e. -60, -30, 0,
+30, +60 deg clockwise from 12 o'clock at --value 0, .25, .5, .75, 1.
`--angle A` (A deg clockwise from 12 o'clock) sets the pointer directly: the
five detent angles spelled as integers alias to their --value, any other angle
overrides the throw and cannot be combined with the throw flags.

The throw is this component's own: a detented selector is a different product
from a 270 deg knob. KnobScene owns flags, footprint, studio (rigs.knob_studio),
camera and receipt. Blender exits 0 after a script exception: callers check
OUT and the receipt line.
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
import meshlib  # noqa: E402
from families import SAME, Alias, Flag, KnobScene  # noqa: E402

R_BASE = 0.30       # base drum radius
NOSE_LEN = 0.575    # fin tip distance from center
H_BASE = 0.105      # base drum height
H_FIN = 0.335       # fin peak height
FIN_REAR = -0.52    # fin rear
FIN_PEAK = -0.13    # y of fin peak
FIN_W0 = 0.145      # fin half-width at its widest (whale-back mass)

COLOURS = {"black": "bakelite-solid", "cream": "bakelite-solid-cream",
           "red": "bakelite-solid-red"}
DETENT_VALUES = {"-60": "0", "-30": "0.25", "0": "0.5", "30": "0.75", "60": "1"}
THROW_FLAGS = ("--value", "--start-deg", "--end-deg", "--detents")


def _shade(ob):
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.shade_smooth()
    return ob


def build_base():
    return meshlib.lathe([(0.001, H_BASE), (R_BASE * 0.86, H_BASE),
                          (R_BASE, H_BASE * 0.55), (R_BASE, 0.0), (0.001, 0.0)],
                         "base", steps=128, shade="select")


def build_fin():
    """Lofted cross-sections along y: pointed-arch top, flat belly. The belly
    rides the base top, then dives toward the panel past the base edge."""
    n_sec, n_arch = 160, 18
    bm = bmesh.new()
    rings = []
    for i in range(n_sec + 1):
        u = i / n_sec
        y = FIN_REAR + u * (NOSE_LEN - FIN_REAR)
        tspan = (NOSE_LEN - y) / (NOSE_LEN - FIN_REAR)
        w = max(FIN_W0 * (tspan ** 0.75), 0.006)
        if y < FIN_PEAK:
            uu = (y - FIN_REAR) / (FIN_PEAK - FIN_REAR)
            ridge = H_BASE * 0.55 + (H_FIN - H_BASE * 0.55) * math.sin(uu * math.pi / 2) ** 1.2
        else:
            uu = (y - FIN_PEAK) / (NOSE_LEN - FIN_PEAK)
            ridge = 0.045 + (H_FIN - 0.045) * (1 - uu) ** 1.35
        # belly: on the drum -> just under its top; past the edge -> dive
        if abs(y) < R_BASE * 0.92:
            zb = H_BASE - 0.012
        else:
            dive = min(1.0, (y - R_BASE * 0.92) / (NOSE_LEN - R_BASE * 0.92)) if y > 0 else 0.0
            zb = (H_BASE - 0.012) * (1 - dive) + 0.012 * dive
        zb = min(zb, ridge - 0.01)
        ring = []
        for k in range(n_arch + 1):             # arch top: (-w, zb) over the keel to (+w, zb)
            s_ = k / n_arch * 2 - 1
            z = zb + (ridge - zb) * (1 - abs(s_) ** 1.7)
            ring.append(bm.verts.new((s_ * w, y, z)))
        for k in range(1, 6):                   # belly: straight back from +w to -w
            s_ = 1 - k / 6 * 2
            ring.append(bm.verts.new((s_ * w, y, zb)))
        rings.append(ring)
    m = len(rings[0])
    for i in range(n_sec):
        r1, r2 = rings[i], rings[i + 1]
        for k in range(m):
            bm.faces.new((r1[k], r1[(k + 1) % m], r2[(k + 1) % m], r2[k]))
    bm.faces.new(tuple(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    return _shade(meshlib.link_bmesh("fin", bm))


class Chickenhead(KnobScene):
    COMPONENT = "knob-chickenhead"
    DEFAULT_OUT = "/tmp/chickenhead.png"
    VALUE = 0.5
    START_DEG = 150.0
    END_DEG = 30.0
    DETENTS = 5
    SLOTS = {"body": COLOURS["black"], "indicator": SAME}
    SLOT_SAME = {"indicator": "body"}
    SLOT_HELP = {"body": "base drum material", "indicator": "keeled pointer fin material"}
    PRESETS = {name: {"body": key, "indicator": SAME} for name, key in COLOURS.items()}
    DEFAULT_PRESET = "black"
    ALIASES = {"preset": [Alias("--color", values=tuple(COLOURS))],
               "value": [Alias("--angle", values=DETENT_VALUES)]}
    FLAGS = (Flag("--angle", float, None,
                  help="pointer angle, deg clockwise from 12 o'clock; overrides the throw"),)

    def __init__(self, argv=None):
        tokens = argv if argv is not None else (
            sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
        self._given = {str(t).partition("=")[0] for t in tokens}
        super().__init__(argv)

    def validate(self):
        super().validate()
        a = self.args
        if a.angle is not None:
            clash = sorted(self._given.intersection(THROW_FLAGS))
            if clash or "--angle" in a.aliased:
                raise SystemExit(f"{self.COMPONENT}: --angle {a.angle:g} overrides the throw; "
                                 f"drop {clash or ['the second --angle']}")

    def angle_deg(self):
        if self.args.angle is not None:
            return 90.0 - self.args.angle
        return super().angle_deg()

    def build_knob(self):
        base, fin = build_base(), build_fin()
        same = self.resolved_slot("indicator") == "body"
        self.bind("body", [base, fin] if same else [base])
        self.bind("indicator", [fin])
        for ob in (base, fin):
            ob.rotation_euler.z = -math.pi / 2
        return [base, fin]


if __name__ == "__main__":
    Chickenhead.main()
