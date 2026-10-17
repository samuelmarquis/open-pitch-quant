"""knob-leather: a saddle-stitched padded leather dome in a turned brass cup at one value.

  blender -b -P knob_scene.py -- OUT [flags]        flag table: ../README.md

Stitched-dome cabinet-knob construction on the object Z axis: a turned brass
cup, a bead-blasted base collar, the padded leather dome (point attribute
`stitch_hole`, 0..1, marks the awl slits and the pin seat), one slanted 3-ply
thread tube per stitch, and the indicator pin on local +X. Every part faces the
dead-on camera. families.KnobScene owns flags, slots, throw, studio, camera and
receipt. Blender exits 0 after a script exception: callers check OUT and the
receipt.
"""

import math
import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
import meshlib  # noqa: E402
from families import Alias, KnobScene  # noqa: E402

R_COLLAR = 0.530      # base collar, sits on the panel
R_BODY = 0.500        # brass cup outer wall
R_LIP_IN = 0.436      # cup inner wall: lip is 6.4% of the diameter per side
R_LEATHER = 0.430     # burnished leather edge; 0.006 shadow gap to the lip
Z_LIP = 0.585         # crown of the brass lip
Z_FLANGE = 0.571      # flat stitched leather flange
R_STITCH = 0.362      # stitch ring = 0.84 of the leather face diameter
R_DOME = 0.340        # padded dome base, pinched by the stitch line
H_DOME = 0.120        # dome rise above the flange
STITCHES = 26         # pitch 0.0875 = 0.10 of the leather face diameter
SLANT = math.radians(15.0)
HOLE_GAP = 0.0048     # half the hole: visible dash is ~0.89 of the pitch
THREAD_W = 0.0120     # half-width (thread 2.8% of the face diameter)
THREAD_H = 0.0085     # half-height: waxed thread flattens under tension
R_PIN = 0.230         # indicator pin radius position along local +X
PIN_R = 0.036         # indicator pin head radius


def arc(cx, cz, radius, a0, a1, n):
    return [
        (cx + radius * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
         cz + radius * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
        for i in range(n + 1)
    ]


def mesh_object(name, verts, faces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    return ob


# ------------------------------------------------------------ leather surface
# Axisymmetric profile of the leather top: padded dome, pinched stitch channel,
# flat flange. Built densely then smoothed so the dome shoulder rolls into the
# channel instead of meeting it at a crease.
_PR = np.linspace(0.0, R_LEATHER, 4001)


def _raw_profile(r):
    x = np.clip(r / R_DOME, 0.0, 1.0)
    dome = np.where(r < R_DOME, H_DOME * (1.0 - x ** 2.2) ** 0.62, 0.0)
    flange_slope = -0.006 * np.clip((r - R_DOME) / (R_LEATHER - R_DOME), 0, 1)
    channel = -0.0042 * np.exp(-((r - R_STITCH) / 0.014) ** 2)
    return Z_FLANGE + dome + flange_slope + channel


def _smooth_1d(z, sigma_units):
    step = _PR[1] - _PR[0]
    sigma = sigma_units / step
    half = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-half, half + 1) / sigma) ** 2)
    k /= k.sum()
    padded = np.concatenate([np.full(half, z[0]), z, np.full(half, z[-1])])
    return np.convolve(padded, k, mode="valid")


_PZ = _smooth_1d(_raw_profile(_PR), 0.0065)
_PZ[: int(0.02 / (_PR[1] - _PR[0]))] = _PZ[0]  # keep the crown flat-topped


def profile_z(r):
    return np.interp(r, _PR, _PZ)


PITCH_ANGLE = 2.0 * math.pi / STITCHES
# Slit half-extents: radial (s) and tangential (g). The visible stitch runs from
# the outer end of one slit to the inner end of the next, which is the slant.
SLIT_S = 0.5 * (R_STITCH * PITCH_ANGLE - 2.0 * HOLE_GAP) * math.tan(SLANT)
# Hole k sits at angle k * pitch (+ half pitch so no hole lands on the pin axis).
HOLE_PHASE = 0.5 * PITCH_ANGLE


def stitch_displacement(x, y):
    """Leather pulled into each slit, plus pillowing between holes."""
    r = np.hypot(x, y)
    theta = np.arctan2(y, x)
    k = np.round((theta - HOLE_PHASE) / PITCH_ANGLE)
    hole_theta = HOLE_PHASE + k * PITCH_ANGLE
    cx, cy = R_STITCH * np.cos(hole_theta), R_STITCH * np.sin(hole_theta)
    nx, ny = np.cos(hole_theta), np.sin(hole_theta)
    tx, ty = -ny, nx
    # slit segment from c - (n s + t g) to c + (n s + t g)
    ax_, ay_ = nx * SLIT_S + tx * HOLE_GAP, ny * SLIT_S + ty * HOLE_GAP
    seg2 = ax_ ** 2 + ay_ ** 2
    t = np.clip(((x - cx) * ax_ + (y - cy) * ay_) / seg2, -1.0, 1.0)
    dx, dy = x - (cx + t * ax_), y - (cy + t * ay_)
    dist = np.hypot(dx, dy)
    hole = np.exp(-(dist / 0.0085) ** 2)
    dimple = -0.0055 * hole
    phase = (theta - hole_theta) / PITCH_ANGLE  # -0.5..0.5, 0 at the hole
    between = 0.5 - 0.5 * np.cos(2.0 * np.pi * phase)
    inner = np.exp(-((r - (R_STITCH - 0.026)) / 0.012) ** 2)
    outer = np.exp(-((r - (R_STITCH + 0.024)) / 0.010) ** 2)
    pillow = 0.0040 * between * inner + 0.0016 * between * outer
    crease_line = -0.0016 * np.exp(-((r - (R_LEATHER - 0.022)) / 0.0024) ** 2)
    seat = np.exp(-((np.hypot(x - R_PIN, y) - PIN_R) / 0.012) ** 2)
    pin_seat = -0.0040 * seat
    # "hole" also drives the shader (punctures and the pin seat hold dirt)
    return dimple + pillow + crease_line + pin_seat, np.maximum(hole, 0.6 * seat)


def leather_pad():
    top_r = np.concatenate([
        np.linspace(0.0, 0.26, 44, endpoint=False),
        np.linspace(0.26, R_LEATHER - 0.012, 150),
    ])
    edge_r = 0.012
    edge = arc(R_LEATHER - edge_r, Z_FLANGE - 0.006 - edge_r, edge_r, 90, 0, 8)[1:]
    ring_profile = [(r, None) for r in top_r[1:]] + edge + [
        (R_LEATHER, Z_FLANGE - 0.050), (R_LEATHER - 0.04, Z_FLANGE - 0.050)]
    segs = STITCHES * 30
    ang = np.linspace(0, 2 * np.pi, segs, endpoint=False)
    ca, sa = np.cos(ang), np.sin(ang)
    verts = [np.array([[0.0, 0.0, float(profile_z(0.0))]])]
    holes = [np.zeros(1)]
    for r, z in ring_profile:
        xs, ys = r * ca, r * sa
        if z is None:
            disp, hole = stitch_displacement(xs, ys)
            zs = profile_z(r) + disp
        else:
            zs, hole = np.full(segs, z), np.zeros(segs)
        verts.append(np.stack([xs, ys, zs], axis=1))
        holes.append(hole)
    verts = np.concatenate(verts)
    holes = np.concatenate(holes)
    faces = []
    for j in range(segs):
        faces.append((0, 1 + j, 1 + (j + 1) % segs))
    for i in range(len(ring_profile) - 1):
        a0 = 1 + i * segs
        b0 = 1 + (i + 1) * segs
        for j in range(segs):
            jn = (j + 1) % segs
            faces.append((a0 + j, b0 + j, b0 + jn, a0 + jn))
    ob = mesh_object("padded leather dome", verts, faces)
    attr = ob.data.attributes.new("stitch_hole", "FLOAT", "POINT")
    attr.data.foreach_set("value", holes.astype(np.float32))
    return ob


def stitch_threads():
    """One tube per visible saddle stitch, slanted, sinking into both slits."""
    along = 30
    around = 14
    lay = 0.030                  # 3-ply lay length along the thread
    verts = []
    faces = []
    for k in range(STITCHES):
        th0 = HOLE_PHASE + k * PITCH_ANGLE
        th1 = th0 + PITCH_ANGLE
        g0 = HOLE_GAP / R_STITCH
        us = np.linspace(0.0, 1.0, along)
        r_path = (R_STITCH + SLIT_S) + us * (-2.0 * SLIT_S)
        th_path = (th0 + g0) + us * (th1 - th0 - 2.0 * g0)
        px, py = r_path * np.cos(th_path), r_path * np.sin(th_path)
        surf = profile_z(np.hypot(px, py))
        end = np.exp(-(us / 0.075) ** 2) + np.exp(-((1.0 - us) / 0.075) ** 2)
        crown = np.sin(np.pi * us) ** 0.35
        pz = surf + THREAD_H * (0.55 * crown - 1.25 * end)
        path = np.stack([px, py, pz], axis=1)
        tang = np.gradient(path, axis=0)
        tang /= np.linalg.norm(tang, axis=1, keepdims=True)
        up = np.array([0.0, 0.0, 1.0])
        side = np.cross(up, tang)
        side /= np.linalg.norm(side, axis=1, keepdims=True)
        normal = np.cross(tang, side)
        length = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
        base = len(verts)
        for i in range(along):
            taper = 1.0 - 0.30 * end[i]
            for j in range(around):
                phi = 2.0 * math.pi * j / around
                ply = 1.0 + 0.13 * math.cos(3.0 * phi - 2.0 * math.pi * length[i] / lay)
                offset = (side[i] * THREAD_W * math.cos(phi) * taper * ply
                          + normal[i] * THREAD_H * math.sin(phi) * taper * ply)
                verts.append(path[i] + offset)
        for i in range(along - 1):
            for j in range(around):
                jn = (j + 1) % around
                a, b = base + i * around, base + (i + 1) * around
                faces.append((a + j, a + jn, b + jn, b + j))
    return mesh_object("waxed saddle stitches", verts, faces)


def brass_cup():
    # Lip crown: one convex turned bead (no flat), so each light draws a thin
    # concentric highlight instead of flooding a flat annulus.
    LIP_DROP = 0.026
    lip_bead = [
        (R_LIP_IN + (R_BODY - R_LIP_IN) * t,
         Z_LIP - LIP_DROP * (1.0 - math.sin(math.pi * t) ** 0.40))
        for t in [0.5 - 0.5 * math.cos(math.pi * i / 28) for i in range(1, 28)]
    ]
    cup = meshlib.lathe(
        [
            (0.0, Z_FLANGE - 0.060),
            (R_LIP_IN - 0.02, Z_FLANGE - 0.060),
            (R_LIP_IN, Z_FLANGE - 0.058),
            (R_LIP_IN, Z_FLANGE - 0.030),
            (R_LIP_IN, Z_LIP - 0.032),
        ]
        + lip_bead
        + [
            (R_BODY, Z_LIP - 0.040),
            (R_BODY, Z_LIP - 0.080),
            (R_BODY, 0.30),
            (R_BODY, 0.14),
            (R_BODY, 0.100),
            (R_BODY - 0.004, 0.090),
            (R_BODY - 0.012, 0.086),
        ],
        "turned brass cup",
        steps=192,
    )
    return cup


def base_collar():
    collar = meshlib.lathe(
        [
            (R_BODY - 0.02, 0.092),
            (R_COLLAR - 0.030, 0.092),
            (R_COLLAR - 0.010, 0.086),
            (R_COLLAR - 0.002, 0.076),
            (R_COLLAR, 0.066),
            (R_COLLAR, 0.020),
            (R_COLLAR - 0.004, 0.006),
            (R_COLLAR - 0.014, 0.0),
            (0.0, 0.0),
        ],
        "bead-blasted base collar",
        steps=192,
    )
    return collar


def indicator_pin():
    pin_z = float(profile_z(R_PIN)) - 0.004
    pin_head = arc(0.0, pin_z + 0.018 - 0.060, 0.060, 90,
                   90 - math.degrees(math.asin((PIN_R - 0.004) / 0.060)), 12)
    pin = meshlib.lathe(
        [(0.0, pin_z + 0.018)] + pin_head[1:]
        + [(PIN_R - 0.001, pin_z + 0.004), (PIN_R, pin_z + 0.001), (PIN_R, pin_z - 0.020),
           (0.0, pin_z - 0.020)],
        "polished brass indicator pin",
        steps=96,
    )
    pin.location.x = R_PIN
    return pin


LEATHERS = {k: f"leather-dyed-{k}" for k in ("tan", "black", "oxblood")}
THREADS = {k: f"thread-waxed-{k}" for k in ("cream", "black", "orange")}


class LeatherKnob(KnobScene):
    COMPONENT = "knob-leather"
    DEFAULT_OUT = "/tmp/knob-leather.png"
    EXTRA_SLOTS = ("thread",)
    SLOTS = {
        "body": "leather-dyed-tan",
        "thread": "thread-waxed-cream",
        "cap": "brass-turned-satin",
        "accent": "brass-turned-blasted",
        "indicator": "brass-turned-polished",
    }
    SLOT_HELP = {
        "body": "padded leather dome material",
        "thread": "saddle-stitch thread material",
        "cap": "turned cup material",
        "accent": "base collar material",
        "indicator": "indicator pin material",
    }
    PRESETS = {name: {"body": key} for name, key in LEATHERS.items()}
    DEFAULT_PRESET = "tan"
    ALIASES = {"preset": [Alias("--leather", values=tuple(LEATHERS))],
               "thread": [Alias("--thread", values=THREADS)]}

    def build_knob(self):
        cup = brass_cup()
        self.bind("cap", [cup])
        collar = base_collar()
        self.bind("accent", [collar])
        pad = leather_pad()
        self.bind("body", [pad])
        threads = stitch_threads()
        self.bind("thread", [threads])
        pin = indicator_pin()
        self.bind("indicator", [pin])
        return [cup, collar, pad, threads, pin]


if __name__ == "__main__":
    LeatherKnob.main()
