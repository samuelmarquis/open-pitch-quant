"""railkit: the geometry the rail family's three members share.

Boolean-free construction throughout, as knob-ring builds its plate: a board
with rectangular apertures is a rectangular partition, not a difference.

Two traps live here, both found by measurement rather than by eye (pass 33):

  * The board must be ONE welded surface. Tiling closed boxes leaves a
    coincident pair of interior walls at every cell boundary whose top edge
    sits exactly in the surface; they print as a hairline grid across the whole
    board — faint on dark metal, blatant on catalin.
  * Solidify grows along the face normal, so the board needs `offset = -1.0`.
    With `+1` its face lands at `z_top + thickness` and buries every tick and
    cursor underneath it, and it fails SILENTLY: the aperture still reads as a
    slot, so the render merely looks deeper.
"""
import bmesh
import bpy

import meshlib

EPS_LIFT = 4e-4          # coplanar tops z-fight; this clears them (knob-ring)


def box(name, x0, x1, y0, y1, z0, z1):
    """An axis-aligned box as its own object."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    return meshlib.link_bmesh(name, bm)


def chamfer_frame(name, x0, x1, y0, y1, z_top, drop, run):
    """The sloped lip between a board's face and an aperture wall: a rectangular
    frame of quads from the outer rect at z_top down and in to the inner rect at
    z_top - drop. Built directly so the chamfer exists only on the aperture's
    free edge — a bevel modifier would round every edge of the board instead."""
    ix0, ix1, iy0, iy1 = x0 + run, x1 - run, y0 + run, y1 - run
    zi = z_top - drop
    bm = bmesh.new()
    ov = [bm.verts.new((x, y, z_top)) for x, y in
          ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    iv = [bm.verts.new((x, y, zi)) for x, y in
          ((ix0, iy0), (ix1, iy0), (ix1, iy1), (ix0, iy1))]
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((ov[i], ov[j], iv[j], iv[i]))
    bm.normal_update()
    return meshlib.link_bmesh(name, bm)


def well(name, x0, x1, y0, y1, z_top, depth, run=0.012, drop=0.010):
    """A recessed rectangular slot: chamfer lip, four walls, floor.
    Returns (parts, aperture_rect) — the rect is the board's hole."""
    zf = z_top - depth
    ix0, ix1, iy0, iy1 = x0 + run, x1 - run, y0 + run, y1 - run
    parts = [
        chamfer_frame(f"{name}-lip", x0, x1, y0, y1, z_top, drop, run),
        box(f"{name}-floor", ix0, ix1, iy0, iy1, zf, zf + 0.004),
        box(f"{name}-wN", ix0, ix1, iy1 - 0.004, iy1, zf, z_top - drop),
        box(f"{name}-wS", ix0, ix1, iy0, iy0 + 0.004, zf, z_top - drop),
        box(f"{name}-wE", ix1 - 0.004, ix1, iy0, iy1, zf, z_top - drop),
        box(f"{name}-wW", ix0, ix0 + 0.004, iy0, iy1, zf, z_top - drop),
    ]
    return parts, (x0, x1, y0, y1)


def tick(name, x, y0, y1, z_top, width, proud=EPS_LIFT):
    """One engraved-and-filled tick, sitting just proud of the board so it never
    z-fights. The fill MATERIAL is the family's choice; this is only geometry."""
    return box(name, x - width / 2, x + width / 2, y0, y1, z_top, z_top + proud)


def tick_row(prefix, x0, travel, z_top, y_in, major, minor,
             major_len=0.100, minor_len=0.050, major_w=0.020, minor_w=0.012):
    """The graduated field above a slot: `major` intervals of `minor` divisions.
    This field is what makes a rail read as a ruler rather than a track, so it
    is the position rail's dominant visual and the crossfader has none."""
    out = []
    if major <= 0:
        return out
    for i in range(major + 1):
        x = x0 + travel * i / major
        out.append(tick(f"{prefix}-maj{i:02d}", x, y_in, y_in + major_len, z_top, major_w))
        if i < major:
            for k in range(1, minor):
                xm = x + travel * (k / minor) / major
                out.append(tick(f"{prefix}-min{i:02d}{k}", xm, y_in, y_in + minor_len,
                                z_top, minor_w))
    return out


def board(w, h, z_top, thickness, apertures, name="plate"):
    """The board as a boolean-free rectangular partition, welded into ONE mesh
    and solidified DOWNWARD. See the module docstring for why both matter."""
    xs, ys = {-w / 2, w / 2}, {-h / 2, h / 2}
    for x0, x1, y0, y1 in apertures:
        xs.update((x0, x1))
        ys.update((y0, y1))
    xs, ys = sorted(xs), sorted(ys)
    bm = bmesh.new()
    vert = {}

    def at(x, y):
        key = (round(x, 6), round(y, 6))
        if key not in vert:
            vert[key] = bm.verts.new((x, y, z_top))
        return vert[key]

    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if any(x0 < cx < x1 and y0 < cy < y1 for x0, x1, y0, y1 in apertures):
                continue
            bm.faces.new((at(xs[i], ys[j]), at(xs[i + 1], ys[j]),
                          at(xs[i + 1], ys[j + 1]), at(xs[i], ys[j + 1])))
    bmesh.ops.dissolve_limit(bm, angle_limit=1e-4, verts=bm.verts, edges=bm.edges)
    bm.normal_update()
    ob = meshlib.link_bmesh(name, bm)
    solid = ob.modifiers.new("solidify", "SOLIDIFY")
    solid.thickness = thickness
    solid.offset = -1.0
    return ob


def grip_cap(name, x, half_w, half_d, z_top, height, sink=0.020, bevel=0.026):
    """A low, wide thumb cap: the crossfader's saddle."""
    ob = box(name, x - half_w, x + half_w, -half_d, half_d, z_top - sink, z_top + height)
    meshlib.finish(ob, bevel_w=bevel, uv=False, smooth_deg=26.0, segments=3)
    return ob


def grip_ribs(prefix, x, half_w, half_d, z_top, height,
              land=0.052, pitch=0.034, rib=0.012):
    """Fine grip ribs either side of a WIDE smooth centre land. The break in the
    rhythm marks the cap's middle, so the cap needs no raised index rib across
    it — that bump would interrupt the very patch that does the marking."""
    out, k = [], 1
    while True:
        xo = land + pitch * k
        if xo > half_w - 0.030:
            return out
        for s in (-1, 1):
            out.append(box(f"{prefix}-rib{s:+d}{k:02d}",
                           x + s * xo - rib / 2, x + s * xo + rib / 2,
                           -half_d * 0.86, half_d * 0.86,
                           z_top + height - 0.002, z_top + height + 0.007))
        k += 1


def carriage(name, x, half_w, half_d, z_top, height, sink=0.012, bevel=0.010):
    """A narrow machined carriage: the position rail's cursor and the range
    rail's jaws. Narrow is the point — it is what separates a cursor-on-a-scale
    from the crossfader's wide balance saddle at product size."""
    ob = box(name, x - half_w, x + half_w, -half_d, half_d, z_top - sink, z_top + height)
    meshlib.finish(ob, bevel_w=bevel, uv=False, smooth_deg=26.0, segments=2)
    return ob


def shadow_catcher(objects):
    """Cut-in: the board catches shadow and paints nothing, so the cut reads
    into the CONSUMER's material rather than one we chose for them."""
    for ob in objects:
        ob.is_shadow_catcher = True
