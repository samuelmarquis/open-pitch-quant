"""knob-chrome: the dead-on chrome dome knob (Telecaster north star) at one value.

  blender -b -P knob_scene.py -- OUT [flags]        flag table: ../README.md

The dome is lathed at scale 1 on the object Z axis with the divet machined at
DIVET_DEG in object space; the object is turned -DIVET_DEG so the divet lies on
local +X, families.KnobScene's pointer axis. KnobScene owns flags, throw,
footprint, studio (rigs.knob_studio), camera and receipt.

`--body chrome-maps` (default) is the component-local chrome whose roughness
and bump are rough.png / bump.png from make_maps.py, mapped in object space
onto this mesh; it is not a matlib key. Any matlib key binds through the slot.
Blender exits 0 after a script exception: callers check OUT and the receipt.
"""

import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
import meshlib  # noqa: E402
from families import KnobScene  # noqa: E402
from matlib import own_material  # noqa: E402

LOCAL_BODY = "chrome-maps"
DIVET_DEG = 225.0        # divet azimuth in object space
DIVET_R, DIVET_AT, DIVET_Z = 0.105, 0.62, 0.695
MAP_SCALE = 0.41         # object-space map lookup: uv = 0.41 * xy + 0.5
BUMP_STRENGTH = 0.18


def dome_profile():
    """(r, z): flat top, shoulder arc from (0.70, 0.60) to (1.0, 0.42), barrel."""
    prof = [(0.0, 0.70), (0.25, 0.69), (0.45, 0.665), (0.62, 0.625), (0.70, 0.60)]
    for i in range(1, 13):
        a = i / 12 * math.pi / 2
        prof.append((0.70 + 0.30 * math.sin(a), 0.60 - 0.18 * (1 - math.cos(a))))
    return prof + [(1.0, 0.10), (0.99, 0.04), (0.93, 0.0)]


def chrome_maps():
    mat = bpy.data.materials.new("chrome")
    mat.use_nodes = True
    n, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Base Color"].default_value = (0.93, 0.945, 0.965, 1)
    bsdf.inputs["Coat Weight"].default_value = 0.0

    def tex(path):
        t = n.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(path))
        t.image.colorspace_settings.name = "Non-Color"
        tc = n.new("ShaderNodeTexCoord")
        mp = n.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (MAP_SCALE, MAP_SCALE, MAP_SCALE)
        mp.inputs["Location"].default_value = (0.5, 0.5, 0.0)
        links.new(tc.outputs["Object"], mp.inputs["Vector"])
        links.new(mp.outputs["Vector"], t.inputs["Vector"])
        return t

    rt = tex(HERE / "rough.png")
    links.new(rt.outputs["Color"], bsdf.inputs["Roughness"])
    bt = tex(HERE / "bump.png")
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = BUMP_STRENGTH
    links.new(bt.outputs["Color"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


class ChromeKnob(KnobScene):
    COMPONENT = "knob-chrome"
    DEFAULT_OUT = "/tmp/knob-chrome.png"
    SLOTS = {"body": LOCAL_BODY}
    SLOT_HELP = {"body": f"dome material; `{LOCAL_BODY}` = the local raster-mapped chrome"}
    # torch-coloured titanium laid out on this dome (rings to its rim, a hot
    # touch on the dimple): Sam, p136-p142
    PRESETS = {"heat-tint": {"body": "titanium-heat-tint"}}

    def check_slots(self):
        if self.args.body != LOCAL_BODY:
            super().check_slots()

    def build_knob(self):
        knob = meshlib.lathe(dome_profile(), "knob", steps=256, merge=1e-4, shade="select")
        ang = math.radians(DIVET_DEG)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=DIVET_R,
                                             location=(DIVET_AT * math.cos(ang),
                                                       DIVET_AT * math.sin(ang), DIVET_Z))
        dent = bpy.context.object
        mod = knob.modifiers.new("divet", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = dent
        bpy.context.view_layer.objects.active = knob
        bpy.ops.object.modifier_apply(modifier="divet")
        bpy.data.objects.remove(dent)
        bpy.ops.object.shade_smooth()
        if self.args.body == LOCAL_BODY:
            own_material(knob, chrome_maps())
        else:
            self.bind("body", [knob])
        knob.rotation_euler.z = -ang
        return [knob]


if __name__ == "__main__":
    ChromeKnob.main()
