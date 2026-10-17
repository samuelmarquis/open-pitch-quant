"""stitchkit: saddle stitching along any closed outline on a flat face.

knob-leather's stitch threads, generalized from its one circle to any CCW
loop (panel-board's rectangle, squircle, rounded rect). Each visible stitch
is one tube of 3-ply waxed thread running from the outer end of one awl slit
to the inner end of the next — that crossing IS the saddle-stitch slant —
crowned at the middle and diving below the face at both ends, so the face
itself hides where the thread enters its hole.

Units are world units; callers scale from their own mm-per-unit. At 25 mm/u
the defaults are a 2.8 mm pitch and 0.7 mm thread, a strap's proportions
(design-lab/refs/threaded-leather.jpg).
"""
import math

import bpy
import numpy as np

PITCH = 0.11
SLANT_DEG = 15.0
HOLE_GAP = 0.006          # half the hole along the path
THREAD_W = 0.014          # half-width
THREAD_H = 0.010          # half-height: waxed thread flattens under tension
LAY = 0.034               # 3-ply lay length along the thread


def resample(loop, pitch):
    """Closed polyline -> (points, tangents, outward normals) at an even
    pitch that divides the perimeter exactly, so the last stitch meets the
    first."""
    p = np.asarray(loop, dtype=float)
    if np.allclose(p[0], p[-1]):
        p = p[:-1]
    seg = np.roll(p, -1, axis=0) - p
    seglen = np.linalg.norm(seg, axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seglen)])
    total = cum[-1]
    n = max(3, int(round(total / pitch)))
    s = np.linspace(0.0, total, n, endpoint=False)
    idx = np.searchsorted(cum, s, side="right") - 1
    t = (s - cum[idx]) / np.maximum(seglen[idx], 1e-12)
    pts = p[idx] + seg[idx] * t[:, None]
    tang = np.roll(pts, -1, axis=0) - np.roll(pts, 1, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    out = np.stack([tang[:, 1], -tang[:, 0]], axis=1)   # CCW loop: right of travel
    return pts, tang, out


def saddle_stitches(loop, z_top, name="saddle stitches", pitch=PITCH,
                    slant_deg=SLANT_DEG, hole_gap=HOLE_GAP, thread_w=THREAD_W,
                    thread_h=THREAD_H, along=18, around=10):
    """One mesh: a thread tube per stitch along `loop` (CCW (x, y) points) on
    the face at `z_top`."""
    pts, _tang, out = resample(loop, pitch)
    n = len(pts)
    verts, faces = [], []
    for k in range(n):
        a, b = pts[k], pts[(k + 1) % n]
        d = b - a
        dl = float(np.linalg.norm(d))
        if dl < 1e-9:
            continue
        u = d / dl
        nrm = 0.5 * (out[k] + out[(k + 1) % n])
        nrm /= np.linalg.norm(nrm)
        slit = 0.5 * (dl - 2.0 * hole_gap) * math.tan(math.radians(slant_deg))
        us = np.linspace(0.0, 1.0, along)
        run = hole_gap + us * (dl - 2.0 * hole_gap)
        cross = slit - us * 2.0 * slit           # outer end of one slit -> inner end of the next
        xy = a[None, :] + u[None, :] * run[:, None] + nrm[None, :] * cross[:, None]
        end = np.exp(-(us / 0.075) ** 2) + np.exp(-((1.0 - us) / 0.075) ** 2)
        crown = np.sin(np.pi * us) ** 0.35
        z = z_top + thread_h * (0.55 * crown - 1.25 * end)
        path = np.column_stack([xy, z])
        tg = np.gradient(path, axis=0)
        tg /= np.linalg.norm(tg, axis=1, keepdims=True)
        side = np.cross(np.array([0.0, 0.0, 1.0]), tg)
        side /= np.linalg.norm(side, axis=1, keepdims=True)
        up = np.cross(tg, side)
        length = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
        base = len(verts)
        for i in range(along):
            taper = 1.0 - 0.30 * end[i]
            for j in range(around):
                phi = 2.0 * math.pi * j / around
                ply = 1.0 + 0.13 * math.cos(3.0 * phi - 2.0 * math.pi * length[i] / LAY)
                verts.append(path[i] + side[i] * thread_w * math.cos(phi) * taper * ply
                             + up[i] * thread_h * math.sin(phi) * taper * ply)
        for i in range(along - 1):
            r0, r1 = base + i * around, base + (i + 1) * around
            for j in range(around):
                jn = (j + 1) % around
                faces.append((r0 + j, r0 + jn, r1 + jn, r1 + j))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    return ob
