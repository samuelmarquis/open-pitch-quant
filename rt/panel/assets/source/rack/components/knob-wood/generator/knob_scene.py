"""knob-wood: the lathe-turned hardwood knob with a flush pointer pin at one value.

  blender -b -P knob_scene.py -- OUT [flags]        flag table: ../README.md

The body is spindle-turned on the object Z axis: top flat, shoulder arc tangent
to a tapered, gently convex flank, small rounded foot, with a bore for the pin.
The pointer pin sits flush in it on local +X at r = INLAY_X. Wood-turned keys are
one 3D grain function in object space, so the end grain on the top and the long
grain on the flank meet at the shoulder and turn with the knob. families.KnobScene
owns flags, slots, throw, studio, camera and receipt.
Blender exits 0 after a script exception: callers check OUT and the receipt.
"""

import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
import meshlib  # noqa: E402
from families import Alias, KnobScene  # noqa: E402

TOP_Z = 0.680
SHOULDER_R = 0.120
BODY_LOW = (0.508, 0.060)
BODY_HIGH = (0.418, 0.575)
BASE_R = 0.045
INLAY_X = 0.220
INLAY_R = 0.062


def turned_profile():
    """Top flat -> shoulder arc tangent to a tapered, gently convex flank ->
    small rounded foot."""
    pts = [(0.0, TOP_Z)]
    ux, uz = BODY_HIGH[0] - BODY_LOW[0], BODY_HIGH[1] - BODY_LOW[1]
    length = math.hypot(ux, uz)
    ux, uz = ux / length, uz / length
    nx, nz = uz, -ux  # outward flank normal
    cz = TOP_Z - SHOULDER_R
    cx = BODY_LOW[0] + (-SHOULDER_R - (cz - BODY_LOW[1]) * nz) / nx
    for i in range(1, 12):
        pts.append((cx * i / 12, TOP_Z))
    a0, a1 = math.pi / 2, math.atan2(nz, nx)
    for i in range(0, 29):
        a = a0 + (a1 - a0) * i / 28
        pts.append((cx + SHOULDER_R * math.cos(a), cz + SHOULDER_R * math.sin(a)))
    tan = pts[-1]
    for i in range(1, 21):  # gently convex flank
        t = i / 20
        r = tan[0] + (BODY_LOW[0] - tan[0]) * t + 0.005 * math.sin(math.pi * t)
        z = tan[1] + (BODY_LOW[1] - tan[1]) * t
        pts.append((r, z))
    # rounded foot: quarter arc from the flank tangent down to the base plane
    fcx, fcz = BODY_LOW[0] - BASE_R * nx, BODY_LOW[1] - BASE_R * nz
    b0 = math.atan2(nz, nx)
    b1 = -math.pi / 2
    for i in range(1, 13):
        a = b0 + (b1 - b0) * i / 12
        pts.append((fcx + BASE_R * math.cos(a), max(0.0, fcz + BASE_R * math.sin(a))))
    pts.append((0.0, pts[-1][1]))
    return pts


def cylinder(name, radius, z0, z1, x=0.0, y=0.0, verts=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=z1 - z0,
                                        location=(x, y, 0.5 * (z0 + z1)))
    ob = bpy.context.object
    ob.name = name
    return ob


def turned_body(name):
    body = meshlib.lathe(turned_profile(), name, steps=192, shade=None)
    cutter = cylinder("inlay bore", INLAY_R + 0.0025, TOP_Z - 0.09, TOP_Z + 0.05, x=INLAY_X)
    mod = body.modifiers.new("bore", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    meshlib.activate(body)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    meshlib.activate(body)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
    return body


def pointer_pin(name):
    pin = cylinder(name, INLAY_R, TOP_Z - 0.08, TOP_Z - 0.0012, x=INLAY_X)
    meshlib.activate(pin)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
    return pin


WOODS = ("walnut", "maple", "cherry", "ebony")
INLAYS = {k: f"inlay-pin-{k}" for k in ("brass", "nickel", "copper", "black", "bone")}


class WoodKnob(KnobScene):
    COMPONENT = "knob-wood"
    DEFAULT_OUT = "/tmp/knob-wood.png"
    SLOTS = {"body": "wood-turned-walnut", "indicator": "inlay-pin-brass"}
    SLOT_HELP = {"body": "turned body material (wood-turned-* keys: one 3D grain field)",
                 "indicator": "flush pointer pin material"}
    PRESETS = {w: {"body": f"wood-turned-{w}"} for w in WOODS}
    DEFAULT_PRESET = "walnut"
    ALIASES = {"preset": [Alias("--wood", values=WOODS)],
               "indicator": [Alias("--inlay", values=INLAYS)]}

    def build_knob(self):
        body = turned_body("turned hardwood body")
        self.bind("body", [body])
        pin = pointer_pin("pointer pin")
        self.bind("indicator", [pin])
        return [body, pin]


if __name__ == "__main__":
    WoodKnob.main()
