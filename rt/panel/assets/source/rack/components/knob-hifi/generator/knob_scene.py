"""knob-hifi: the solid machined-aluminium hi-fi volume knob at one value.

  blender -b -P knob_scene.py -- OUT [flags]        flag table: ../README.md

One billet on the object Z axis: skirt, ledge and cap wall; a real-geometry
diamond knurl band (two opposing helical groove sets, 45 deg run-out chamfers);
a diamond-cut chamfer at the top edge; the top face with an engraved slot and
its paint fill along local +X. Measured from Kilo International OED-series
knobs (H/D 0.805, knurl 0.548 D, 77 grooves per set at ~27.5 deg).

The top face is the `cap` slot. `blasted` and `turned` are cap values that
resolve to the preset's finish (bead-blast top or fine-turned face); any key also
works. families.KnobScene owns flags, slots, throw, studio, camera and receipt;
the receipt adds `[knurl:grooves=N,axial-pitch=P]`.
Blender exits 0 after a script exception: callers check OUT and the receipt.
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
import meshlib  # noqa: E402
from families import Alias, KnobScene  # noqa: E402

R = 0.460                  # knurl crest radius
KNURL_N = 77               # grooves around, per helix set
KNURL_ANGLE = 27.5         # helix angle from the knob axis, degrees
KNURL_DEPTH = 0.0125       # crest to root (45-degree flanks)
KNURL_FLAT = 0.75          # crest truncation level (flat diamond tops)
Z_R_BOT = 0.153            # knurl reaches full diameter
Z_R_TOP = 0.657
R_CHAMFER_TOP = R - KNURL_DEPTH - 0.006    # run-out chamfers cut past the root
R_CHAMFER_BOT = R - KNURL_DEPTH - 0.010
Z_LEDGE = Z_R_TOP + (R - R_CHAMFER_TOP)
Z_BAND_LO = Z_R_BOT - (R - R_CHAMFER_BOT)
R_SKIRT = 0.4296
R_CAP = 0.4255
Z_TOP = 0.741
# Diamond-cut chamfer: a flat facet at CUT_SLOPE with small edge breaks. From the
# dead-on camera the keybar mirrors in a 12-18 degree facet, the kicker at ~22
# degrees and the fill only at ~1-4 degrees, which the inner edge break sweeps.
CUT_SLOPE = 15.0
CUT_WIDTH = 0.022          # radial width
CUT_BREAK_IN = 0.0045
CUT_BREAK_OUT = 0.0022
R_FACE = R_CAP - CUT_WIDTH
E = 0.0015                 # edge-loop inset next to hard corners
SLOT_DEPTH = 0.006
SLOT_HALF_W = 0.0105
SLOT_OUTER = R_FACE - 0.040
SLOT_INNER = SLOT_OUTER - 0.235


def cut_profile(n=44):
    def smooth(t):
        t = min(max(t, 0.0), 1.0)
        return t * t * (3.0 - 2.0 * t)

    def slope(s):
        if s < CUT_BREAK_IN:
            return CUT_SLOPE * smooth(s / CUT_BREAK_IN)
        if s > CUT_WIDTH - CUT_BREAK_OUT:
            return CUT_SLOPE + (60.0 - CUT_SLOPE) * smooth(
                (s - CUT_WIDTH + CUT_BREAK_OUT) / CUT_BREAK_OUT)
        return CUT_SLOPE

    pts = [(R_FACE, Z_TOP)]
    z = Z_TOP
    for i in range(n):
        s0, s1 = CUT_WIDTH * i / n, CUT_WIDTH * (i + 1) / n
        z -= (s1 - s0) * math.tan(math.radians(slope(0.5 * (s0 + s1))))
        pts.append((R_FACE + s1, z))
    return pts


CUT_PROFILE = cut_profile()
Z_CUT = CUT_PROFILE[-1][1]


def lathe(profile, name, smooth_angle=40.0):
    return meshlib.lathe(profile, name, steps=288, merge=1e-6, recalc_normals=True,
                         shade=smooth_angle)


def stadium(name, x0, x1, half_w, z0, z1, steps=16):
    """Straight slot with round ends along +X, as a closed prism."""
    outline = []
    for i in range(steps + 1):
        t = -0.5 * math.pi + math.pi * i / steps
        outline.append((x1 + half_w * math.cos(t), half_w * math.sin(t)))
    for i in range(steps + 1):
        t = 0.5 * math.pi + math.pi * i / steps
        outline.append((x0 + half_w * math.cos(t), half_w * math.sin(t)))
    bm = bmesh.new()
    top = [bm.verts.new((x, y, z1)) for x, y in outline]
    bot = [bm.verts.new((x, y, z0)) for x, y in outline]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    n = len(outline)
    for i in range(n):
        bm.faces.new((bot[i], bot[(i + 1) % n], top[(i + 1) % n], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return meshlib.link_bmesh(name, bm)


def billet_body(name):
    return lathe([
        (0.0, 0.0),
        (R_SKIRT - 0.008, 0.0),
        (R_SKIRT - 0.0025, 0.0006),
        (R_SKIRT, 0.006),
        (R_SKIRT, 0.006 + E),
        (R_SKIRT, Z_BAND_LO - E),
        (R_SKIRT, Z_BAND_LO),
        (R_SKIRT + E, Z_BAND_LO),
        (R_CHAMFER_BOT - E, Z_BAND_LO),
        (R_CHAMFER_BOT, Z_BAND_LO),
        (R_CHAMFER_BOT - 0.004, Z_BAND_LO + 0.01),      # hidden core
        (R_CHAMFER_TOP - 0.004, Z_LEDGE - 0.01),
        (R_CHAMFER_TOP, Z_LEDGE),
        (R_CHAMFER_TOP - E, Z_LEDGE),
        (R_CAP + E, Z_LEDGE),
        (R_CAP, Z_LEDGE),
        (R_CAP, Z_LEDGE + E),
        (R_CAP, Z_CUT - E),
        (R_CAP, Z_CUT),
    ], name)


def engraved_face(name):
    face = lathe([(R_FACE, Z_TOP), (R_FACE - E, Z_TOP), (0.0, Z_TOP), (0.0, Z_TOP - 0.04),
                  (R_FACE, Z_TOP - 0.04)], name, smooth_angle=30.0)
    cutter = stadium("indicator cutter", SLOT_INNER, SLOT_OUTER, SLOT_HALF_W,
                     Z_TOP - SLOT_DEPTH, Z_TOP + 0.01)
    boolean = face.modifiers.new("engrave", "BOOLEAN")
    boolean.operation = "DIFFERENCE"
    boolean.solver = "EXACT"
    boolean.object = cutter
    meshlib.activate(face)
    bpy.ops.object.modifier_apply(modifier=boolean.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return face


FINISHES = ("silver", "black", "champagne", "blue")
CHAMFER = {"champagne": "aluminium-diamond-cut-champagne"}
FILL = {"black": "engraving-fill-flat-light", "blue": "engraving-fill-flat-light"}
TOP_FACES = {
    "blasted": "aluminium-bead-blast-anodized-{preset}@rough=0.4,metallic=0.85",
    "turned": "aluminium-fine-turned-{preset}",
}


class HifiKnob(KnobScene):
    COMPONENT = "knob-hifi"
    DEFAULT_OUT = "/tmp/knob-hifi.png"
    EXTRA_SLOTS = ("knurl",)
    SLOTS = {
        "body": "aluminium-bead-blast-anodized-silver",
        "knurl": "aluminium-bead-blast-anodized-silver@rough=0.34,grain=1.6,metallic=0.78",
        "cap": "blasted",
        "accent": "aluminium-diamond-cut",
        "indicator": "engraving-fill-flat",
    }
    SLOT_HELP = {
        "body": "skirt, ledge and cap wall material",
        "knurl": "diamond knurl band material",
        "cap": "top face: `blasted` or `turned` in the preset's finish, or a key",
        "accent": "diamond-cut top chamfer material",
        "indicator": "engraved indicator fill material",
    }
    PRESETS = {f: {
        "body": f"aluminium-bead-blast-anodized-{f}",
        "knurl": f"aluminium-bead-blast-anodized-{f}@rough=0.34,grain=1.6,metallic=0.78",
        "accent": CHAMFER.get(f, "aluminium-diamond-cut"),
        "indicator": FILL.get(f, "engraving-fill-flat"),
    } for f in FINISHES}
    DEFAULT_PRESET = "silver"
    SLOT_VALUES = {"cap": TOP_FACES}
    ALIASES = {"preset": [Alias("--finish", values=FINISHES)],
               "cap": [Alias("--top", values=tuple(TOP_FACES))]}

    def build_knob(self):
        body = billet_body("blasted skirt, ledge and cap wall")
        self.bind("body", [body])
        cut = lathe(list(reversed(CUT_PROFILE)), "diamond-cut top chamfer", smooth_angle=60.0)
        self.bind("accent", [cut])
        face = engraved_face("turned top face")
        self.bind("cap", [face])
        fill = stadium("indicator paint fill", SLOT_INNER, SLOT_OUTER, SLOT_HALF_W - 0.0004,
                       Z_TOP - SLOT_DEPTH + 0.0005, Z_TOP - 0.0012)
        self.bind("indicator", [fill])
        knurl, pitch = meshlib.diamond_knurl("diamond knurl band", R, KNURL_N, KNURL_ANGLE,
                                             KNURL_DEPTH, KNURL_FLAT, Z_BAND_LO, Z_LEDGE,
                                             R_CHAMFER_BOT, R_CHAMFER_TOP)
        self.bind("knurl", [knurl])
        self.notes.append(f"[knurl:grooves={KNURL_N},axial-pitch={pitch:.4f}]")
        return [body, cut, face, fill, knurl]


if __name__ == "__main__":
    HifiKnob.main()
