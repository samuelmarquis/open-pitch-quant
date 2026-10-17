"""Conduit path physics: take-off rays, board-plane drapes, viewer-facing lead +
graded fold, dead-on aim and yaw, film projection and the image-point checks.

Blender Python (`mathutils.Vector`, single precision). Functions keep the source
expression order, so sampled points are float-identical to the generator copy
(`selftest_shared.py` compares ribbon, smooth and corrugated paths at < 1e-9).
No module state: everything a generator held as a global is a parameter or an
attribute of the object that owns it.

Pieces and where they come from (rib = conduit-ribbon, the original; cor =
conduit-corrugated; smo = conduit-smooth):

  auto_dir, takeoff, slot_azimuth    rib (cor/smo: no slot)
  H5, lead_fraction, fold_window     rib == cor == smo
  aim(P, inplane, C, law)            laws physical | plane | full. rib's `deadon`
                                     is `plane`; cor/smo's `deadon` is `full`.
                                     cor/smo dot C-P with (inplane.x, inplane.y, 0);
                                     identical for every take-off ray (z = 0).
  ViewerRun                          rib/cor/smo _ease_coeffs, _viewer_delta,
                                     path_point, _build, tangent. The fold reads
                                     board_pd(t) -> (P, d/dt, d2/dt2); rib passes
                                     its canon drape, cor/smo their board path.
                                     tangent(): rib states BOTH board-plane end
                                     tangents analytically (pass board_start=DA,
                                     board_end=-DB); cor/smo difference them.
  CanonDrape                         rib _base_point/_base_d1/_base_d2: full-chord
                                     Hermite + (4t(1-t))^2 sag + lift*(4t(1-t))^1.5
  ClampedBase                        cor == smo _hermite/_base/_base_d: straight
                                     leads of clamp_l + Hermite between them.
                                     cor rescales clamp_u after construction when
                                     clamp_u + blend_u > 0.49 (assign .clamp_u).
  accepted_canon(_d)                 cor _accepted(_d)  (same law as rib's drape)
  accepted_hump(_d)                  smo _accepted(_d)  (inline 6x^5-15x^4+10x^3;
                                     cor's `--envelope hump` uses sstep() instead,
                                     a different float evaluation of that polynomial)
  ease_coefficients, graded_ease(_d) cor _ease_env/_env_d default branch == smo _hump/_hump_d
  sstep, YawComp (cw, z)             cor == smo _sstep/_cw/_zcomp
  BoardPath                          cor/smo _board_point/_board_pd (lift_w = LIFT_K*R
                                     in cor, 0.9*R in smo)
  phi_for                            cor/smo _phi_for (FACING gate stays in the caller)
  Film.deadon / Film.basis           rib/cor _pxy (z-difference) / smo _pxy (basis)
  rim_dev, circ_img                  cor/smo (projection through a Film)
  face_check_circles                 cor/smo _face_check (circles in units of `unit`)
  face_check_slot                    rib _face_check (rectangular slotted header)

Envelope dispatch (`--envelope canon|hump|r7|clamped`), camera fitting and every
diagnostic print stay in the generators.
"""

import math

from mathutils import Vector

UP = Vector((0.0, 0.0, 1.0))


# ------------------------------------------------------------------- take-off
def auto_dir(A, B, side, takeoff="horizontal", ch=None):
    """`--a-dir auto`: the chord (`takeoff == "chord"`) or level along +-x, always
    pointing into the span."""
    if ch is None:
        ch = (B - A).normalized()
    if takeoff == "chord":
        return ch if side == "a" else -ch
    sgn = 1.0 if B.x >= A.x else -1.0
    return Vector((sgn if side == "a" else -sgn, 0.0, 0.0))


def slot_azimuth(deg, side, ch):
    """A viewer end's slot axis (degrees) inverted into its fold azimuth: the
    perpendicular pointing into the span."""
    a = math.radians(deg)
    n = Vector((-math.sin(a), math.cos(a), 0.0))
    return n if n.dot(ch if side == "a" else -ch) >= 0 else -n


def takeoff(spec, side, A, B, mode="horizontal", slot=None, ch=None):
    """In-plane take-off ray for `--a-dir/--b-dir` spec: auto | viewer | degrees
    CCW from +x. `slot` (degrees) overrides with slot_azimuth."""
    if ch is None:
        ch = (B - A).normalized()
    if slot is not None:
        return slot_azimuth(slot, side, ch)
    if str(spec).lower() in ("auto", "viewer"):
        return auto_dir(A, B, side, mode, ch)
    a = math.radians(float(spec))
    return Vector((math.cos(a), math.sin(a), 0.0)).normalized()


# ----------------------------------------------------------------- viewer fold
def H5(v):
    """Quintic Hermite weights taking (value, slope, curvature) at v=0 to 0 at v=1."""
    v2, v3 = v * v, v * v * v
    return (1 - 10 * v3 + 15 * v3 * v - 6 * v3 * v2,
            v - 6 * v3 + 8 * v3 * v - 3 * v3 * v2,
            0.5 * v2 - 1.5 * v3 + 1.5 * v3 * v - 0.5 * v3 * v2)


def lead_fraction(lead_l, total, view_a, view_b):
    """One viewer lead as a fraction of the estimated run (0 without viewer ends)."""
    tot_est = total + (lead_l if view_a else 0.0) + (lead_l if view_b else 0.0)
    return lead_l / tot_est if (view_a or view_b) else 0.0


def fold_window(lead_u, ease=1.0 / 3.0):
    """T2: where the graded fold hands over to the drape, guard-railed to
    [0.25, 0.98] of the half-span left after the lead."""
    return lead_u + min(max(ease - lead_u, 0.25 * (0.5 - lead_u)),
                        0.98 * (0.5 - lead_u))


def aim(P, inplane, C, law="plane"):
    """(axis, angle to +z) of a viewer terminal at P for camera centre C.
    physical: +z. plane: tilt within the plane of +z and `inplane` so C lies in
    the side-wall plane. full: the axis points at C. C None -> +z."""
    if C is None or law == "physical":
        return Vector((0.0, 0.0, 1.0)), 0.0
    W = Vector((C[0] - P.x, C[1] - P.y, C[2] - P.z))
    if law == "plane":
        psi = math.atan2(W.dot(inplane), W.z)
        return (inplane * math.sin(psi) + UP * math.cos(psi)).normalized(), psi
    if law != "full":
        raise ValueError(f"aim law must be physical, plane or full, not {law!r}")
    D = W.normalized()
    return D, D.angle(UP)


class ViewerRun:
    """The whole centreline: the board-plane path `board(t)`, replaced at a
    viewer end by a straight lead of `lead_l` on the terminal axis over
    tau <= lead_u and a quintic fold graded back into the board path by t2.
    `board_pd(t)` returns (point, d/dt, d2/dt2) of the board path. Set each
    viewer end's axis with `set_axis` (recomputes its fold)."""

    def __init__(self, A, B, board, board_pd=None, view_a=False, view_b=False,
                 lead_l=0.0, lead_u=0.0, t2=0.0):
        self.A, self.B = A, B
        self.board, self.board_pd = board, board_pd
        self.view_a, self.view_b = view_a, view_b
        self.viewer = view_a or view_b
        self.lead_l, self.lead_u, self.t2 = lead_l, lead_u, t2
        self.axis_a = self.axis_b = Vector((0.0, 0.0, 1.0))
        self.ease_a = self.ease_b = None

    def set_axis(self, side, axis):
        if side == "a":
            self.axis_a = axis
            self.ease_a = self.ease_coeffs("a")
        else:
            self.axis_b = axis
            self.ease_b = self.ease_coeffs("b")

    def ease_coeffs(self, side):
        P0, D = (self.A, self.axis_a) if side == "a" else (self.B, self.axis_b)
        sgn = 1.0 if side == "a" else -1.0
        t = self.lead_u if side == "a" else 1.0 - self.lead_u
        w = self.t2 - self.lead_u
        P, d1, d2 = self.board_pd(t)
        return (P0 + D * self.lead_l - P,
                (D * (self.lead_l / self.lead_u) - d1 * sgn) * w,
                d2 * (-w * w))

    def viewer_delta(self, side, tau):
        c = self.ease_a if side == "a" else self.ease_b
        h = H5((tau - self.lead_u) / (self.t2 - self.lead_u))
        return c[0] * h[0] + c[1] * h[1] + c[2] * h[2]

    def point(self, t):
        if self.viewer:
            for side, on in (("a", self.view_a), ("b", self.view_b)):
                if not on:
                    continue
                tau = t if side == "a" else 1.0 - t
                if tau <= self.lead_u:
                    P0, D = (self.A, self.axis_a) if side == "a" else (self.B, self.axis_b)
                    return P0 + D * (self.lead_l * tau / self.lead_u)
                if tau < self.t2:
                    return self.board(t) + self.viewer_delta(side, tau)
        return self.board(t)

    def sample(self, n):
        """(points, cumulative arclength) at t = i/(n-1)."""
        path = [self.point(i / (n - 1)) for i in range(n)]
        arclen = [0.0]
        for i in range(1, n):
            arclen.append(arclen[-1] + (path[i] - path[i - 1]).length)
        return path, arclen

    def tangent(self, path, i, board_start=None, board_end=None):
        """Unit tangent at sample i: a viewer end's axis, else the given analytic
        board-plane end ray, else a central (one-sided at the ends) difference."""
        n = len(path)
        if i == 0:
            if self.view_a:
                return self.axis_a
            if board_start is not None:
                return board_start
        if i == n - 1:
            if self.view_b:
                return -self.axis_b
            if board_end is not None:
                return board_end
        a = max(0, i - 1)
        b = min(n - 1, i + 1)
        return (path[b] - path[a]).normalized()


# ---------------------------------------------------------------------- drapes
class CanonDrape:
    """Full-chord cubic Hermite with take-off tangents DA, -DB (magnitude |chord|),
    sag_w * (4t(1-t))^2 down (-y) and lift * (4t(1-t))^1.5 up (+z)."""

    def __init__(self, A, B, DA, DB, sag_w, lift):
        self.A, self.B = A, B
        chord_l = (B - A).length
        self.M0 = DA * chord_l
        self.M1 = -DB * chord_l
        self.sag_w, self.lift = sag_w, lift

    def point(self, t):
        A, B, M0, M1 = self.A, self.B, self.M0, self.M1
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1
        h10 = t ** 3 - 2 * t ** 2 + t
        h01 = -2 * t ** 3 + 3 * t ** 2
        h11 = t ** 3 - t ** 2
        P = A * h00 + M0 * h10 + B * h01 + M1 * h11
        env = (4 * t * (1 - t)) ** 2
        sag = self.sag_w * env
        lift = self.lift * (4 * t * (1 - t)) ** 1.5
        return P + Vector((0, -sag, lift))

    def d1(self, t):
        A, B, M0, M1 = self.A, self.B, self.M0, self.M1
        P = (A * (6 * t * t - 6 * t) + M0 * (3 * t * t - 4 * t + 1)
             + B * (-6 * t * t + 6 * t) + M1 * (3 * t * t - 2 * t))
        b, bp = 4 * t - 4 * t * t, 4 - 8 * t
        return P + Vector((0, -self.sag_w * 2 * b * bp,
                           self.lift * 1.5 * math.sqrt(max(b, 1e-12)) * bp))

    def d2(self, t):
        A, B, M0, M1 = self.A, self.B, self.M0, self.M1
        P = (A * (12 * t - 6) + M0 * (6 * t - 4)
             + B * (-12 * t + 6) + M1 * (6 * t - 2))
        b, bp, bpp = 4 * t - 4 * t * t, 4 - 8 * t, -8.0
        r = math.sqrt(max(b, 1e-12))
        return P + Vector((0, -self.sag_w * 2 * (bp * bp + b * bpp),
                           self.lift * (0.75 * bp * bp / r + 1.5 * r * bpp)))

    def pd(self, t):
        return self.point(t), self.d1(t), self.d2(t)


def sstep(x):
    """smootherstep 6x^5-15x^4+10x^3, clamped: f = f' = f'' = 0 at 0 and 1."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return x * x * x * (x * (x * 6 - 15) + 10)


class ClampedBase:
    """Straight leads of clamp_l along DA from A and DB from B, and a cubic
    Hermite between the lead ends with tangents of magnitude equal to its own
    chord. When both rays are the chord it is exactly A.lerp(B, t)."""

    def __init__(self, A, B, DA, DB, clamp_l):
        self.A, self.B, self.DA, self.DB = A, B, DA, DB
        ch = (B - A).normalized()
        self.lerp_ok = (DA - ch).length < 1e-9 and (DB + ch).length < 1e-9
        self.clamp_l = clamp_l
        self.A2 = A + DA * clamp_l
        self.B2 = B + DB * clamp_l
        mid_l = (self.B2 - self.A2).length
        self.tot_l = 2 * clamp_l + mid_l
        self.clamp_u = clamp_l / self.tot_l if self.tot_l > 0 else 0.0
        self.M0 = DA * mid_l
        self.M1 = -DB * mid_l

    def hermite(self, tau):
        h00 = 2 * tau ** 3 - 3 * tau ** 2 + 1
        h10 = tau ** 3 - 2 * tau ** 2 + tau
        h01 = -2 * tau ** 3 + 3 * tau ** 2
        h11 = tau ** 3 - tau ** 2
        return self.A2 * h00 + self.M0 * h10 + self.B2 * h01 + self.M1 * h11

    def point(self, t):
        cu = self.clamp_u
        if self.lerp_ok:
            return self.A.lerp(self.B, t)
        if cu > 0.0:
            if t <= cu:
                return self.A + self.DA * (t / cu * self.clamp_l)
            if t >= 1.0 - cu:
                return self.B + self.DB * ((1.0 - t) / cu * self.clamp_l)
            return self.hermite((t - cu) / (1.0 - 2 * cu))
        return self.hermite(t)

    def d(self, t):
        """(d/dt, d2/dt2)."""
        cu = self.clamp_u
        Z = Vector((0.0, 0.0, 0.0))
        if self.lerp_ok:
            return self.B - self.A, Z
        if cu > 0.0:
            if t <= cu:
                return self.DA * (self.clamp_l / cu), Z
            if t >= 1.0 - cu:
                return -self.DB * (self.clamp_l / cu), Z
            q = 1.0 / (1.0 - 2 * cu)
            tau = (t - cu) * q
        else:
            q, tau = 1.0, t
        A2, B2, M0, M1 = self.A2, self.B2, self.M0, self.M1
        return ((A2 * (6 * tau * tau - 6 * tau) + M0 * (3 * tau * tau - 4 * tau + 1)
                 + B2 * (-6 * tau * tau + 6 * tau) + M1 * (3 * tau * tau - 2 * tau))
                * q,
                (A2 * (12 * tau - 6) + M0 * (6 * tau - 4)
                 + B2 * (-12 * tau + 6) + M1 * (6 * tau - 2)) * (q * q))


def accepted_canon(t):
    """(sag, lift) = ((4t(1-t))^2, (4t(1-t))^1.5)."""
    base = 4 * t * (1 - t)
    return base ** 2, base ** 1.5


def accepted_canon_d(t):
    g = 4 * t - 4 * t * t
    gp, gpp = 4 - 8 * t, -8.0
    r = math.sqrt(g)
    return ((g * g, 2 * g * gp, 2 * (gp * gp + g * gpp)),
            (g * r, 1.5 * r * gp, 0.75 * gp * gp / r + 1.5 * r * gpp))


def accepted_hump(t, clamp_u):
    """Reparametrised C2 hump outside the clamp: sag = smootherstep of the
    mirrored parameter, lift = sag^0.75; canon law when clamp_u <= 0."""
    if clamp_u <= 0:
        return (4 * t * (1 - t)) ** 2, (4 * t * (1 - t)) ** 1.5
    tt = min(1.0, max(0.0, (t - clamp_u) / (1 - 2 * clamp_u)))
    x = 2 * tt if tt <= 0.5 else 2 * (1 - tt)
    e = 6 * x ** 5 - 15 * x ** 4 + 10 * x ** 3
    return e, e ** 0.75


def accepted_hump_d(t, clamp_u):
    """Analytic ((E, E', E''), (L, L', L'')) of accepted_hump; valid for
    clamp_u < t < 0.5."""
    q = 2.0 / (1 - 2 * clamp_u)
    x = (t - clamp_u) * q
    e = 6 * x ** 5 - 15 * x ** 4 + 10 * x ** 3
    ep = (30 * x ** 4 - 60 * x ** 3 + 30 * x ** 2) * q
    epp = (120 * x ** 3 - 180 * x ** 2 + 60 * x) * q * q
    lp = 0.75 * e ** -0.25 * ep
    lpp = 0.75 * (e ** -0.25 * epp - 0.25 * e ** -1.25 * ep * ep)
    return ((e, ep, epp), (e ** 0.75, lp, lpp))


def ease_coefficients(accepted_d, clamp_u, ease=1.0 / 3.0):
    """(t2, ease_c) for the graded ease from the clamp into the accepted drape;
    accepted_d(t) -> ((E, E', E''), (L, L', L'')). (0.0, []) without a clamp."""
    t2 = 0.0
    ease_c = []
    if clamp_u > 0.0:
        lo, hi = 0.25 * (0.5 - clamp_u), 0.98 * (0.5 - clamp_u)
        t2 = clamp_u + min(max(ease - clamp_u, lo), hi)
        eb = t2 - clamp_u
        for d in accepted_d(t2):
            V, D, K = d[0], d[1] * eb, d[2] * eb * eb
            ease_c.append((10 * V - 4 * D + 0.5 * K,
                           7 * D - K - 15 * V,
                           0.5 * K - 3 * D + 6 * V))
    return t2, ease_c


def graded_ease(t, accepted, clamp_u, t2, ease_c):
    """(sag, lift): 0 over the clamp, the quintic ease to t2, accepted(t) past it."""
    tm = t if t <= 0.5 else 1.0 - t
    if tm >= t2:
        return accepted(t)
    if tm <= clamp_u:
        return 0.0, 0.0
    u = (tm - clamp_u) / (t2 - clamp_u)
    u3 = u * u * u
    return (ease_c[0][0] * u3 + ease_c[0][1] * u3 * u + ease_c[0][2] * u3 * u * u,
            ease_c[1][0] * u3 + ease_c[1][1] * u3 * u + ease_c[1][2] * u3 * u * u)


def graded_ease_d(t, accepted_d, clamp_u, t2, ease_c):
    """Analytic ((sag, sag', sag''), (lift, lift', lift'')) of graded_ease."""
    tm = t if t <= 0.5 else 1.0 - t
    sg = 1.0 if t <= 0.5 else -1.0
    if tm >= t2:
        return tuple((v[0], sg * v[1], v[2]) for v in accepted_d(tm))
    if tm <= clamp_u:
        return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    q = 1.0 / (t2 - clamp_u)
    u = (tm - clamp_u) * q
    u2, u3 = u * u, u * u * u
    return tuple((c[0] * u3 + c[1] * u3 * u + c[2] * u3 * u2,
                  sg * q * (3 * c[0] * u2 + 4 * c[1] * u3 + 5 * c[2] * u3 * u),
                  q * q * (6 * c[0] * u + 12 * c[1] * u2 + 20 * c[2] * u3))
                 for c in ease_c)


class YawComp:
    """Dead-on yaw as a z-offset field: -tan(phi) * (P - end).d0 weighted 1 over
    [0, comp_u] and smootherstepped to 0 by comp_u + comp_b (mirrored for b).
    Set phi_a / phi_b (radians) directly."""

    def __init__(self, A, B, DA, DB, comp_u, comp_b):
        self.A, self.B, self.DA, self.DB = A, B, DA, DB
        self.comp_u, self.comp_b = comp_u, comp_b
        self.phi_a = self.phi_b = 0.0

    def cw(self, t):
        return 1.0 - sstep((t - self.comp_u) / self.comp_b)

    def z(self, P, t):
        z = 0.0
        if self.phi_a:
            w = self.cw(t)
            if w > 0.0:
                z -= math.tan(self.phi_a) * (P - self.A).dot(self.DA) * w
        if self.phi_b:
            w = self.cw(1.0 - t)
            if w > 0.0:
                z -= math.tan(self.phi_b) * (P - self.B).dot(self.DB) * w
        return z


class BoardPath:
    """base.point(t) + (0, -sag_w*sag, lift_w*lift + yaw.z) with (sag, lift) =
    envelope(t); `pd` adds envelope_d's derivatives to base.d (the yaw field is
    point-only, exact while a viewer end carries no yaw)."""

    def __init__(self, base, envelope, envelope_d, sag_w, lift_w, yaw=None):
        self.base, self.envelope, self.envelope_d = base, envelope, envelope_d
        self.sag_w, self.lift_w, self.yaw = sag_w, lift_w, yaw

    def point(self, t):
        sag_e, lift_e = self.envelope(t)
        sag = self.sag_w * sag_e
        lift = self.lift_w * lift_e
        P = self.base.point(t)
        zc = self.yaw.z(P, t) if self.yaw is not None else 0.0
        return P + Vector((0, -sag, lift + zc))

    def pd(self, t):
        (E, Ep, Epp), (L, Lp, Lpp) = self.envelope_d(t)
        d1, d2 = self.base.d(t)
        return (self.point(t),
                d1 + Vector((0.0, -self.sag_w * Ep, self.lift_w * Lp)),
                d2 + Vector((0.0, -self.sag_w * Epp, self.lift_w * Lpp)))


def phi_for(P, d0, C, face_s):
    """Yaw (tip away from the camera) that puts camera centre C in the terminal
    face plane at axial offset face_s: cos(phi) d0.(C-P) - sin(phi)(Cz-Pz) = face_s.
    0 when unsolvable."""
    g = Vector(C) - P
    a, dz = d0.dot(Vector((g.x, g.y, 0.0))), g.z
    rho = math.hypot(a, dz)
    if rho < 1e-9 or abs(face_s) > rho:
        return 0.0
    return math.acos(face_s / rho) - math.atan2(dz, a)


# ------------------------------------------------------------------------ film
class Film:
    """Perspective film projection, 36 mm sensor width, `w` x `h` px, in pixels
    with +y down. `deadon`: camera at (cam_x, cam_y, cam_z) looking down -z.
    `basis`: camera location + (right, up, forward) unit vectors."""

    def __init__(self, w, h, lens, cam=None, basis=None):
        self.w, self.h = w, h
        self.fpx = (w / 2) / (18.0 / lens)
        self.cam = cam
        self.basis = basis

    @classmethod
    def deadon(cls, w, h, lens, cam_x, cam_y, cam_z):
        return cls(w, h, lens, cam=(cam_x, cam_y, cam_z))

    @classmethod
    def from_basis(cls, w, h, lens, loc, right, up, fwd):
        return cls(w, h, lens, basis=(loc, right, up, fwd))

    @property
    def centre(self):
        return self.cam if self.basis is None else self.basis[0]

    def pxy(self, P):
        if self.basis is None:
            cam_x, cam_y, cam_z = self.cam
            q = cam_z - P.z
            return (self.w / 2 + self.fpx * (P.x - cam_x) / q,
                    self.h / 2 - self.fpx * (P.y - cam_y) / q)
        loc, right, up, fwd = self.basis
        v = P - loc
        q = max(1e-9, v.dot(fwd))
        return (self.w / 2 + self.fpx * v.dot(right) / q,
                self.h / 2 - self.fpx * v.dot(up) / q)


def rim_dev(P, D, s_ax, rad, film, steps=720):
    """(max deviation from its best-fit straight line in px, that line's angle off
    plumb in degrees) of the circle radius rad at axial offset s_ax on (P, D)."""
    side = D.cross(Vector((0.0, 1.0, 0.0)))
    if side.length < 1e-6:
        side = D.cross(Vector((0.0, 0.0, 1.0)))
    side.normalize()
    up = side.cross(D).normalized()
    O = P + D * s_ax
    pts = []
    for k in range(steps):
        a = 2 * math.pi * k / steps
        pts.append(film.pxy(O + (up * math.cos(a) + side * math.sin(a)) * rad))
    mx = sum(p[0] for p in pts) / len(pts)
    my = sum(p[1] for p in pts) / len(pts)
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    syy = sum((p[1] - my) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    th = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ux, uy = math.cos(th), math.sin(th)
    dev = max(abs(-(p[1] - my) * ux + (p[0] - mx) * uy) for p in pts)
    return dev, abs(math.degrees(math.atan2(abs(ux), abs(uy))))


def circ_img(r, s, P, D, film, steps=240):
    """(image centre, half-extents, bbox) in px of the circle radius r at axial
    offset s on the axis (P, D); the centre is the bbox centre."""
    O = P + D * s
    e2 = D.cross(UP)
    e2 = (e2.normalized() if e2.length_squared > 1e-24
          else Vector((1.0, 0.0, 0.0)))
    e3 = D.cross(e2).normalized()
    pts = [film.pxy(O + (e2 * math.cos(2 * math.pi * k / steps)
                         + e3 * math.sin(2 * math.pi * k / steps)) * r)
           for k in range(steps)]
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    bb = (min(xs), min(ys), max(xs), max(ys))
    return (((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2),
            ((bb[2] - bb[0]) / 2, (bb[3] - bb[1]) / 2), bb)


def face_check_circles(P, D, circles, unit, film):
    """(concentricity, bore eccentricity, barrel outside the face) in px for a
    body of revolution on axis (P, D); circles are (radius, axial offset) in
    `unit`s, the smallest radius is the bore."""
    cs = [circ_img(r * unit, s * unit, P, D, film) for r, s in circles]
    iw = max(range(len(cs)), key=lambda k: cs[k][1][0])
    fc, _, fb = cs[iw]
    ecc = max(math.hypot(c[0][0] - fc[0], c[0][1] - fc[1]) for c in cs)
    ib = min(range(len(cs)), key=lambda k: circles[k][0])
    bore = math.hypot(cs[ib][0][0] - fc[0], cs[ib][0][1] - fc[1])
    out = 0.0
    for _c, _e, b in cs:
        out = max(out, fb[0] - b[0], b[2] - fb[2], fb[1] - b[1], b[3] - fb[3])
    return ecc, bore, max(0.0, out)


def face_check_slot(P, inplane, D, film, face_s, dims):
    """Ribbon's slotted-header image check on axis D from P: (slot-edge deviation
    from the slot axis, cross-slot deviation from its normal, barrel outside the
    face across the slot, along it, face x min/max, box x min/max), px.
    dims = (fl_w, fl_t, flg_th, bd_w, bd_t, body_l, back_th)."""
    fl_w, fl_t, flg_th, bd_w, bd_t, body_l, back_th = dims
    e2 = UP.cross(D)
    e2 = (e2.normalized() if e2.length_squared > 1e-24
          else UP.cross(inplane).normalized())
    e3 = D.cross(e2).normalized()
    O = P + D * face_s
    e2n = UP.cross(inplane).normalized()
    cx, cy = e2n.x, -e2n.y

    def quad(s, w, t):
        return [film.pxy(O + D * s + e2 * (a * w) + e3 * (b * t))
                for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]

    def along(q):
        return q[0] * cx + q[1] * cy

    def across(q):
        return -q[0] * cy + q[1] * cx

    f = quad(0.0, fl_w, fl_t)
    on_axis = max(abs(across(f[0]) - across(f[1])), abs(across(f[3]) - across(f[2])))
    on_norm = max(abs(along(f[1]) - along(f[2])), abs(along(f[0]) - along(f[3])))
    box = (f + quad(-flg_th, fl_w, fl_t)
           + quad(-flg_th, bd_w, bd_t) + quad(-body_l, bd_w, bd_t)
           + quad(-body_l - back_th, bd_w, bd_t))
    fx = [across(q) for q in f]
    fy = [along(q) for q in f]
    bx = [across(q) for q in box]
    by = [along(q) for q in box]
    return (on_axis, on_norm,
            max(0.0, max(bx) - max(fx)) + max(0.0, min(fx) - min(bx)),
            max(0.0, max(by) - max(fy)) + max(0.0, min(fy) - min(by)),
            min(q[0] for q in f), max(q[0] for q in f),
            min(q[0] for q in box), max(q[0] for q in box))
