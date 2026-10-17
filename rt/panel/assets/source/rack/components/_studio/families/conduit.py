"""ConduitScene: the conduit family standard (PLAN 2.9) over ComponentScene.

Members: conduit-corrugated, conduit-piping, conduit-ribbon, conduit-smooth.
Board coordinates are pixels, S = 0.01 world units per px, board y down (world
-y). OUT is positional; the render is RGBA on transparent film, `--size` wide.

A conduit generator declares ComponentScene's attributes plus, where its canon
differs, the family defaults below (None omits that flag), and implements
`build_conduit(self)`:

  A, B = "90,300", "810,320"   --a / --b      endpoint X,Y, board px
  DIRS = True                  --a-dir / --b-dir   auto | viewer | degrees CCW from +x
  SLACK = 70.0                 --slack        mid-span sag, board px
  RADIUS = 16.0                --radius       tube / wire / pipe radius, board px
  TAKEOFF = "horizontal"       --takeoff      horizontal | chord
  ZLEAD = "auto"               --zlead        viewer-end straight lead, R | auto
  FACINGS = (deadon, physical) --facing       terminal camera compensation
  TERMINALS = None             --terminal     terminal kind (the component's own set)
  TERMINAL = None                             its default
  LENS = 50.0                  --lens         mm on a 36 mm sensor
  SIZE = (900, 620)            --size         WxH | auto
  DUMP_PATH = True             --dump-path    write the sampled path, exit before geometry
  EXTRA_SLOTS = ()             slots beyond FAMILY_SLOTS
  SLOT_AUTO = ()               slots whose spec may be `auto` (resolved by auto_slot)

Always present: --deterministic (CPU device, seed 0, denoise off, adaptive off;
the resolved flags say so), --dump-aim (viewer-end diagnostics, exit before
geometry).

Resolution: `--size WxH` is the exact output; `auto` renders --res wide at
SIZE's aspect, so the defaults render SIZE. --size with a non-default --res is
an error. --scale is unsupported (framing follows the span).

Slots (FAMILY_SLOTS): jacket = the run's wall, insulation or pipe; core = what
runs inside it; fitting = the terminal hardware body; bore = a recess cut into
the fitting; fastener = bolts. A slot spec `auto` (SLOT_AUTO slots) is replaced
in the resolved flags by `auto_slot(slot)`, the key the component pairs with its
other flags.

Slot params: ComponentScene.bind / bind_each / bind_faces with PARAM_ORIGINS =
the four conduit components, so `params` and `lengths` reach only keys that
originate in the family; keys from outside it keep their presets.
radius_scaled(slot, names, radius) -> {param: value}: for a family key, each
  named param the key has, as its preset times (radius in the key's calibration
  units) / the canon radius of the key's origin component (CANON_RADIUS); pass
  it as `params`. {} for other keys.
given(key) -> bool: the flag (or one of its aliases) appears in argv.

Studio (built by the generator):
  studio(cx, cy, span)            THE HOUSE RIG: rigs.knob_studio at scale `span` (the
                                  subject's footprint span, world units) and
                                  PANEL_STOPS, the light the knob family and
                                  panel-board ship, centred on (cx, cy); no camera
  camera(loc, rot, lens)          perspective, scene camera

ClampedRun: the corrugated / smooth centreline on pathkit (clamped straight
leads, graded ease into an accepted drape, dead-on yaw field, viewer lead and
fold, the aim/camera fixed point) and the fold / seat / comb / leak numbers it
reports.
"""

import math
import sys

from .base import SAME, Alias, ComponentScene, Flag  # noqa: F401

S = 0.01
FAMILY_SLOTS = ("jacket", "core", "fitting", "bore", "fastener")
FAMILY_SLOT_HELP = {
    "jacket": "the run's wall / insulation / pipe material",
    "core": "material running inside the jacket",
    "fitting": "terminal hardware body material",
    "bore": "recess cut into the fitting",
    "fastener": "bolt material",
}
CONDUIT_COMPONENTS = ("conduit-corrugated", "conduit-piping", "conduit-ribbon", "conduit-smooth")
CANON_RADIUS = {"conduit-corrugated": 0.16, "conduit-smooth": 0.16, "conduit-ribbon": 0.06,
                "conduit-piping": 0.18}
AUTO = "auto"


def point(raw):
    try:
        x, y = (float(v) for v in str(raw).split(","))
    except ValueError:
        raise SystemExit(f"{raw!r} is not X,Y")
    return str(raw)


point.__name__ = "X,Y"


def xy(raw):
    """(x, y) floats of an X,Y flag value."""
    x, y = map(float, str(raw).split(","))
    return x, y


def direction(raw):
    text = str(raw)
    if text.lower() in ("auto", "viewer"):
        return text
    try:
        float(text)
    except ValueError:
        raise SystemExit(f"{raw!r} is neither auto, viewer nor degrees")
    return text


direction.__name__ = "auto|viewer|deg"


def radii(raw):
    text = str(raw)
    if text.lower() == "auto":
        return text
    try:
        float(text)
    except ValueError:
        raise SystemExit(f"{raw!r} is neither auto nor a length in R")
    return text


radii.__name__ = "R|auto"


def size(raw):
    text = str(raw)
    if text == AUTO:
        return text
    try:
        w, h = (int(v) for v in text.split("x"))
    except ValueError:
        raise SystemExit(f"--size {raw!r} is not WxH")
    if w < 16 or h < 16:
        raise SystemExit("--size must be at least 16x16")
    return text


size.__name__ = "WxH|auto"


class ConduitScene(ComponentScene):
    A = "90,300"
    B = "810,320"
    DIRS = True
    SLACK = 70.0
    RADIUS = 16.0
    TAKEOFF = "horizontal"
    ZLEAD = AUTO
    FACINGS = ("deadon", "physical")
    TERMINALS = None
    TERMINAL = None
    LENS = 50.0
    SIZE = (900, 620)
    DUMP_PATH = True
    EXTRA_SLOTS = ()
    SLOT_AUTO = ()
    RES = 900
    SAMPLES = 200
    SCALE_SUPPORTED = False
    PARAM_ORIGINS = CONDUIT_COMPONENTS

    # ------------------------------------------------------------------ schema
    @classmethod
    def family_flags(cls):
        flags = []
        if cls.A is not None:
            flags += [Flag("--a", point, cls.A, help="endpoint A, board px"),
                      Flag("--b", point, cls.B, help="endpoint B, board px")]
        if cls.DIRS:
            flags += [Flag("--a-dir", direction, AUTO,
                           help="take-off at A: auto, viewer (toward the camera) or degrees"),
                      Flag("--b-dir", direction, AUTO, help="take-off at B, as --a-dir")]
        if cls.SLACK is not None:
            flags.append(Flag("--slack", float, cls.SLACK, help="mid-span sag, board px"))
        flags.append(Flag("--radius", float, cls.RADIUS, help="radius, board px (R = radius x 0.01)"))
        if cls.TAKEOFF is not None:
            flags.append(Flag("--takeoff", str, cls.TAKEOFF, choices=("horizontal", "chord"),
                              help="auto take-off ray: level, or along the endpoint chord"))
        flags.append(Flag("--facing", str, cls.FACINGS[0], choices=cls.FACINGS,
                          help="terminal camera compensation"))
        if cls.ZLEAD is not None:
            flags.append(Flag("--zlead", radii, cls.ZLEAD,
                              help="viewer-end straight lead, R; auto = bore + 1.20 R"))
        if cls.TERMINALS is not None:
            flags.append(Flag("--terminal", str, cls.TERMINAL, choices=cls.TERMINALS,
                              help="terminal kind"))
        flags += [
            Flag("--lens", float, cls.LENS, help="focal length, mm (36 mm sensor)"),
            Flag("--size", size, AUTO,
                 help=f"output WxH; auto = --res wide at {cls.SIZE[0]}x{cls.SIZE[1]}"),
            Flag("--deterministic", "switch",
                 help="CPU device, seed 0, denoise and adaptive off"),
            Flag("--dump-aim", "switch", help="print viewer-end diagnostics, exit before geometry"),
        ]
        if cls.DUMP_PATH:
            flags.append(Flag("--dump-path", str, "",
                              help="write the sampled path to this file, exit before geometry"))
        return flags

    @classmethod
    def slot_help(cls, slot):
        text = cls.SLOT_HELP.get(slot, FAMILY_SLOT_HELP.get(slot, f"{slot} material"))
        if slot in cls.SLOT_AUTO:
            text += "; `auto` = the component's pairing for its flags"
        return text

    @classmethod
    def schema(cls):
        stray = sorted(set(cls.SLOTS) - set(FAMILY_SLOTS) - set(cls.EXTRA_SLOTS))
        if stray:
            raise TypeError(f"{cls.__name__}: slots {stray} are not family slots "
                            f"{FAMILY_SLOTS}; declare them in EXTRA_SLOTS")
        schema = super().schema()
        schema.flags["--res"].help = f"output width, px (height at {cls.SIZE[0]}x{cls.SIZE[1]} aspect)"
        return schema

    # ------------------------------------------------------------------- setup
    def __init__(self, argv=None):
        if argv is None:
            argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
        self.argv = list(argv)
        super().__init__(self.argv)

    def given(self, key):
        flag = self.args.schema.flags["--" + key]
        names = {flag.name} | {a.old for a in flag.aliases}
        return any(t.partition("=")[0] in names for t in self.argv if t.startswith("--"))

    def validate(self):
        a = self.args
        for slot in self.SLOT_AUTO:
            if a.values[slot] == AUTO:
                a.values[slot] = self.auto_slot(slot)
        if a.deterministic:
            a.values.update(seed=0, denoise="off", adaptive="off")
        if a.size != AUTO and a.res != self.RES:
            raise SystemExit(f"{self.COMPONENT}: give --size or --res, not both")
        if a.radius <= 0:
            raise SystemExit(f"{self.COMPONENT}: --radius must be positive")
        super().validate()

    def auto_slot(self, slot):
        raise NotImplementedError(f"{self.COMPONENT}: no auto pairing for --{slot}")

    @property
    def size(self):
        a = self.args
        if a.size != AUTO:
            return tuple(int(v) for v in a.size.split("x"))
        return a.res, round(a.res * self.SIZE[1] / self.SIZE[0])

    @property
    def R(self):
        return self.args.radius * S

    def build(self):
        sc = self.scene
        sc.render.resolution_x, sc.render.resolution_y = self.size
        if self.args.deterministic:
            sc.cycles.device = "CPU"
            self.device = "CPU"
        self.build_conduit()

    def build_conduit(self):
        raise NotImplementedError

    # ------------------------------------------------------------------- slots
    def radius_scaled(self, slot, names, radius):
        """{param: preset x radius / canon radius} for a family key (module docstring)."""
        from matlib.core import origin_component

        entry = self.slot_entry(slot)
        origin = origin_component(entry)
        if origin not in CONDUIT_COMPONENTS:
            return {}
        k = self.build_mm(entry) / entry.calib_mm_per_unit
        return {p: entry.params[p] * (radius * k) / CANON_RADIUS[origin]
                for p in names if p in entry.params}

    # ------------------------------------------------------------------ studio
    def studio(self, cx, cy, span):
        """The house rig at scale `span`, moved from the origin onto (cx, cy).
        Scale-invariant, so a run `span` long is lit as a knob of footprint 1 is."""
        import rigs

        rig = rigs.knob_studio(self.scene, scale=span, local_dir=self.local_dir, camera=False,
                               stops=rigs.PANEL_STOPS)
        for ob in rig.values():
            if hasattr(ob, "location"):
                ob.location.x += cx
                ob.location.y += cy
        self.notes.append(f"[studio:house,scale={span:.2f}]")
        return rig

    def camera(self, loc, rot=(0, 0, 0), lens=None):
        import bpy

        bpy.ops.object.camera_add(location=loc, rotation=rot)
        cam = bpy.context.object
        cam.data.lens = self.args.lens if lens is None else lens
        self.scene.camera = cam
        return cam


# ------------------------------------------------------------ clamped centreline
class ClampedRun:
    """conduit-corrugated / conduit-smooth centreline, on pathkit.

    Endpoints A, B (world, z = 1.6 R); take-off rays DA, DB (pathkit.takeoff);
    `clamp_l` straight leads (ClampedBase); `blend` (corrugated's --clamp-blend,
    None elsewhere) rescales clamp_u when clamp_u + blend_u > 0.49; ease window
    and coefficients from `accepted_d(t, clamp_u)`; `envelope(run)` and
    `envelope_d(run)` return the (sag, lift) callables once clamp_u, t2 and
    ease_c exist; `graded` selects the compensation-ramp floor law; yaw field
    (YawComp) and BoardPath at sag_w = slack px x S, `lift_w`; viewer lead of
    `lead_l` and fold window (ViewerRun). N = 900 samples.
    """

    N = 900

    def __init__(self, A, B, a_dir, b_dir, takeoff, R, slack, lift_w, clamp, ease, clamp_l,
                 accepted_d, envelope, envelope_d, graded, bore_s, zlead, blend=None):
        import pathkit

        self.pk = pathkit
        self.A, self.B, self.R = A, B, R
        self.a_dir, self.b_dir = a_dir, b_dir
        ch = (B - A).normalized()
        self.ch = ch
        self.DA = pathkit.takeoff(a_dir, "a", A, B, takeoff, ch=ch)
        self.DB = pathkit.takeoff(b_dir, "b", A, B, takeoff, ch=ch)
        self.chord_l = (B - A).length
        self.base = base = pathkit.ClampedBase(A, B, self.DA, self.DB, clamp_l)
        self.blend_u = 0.0
        if blend is not None:
            cu = base.clamp_u
            bu = cu * max(1e-6, blend)
            if cu + bu > 0.49:
                k = 0.49 / (cu + bu)
                cu, bu = cu * k, bu * k
            base.clamp_u, self.blend_u = cu, bu
        cu = self.clamp_u = base.clamp_u
        self.clamp = clamp
        self.t2, self.ease_c = pathkit.ease_coefficients(lambda t: accepted_d(t, cu), cu, ease)
        self.envelope, self.envelope_d = envelope(self), envelope_d(self)
        comp_u = cu if cu > 0.0 else min(0.20, (clamp * R / base.tot_l if base.tot_l > 0 else 0.0))
        cb7 = min(comp_u * 3.0, 0.45 - comp_u)
        self.comp_u = comp_u
        self.comp_b = max(1e-6, cb7 if not graded
                          else min(max(cb7, self.t2 - comp_u), 0.45 - comp_u))
        self.yaw = pathkit.YawComp(A, B, self.DA, self.DB, comp_u, self.comp_b)
        self.board = pathkit.BoardPath(base, self.envelope, self.envelope_d, slack * S, lift_w,
                                       self.yaw)
        self.view_a = str(a_dir).lower() == "viewer"
        self.view_b = str(b_dir).lower() == "viewer"
        self.viewer = self.view_a or self.view_b
        self.bore_s = bore_s
        self.zlead_r = (bore_s / R + 1.20) if str(zlead).lower() == "auto" else float(zlead)
        self.lead_l = self.zlead_r * R
        self.lead_u = pathkit.lead_fraction(self.lead_l, base.tot_l, self.view_a, self.view_b)
        self.t2v = pathkit.fold_window(self.lead_u, ease) if self.viewer else 0.0
        self.run = pathkit.ViewerRun(A, B, self.board.point, self.board.pd, self.view_a,
                                     self.view_b, self.lead_l, self.lead_u, self.t2v)
        self.psi_a = self.psi_b = 0.0
        self.path = self.arclen = None

    @property
    def phi_a(self):
        return self.yaw.phi_a

    @property
    def phi_b(self):
        return self.yaw.phi_b

    @property
    def total(self):
        return self.arclen[-1]

    def sample(self):
        self.path, self.arclen = self.run.sample(self.N)

    def tangent(self, i):
        return self.run.tangent(self.path, i)

    def settle(self, camera, centre, residual, phi, law, tag):
        """The aim/camera/yaw fixed point: camera() -> cam, centre(cam) -> C,
        residual(prev, cam), phi(P, d0, C) -> yaw. Returns (cam, passes)."""
        pk, A, B = self.pk, self.A, self.B
        cam, res = None, 0.0
        for it in range(1, 65 if self.viewer else 25):
            C = centre(cam) if cam is not None else None
            if self.view_a:
                axis, self.psi_a = pk.aim(A, self.DA, C, law)
                self.run.set_axis("a", axis)
            if self.view_b:
                axis, self.psi_b = pk.aim(B, self.DB, C, law)
                self.run.set_axis("b", axis)
            self.sample()
            prev, cam = cam, camera()
            res = residual(prev, cam) if prev is not None else 1.0
            C = centre(cam)
            pa = 0.0 if self.view_a else phi(A, self.DA, C)
            pb = 0.0 if self.view_b else phi(B, self.DB, C)
            if (abs(pa - self.yaw.phi_a) < 1e-13 and abs(pb - self.yaw.phi_b) < 1e-13
                    and (not self.viewer or res < 1e-6)):
                return cam, it
            self.yaw.phi_a, self.yaw.phi_b = pa, pb
        print(f"[{tag}] WARNING: the dead-on yaw / viewer aim did not settle in {it} passes"
              f" (camera still moving {res:.3e} world units)")
        return cam, it

    # ---------------------------------------------------------- diagnostics
    def kappa(self):
        """kappa * R at every sample."""
        N, arclen, R = self.N, self.arclen, self.R
        kap = [0.0] * N
        for i in range(1, N - 1):
            ds = (arclen[i + 1] - arclen[i - 1]) / 2
            if ds > 0:
                kap[i] = ((self.tangent(i + 1) - self.tangent(i - 1)) / (2 * ds)).length * R
        return kap

    def seat(self, lip_s):
        """Distance from the terminal axis, in R, of the sample nearest the lip at
        axial `lip_s` from the gland origin 0.5 R behind the endpoint."""
        R = self.R
        t0 = self.tangent(0)
        org = self.path[0] - t0 * 0.5 * R
        head = [P for P, s in zip(self.path, self.arclen) if s <= 8.0 * R] or self.path[:2]
        best = min(head, key=lambda P: abs((P - org).dot(t0) - lip_s))
        d = best - org
        return (d - t0 * d.dot(t0)).length / R

    def tilts(self):
        N = self.N
        return (math.degrees(math.asin(max(-1.0, min(1.0, self.tangent(0).y)))),
                math.degrees(math.asin(max(-1.0, min(1.0, -self.tangent(N - 1).y)))))

    def comb(self, kap):
        """(lead kappa, peak index, max dkappa/ds, mid-span third) at the board clamp."""
        N, arclen, R = self.N, self.arclen, self.R
        ju = max(2, int(round(self.clamp_u * (N - 1))))
        lead_k = max(kap[1:ju - 1]) if ju > 3 else 0.0
        win = list(range(ju + 2, max(ju + 4, int(0.35 * (N - 1)))))
        pk = max(win, key=lambda i: kap[i])
        dk = 0.0
        for i in win[:-1]:
            d = (arclen[i + 1] - arclen[i]) / R
            if d > 0:
                dk = max(dk, abs(kap[i + 1] - kap[i]) / d)
        return lead_k, pk, dk, max(kap[(N - 1) // 3:2 * (N - 1) // 3])

    def viewer_comb(self, kap, side):
        """(lead kappa, peak index, max dkappa/ds, peak distance from the fitting)."""
        N, arclen, R = self.N, self.arclen, self.R
        juv = max(2, int(round(self.lead_u * (N - 1))))
        winv = list(range(juv + 2, max(juv + 4, int(round(self.t2v * (N - 1))) + 2)))
        ix = (lambda j: j) if side == "a" else (lambda j: N - 1 - j)
        lk = max(kap[ix(j)] for j in range(1, juv - 1)) if juv > 3 else 0.0
        pkv = ix(max(winv, key=lambda j: kap[ix(j)]))
        dkv = 0.0
        for j in winv[:-1]:
            dd = abs(arclen[ix(j + 1)] - arclen[ix(j)]) / R
            if dd > 0:
                dkv = max(dkv, abs(kap[ix(j + 1)] - kap[ix(j)]) / dd)
        sfe = arclen[pkv] if side == "a" else self.total - arclen[pkv]
        return lk, pkv, dkv, sfe

    def viewer_seat(self, side):
        """Tube off the aimed axis over the bore (+0.5 R), in R."""
        P = self.A if side == "a" else self.B
        D = self.run.axis_a if side == "a" else self.run.axis_b
        w = [self.path[i] - P for i in range(self.N)
             if (self.arclen[i] if side == "a" else self.total - self.arclen[i])
             <= self.bore_s + 0.5 * self.R]
        return max((v - D * v.dot(D)).length for v in w) / self.R

    def leak(self):
        """Largest board-plane yaw z-offset over any viewer end's fold window."""
        out = 0.0
        for side, on in (("a", self.view_a), ("b", self.view_b)):
            if not on:
                continue
            for j in range(33):
                t = self.lead_u + (self.t2v - self.lead_u) * j / 32.0
                if side == "b":
                    t = 1.0 - t
                out = max(out, abs(self.yaw.z(self.base.point(t), t)))
        return out

    def print_rim(self, tag, facing, rim_s, rim_r, film, w, h):
        pk, N = self.pk, self.N
        if not self.viewer:
            dev_a, ang_a = pk.rim_dev(self.path[0], self.tangent(0), rim_s, rim_r, film)
            dev_b, ang_b = pk.rim_dev(self.path[-1], -self.tangent(N - 1), rim_s, rim_r, film)
            print(f"[{tag}] facing={facing}: terminal yaw a {math.degrees(self.phi_a):+.4f} "
                  f"deg / b {math.degrees(self.phi_b):+.4f} deg (tipped away from the camera; "
                  f"about a fixed +y axis they are opposite in sign) · silhouette rim off "
                  f"STRAIGHT a {dev_a:.4f} px / b {dev_b:.4f} px, that line "
                  f"{ang_a:.2f}/{ang_b:.2f} deg off plumb, at {w}x{h}")
            return
        bits = []
        for sd, vw, P, D in (("a", self.view_a, self.path[0], self.tangent(0)),
                             ("b", self.view_b, self.path[-1], -self.tangent(N - 1))):
            if vw:
                bits.append(f"{sd} VIEWER (see the aim block)")
            else:
                dv, an = pk.rim_dev(P, D, rim_s, rim_r, film)
                bits.append(f"{sd} yaw {math.degrees(self.phi_a if sd == 'a' else self.phi_b):+.4f}"
                            f" deg, rim off STRAIGHT {dv:.4f} px at {an:.2f} deg off plumb")
        print(f"[{tag}] facing={facing}, at {w}x{h}: " + " · ".join(bits))

    def print_comb(self, tag, envelope, kap, comb):
        lead_k, pk, dk, mid3 = comb
        print(f"[{tag}] junction comb (envelope={envelope}"
              f"{f', ease to t={self.t2:.4f}' if (self.ease_c and envelope == 'clamped') else ''}"
              f"): kappa*R over the straight lead {lead_k:.5f} (0.0 = exactly straight) · peak "
              f"{kap[pk]:.4f} at {self.arclen[pk] / self.R:.2f} R from the a terminal · max "
              f"dkappa/ds {dk:.4f} /R^2 · mid-span third {mid3:.4f}")

    def print_aim(self, tag, facing, passes, circles, film, laws):
        """Viewer-end aim rows: face checks under physical / deadon / plane."""
        pk = self.pk
        for sd, on, P, ip, psi in (("a", self.view_a, self.A, self.DA, self.psi_a),
                                   ("b", self.view_b, self.B, self.DB, self.psi_b)):
            if not on:
                continue
            print(f"[{tag}] {sd} end VIEWER, facing={facing}: aim psi "
                  f"{math.degrees(psi):+.4f} deg off +z toward the CAMERA CENTRE "
                  f"(self-collapsing: 0 when the camera is over the fitting) · "
                  f"aim/camera fixed point settled in {passes} passes")
            for m in ("physical", "deadon", "plane"):
                D = pk.aim(P, ip, film.centre, laws.get(m, m))[0]
                ec, bo, ou = pk.face_check_circles(P, D, circles, self.R, film)
                print(f"[{tag}]   fitting as {m:<8} circles off concentric "
                      f"{ec:7.3f} px · counterbore off the rim's centre "
                      f"{bo:7.3f} px · barrel outside the face {ou:6.3f} px")

    def print_leak(self, tag):
        leak = self.leak()
        print(f"[{tag}] fold/yaw independence: board-plane z-compensation over the "
              f"fold window {leak:.3e} world units (0 = the fold's analytic "
              f"derivatives are exact)")
        if leak > 1e-9:
            print(f"[{tag}] WARNING: a board-plane yaw reaches into the fold — the "
                  "junction's analytic derivatives omit it and the C2 claim is void.")

    def dump(self, path, kap, head):
        with open(path, "w") as f:
            f.write(head)
            for i in range(self.N):
                P = self.path[i]
                f.write("%r %r %r %r %r %r\n" % (i / (self.N - 1), self.arclen[i],
                                                 P.x, P.y, P.z, kap[i]))
