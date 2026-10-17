"""`bakelib` — the compose/verify recipe for additive scene-linear layer bakes.

VENV-SIDE, NOT BLENDER-SIDE. This module wants numpy + PIL (and scipy for the
bloom ladder only, imported where it is used) and no `bpy`, so it runs under
`design-lab/.venv/bin/python` or any numpy install; its neighbour `matlib.py` is the
exact opposite and only ever runs inside Blender. Nothing here imports bpy and
nothing here may start to.

A layer bake ships `face` plus a set of additive `delta` EXRs, and a consumer
rebuilds any state with ONE recipe:

    linear = face + SUM(delta[i] for i in lit)      # scene-linear, half EXR
    linear = linear + SUM(w_k * gaussian(H(linear), sigma_k))   # the bloom
    byte   = round(255 * trilinear(cube, log2_shaper(linear)))  # AgX as a LUT

NO COMPONENT CONSTANTS LIVE HERE. The glare threshold, the smoothness, the
sigma ladder, the fitted weights, the luma-vs-per-channel choice and the LUT's
EV window are all arguments — a `Recipe` carries one component's set, and a
component's own driver (or its shipped manifest) is the only place they are
written down. Two components with different thresholds share this file without
either one's numbers leaking into the other's.

THE VERIFIER

    design-lab/.venv/bin/python components/_studio/bakelib.py verify DIR [DIR…]

One invocation verifies one bake config dir — the shipped `<config>_face.exr` +
`<config>_<state>.exr` layers next to the tracked `<config>.json` manifest — and
emits ONE JSON summary; several dirs may be passed at once, so a whole
component's bake is one command and one output file, which is the bar: verifying
a bake must never again mean authoring numpy per round.

    verify components/display-nixie/bake/*/ \
        --canon components/display-nixie/renders \
        --truth-lin 'design-lab/passes/24-nixie/_renders_bake/{config}/truth_lin_{num}.exr' \
        --out /tmp/nixie-verify.json

The manifest is the source of truth for the recipe (`bloom.*`, `view_transform.*`)
and for the FLOORS: `residual.full_recipe` and `residual.linear_additivity` are
the numbers the bake recorded when it was built, so a re-verification that
reproduces them proves the shipped layers still compose to the shipped tiles.
`--cube` / `--threshold` / `--sigmas` / `--weights` override the manifest for a
what-if; by default nothing needs to be passed but the directory.

Each check is one state of one config, resolved from the manifest's recorded
residual keys (any option key may be scoped `CONFIG:KEY` when several dirs are
verified at once, and a scoped key may name a state the bake never recorded):

  layers  the trailing token of the key when it names a delta file (`… d8` ->
          `d8`), else `--state KEY=A1,A2,…` / `*` (every delta) / `` (face only)
          / `@X` (glyph X out of the manifest's own `decode` table)
  canon   `--tile KEY=NAME`, else `<canon>/<key>.png`, else the manifest's
          `covers` zipped against the recorded keys, else `<canon>/<token>.png`
  truth   `--truth-lin` pattern (or `--truth KEY=PATTERN` for one state),
          `{config}` `{state}` `{num}` substituted; the true single linear
          render the additivity check needs, which is bake scratch and not
          shipped — without it the recorded floor is echoed, not re-measured

JSON: {"tool", "pass", "summary", "configs": [{config, dir, layers, manifest…}],
"checks": [{config, state, canon, layers, additivity: {mean_pct, peak,
floor_mean_pct, delta_pct, source}, full_recipe: {mean, peak, p999, over2,
uncovered_frac, floor_mean, floor_peak, mean_delta, peak_delta}, ok, notes}]}.
Exit status is 1 when any check fails its tolerance, so it is scriptable.
"""
from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

LUMA_709 = np.array([0.2126, 0.7152, 0.0722])


# --------------------------------------------------------------- subprocess
def run(cmd, expect):
    """A child process that is trusted only as far as its output file.

    Blender in particular exits 0 even on a script exception, so a return code
    proves nothing and the landed file is the only evidence there is."""
    t0 = time.time()
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if not Path(expect).exists():
        raise RuntimeError(f"no output {expect}\n{r.stdout[-1500:]}\n{r.stderr[-600:]}")
    return time.time() - t0, r.stdout


# ---------------------------------------------------------------- EXR input
# Hand-rolled because the venv has numpy/scipy/PIL and no OpenEXR binding at
# all: PIL cannot open an EXR and imageio has no plugin for one here. Scanline
# half-float ZIP is what every layer in this bin is written as (Blender's
# `exr_codec = "ZIP"`), so that is what this reads — anything else raises rather
# than guesses.
_PIXEL_T = {0: np.uint32, 1: np.float16, 2: np.float32}
_BLOCK_LINES = {0: 1, 2: 1, 3: 16}          # NONE, ZIPS, ZIP
_COMPRESSION = {0: "none", 1: "rle", 2: "zips", 3: "zip", 4: "piz", 5: "pxr24",
                6: "b44", 7: "b44a", 8: "dwaa", 9: "dwab"}


def read_exr(path):
    """A scanline EXR as (H, W, C) float32, channels ordered R, G, B[, A].

    Top-down, i.e. the orientation PIL and the canon PNGs use, NOT Blender's
    bottom-up `pixels` buffer."""
    d = Path(path).read_bytes()
    if len(d) < 8 or struct.unpack("<I", d[:4])[0] != 0x01312F76:
        raise ValueError(f"{path}: not an OpenEXR file")
    if struct.unpack("<I", d[4:8])[0] & 0x200:
        raise NotImplementedError(f"{path}: tiled EXR")
    i, attrs, chans = 8, {}, []
    while True:
        j = d.index(b"\0", i)
        name, i = d[i:j].decode(), j + 1
        if not name:
            break
        j = d.index(b"\0", i)
        typ, i = d[i:j].decode(), j + 1
        size = struct.unpack("<i", d[i:i + 4])[0]
        val, i = d[i + 4:i + 4 + size], i + 4 + size
        if typ == "chlist":
            k = 0
            while val[k]:
                j = val.index(b"\0", k)
                nm, k = val[k:j].decode(), j + 1
                pt = struct.unpack("<i", val[k:k + 4])[0]
                chans.append((nm, _PIXEL_T[pt]))
                k += 16
        else:
            attrs[name] = val
    x0, y0, x1, y1 = struct.unpack("<4i", attrs["dataWindow"])
    w, h = x1 - x0 + 1, y1 - y0 + 1
    comp = attrs["compression"][0]
    if comp not in _BLOCK_LINES:
        raise NotImplementedError(
            f"{path}: {_COMPRESSION.get(comp, comp)} compression")
    lines = _BLOCK_LINES[comp]
    nblocks = (h + lines - 1) // lines
    offsets = struct.unpack(f"<{nblocks}Q", d[i:i + 8 * nblocks])
    stride = sum(np.dtype(t).itemsize for _, t in chans)
    plane = {nm: np.empty((h, w), dtype=t) for nm, t in chans}
    for off in offsets:
        y, n = struct.unpack("<ii", d[off:off + 8])
        rows = min(lines, h - (y - y0))
        raw = d[off + 8:off + 8 + n]
        if n < rows * w * stride:
            # zlib, then OpenEXR's two undo steps: a wrapping byte-delta
            # predictor, then the de-interleave of the two half-buffers.
            b = np.frombuffer(zlib.decompress(raw), dtype=np.uint8).astype(np.int32)
            b[1:] -= 128
            b = (np.cumsum(b, dtype=np.int32) & 0xFF).astype(np.uint8)
            half = (len(b) + 1) // 2
            buf = np.empty(len(b), dtype=np.uint8)
            buf[0::2], buf[1::2] = b[:half], b[half:]
        else:
            buf = np.frombuffer(raw, dtype=np.uint8)
        k = 0
        for r in range(rows):
            for nm, t in chans:                 # alphabetical, per the chlist
                sz = w * np.dtype(t).itemsize
                plane[nm][y - y0 + r] = np.frombuffer(
                    bytes(buf[k:k + sz]), dtype=t)
                k += sz
    order = [c for c in ("R", "G", "B", "A") if c in plane]
    return np.stack([plane[c].astype(np.float32) for c in order], axis=-1)


# ------------------------------------------------------------------- stats
def stat(d):
    return dict(peak=float(d.max()), mean=float(d.mean()),
                p999=float(np.percentile(d, 99.9)), over2=float((d > 2).mean()))


def compose(face, deltas):
    """`face + SUM(deltas)` in float64 — the whole of the linear half of the
    recipe, and the reason a bake is 18 renders instead of 131072."""
    L = np.asarray(face).astype(np.float64).copy()
    for d in deltas:
        L += d
    return L


def additivity(got, ref):
    """The layer sum against a true single render of the same state. Anything
    that is not additive in scene-linear — coverage, extinction, a nonlinear
    denoise — shows up here and nowhere else.

    CONTIGUOUS FIRST. numpy sums float32 pairwise, in blocks, so the total over
    a non-contiguous slice (an RGB view of an RGBA buffer, say) rounds
    differently from the total over the same values laid out flat. The relative
    figures below are ratios of such sums and must not depend on how the caller
    happened to slice its input."""
    got, ref = np.ascontiguousarray(got), np.ascontiguousarray(ref)
    r = np.abs(got - ref)
    return dict(peak=float(r.max()), mean=float(r.mean()),
                rel_peak=float((r / np.maximum(ref, 1e-3)).max()),
                rel_mean=float(r.sum() / max(float(ref.sum()), 1e-9)))


def load_cube(path, n):
    """A 3D `.cube` as (n, n, n, 3), red fastest — the file's own convention."""
    txt = [l for l in Path(path).read_text().splitlines()
           if l and not l.startswith("#") and not l[0].isalpha()]
    return np.array([[float(x) for x in l.split()] for l in txt],
                    dtype=np.float32).reshape(n, n, n, 3)


# ------------------------------------------------------------- the recipe
class Recipe:
    """One component's display pipeline: soft-knee highlights, an octave ladder
    of gaussians, and a view transform carried as a 3D LUT.

    `weights` and `luma` stay call arguments rather than state because the bake
    that fits them does not have them yet when it builds the Recipe."""

    def __init__(self, cube, sigmas, threshold, smoothness, min_ev, max_ev,
                 lut_n=33):
        self.sigmas = list(sigmas)
        self.threshold, self.smoothness = float(threshold), float(smoothness)
        self.min_ev, self.max_ev, self.lut_n = float(min_ev), float(max_ev), int(lut_n)
        self.cube = (cube if isinstance(cube, np.ndarray)
                     else load_cube(cube, self.lut_n))

    @classmethod
    def from_manifest(cls, man, cube=None, base=None):
        """The recipe a shipped manifest describes. The manifest is the
        contract, so it — not this file, and not the driver that wrote it — is
        what a consumer and this verifier both read."""
        b, v = man["bloom"], man["view_transform"]
        if cube is None:
            cube = Path(base or ".") / v["lut"]
        return cls(cube=cube, sigmas=b["sigma_px"], threshold=b["threshold"],
                   smoothness=b["smoothness"], min_ev=v["min_ev"],
                   max_ev=v["max_ev"], lut_n=v["size"])

    # -- bloom
    def highlights(self, L):
        """The soft-knee threshold the glare node extracts its bloom source
        with: quadratic through a knee of width `threshold*smoothness`, linear
        above it, zero below."""
        knee = self.threshold * self.smoothness
        soft = np.clip(L - self.threshold + knee, 0.0, 2.0 * knee)
        soft = soft * soft / (4.0 * knee)
        return np.maximum(soft, L - self.threshold)

    def _source(self, L, luma):
        H = self.highlights(L)
        if luma:
            y = H @ LUMA_709
            H = np.repeat(y[..., None], 3, axis=2)
        return H

    def _blur(self, H, s):
        from scipy.ndimage import gaussian_filter   # bloom only: I/O and compose need numpy

        return H if s == 0 else gaussian_filter(H, (s, s, 0))

    def basis(self, L, luma=False):
        """The ladder as separate planes — the design matrix a weight fit needs."""
        H = self._source(L, luma)
        return np.stack([self._blur(H, s) for s in self.sigmas])

    def bloom(self, L, weights, luma=False):
        H = self._source(L, luma)
        out = L.copy()
        for s, w in zip(self.sigmas, weights):
            if w:
                out += w * self._blur(H, s)
        return out

    # -- view transform
    def lut(self, L):
        """log2 shaper into the cube, then trilinear. The cube's domain is the
        transform's own EV window, so the clamp at each end is the transform's
        and not the LUT's."""
        C, n = self.cube, self.lut_n
        t = np.clip((np.log2(np.maximum(L, 1e-10)) - self.min_ev)
                    / (self.max_ev - self.min_ev), 0.0, 1.0)
        g = t * (n - 1)
        i0 = np.minimum(np.floor(g).astype(np.int32), n - 2)
        f = g - i0
        r0, g0, b0 = i0[..., 0], i0[..., 1], i0[..., 2]
        fr, fg, fb = f[..., 0], f[..., 1], f[..., 2]
        out = np.zeros(L.shape, dtype=np.float64)
        for dr in (0, 1):
            wr = fr if dr else 1.0 - fr
            for dg in (0, 1):
                wg = fg if dg else 1.0 - fg
                for db in (0, 1):
                    wb = fb if db else 1.0 - fb
                    out += (wr * wg * wb)[..., None] * C[b0 + db, g0 + dg, r0 + dr]
        return out

    def display(self, L):
        """Scene-linear straight to bytes, NO bloom — the floor every bloom
        number has to be read against."""
        return np.clip(np.round(self.lut(L) * 255.0), 0, 255)

    def to_bytes(self, L, weights, luma=False):
        return self.display(self.bloom(L, weights, luma))


# ------------------------------------------------------------ verify (CLI)
def _canon(path):
    """A canon tile as (RGB float, alpha).

    ALPHA IS NOT DECORATION. A tile that looks through its own window is only
    partly covered, and Blender writes PNG with STRAIGHT alpha while the layers
    are premultiplied — comparing a straight byte against a premultiplied one at
    partial coverage compares two encodings, not two renders. So the headline
    residual is taken over fully covered pixels, with the full-frame figure
    beside it."""
    a = np.asarray(Image.open(path).convert("RGBA")).astype(float)
    return a[..., :3], a[..., 3]


def _layer_files(d, man):
    face = d / man["layers"]["face"]
    deltas = {}
    for p in sorted(d.glob("*.exr")):
        if p.name != face.name:
            deltas[p.stem[len(d.name) + 1:] if p.stem.startswith(d.name + "_")
                   else p.stem] = p
    return face, deltas


def _for_config(m, cfg):
    """The `KEY=…` options that apply to one config dir. A key may be written
    `CONFIG:KEY` to scope it — which matters because several dirs verify in one
    invocation, and because a state name and a config name can collide."""
    own, shared = {}, {}
    for k, v in m.items():
        c, sep, kk = k.partition(":")
        if sep and c == cfg:
            own[kk] = v
        elif not sep:
            shared[k] = v
    return {**shared, **own}, list(own)


def _floors(man):
    """(additivity floor per key, full-recipe floor per key). A component that
    measured additivity once per config rather than once per state records a
    flat dict; that floor then applies to every one of its states."""
    res = man.get("residual", {})
    add, rec = res.get("linear_additivity") or {}, res.get("full_recipe") or {}
    if add and not isinstance(next(iter(add.values())), dict):
        add = {"*": add}
    return add, rec


def _state_layers(key, cfg, spec, deltas, man):
    """The delta names one check sums. `*` every delta, `` face only, `@G` the
    manifest's decode table for glyph G, else a comma list — and with no spec at
    all, the key's trailing token when it names a delta of its own."""
    tok = key[len(cfg) + 1:] if key.startswith(cfg + " ") else key
    if spec is None:
        return ([tok], tok) if tok in deltas else (None, tok)
    spec = spec.strip()
    if spec == "*":
        return list(deltas), tok
    if not spec:
        return [], tok
    if spec.startswith("@"):
        return man["decode"][spec[1:]].split(), tok
    return [s for s in (x.strip() for x in spec.split(",")) if s], tok


def _resolve_canon(key, tok, cfg, man, keys, canon_dir, tiles):
    if key in tiles:
        p = Path(tiles[key])
        return p if p.suffix else (Path(canon_dir or ".") / f"{tiles[key]}.png")
    if not canon_dir:
        return None
    canon_dir = Path(canon_dir)
    for cand in (canon_dir / f"{key}.png", canon_dir / f"{tok}.png"):
        if cand.exists():
            return cand
    # `covers` names the tiles this config stands in for, in the order the bake
    # recorded its states — so the tile-bearing states are the leading ones and
    # a config that covers fewer tiles than it recorded states simply runs out.
    covers = man.get("covers") or []
    i = list(keys).index(key)
    if i < len(covers):
        p = canon_dir / f"{covers[i]}.png"
        if p.exists():
            return p
    return None


def verify_dir(d, args):
    d = Path(d)
    man = json.loads((d / f"{d.name}.json").read_text())
    R = Recipe.from_manifest(man, cube=args.cube, base=d)
    if args.threshold is not None:
        R.threshold = args.threshold
    if args.sigmas:
        R.sigmas = [float(x) for x in args.sigmas.split(",")]
    weights = ([float(x) for x in args.weights.split(",")] if args.weights
               else man["bloom"]["weights"])
    luma = man["bloom"]["highlight"] == "luma"
    face_p, deltas = _layer_files(d, man)
    add_floor, rec_floor = _floors(man)
    states, extra = _for_config(args.state, d.name)
    tiles, _ = _for_config(args.tile, d.name)
    truths, _ = _for_config(args.truth, d.name)

    disk = man.get("disk", {})
    exrs = sorted(d.glob("*.exr"))
    cfg_row = dict(
        config=d.name, dir=str(d), contract=man.get("contract"),
        highlight=man["bloom"]["highlight"], threshold=R.threshold,
        weights_source="cli" if args.weights else "manifest",
        layers=dict(found=len(exrs), expected=disk.get("files"),
                    deltas=len(deltas), expected_deltas=disk.get("deltas"),
                    bytes=sum(p.stat().st_size for p in exrs),
                    expected_bytes=disk.get("bytes")))
    cfg_row["layers"]["ok"] = (disk.get("files") in (None, len(exrs))
                               and disk.get("bytes") in
                               (None, cfg_row["layers"]["bytes"]))

    # The recorded keys are the check set — the states the bake measured are the
    # states that have floors — plus any CONFIG-scoped state named on the
    # command line, which is how a state the bake never recorded is looked at.
    keys = list(rec_floor) or [k for k in add_floor if k != "*"]
    keys += [k for k in extra if k not in keys]
    checks, face = [], None
    for key in keys:
        tok0 = key[len(d.name) + 1:] if key.startswith(d.name + " ") else key
        layers, tok = _state_layers(key, d.name, states.get(
            key, states.get(tok0)), deltas, man)
        tile = _resolve_canon(key, tok, d.name, man, keys, args.canon, tiles)
        # Every row carries every key — a reader of the JSON should never have
        # to ask whether a field is there before asking what it says.
        row = dict(config=d.name, state=tok, key=key, layers=layers,
                   canon=str(tile) if tile else None, skipped=None,
                   additivity=None, full_recipe=None, ok=None, notes=[])
        if layers is None:
            row.update(ok=None, skipped="no layer set for this state "
                                        "(pass --state)")
            checks.append(row)
            continue
        missing = [n for n in layers if n not in deltas]
        if missing:
            row.update(ok=False, skipped=f"missing layers {missing}")
            checks.append(row)
            continue
        if face is None:
            face = read_exr(face_p)
        L = compose(face[..., :3], [read_exr(deltas[n])[..., :3] for n in layers])

        # additivity, against a true single render of the same state
        af = add_floor.get(key, add_floor.get("*"))
        a_row = dict(floor_mean_pct=(af["rel_mean"] * 100 if af else None),
                     floor_peak=(af["peak"] if af else None))
        pat = truths.get(key, truths.get(tok, args.truth_lin))
        truth = None
        if pat:
            num = "".join(c for c in tok if c.isdigit())
            truth = Path(pat.format(config=d.name, state=tok, num=num))
        if truth is not None and truth.exists():
            m = additivity(L, read_exr(truth)[..., :3])
            a_row.update(source="measured", mean_pct=m["rel_mean"] * 100,
                         mean=m["mean"], peak=m["peak"])
            if af is not None:
                a_row["delta_pct"] = a_row["mean_pct"] - af["rel_mean"] * 100
                a_row["peak_delta"] = m["peak"] - af["peak"]
        else:
            a_row.update(source="manifest", mean_pct=a_row["floor_mean_pct"],
                         mean=(af or {}).get("mean"), peak=(af or {}).get("peak"),
                         delta_pct=0.0 if af else None)
            if truth is not None:
                row["notes"].append(f"no truth render at {truth}")
        row["additivity"] = a_row

        # the full recipe, against the canon tile
        if tile is None:
            row["full_recipe"] = None
            row["notes"].append("no canon tile (pass --canon/--tile)")
        else:
            want, alpha = _canon(tile)
            cov = alpha >= 255.0
            dd = np.abs(R.to_bytes(L, weights, luma) - want)
            s = stat(dd[cov])
            fl = rec_floor.get(key) or {}
            s.update(uncovered_frac=float((~cov).mean()),
                     floor_mean=fl.get("mean"), floor_peak=fl.get("peak"))
            if fl:
                s["mean_delta"] = s["mean"] - fl["mean"]
                s["peak_delta"] = s["peak"] - fl["peak"]
            row["full_recipe"] = s
        bad = []
        fr = row["full_recipe"]
        if fr and fr.get("mean_delta") is not None:
            if abs(fr["mean_delta"]) > args.tol_mean:
                bad.append(f"full-recipe mean off floor by {fr['mean_delta']:+.4f}")
            if abs(fr["peak_delta"]) > args.tol_peak:
                bad.append(f"full-recipe peak off floor by {fr['peak_delta']:+.1f}")
        if a_row.get("delta_pct") is not None and \
                abs(a_row["delta_pct"]) > args.tol_add_pct:
            bad.append(f"additivity off floor by {a_row['delta_pct']:+.4f} %")
        row["ok"] = not bad
        row["notes"] += bad
        checks.append(row)
        if len([c for c in checks if c.get("ok") is not None]) >= args.spot:
            break
    cfg_row["checked"] = len([c for c in checks if c.get("ok") is not None])
    cfg_row["ok"] = cfg_row["layers"]["ok"] and all(
        c["ok"] for c in checks if c.get("ok") is not None)
    return cfg_row, checks


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="bakelib", description="verify a shipped layer bake against its "
                                    "own manifest, one JSON out")
    sub = ap.add_subparsers(dest="mode", required=True)
    v = sub.add_parser("verify")
    v.add_argument("dirs", nargs="+", help="bake config dir(s): the layer EXRs "
                                           "next to <config>.json")
    v.add_argument("--canon", help="directory of canon tiles (PNG)")
    v.add_argument("--tile", action="append", default=[],
                   metavar="KEY=NAME", help="canon tile for one state")
    v.add_argument("--state", action="append", default=[], metavar="KEY=SPEC",
                   help="lit layers for one state: `*`, ``, `@GLYPH`, or a "
                        "comma list of delta names. Any KEY may be written "
                        "CONFIG:KEY to scope it to one dir; only a scoped key "
                        "can add a state the manifest never recorded")
    v.add_argument("--truth-lin", metavar="PATTERN",
                   help="true single linear render per state, with {config} "
                        "{state} {num}; without it the additivity floor is "
                        "echoed rather than re-measured")
    v.add_argument("--truth", action="append", default=[], metavar="KEY=PATTERN",
                   help="the same, for ONE state — which is what a component "
                        "that measured additivity once per config needs")
    v.add_argument("--cube", help="override the manifest's LUT path")
    v.add_argument("--threshold", type=float, help="override the glare threshold")
    v.add_argument("--sigmas", help="override the sigma ladder (comma list)")
    v.add_argument("--weights", help="override the bloom weights (comma list)")
    v.add_argument("--spot", type=int, default=3,
                   help="states per config (default 3; spot checks are the norm)")
    v.add_argument("--all", action="store_true", help="every recorded state")
    v.add_argument("--tol-mean", type=float, default=0.01,
                   help="allowed drift in the full-recipe mean, bytes")
    v.add_argument("--tol-peak", type=float, default=1.0,
                   help="allowed drift in the full-recipe peak, bytes")
    v.add_argument("--tol-add-pct", type=float, default=0.01,
                   help="allowed drift in the additivity mean, %%")
    v.add_argument("--out", help="write the JSON here instead of to stdout")
    a = ap.parse_args(argv)
    a.state = dict(s.split("=", 1) for s in a.state)
    a.tile = dict(s.split("=", 1) for s in a.tile)
    a.truth = dict(s.split("=", 1) for s in a.truth)
    if a.all:
        a.spot = 10 ** 6

    configs, checks = [], []
    for d in a.dirs:
        c, ch = verify_dir(d, a)
        configs.append(c)
        checks += ch
    ran = [c for c in checks if c.get("ok") is not None]
    out = dict(tool="bakelib/1", mode="verify",
               summary=dict(configs=len(configs), checks=len(ran),
                            failed=len([c for c in ran if not c["ok"]]),
                            skipped=len(checks) - len(ran)),
               configs=configs, checks=checks)
    out["pass"] = all(c["ok"] for c in configs)
    txt = json.dumps(out, indent=2) + "\n"
    if a.out:
        Path(a.out).write_text(txt)
        print(f"{'PASS' if out['pass'] else 'FAIL'} "
              f"{out['summary']['checks']} checks, "
              f"{out['summary']['failed']} failed -> {a.out}")
    else:
        sys.stdout.write(txt)
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
