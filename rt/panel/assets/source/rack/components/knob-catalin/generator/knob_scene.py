"""knob-catalin: the Catalin (cast marbled phenolic) deco radio knob at one value.

  blender -b -P knob_scene.py -- OUT [flags]        flag table: ../README.md

A polar-grid solid of revolution on the object Z axis: skirt tier, 12-flute
rosette (near-vertical grip wall rolling into a 50 deg shoulder), ledge,
cove/riser bead and a low dome with a raised centre boss. The pointer is an
engraved groove along local +X from the dome centre, over the bead and down the
+X lobe crest; catalin keys paint it with their inlay colour. families.KnobScene
owns flags, slots, throw, studio, camera and receipt.

--scale is a coherent zoom: ZOOM multiplies the body material's world-space AO
distances and active subsurface scales by it. --debug thin|swirl|vein replaces the surface with that catalin
field as emission; nospec zeroes specular and coat (catalin keys only).
Blender exits 0 after a script exception: callers check OUT and the receipt.
"""

import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
from families import Alias, Flag, KnobScene  # noqa: E402

N_FLUTES = 12
FLUTE_DEPTH = 0.072
FLUTE_POWER = 1.20
CONE_Z0 = 0.118
CONE_R1 = 0.300
SHOULDER_DEG = 50.0
CONE_TOP = [0.52]
POINTER_W = 0.034
POINTER_D = 0.014
POINTER_R0 = 0.070
POINTER_ZMIN = 0.165
TOP_Z = 0.750
TOP_STEP = 0.016
STEP_R = 0.160


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def profile_points():
    """(r, z, kind) along the silhouette, bottom centre -> top centre."""
    pts = []

    def line(a, b, kind, step=0.006):
        n = max(2, int(math.dist(a, b) / step))
        for i in range(n):
            t = i / n
            pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, kind))

    def arc(c, rad, a0, a1, kind, step=0.004):
        n = max(3, int(abs(a1 - a0) * rad / step))
        for i in range(n):
            a = a0 + (a1 - a0) * i / n
            pts.append((c[0] + rad * math.cos(a), c[1] + rad * math.sin(a), kind))

    d = math.radians
    # underside and skirt tier
    line((0.0, 0.0), (0.515, 0.0), "under", step=0.03)
    arc((0.515, 0.030), 0.030, d(-90), d(0), "skirt")
    line((0.545, 0.030), (0.545, 0.064), "skirt")
    arc((0.515, 0.064), 0.030, d(0), d(90), "skirt")
    # skirt step ledge into the cone foot (small cove)
    line((0.515, 0.094), (0.505, 0.094), "skirt")
    arc((0.505, 0.106), 0.012, d(-90), d(-180), "skirt")
    # fluted run: grip wall rolling into the shoulder, flanks facing the lights
    w0 = (0.493, 0.106)
    w1 = (0.466, 0.300)
    line(w0, w1, "cone", step=0.005)
    a1 = math.atan2(w1[1] - w0[1], w1[0] - w0[0])
    a2 = d(180 - SHOULDER_DEG)
    rad = 0.13
    cen = (w1[0] - rad * math.sin(a1), w1[1] + rad * math.cos(a1))
    arc(cen, rad, a1 - d(90), a2 - d(90), "cone", step=0.004)
    s0 = (cen[0] + rad * math.cos(a2 - d(90)), cen[1] + rad * math.sin(a2 - d(90)))
    t = (CONE_R1 - s0[0]) / math.cos(a2)
    c1 = (CONE_R1, s0[1] + t * math.sin(a2))
    line(s0, c1, "cone", step=0.005)
    CONE_TOP[0] = c1[1]
    nr, nz = math.sin(a2), -math.cos(a2)   # outward normal of the shoulder
    sr = 0.022
    sc = (c1[0] - nr * sr, c1[1] - nz * sr)
    arc(sc, sr, math.atan2(nz, nr), d(90), "ledge")
    ledge_z = sc[1] + sr
    r1 = sc[0] - 0.020
    line((sc[0], ledge_z), (r1, ledge_z), "top")
    # cove up, short riser, convex round onto the dome
    cv = 0.008
    arc((r1, ledge_z + cv), cv, d(-90), d(-180), "top")
    r2 = r1 - cv
    line((r2, ledge_z + cv), (r2, ledge_z + cv + 0.010), "top")
    rd = 0.010
    zr = ledge_z + cv + 0.010
    arc((r2 - rd, zr), rd, d(0), d(58), "top")
    R = r2 - rd + rd * math.cos(d(58))
    z0 = zr + rd * math.sin(d(58))
    # low dome with one deco step (raised centre boss)
    n = 130
    for i in range(1, n + 1):
        r = R * (1.0 - i / n)
        z = z0 + (TOP_Z - TOP_STEP - z0) * (1.0 - (r / R) ** 2)
        z += TOP_STEP * smoothstep(STEP_R + 0.007, STEP_R - 0.007, r)
        pts.append((r, z, "top"))
    return pts


def flute_cut(theta, z, r):
    """Radial inward cut for the fluted cone at angle theta, height z."""
    z1 = CONE_TOP[0]
    t_top = min(1.0, max(0.0, (z - (z1 - 0.120)) / 0.114))
    t_bot = min(1.0, max(0.0, ((CONE_Z0 + 0.070) - z) / 0.070))
    env = math.sqrt(max(0.0, 1.0 - t_top * t_top)) * math.sqrt(max(0.0, 1.0 - t_bot * t_bot))
    if env <= 0.0:
        return 0.0
    phase = (theta * N_FLUTES / (2.0 * math.pi)) % 1.0
    u = abs(phase - 0.5) * 2.0          # 0 at valley centre, 1 at lobe crest
    g = (0.5 + 0.5 * math.cos(math.pi * u)) ** FLUTE_POWER  # 1 valley, 0 crest
    depth = FLUTE_DEPTH * (0.45 + 0.55 * r / 0.49)
    return depth * max(0.0, g - (1.0 - env)) / max(env, 1e-4) * env ** 0.5


def pointer_groove(theta, r, z):
    x = r * math.cos(theta)
    y = r * math.sin(theta)
    if x <= 0.0:
        return 0.0
    lateral = abs(y)
    across = 1.0 - smoothstep(POINTER_W * 0.30, POINTER_W * 0.5, lateral)
    along = (smoothstep(POINTER_R0 - 0.006, POINTER_R0 + 0.004, x)
             * smoothstep(POINTER_ZMIN - 0.012, POINTER_ZMIN + 0.012, z))
    return POINTER_D * across * along


def build_body(name, steps=720):
    prof = profile_points()
    rings = []
    verts = []
    for (r, z, kind) in prof:
        if r < 1e-6:
            continue
        ring = []
        for j in range(steps):
            th = 2.0 * math.pi * j / steps
            rr = r
            zz = z
            if kind == "cone":
                rr = r - flute_cut(th, z, r) - pointer_groove(th, r, z)
            if kind in ("top", "ledge"):
                cut = pointer_groove(th, r, z)
                zz = z - cut
                rr = r - 0.8 * cut      # also bites into risers and the bead
            ring.append(len(verts))
            verts.append((rr * math.cos(th), rr * math.sin(th), zz))
        rings.append(ring)
    bottom = len(verts)
    verts.append((0.0, 0.0, 0.0))
    top = len(verts)
    verts.append((0.0, 0.0, TOP_Z - 0.0))
    faces = []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(steps):
            k = (j + 1) % steps
            faces.append((a[j], a[k], b[k], b[j]))
    for j in range(steps):
        k = (j + 1) % steps
        faces.append((bottom, rings[0][k], rings[0][j]))
        faces.append((top, rings[-1][j], rings[-1][k]))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.validate()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    return ob


def catalin_probe(mat, probe):
    """Wire a catalin field to the output as emission (or zero spec/coat)."""
    nt = mat.node_tree
    nodes = list(nt.nodes)
    bsdf = nt.nodes.get("Principled BSDF")
    out = nt.nodes.get("Material Output")

    def linked_from(sock):
        return sock.links[0].from_node if sock.is_linked else None

    try:
        if probe == "nospec":
            bsdf.inputs["Specular IOR Level"].default_value = 0.0
            bsdf.inputs["Coat Weight"].default_value = 0.0
            return
        if probe == "thin":
            node = next(n for n in nodes if n.bl_idname == "ShaderNodeMapRange"
                        and abs(n.inputs["From Min"].default_value - 0.30) < 1e-6
                        and abs(n.inputs["From Max"].default_value - 0.62) < 1e-6)
            field = node.outputs["Result"]
        else:
            mixes = [n for n in nodes if n.bl_idname == "ShaderNodeMix" and n.data_type == "RGBA"]
            fac = {n: {s.identifier: s for s in n.inputs} for n in mixes}
            if probe == "swirl":
                mix = next(n for n in mixes if fac[n]["A_Color"].is_linked
                           and getattr(linked_from(fac[n]["Factor_Float"]), "operation", "") == "MINIMUM")
                field = fac[mix]["Factor_Float"].links[0].from_socket
            else:
                mul = next(linked_from(fac[n]["Factor_Float"]) for n in mixes
                           if getattr(linked_from(fac[n]["Factor_Float"]), "operation", "") == "MULTIPLY"
                           and abs(linked_from(fac[n]["Factor_Float"]).inputs[1].default_value - 0.55) < 1e-6)
                field = mul.inputs[0].links[0].from_socket
    except (StopIteration, AttributeError, KeyError, IndexError):
        raise SystemExit(f"knob-catalin: --debug {probe} needs a catalin key on --body")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(field, em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])


COLORWAYS = {"butterscotch": "catalin", "cherry": "catalin-cherry", "jade": "catalin-jade"}


class CatalinKnob(KnobScene):
    COMPONENT = "knob-catalin"
    DEFAULT_OUT = "/tmp/knob-catalin.png"
    SLOTS = {"body": "catalin"}
    ZOOM = {"body": ("ao", "subsurface")}
    SLOT_HELP = {"body": "cast rosette body material (catalin keys paint the pointer groove)"}
    PRESETS = {name: {"body": key} for name, key in COLORWAYS.items()}
    DEFAULT_PRESET = "butterscotch"
    ALIASES = {"preset": [Alias("--color", values=tuple(COLORWAYS))]}
    FLAGS = (Flag("--debug", str, "none", choices=("none", "nospec", "thin", "swirl", "vein"),
                  help="diagnostic: thin, swirl or vein as emission; nospec = no specular/coat"),)

    def build_knob(self):
        body = build_body("catalin rosette body")
        mat = self.bind("body", [body])
        if self.args.debug != "none":
            catalin_probe(mat, self.args.debug)
        return [body]


if __name__ == "__main__":
    CatalinKnob.main()
