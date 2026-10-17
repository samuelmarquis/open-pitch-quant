"""knob-heady: the lampworked art-glass knob at one value, in one of four styles.

  blender -b -P knob_scene.py -- OUT [flags]        flag table: ../README.md

A thick clear borosilicate dome (slot `cap`) set in a dark collar (slot `body`)
over an opaque backing (slot `backing`). All worked colour is real geometry
inside that refractive volume, never paint on the dome, and every ray through
the glass ends on the knob's own geometry. The pointer lies on local +X.

The preset is the style (`--style NAME` selects it): it chooses the inclusion
geometry and binds its slots. `inclusion` / `inclusion-b` are the fumed style's
silver / gold fume sheets and the crushed style's opal chips / dichroic shards;
implosion and linework do not use them. The coloured lampwork inside a style
(petals, canes, murrine, rings) is the style's own colour roster, built from the
`lampwork-colour` key. When the indicator key declares `name`, `rgb` or `sss`
and the spec does not set them, the fumed and crushed styles fill their cane
pointer's values.

families.KnobScene owns flags, slots, throw, footprint, studio (rigs.knob_studio),
camera and receipt. Blender exits 0 after a script exception: callers check OUT and the
receipt line.
"""

import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
import meshlib  # noqa: E402
from families import Alias, KnobScene  # noqa: E402

STYLES = ("implosion", "fumed", "linework", "crushed")

# Cap construction, units at scale 1. The collar lip overhangs the glass
# girdle, so the visible dome (r ~0.552) stays inside the footprint.
COLLAR_R = 0.635
GLASS_R = 0.566
FLOOR_Z = 0.060
GLASS_BOTTOM = 0.070
BACK_TOP = 0.076          # backing face sits inside the glass: no air film
DOME_BASE_Z = 0.228
DOME_TOP = 0.540
_H = DOME_TOP - DOME_BASE_Z
DOME_R = (GLASS_R ** 2 + _H ** 2) / (2.0 * _H)
DOME_CZ = DOME_TOP - DOME_R
INCLUSION_R = 0.525       # colour runs under the bezel lip, never past the wall

# Cane pointers filled into the indicator key's params (see module docstring).
POINTER_PARAMS = {
    "fumed": {"name": "opaque white cane", "rgb": (0.90, 0.90, 0.87), "sss": 0.25},
    "crushed": {"name": "serum magenta cane", "rgb": (0.95, 0.02, 0.42), "sss": 0.1},
}

CORE = {"body": "moulded-black-matte", "cap": "borosilicate-clear",
        "backing": "glass-jet", "bubble": "borosilicate-seed-bubble"}


def dome_z(r):
    return DOME_CZ + math.sqrt(max(DOME_R ** 2 - r * r, 0.0))


# ------------------------------------------------------------------ geometry

def lathe(profile, name, steps=160):
    """Closed revolve with outward normals (refraction depends on facing)."""
    return meshlib.lathe(profile, name, steps=steps, recalc_normals=True)


def mesh_object(name, bm, shade_smooth=True, recalc=True):
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.polygons.foreach_set("use_smooth", [shade_smooth] * len(mesh.polygons))
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    return ob


def solidify(ob, thickness):
    meshlib.activate(ob)
    mod = ob.modifiers.new("sheet thickness", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 0.0
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return ob


def add_ribbon(bm, r0, r1, centre, half_width, height, n_r=72, n_u=6):
    """Quad strip over (r, u): angle = centre(r) + u * half_width(r)."""
    rows = []
    for i in range(n_r + 1):
        r = r0 + (r1 - r0) * i / n_r
        row = []
        for j in range(n_u + 1):
            a = centre(r) + (-1.0 + 2.0 * j / n_u) * half_width(r)
            row.append(bm.verts.new((r * math.cos(a), r * math.sin(a), height(r))))
        rows.append(row)
    for i in range(n_r):
        for j in range(n_u):
            bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))


def add_tube(bm, pts, radius, sides=10):
    """Capped tube along a polyline; radius may be a function of t in 0..1."""
    pts = [Vector(p) for p in pts]
    rad = radius if callable(radius) else (lambda _t: radius)
    n = len(pts)
    t_prev = (pts[1] - pts[0]).normalized()
    ref = Vector((0, 0, 1)) if abs(t_prev.z) < 0.9 else Vector((1, 0, 0))
    nrm = t_prev.cross(ref).normalized()
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            t = t_prev
        elif i == n - 1:
            t = (pts[-1] - pts[-2]).normalized()
        else:
            t = (pts[i + 1] - pts[i - 1]).normalized()
        axis = t_prev.cross(t)
        if axis.length > 1e-9:
            nrm = Matrix.Rotation(t_prev.angle(t), 3, axis.normalized()) @ nrm
        t_prev = t
        binormal = t.cross(nrm).normalized()
        nrm = binormal.cross(t).normalized()
        rr = rad(i / (n - 1))
        rings.append([
            bm.verts.new(p + rr * (math.cos(a) * nrm + math.sin(a) * binormal))
            for a in (2 * math.pi * k / sides for k in range(sides))
        ])
    for i in range(n - 1):
        for k in range(sides):
            k1 = (k + 1) % sides
            bm.faces.new((rings[i][k], rings[i][k1], rings[i + 1][k1], rings[i + 1][k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def add_blob(bm, loc, radii, rot=(0.0, 0.0, 0.0), subdiv=2, jitter=0.0, rng=None):
    """Icosphere scaled to radii; jitter makes an irregular fracture chip."""
    made = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    rot_m = (Matrix.Rotation(rot[2], 3, "Z") @ Matrix.Rotation(rot[1], 3, "Y")
             @ Matrix.Rotation(rot[0], 3, "X"))
    for v in made["verts"]:
        co = v.co.copy()
        if jitter:
            co *= 1.0 + rng.uniform(-jitter, jitter)
        co = Vector((co.x * radii[0], co.y * radii[1], co.z * radii[2]))
        v.co = rot_m @ co + Vector(loc)
    return made["verts"]


def add_flake(bm, loc, size, tilt, spin, rng):
    """Irregular flat shard (convex polygon) for a thin coated sheet."""
    k = rng.randint(5, 7)
    angles = sorted(rng.uniform(0, 2 * math.pi) for _ in range(k))
    rot_m = (Matrix.Rotation(spin, 3, "Z") @ Matrix.Rotation(tilt[1], 3, "Y")
             @ Matrix.Rotation(tilt[0], 3, "X"))
    verts = []
    for a in angles:
        rr = size * rng.uniform(0.55, 1.0)
        verts.append(bm.verts.new(rot_m @ Vector((rr * math.cos(a), rr * math.sin(a), 0.0))
                                  + Vector(loc)))
    bm.faces.new(verts)


def lathe_ring(name, r_in, r_out, z0, z1, steps=160):
    return lathe([(r_in, z0), (r_out, z0), (r_out, z1), (r_in, z1), (r_in, z0)], name, steps)


def pointer_clear(r, a, margin=0.30, r_min=0.22):
    """True when (r, angle) keeps out of the pointer's corridor on +X."""
    a = math.atan2(math.sin(a), math.cos(a))
    return not (abs(a) < margin and r > r_min)



# ------------------------------------------------------------------ scene

class HeadyKnob(KnobScene):
    COMPONENT = "knob-heady"
    DEFAULT_OUT = "/tmp/knob-heady.png"
    VALUE = 0.5
    SAMPLES = 256
    EXTRA_SLOTS = ("backing", "bubble", "inclusion", "inclusion-b")
    SLOTS = {
        "body": CORE["body"],
        "cap": CORE["cap"],
        "indicator": "opal-synthetic",
        "backing": CORE["backing"],
        "bubble": CORE["bubble"],
        "inclusion": "colloidal-silver-fume",
        "inclusion-b": "colloidal-gold-fume",
    }
    SLOT_HELP = {
        "body": "collar material",
        "cap": "encasement dome glass",
        "indicator": "pointer inclusion (opal dot / cane / opal inlay)",
        "backing": "opaque backing disc and setting pad",
        "bubble": "seed bubbles (inward normals)",
        "inclusion": "fumed: silver fume sheets; crushed: crushed opal chips",
        "inclusion-b": "fumed: gold fume sheets; crushed: dichroic shards",
    }
    PRESETS = {
        "implosion": {**CORE, "indicator": "opal-synthetic"},
        "fumed": {**CORE, "indicator": "lampwork-colour",
                  "inclusion": "colloidal-silver-fume", "inclusion-b": "colloidal-gold-fume"},
        "linework": {**CORE, "indicator": "opal-synthetic"},
        "crushed": {**CORE, "indicator": "lampwork-colour",
                    "inclusion": "opal-crushed", "inclusion-b": "dichroic-coating"},
    }
    DEFAULT_PRESET = "implosion"
    ALIASES = {"preset": [Alias("--style", values=STYLES)]}

    # ---------------------------------------------------------------- slots
    def use(self, slot, ob):
        """Queue `ob` for `slot`; build_knob binds every slot's objects at once."""
        self.queued[slot].append(ob)
        self.parts.append(ob)
        return ob

    def colour(self, ob, label, rgb, sss=0.0):
        """One entry of the style's lampwork colour roster."""
        from matlib import build, own_material

        own_material(ob, build("lampwork-colour", self.ctx, name=label, rgb=rgb, sss=sss))
        self.parts.append(ob)
        return ob

    # -------------------------------------------------------------- geometry
    def build_knob(self):
        style = self.args.preset
        self.rng = rng = random.Random(STYLES.index(style) * 7919 + 26)
        self.queued = defaultdict(list)
        self.parts = []

        self.use("body", lathe(
            [(0.0, 0.0), (0.600, 0.0), (0.625, 0.012), (COLLAR_R, 0.035), (COLLAR_R, 0.195),
             (0.631, 0.222), (0.620, 0.240), (0.603, 0.250), (0.575, 0.254), (0.560, 0.252),
             (0.553, 0.246), (0.550, 0.236), (0.550, FLOOR_Z), (0.0, FLOOR_Z)],
            "bezel collar body", steps=192))
        self.use("backing", lathe(
            [(0.0, FLOOR_Z + 0.001), (0.549, FLOOR_Z + 0.001), (0.549, BACK_TOP), (0.0, BACK_TOP)],
            "backing disc", steps=192))

        a0 = math.asin(GLASS_R / DOME_R)
        arc = [(DOME_R * math.sin(a0 * (1.0 - i / 96)), DOME_CZ + DOME_R * math.cos(a0 * (1.0 - i / 96)))
               for i in range(97)]
        arc[-1] = (0.0, DOME_TOP)
        glass = lathe([(0.0, GLASS_BOTTOM), (GLASS_R, GLASS_BOTTOM)] + arc, "encasement dome", 256)
        meshlib.activate(glass)
        try:
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(25.0))
        except (AttributeError, RuntimeError):
            pass
        self.use("cap", glass)

        bubble_floor = getattr(self, f"build_{style}")(rng)

        # A few seed bubbles in the clear encasement above the worked colour.
        bm = bmesh.new()
        placed = 0
        while placed < 8:
            r = 0.40 * math.sqrt(rng.random())
            a = rng.uniform(0, 2 * math.pi)
            if not pointer_clear(r, a, 0.45, 0.25):
                continue
            top = dome_z(r) - 0.03
            if top <= bubble_floor + 0.01:
                continue
            br = rng.uniform(0.004, 0.011)
            add_blob(bm, (r * math.cos(a), r * math.sin(a), rng.uniform(bubble_floor + 0.01, top)),
                     (br, br, br), subdiv=2)
            placed += 1
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        self.use("bubble", mesh_object("seed bubbles", bm, recalc=False))

        pointer = POINTER_PARAMS.get(self.args.preset, {})
        for slot, obs in self.queued.items():
            self.bind(slot, obs, params=pointer if self.resolved_slot(slot) == "indicator" else None)
        return self.parts

    def build_implosion(self, rng):
        """Layered petals gathered in a twisting funnel whose point sits deep on
        the axis; each petal stacks base colour, a brighter stripe and a white
        core toward the viewer."""
        n = 12
        pitch = 2 * math.pi / n
        r_tip, z_tip, z_rim = 0.430, 0.082, 0.220
        twist = 1.7

        def height(r):
            return z_tip + (z_rim - z_tip) * (r / r_tip) ** 1.3

        def half(r, share):
            s = min(r / r_tip, 1.0)
            return pitch * share * math.sqrt(s) * math.sqrt(max(1.0 - s ** 4, 0.0))

        # Hand-pulled, not machined: each petal gets its own offset, twist, width
        # and a slight wobble, shared by all of its colour layers.
        petals = [
            dict(c0=(k + 0.5) * pitch + rng.uniform(-0.035, 0.035),
                 twist=twist * rng.uniform(0.94, 1.06),
                 width=rng.uniform(0.90, 1.08),
                 phase=rng.uniform(0, 2 * math.pi))
            for k in range(n)
        ]

        def centre_fn(p):
            return lambda r: (p["c0"] + p["twist"] * (1.0 - r / r_tip) ** 1.7
                              + 0.018 * (r / r_tip) * math.sin(38.0 * r + p["phase"]))

        layers = (
            # label, rgb, petal parity, width share, lift toward viewer, sss
            ("cobalt petal", (0.015, 0.07, 0.62), 0, 0.62, 0.000, 0.10),
            ("sky stripe", (0.08, 0.50, 0.98), 0, 0.34, 0.004, 0.12),
            ("ruby petal", (0.72, 0.03, 0.02), 1, 0.62, 0.000, 0.10),
            ("tangerine stripe", (1.0, 0.46, 0.03), 1, 0.34, 0.004, 0.12),
        )
        for label, rgb, parity, share, lift, sss in layers:
            bm = bmesh.new()
            for p in petals[parity::2]:
                add_ribbon(bm, 0.008, r_tip, centre_fn(p),
                           lambda r, share=share * p["width"]: half(r, share),
                           lambda r, lift=lift: height(r) + lift, n_r=90)
            self.colour(solidify(mesh_object(label, bm), 0.0035), label, rgb, sss)

        bm = bmesh.new()
        for p in petals:
            add_ribbon(bm, 0.008, r_tip * 0.97, centre_fn(p),
                       lambda r: half(r, 0.08), lambda r: height(r) + 0.0075, n_r=90, n_u=2)
        self.colour(solidify(mesh_object("white core line", bm), 0.0015),
                    "latticino white", (0.88, 0.88, 0.84), 0.2)

        # The opal sits in the black margin between two petal tips on +X.
        bm = bmesh.new()
        add_blob(bm, (0.468, 0.0, 0.228), (0.058, 0.058, 0.025))
        self.use("indicator", mesh_object("opal dot pointer", bm))
        return 0.27

    def build_fumed(self, rng):
        """Silver and gold fume bands over black, crossing a white opal ring."""
        self.colour(lathe_ring("white ring under fume", 0.17, 0.31, BACK_TOP - 0.003,
                               BACK_TOP + 0.006),
                    "opal white ring", (0.86, 0.86, 0.83), 0.25)

        n = 8
        pitch = 2 * math.pi / n
        r_out = INCLUSION_R - 0.005
        for p, (slot, label) in enumerate((("inclusion", "silver fume"),
                                           ("inclusion-b", "gold fume"))):
            bm = bmesh.new()
            for k in range(p, n, 2):
                c0 = k * pitch + pitch * 0.5

                def centre(r, c0=c0):
                    return c0 + 2.3 * (r / r_out) ** 1.25

                add_ribbon(bm, 0.03, r_out, centre, lambda r: pitch * 0.31,
                           lambda r: 0.125 + 0.035 * (r / r_out), n_r=90, n_u=10)
            self.use(slot, mesh_object(label, bm))

        bm = bmesh.new()
        pts = [(0.335 + 0.130 * t / 20, 0.0, 0.205) for t in range(21)]
        add_tube(bm, pts, lambda t: 0.021 * min(1.0, (min(t, 1 - t) / 0.12) ** 0.5 * 0.6 + 0.4),
                 sides=14)
        self.use("indicator", mesh_object("white cane pointer", bm))
        return 0.20

    def build_linework(self, rng):
        """Reticello: two opposed spiral cane layers with a bubble in every cell."""
        n = 16
        k = 1.0
        r0, r1 = 0.078, INCLUSION_R - 0.01
        z_a, z_b = 0.106, 0.124
        cane = 0.0065
        steps = 70

        def spiral(theta0, sign, z):
            # A pulled cane never runs true: slight lateral and depth wobble.
            phase = rng.uniform(0, 2 * math.pi)
            pts = []
            for i in range(steps + 1):
                r = r0 * (r1 / r0) ** (i / steps)
                a = theta0 + sign * k * math.log(r / r0) + 0.010 * math.sin(55.0 * r + phase)
                dz = 0.004 * (r - r0) / (r1 - r0) + 0.0012 * math.sin(31.0 * r + phase)
                pts.append((r * math.cos(a), r * math.sin(a), z + dz))
            return pts

        def taper(t):
            return cane * (0.55 + 0.45 * min(1.0, (1.0 - t) / 0.06))

        bm = bmesh.new()
        for i in range(n):
            add_tube(bm, spiral(2 * math.pi * i / n, 1.0, z_a), taper, sides=8)
        self.colour(mesh_object("latticino layer", bm), "latticino white", (0.88, 0.88, 0.84), 0.2)

        for p, (label, rgb) in enumerate((("teal cane", (0.0, 0.52, 0.55)),
                                          ("amber cane", (0.98, 0.50, 0.04)))):
            bm = bmesh.new()
            for j in range(p, n, 2):
                add_tube(bm, spiral(2 * math.pi * (j + 0.5) / n, -1.0, z_b), taper, sides=8)
            self.colour(mesh_object(label, bm), label, rgb, 0.1)

        bm = bmesh.new()
        step = 2 * math.pi / n
        for i in range(n):
            u = (i + 0.5) * step
            for m in range(-4, 40):
                v = u + (m + 0.5) * step
                r = r0 * math.exp((v - u) / (2 * k))
                if not r0 * 1.25 < r < r1 * 0.97:
                    continue
                theta = (u + v) / 2.0
                cell = 2 * math.pi * r / n / math.sqrt(2.0)
                br = min(max(0.17 * cell, 0.0030), 0.0105)
                add_blob(bm, (r * math.cos(theta), r * math.sin(theta), (z_a + z_b) / 2),
                         (br, br, br * 0.85), subdiv=2)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        self.use("bubble", mesh_object("reticello cell bubbles", bm, recalc=False))

        for label, rgb, rad, z1 in (
            ("murrine white rim", (0.88, 0.88, 0.84), 0.088, 0.136),
            ("murrine cobalt ring", (0.03, 0.12, 0.80), 0.064, 0.139),
            ("murrine sun core", (1.0, 0.78, 0.05), 0.030, 0.142),
        ):
            ob = lathe([(0.0, BACK_TOP - 0.002), (rad, BACK_TOP - 0.002), (rad + 0.003, z1 - 0.004),
                        (rad, z1), (0.0, z1)], label, steps=96)
            self.colour(ob, label, rgb, 0.15)

        # Black-backed opal: the jet pad separates it from the white latticino.
        bm = bmesh.new()
        add_blob(bm, (0.420, 0.0, 0.158), (0.108, 0.058, 0.007), subdiv=3)
        self.use("backing", mesh_object("jet setting pad", bm))

        bm = bmesh.new()
        add_blob(bm, (0.420, 0.0, 0.182), (0.090, 0.040, 0.022), subdiv=3)
        self.use("indicator", mesh_object("opal inlay pointer", bm))
        return 0.19

    def build_crushed(self, rng):
        """Crushed opal and dichro shards settled over jet, one bold cane pointer."""
        bm = bmesh.new()
        placed = 0
        while placed < 130:
            r = INCLUSION_R * math.sqrt(rng.random())
            a = rng.uniform(0, 2 * math.pi)
            if not pointer_clear(r, a, 0.34, 0.20):
                continue
            size = rng.uniform(0.012, 0.034)
            z = BACK_TOP + size * 0.6 + abs(rng.gauss(0.0, 0.035))
            add_blob(bm, (r * math.cos(a), r * math.sin(a), z),
                     (size, size * rng.uniform(0.6, 1.0), size * rng.uniform(0.45, 0.8)),
                     rot=(rng.uniform(0, 6.3), rng.uniform(0, 6.3), rng.uniform(0, 6.3)),
                     subdiv=1, jitter=0.35, rng=rng)
            placed += 1
        self.use("inclusion", mesh_object("crushed opal", bm, shade_smooth=False))

        bm = bmesh.new()
        placed = 0
        while placed < 56:
            r = INCLUSION_R * math.sqrt(rng.random())
            a = rng.uniform(0, 2 * math.pi)
            if not pointer_clear(r, a, 0.34, 0.20):
                continue
            z = rng.uniform(0.095, 0.215)
            add_flake(bm, (r * math.cos(a), r * math.sin(a), z), rng.uniform(0.020, 0.048),
                      (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5)), rng.uniform(0, 6.3), rng)
            placed += 1
        self.use("inclusion-b", solidify(mesh_object("dichro shards", bm, shade_smooth=False),
                                         0.0016))

        bm = bmesh.new()
        pts = [(0.265 + 0.200 * t / 24, 0.0, 0.215) for t in range(25)]
        add_tube(bm, pts, lambda t: 0.022 * (0.45 + 0.55 * min(1.0, min(t, 1 - t) / 0.10)), sides=14)
        self.use("indicator", mesh_object("serum cane pointer", bm))
        return 0.26

    # ---------------------------------------------------------------- studio
    def build(self):
        """KnobScene.build after the thick-glass light-path settings."""
        c = self.scene.cycles
        # Every camera path crosses the dome twice plus any transmissive
        # inclusion, and the inclusions are lit only through the dome.
        c.max_bounces = 24
        c.diffuse_bounces = 4
        c.glossy_bounces = 8
        c.transmission_bounces = 24
        c.transparent_max_bounces = 32
        c.volume_bounces = 0
        c.caustics_reflective = True
        c.caustics_refractive = True
        c.blur_glossy = 0.6
        c.sample_clamp_indirect = 8.0
        if self.device == "GPU":
            c.denoising_use_gpu = True
        return super().build()


if __name__ == "__main__":
    HeadyKnob.main()
