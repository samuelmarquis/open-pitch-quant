"""Shared mesh geometry: revolves, sectors, corner/fillet loops, knurls, glyph
conform, bevel finishing.

Blender 5.2 (`bpy`, `bmesh`, `mathutils`). Each helper reproduces the vertex array
of the generator copy it was lifted from (max |diff| < 1e-6, `selftest_shared.py`);
float arithmetic is kept in the source's order, including `mathutils.Vector`
(single precision) where the source used it. Objects are linked to
`bpy.context.collection`.

Revolves
- `lathe(profile, name, steps, merge, recalc_normals, shade)`: bmesh.ops.spin of an
  OPEN (r, z) polyline about +Z, then remove_doubles. Copies:
    knob-boss, knob-led, knob-leather   steps=160 (shade="smooth")
    knob-heady                          steps=160, recalc_normals=True
    knob-chickenhead                    steps=128, shade="select"
    knob-handwheel, led-indicator       steps=96,  shade="select"
    toggle-bat                          steps=96,  shade="select" (its `axis` arg unused by callers is not carried)
    knob-witchhat                       steps=256
    knob-wood                           steps=192, shade=None
    knob-davies                         steps=256, recalc_normals=True, shade=None
    knob-hifi                           steps=288, merge=1e-6, recalc_normals=True, shade=40.0
  shade: "smooth" deselects all, activates, shade_smooth; "select" activates and
  selects WITHOUT deselecting others first, then shade_smooth (acts on every
  selected object); a number = per-edge smooth-by-angle in bmesh; None = none.
  conduit-corrugated's lathe (axis +X, closed option) is not covered.
- `revolve(profile, name, steps, rfun, unit, collapse_axis, order, smooth_angle)`:
  a CLOSED (r, z) or (r, z, mod) polygon, one ring per profile point, angular
  radius r*(1 + mod*(rfun(theta) - 1)). Copies:
    jack-socket lathe      steps=288, unit=1/25 (MM), smooth_angle=22.0
    display-nixie lathe    steps=SEG or seg, unit=MM, smooth_angle=24.0
    display-segment lathe  (r, z) profile, steps=SEG, unit=MM, smooth_angle=22.0
    knob-ring spun         steps=192, collapse_axis=False, order="angle", smooth_angle=None
- `sector` (knob-ring): annular-sector block a0..a1.
- `hex_rfun`, `flute_rfun(n, amp)`, `squircle_rfun(n)`: angular radius functions
  (jack-socket, display-nixie).

Loops
- `superellipse_loop(hx, hy, r, n, seg, clamp, sharp_below, dedupe, drop_wrap, min_r)`:
  CCW loop, four superellipse corners (n=2 circle, n=4 squircle). Copies:
    panel-board rounded_loop(hx,hy,r,n,seg=20)  defaults
    screen-monitor superellipse(..., seg=22)   seg=22
    rack-hardware rrect(..., n=4.0, seg=16)    seg=16
    meter-vu outline(..., seg=26)              seg=26, clamp=1.0, sharp_below=None,
                                               dedupe=1e-5, drop_wrap=True
    display-segment round_rect(hx,hy,r,n=5)    n=2.0, seg=<its n>, clamp=0.9,
                                               min_r=0.001, sharp_below=None, dedupe=None
  screen-monitor and display-segment evaluate the arc angle as (pi/2*k)/seg rather
  than (pi/2)*(k/seg). That is one ulp of angle, but at an arc end where cos or
  sin is ~0 the exponent 2/n amplifies it: screen-monitor's loop moves by up to
  1.2e-7 world units there (measured, n=5); display-segment's circular arcs are
  exact.
- `fillet_corner` (panel-board `_fillet`), `fillet` (display-nixie, closed or open,
  one radius), `filleted` (knob-witchhat, per-corner radii, Vector arithmetic).
  They differ in clamps (0.49 vs 0.45 of the adjacent run) and degenerate-angle
  guards and are kept separate.

Knurls
- `flute_offset` + `fluted_revolve` (knob-davies straight flutes: per-column
  inward offset along the 2-D profile normal, weighted by the profile's third
  column, capped at both ends on the axis).
- `diamond_knurl` (knob-hifi: two helical groove families on a lattice-aligned
  grid, crease-split quads, 45 deg run-out cones). Returns (object, axial_pitch).

Text
- `glyph_mesh(font, text, ...)`: FONT curve -> evaluated mesh (knob-witchhat).
- `conform_glyphs_to_cone(font, labels, ...)`: witchhat's stamped numerals.
  Labels are (text, theta, r_centre); multi-glyph labels get `kern` as
  space_character, single glyphs 1.0. Returns (object, top_faces) with top_faces
  a list of per-face [(r, theta), ...] in plan coordinates before subdivision.

Bevel
- `bevel`, `brush_uv`, `finish` (panel-board `_finish`: bevel, cube-projected
  `brush` UV, auto-smooth), `auto_smooth` (jack-socket `_smooth`).
"""

import math

import bmesh
import bpy
from mathutils import Vector


# ------------------------------------------------------------------ object utils
def activate(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def smooth(ob):
    activate(ob)
    bpy.ops.object.shade_smooth()
    return ob


def auto_smooth(ob, angle_deg):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.shade_auto_smooth(angle=math.radians(angle_deg))
    ob.select_set(False)
    return ob


def link_bmesh(name, bm, smooth_angle=None):
    """bmesh -> linked object; frees `bm`. With `smooth_angle` (deg) faces are
    smooth and edges sharper than it are marked flat."""
    if smooth_angle is not None:
        limit = math.radians(smooth_angle)
        for face in bm.faces:
            face.smooth = True
        for edge in bm.edges:
            if len(edge.link_faces) == 2 and edge.calc_face_angle(0.0) > limit:
                edge.smooth = False
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    return ob


# --------------------------------------------------------------------- revolves
def lathe(profile, name, steps=160, merge=1e-5, recalc_normals=False, shade="smooth"):
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1),
                   angle=2 * math.pi, steps=steps, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
    if recalc_normals:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if isinstance(shade, (int, float)) and not isinstance(shade, bool):
        return link_bmesh(name, bm, smooth_angle=shade)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    if shade == "smooth":
        smooth(ob)
    elif shade == "select":
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.shade_smooth()
    elif shade is not None:
        raise ValueError(f"lathe shade must be 'smooth', 'select', a number or None, not {shade!r}")
    return ob


def revolve(profile, name, steps=288, rfun=None, unit=1.0, collapse_axis=True,
            order="profile", smooth_angle=22.0):
    if order not in ("profile", "angle"):
        raise ValueError("revolve order must be 'profile' or 'angle'")
    pts = [(p[0], p[1], p[2] if len(p) > 2 else 0) for p in profile]
    n = len(pts)
    bm = bmesh.new()

    def vert(p, i):
        r, z, mod = p
        th = 2.0 * math.pi * i / steps
        k = 1.0 if rfun is None else rfun(th)
        rr = r * (1.0 + mod * (k - 1.0)) * unit
        return bm.verts.new((rr * math.cos(th), rr * math.sin(th), z * unit))

    grid = [None] * n
    if order == "profile":
        for a, p in enumerate(pts):
            if collapse_axis and p[0] <= 1e-9:
                grid[a] = [bm.verts.new((0.0, 0.0, p[1] * unit))] * steps
            else:
                grid[a] = [vert(p, i) for i in range(steps)]
    else:
        for a, p in enumerate(pts):
            if collapse_axis and p[0] <= 1e-9:
                raise ValueError("order='angle' does not support collapse_axis on r == 0")
            grid[a] = [None] * steps
        for i in range(steps):
            for a, p in enumerate(pts):
                grid[a][i] = vert(p, i)

    def face(quad_in):
        quad, seen = [], set()
        for v in quad_in:
            if id(v) not in seen:
                seen.add(id(v))
                quad.append(v)
        if len(quad) >= 3:
            try:
                bm.faces.new(quad)
            except ValueError:
                pass

    if order == "profile":
        for a in range(n):
            ra, rb = grid[a], grid[(a + 1) % n]
            for i in range(steps):
                j = (i + 1) % steps
                face((ra[i], ra[j], rb[j], rb[i]))
    else:
        for i in range(steps):
            j = (i + 1) % steps
            for a in range(n):
                a2 = (a + 1) % n
                face((grid[a][i], grid[a][j], grid[a2][j], grid[a2][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    if smooth_angle is not None:
        auto_smooth(ob, smooth_angle)
    return ob


def sector(name, r0, r1, z0, z1, a0, a1, steps=8):
    """Annular-sector solid spanning a0..a1 radians between radii r0 < r1."""
    bm = bmesh.new()
    lo, hi = [], []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        c, s = math.cos(a), math.sin(a)
        lo.append((bm.verts.new((r0 * c, r0 * s, z0)),
                   bm.verts.new((r1 * c, r1 * s, z0))))
        hi.append((bm.verts.new((r0 * c, r0 * s, z1)),
                   bm.verts.new((r1 * c, r1 * s, z1))))
    for i in range(steps):
        bm.faces.new((lo[i][0], lo[i][1], lo[i + 1][1], lo[i + 1][0]))       # bottom
        bm.faces.new((hi[i][0], hi[i + 1][0], hi[i + 1][1], hi[i][1]))       # top
        bm.faces.new((lo[i][0], lo[i + 1][0], hi[i + 1][0], hi[i][0]))       # inner
        bm.faces.new((lo[i][1], hi[i][1], hi[i + 1][1], lo[i + 1][1]))       # outer
    bm.faces.new((lo[0][0], hi[0][0], hi[0][1], lo[0][1]))                   # start cap
    bm.faces.new((lo[-1][0], lo[-1][1], hi[-1][1], hi[-1][0]))               # end cap
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def hex_rfun(theta):
    """Across-flats hex: 1 at a flat's centre, 1/cos30 at a corner."""
    t = ((theta + math.pi / 6) % (math.pi / 3)) - math.pi / 6
    return 1.0 / math.cos(t)


def flute_rfun(n, amp):
    return lambda theta: 1.0 + amp * math.cos(n * theta)


def squircle_rfun(n=4.0):
    """Rounded square with r(0) = 1."""
    def f(theta):
        c, s = abs(math.cos(theta)), abs(math.sin(theta))
        return 1.0 / (c ** n + s ** n) ** (1.0 / n)
    return f


# ------------------------------------------------------------------------ loops
def superellipse_loop(hx, hy, r, n=4.0, seg=20, clamp=0.999, sharp_below=1e-4,
                      dedupe=1e-6, drop_wrap=False, min_r=None):
    r = min(r, hx * clamp, hy * clamp)
    if min_r is not None:
        r = max(min_r, r)
    if sharp_below is not None and r <= sharp_below:
        return [(hx, hy), (-hx, hy), (-hx, -hy), (hx, -hy)]
    e = 2.0 / n
    pts = []
    for (cx, cy, t0) in ((hx - r, hy - r, 0.0), (-(hx - r), hy - r, math.pi / 2),
                         (-(hx - r), -(hy - r), math.pi), (hx - r, -(hy - r), 1.5 * math.pi)):
        for k in range(seg + 1):
            t = t0 + (math.pi / 2) * (k / seg)
            c, s = math.cos(t), math.sin(t)
            pts.append((cx + r * math.copysign(abs(c) ** e, c),
                        cy + r * math.copysign(abs(s) ** e, s)))
    if dedupe is None:
        return pts
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > dedupe or abs(p[1] - out[-1][1]) > dedupe:
            out.append(p)
    if (drop_wrap and len(out) > 2 and abs(out[0][0] - out[-1][0]) < dedupe
            and abs(out[0][1] - out[-1][1]) < dedupe):
        out.pop()
    return out


def fillet_corner(a, b, c, rad, seg=6):
    """Arc points replacing corner b between b->a and b->c (never b itself,
    unless the corner is degenerate)."""
    ax, ay = a[0] - b[0], a[1] - b[1]
    cx, cy = c[0] - b[0], c[1] - b[1]
    la = math.hypot(ax, ay) or 1e-9
    lc = math.hypot(cx, cy) or 1e-9
    ux, uy = ax / la, ay / la
    vx, vy = cx / lc, cy / lc
    cosang = max(-1.0, min(1.0, ux * vx + uy * vy))
    half = math.acos(cosang) / 2.0
    if half < 1e-4 or half > math.pi / 2 - 1e-4:
        return [b]
    t = min(rad / math.tan(half), la * 0.49, lc * 0.49)
    rad = t * math.tan(half)
    p1 = (b[0] + ux * t, b[1] + uy * t)
    p2 = (b[0] + vx * t, b[1] + vy * t)
    bx, by = ux + vx, uy + vy
    lb = math.hypot(bx, by) or 1e-9
    d = rad / math.sin(half)
    ctr = (b[0] + bx / lb * d, b[1] + by / lb * d)
    a0 = math.atan2(p1[1] - ctr[1], p1[0] - ctr[0])
    a1 = math.atan2(p2[1] - ctr[1], p2[0] - ctr[0])
    while a1 - a0 > math.pi:
        a1 -= 2 * math.pi
    while a0 - a1 > math.pi:
        a1 += 2 * math.pi
    return [(ctr[0] + rad * math.cos(a0 + (a1 - a0) * k / seg),
             ctr[1] + rad * math.sin(a0 + (a1 - a0) * k / seg))
            for k in range(seg + 1)]


def fillet(pts, rf, n=5, closed=False):
    """Round every real corner of a polyline to radius rf (clamped to 0.45 of
    each adjacent run); corners within 3 deg of straight or folded are kept."""
    m = len(pts)
    if m < 3 or rf <= 0:
        return list(pts)
    out = []
    rng = range(m) if closed else range(1, m - 1)
    if not closed:
        out.append(tuple(pts[0]))
    for i in rng:
        ax, ay = pts[(i - 1) % m]
        bx, by = pts[i]
        cx, cy = pts[(i + 1) % m]
        v1 = (ax - bx, ay - by)
        v2 = (cx - bx, cy - by)
        l1 = math.hypot(*v1)
        l2 = math.hypot(*v2)
        if l1 < 1e-9 or l2 < 1e-9:
            continue
        u1 = (v1[0] / l1, v1[1] / l1)
        u2 = (v2[0] / l2, v2[1] / l2)
        ang = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1])))
        if ang > math.radians(176) or ang < math.radians(3):
            out.append((bx, by))
            continue
        t = min(rf / math.tan(ang / 2), l1 * 0.45, l2 * 0.45)
        r_eff = t * math.tan(ang / 2)
        p1 = (bx + u1[0] * t, by + u1[1] * t)
        p2 = (bx + u2[0] * t, by + u2[1] * t)
        bis = (u1[0] + u2[0], u1[1] + u2[1])
        bl = math.hypot(*bis)
        if bl < 1e-9:
            out.append((bx, by))
            continue
        d = r_eff / math.sin(ang / 2)
        ctr = (bx + bis[0] / bl * d, by + bis[1] / bl * d)
        a1 = math.atan2(p1[1] - ctr[1], p1[0] - ctr[0])
        a2 = math.atan2(p2[1] - ctr[1], p2[0] - ctr[0])
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        for k in range(n + 1):
            aa = a1 + da * k / n
            out.append((ctr[0] + r_eff * math.cos(aa), ctr[1] + r_eff * math.sin(aa)))
    if not closed:
        out.append(tuple(pts[-1]))
    return out


def filleted(points, radii, seg=7):
    """Open polyline with a circular fillet of radii[i] at each interior corner
    (0 keeps the corner). Unclamped: a radius too large for its runs overshoots."""
    out = [points[0]]
    for i in range(1, len(points) - 1):
        rad = radii[i]
        p = Vector((*points[i], 0))
        if rad <= 0:
            out.append(points[i])
            continue
        u1 = (Vector((*points[i - 1], 0)) - p).normalized()
        u2 = (Vector((*points[i + 1], 0)) - p).normalized()
        half = 0.5 * math.acos(max(-1.0, min(1.0, u1.dot(u2))))
        t = rad / math.tan(half)
        start, end = p + u1 * t, p + u2 * t
        centre = p + (u1 + u2).normalized() * (rad / math.sin(half))
        a, b = start - centre, end - centre
        a0, a1 = math.atan2(a.y, a.x), math.atan2(b.y, b.x)
        while a1 - a0 > math.pi:
            a1 -= 2 * math.pi
        while a0 - a1 > math.pi:
            a1 += 2 * math.pi
        for k in range(seg + 1):
            ang = a0 + (a1 - a0) * k / seg
            out.append((centre.x + rad * math.cos(ang), centre.y + rad * math.sin(ang)))
    out.append(points[-1])
    return out


# ----------------------------------------------------------------------- knurls
def flute_offset(theta, flutes, groove_half, land_crown, flute_depth):
    """Inward offset at angle theta: crowned lands, narrow V-bottomed grooves
    (groove_half is a fraction of one flute period)."""
    phase = (theta * flutes / (2.0 * math.pi)) % 1.0
    s = abs(math.sin(math.pi * phase))
    edge = min(phase, 1.0 - phase) / groove_half
    groove = max(0.0, 1.0 - edge) ** 1.3
    return -land_crown * (1.0 - s) - flute_depth * groove


def fluted_revolve(name, profile, offset, cols, bottom_z=None, top_z=None):
    """Revolve an open (r, z, weight) profile into `cols` columns, displacing each
    ring along its outward 2-D profile normal by offset(theta) * weight, and cap
    both ends with a fan to an axis vertex at bottom_z / top_z (default: the
    first / last profile z). Faces smooth, normals recalculated."""
    prof = profile
    n = len(prof)
    normals = []
    for i in range(n):
        a = prof[max(0, i - 1)]
        b = prof[min(n - 1, i + 1)]
        tr, tz = b[0] - a[0], b[1] - a[1]
        length = math.hypot(tr, tz) or 1.0
        normals.append((tz / length, -tr / length))
    offsets = [offset(2.0 * math.pi * j / cols) for j in range(cols)]
    verts = []
    for (r, z, w), (nr, nz) in zip(prof, normals):
        for j in range(cols):
            th = 2.0 * math.pi * j / cols
            d = offsets[j] * w
            rr = r + d * nr
            zz = z + d * nz
            verts.append((rr * math.cos(th), rr * math.sin(th), zz))
    faces = []
    for i in range(n - 1):
        for j in range(cols):
            k = (j + 1) % cols
            faces.append((i * cols + j, i * cols + k, (i + 1) * cols + k, (i + 1) * cols + j))
    bottom = len(verts)
    verts.append((0.0, 0.0, prof[0][1] if bottom_z is None else bottom_z))
    top = len(verts)
    verts.append((0.0, 0.0, prof[-1][1] if top_z is None else top_z))
    for j in range(cols):
        k = (j + 1) % cols
        faces.append((bottom, k, j))
        faces.append(((n - 1) * cols + j, (n - 1) * cols + k, top))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    return ob


def diamond_knurl(name, r, n, angle_deg, depth, flat, z_lo, z_hi,
                  r_chamfer_bot, r_chamfer_top, k=16, smooth_angle=22.0):
    """Diamond knurl band of crest radius r between z_lo and z_hi: `n` grooves
    around per helix set at `angle_deg` from the axis, crest-to-root `depth`,
    crests truncated at `flat`, run-out cones reaching radius r_chamfer_* at the
    band ends. `k` grid steps per groove period. Returns (object, axial_pitch)."""
    circ_pitch = 2 * math.pi * r / n
    axial_pitch = circ_pitch / math.tan(math.radians(angle_deg))
    height = z_hi - z_lo
    rows = max(8, round(height / axial_pitch * k))
    axial_pitch = height * k / rows
    cols = n * k

    def tri(x):
        f = x - math.floor(x)
        return 1.0 - abs(1.0 - 2.0 * f)

    bm = bmesh.new()
    grid = []
    for j in range(rows + 1):
        z = z_lo + height * j / rows
        b = j / k
        cone = min(r_chamfer_top + (z_hi - z), r_chamfer_bot + (z - z_lo))
        row = []
        for i in range(cols):
            a = i / k
            h = min(tri(a + b), tri(a - b), flat) / flat
            rr = min(r - depth * (1.0 - h), cone)
            t = 2 * math.pi * i / cols
            row.append(bm.verts.new((rr * math.cos(t), rr * math.sin(t), z)))
        grid.append(row)
    flat_marks = {round(flat * k / 2) % k, (k - round(flat * k / 2)) % k, 0, k // 2}
    for j in range(rows):
        for i in range(cols):
            i1 = (i + 1) % cols
            p00, p10 = grid[j][i], grid[j][i1]
            p01, p11 = grid[j + 1][i], grid[j + 1][i1]
            if (i + j + 1) % k in flat_marks:     # u-crease: (i+1,j)-(i,j+1)
                bm.faces.new((p00, p10, p01))
                bm.faces.new((p10, p11, p01))
            else:                                 # v-crease or planar
                bm.faces.new((p00, p10, p11))
                bm.faces.new((p00, p11, p01))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return link_bmesh(name, bm, smooth_angle=smooth_angle), axial_pitch


# ------------------------------------------------------------------------- text
def glyph_mesh(font, text, space_character=1.0, offset=0.0, extrude=0.02,
               resolution_u=10, size=1.0, align_x="LEFT"):
    """Evaluated mesh of `text` set in `font` (a bpy font), glyph baseline on
    y = 0, extruded +-extrude about z = 0. The caller owns the returned mesh."""
    curve = bpy.data.curves.new(f"numeral {text}", type="FONT")
    curve.body = text
    curve.font = font
    curve.size = size
    curve.align_x = align_x
    curve.extrude = extrude
    curve.offset = offset
    curve.resolution_u = resolution_u
    curve.space_character = space_character
    tmp = bpy.data.objects.new(f"tmp {text}", curve)
    bpy.context.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    return mesh


def conform_glyphs_to_cone(font, labels, cap_height, cone_z, slope_deg, proud,
                           buried, max_edge, kern=1.0, stroke_offset=0.0,
                           ref_text="1", subdiv_iters=8, mesh_name="stamped numerals",
                           object_name="stamped numerals 1-10"):
    """Stamp text labels onto a cone of revolution.

    Glyphs are scaled so `ref_text`'s height is `cap_height`, centred on their
    own x extent and the reference's y band, and wrapped so glyph x runs along
    the circle of radius r_centre (arc length) and glyph y runs up the slant
    (+y outward). Edges longer than `max_edge` (world) are split up to
    `subdiv_iters` times, then front vertices (z > 0) sit `proud` off the surface
    `cone_z(r)` along its normal and back vertices `buried` below it.
    `slope_deg` is the cone's angle from the panel plane."""
    ref = glyph_mesh(font, ref_text, offset=stroke_offset)
    ys = [v.co.y for v in ref.vertices]
    base_y, cap_y = min(ys), max(ys)
    k = cap_height / (cap_y - base_y)
    bpy.data.meshes.remove(ref)

    cos_s, sin_s = math.cos(math.radians(slope_deg)), math.sin(math.radians(slope_deg))
    top_faces = []
    bm_all = bmesh.new()
    for text, theta_n, r_c in labels:
        space = kern if len(text) > 1 else 1.0
        mesh = glyph_mesh(font, text, space_character=space, offset=stroke_offset)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bpy.data.meshes.remove(mesh)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.normal_update()
        xs = [v.co.x for v in bm.verts]
        x_mid = 0.5 * (min(xs) + max(xs))
        y_mid = 0.5 * (base_y + cap_y)

        def plan(x, y, x_mid=x_mid, y_mid=y_mid, theta_n=theta_n, r_c=r_c):
            u = (x - x_mid) * k
            s = (y - y_mid) * k
            r = r_c + s * cos_s
            th = theta_n - u / r
            return r, th

        for f in bm.faces:
            if f.normal.z > 0.5:
                top_faces.append([plan(v.co.x, v.co.y) for v in f.verts])

        for _ in range(subdiv_iters):
            long = [e for e in bm.edges
                    if (e.verts[0].co - e.verts[1].co).xy.length * k > max_edge]
            if not long:
                break
            bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=False)
            bmesh.ops.triangulate(bm, faces=bm.faces)
        for v in bm.verts:
            x, y, z = v.co
            r, th = plan(x, y)
            off = proud if z > 0 else -buried
            zz = cone_z(r)
            rr = r + off * sin_s
            v.co = (rr * math.cos(th), rr * math.sin(th), zz + off * cos_s)
        tmp = bpy.data.meshes.new("tmp")
        bm.to_mesh(tmp)
        bm.free()
        bm_all.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    mesh = bpy.data.meshes.new(mesh_name)
    bm_all.normal_update()
    bm_all.to_mesh(mesh)
    bm_all.free()
    ob = bpy.data.objects.new(object_name, mesh)
    bpy.context.collection.objects.link(ob)
    return ob, top_faces


# ------------------------------------------------------------------------ bevel
def bevel(ob, width, segments=2, angle_deg=30.0):
    """Apply an angle-limited bevel modifier."""
    bpy.context.view_layer.objects.active = ob
    bev = ob.modifiers.new("bevel", "BEVEL")
    bev.width = width
    bev.segments = segments
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(angle_deg)
    bpy.ops.object.modifier_apply(modifier="bevel")
    return ob


def brush_uv(ob, name="brush"):
    """Cube-projected UV layer `name`, made active."""
    u = ob.data.uv_layers.get(name) or ob.data.uv_layers.new(name=name)
    ob.data.uv_layers.active = u
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=1.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    return ob


def finish(ob, bevel_w=0.010, uv=True, smooth_deg=20.0, angle_deg=30.0, segments=2):
    """Bevel every edge past `angle_deg`, cube-project a `brush` UV, auto-smooth
    at `smooth_deg` (keep it below the bevel's facet angle so flat faces stay
    flat). Operates on the active object; `ob` is made active first."""
    bpy.context.view_layer.objects.active = ob
    bevel(ob, bevel_w, segments=segments, angle_deg=angle_deg)
    if uv:
        brush_uv(ob)
    bpy.ops.object.shade_auto_smooth(angle=math.radians(smooth_deg))
    return ob
