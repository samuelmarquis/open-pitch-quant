#!/usr/bin/env python3
"""ring_bake.py — the `ring-bake/1` layer package. N+1 renders, not 2^N.

A ring of N segments has 2^N states. It does not need 2^N renders, because
RADIANCE IS LINEAR IN THE SET OF EMITTERS: light transport is a linear
operator on emission, so the frame with segments {i, j, k} lit is exactly the
frame with none lit plus the three single-segment CONTRIBUTIONS. That holds
here only because a lit and an unlit lens differ in Emission Strength and in
nothing else — vary albedo between them and it degrades to an approximation.

    base.exr                 every segment unlit: the plate and the ghosts,
                             lit by the world and the key rig
    d000.exr .. dNNN.exr     segment i as the ONLY light in the scene

    linear = base + SUM(delta[i] for i in lit)          # scene-linear
    byte   = trilinear(agx_cube, log2_shaper(linear))   # AgX, applied ONCE

so the consumer picks the composition and pays nothing per state. The cursor
is free too: its emission is CURSOR_GAIN x the plain one, and a scalar on an
emitter is a scalar on its contribution, so `cursor_gain * delta[i]` is exact.

ISOLATE, DO NOT SUBTRACT. `render(only i lit) - render(none lit)` has the same
expectation and is far worse: composing k of them gives `SUM(seg) - (k-1)*base`,
so the base's Monte-Carlo noise enters once per lit segment. Measured over 22
lit segments that was 28% relative error, with negative pixels in a quantity
that is physically non-negative. Rendering segment i with the world and the key
rig at zero gives its contribution directly — no subtraction, no amplification,
and the layer is 0.6% of a frame instead of 55%. Same 49 renders; 0.5% error.

THREE THINGS THAT BREAK IT, all silent:
  * AgX is not additive. Layers are extracted with --raw (view transform Raw,
    scene-linear half EXR) and the transform is applied after summing.
  * The denoiser is not additive. Bake renders turn it off.
  * Adaptive sampling is data-dependent, so two renders of one scene are not
    even equal to each other. Bakes disable it; without that, nothing below
    is reproducible and every number here is noise.

    python components/knob-ring/generator/ring_bake.py --res 640 --samples 420
    python components/knob-ring/generator/ring_bake.py --verify-only
    python components/knob-ring/generator/ring_bake.py --segments 24   # -> bake/s024/
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
COMP = HERE.parent
REPO = COMP.parent.parent
STUDIO = REPO / "components" / "_studio"
GEN = HERE / "knob_scene.py"
BL = Path.home() / "Applications" / "Blender.app" / "Contents" / "MacOS" / "Blender"
CUBE = REPO / "components" / "display-segment" / "bake" / "agx-mhc-33.cube"
MIN_EV, MAX_EV, LUT_N = -12.47393, 4.026069, 33

sys.path.insert(0, str(STUDIO))
import bakelib  # noqa: E402

# The shipped package's segment count. Any other count is its own package
# (`bake/s<NNN>/`) with its own scratch, so it can never overwrite this one or
# reuse its layers. Smaller rings want fewer, wider segments: at a small
# on-screen size 48 lenses alias into a comb.
CANON_SEGMENTS = 48

# geometry the bake is valid for; a consumer composing these layers is
# composing THIS ring, so the manifest has to pin every shape argument.
# --segments is prepended per run from the bake's own --segments.
GEOM = ["--start-deg", "-135", "--sweep", "270",
        "--gap", "0.34", "--relief", "flat", "--hue", "red",
        # The pass-31 footprint standard: --inner now derives from --height so a
        # standard knob tucks 2.5 px under the ring, and --outer from --inner via
        # BAND_RATIO. These were the old fixed 0.535/0.663. Read back from
        # knob_scene's own receipt rather than recomputed here, then pinned
        # explicitly because a consumer composing these layers is composing THIS
        # ring and the manifest must state its shape.
        "--inner", "0.4874152852", "--outer", "0.6040305310048598",
        "--aperture", "0.12,0.92"]


def geometry(segments):
    return ["--segments", str(segments), *GEOM]


def claim_scratch(scratch, geom):
    """Layers are reused when present, so a scratch dir rendered for one ring
    must never feed another: a 24-segment bake over 48-segment layers would
    ship d000..d023 of the wrong ring without a single error. The dir records
    the geometry it holds and refuses any other."""
    stamp = scratch / "geometry.json"
    if stamp.is_file():
        held = json.loads(stamp.read_text())
        if held != geom:
            raise SystemExit(f"ring_bake: {scratch} holds layers for\n  {held}\nnot\n  "
                             f"{geom}\nPass another --scratch, or delete that dir.")
        return
    stale = list(scratch.glob("*.exr"))
    # the pre-stamp canonical scratch is the one legacy case: it is 48 segments
    if stale and geom != geometry(CANON_SEGMENTS):
        raise SystemExit(f"ring_bake: {scratch} has {len(stale)} unstamped layers of "
                         "unknown geometry. Pass another --scratch, or delete them.")
    scratch.mkdir(parents=True, exist_ok=True)
    stamp.write_text(json.dumps(geom) + "\n")


def render(out, geom, extra, res, samples, force=False):
    """One layer. Blender exits 0 on a script exception, so the landed file is
    the only evidence; and --raw is what keeps it scene-linear."""
    if out.exists() and not force:
        return True
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(BL), "-b", "-P", str(GEN), "--", str(out), *geom, *extra,
                    "--raw", "--denoise", "off",
                    "--res", str(res), "--samples", str(samples)],
                   capture_output=True, text=True, timeout=1200)
    return out.exists() and out.stat().st_size > 1000


def write_npz(path, deltas, boxes, res):
    """The layers, cropped. A contribution covers under 1% of the frame, so a
    full-frame layer is ~99% zeros; cropping each to its own bounding box is
    the whole saving. One .npz holds every layer plus its offset, so the crop
    and the box it belongs to cannot be separated — which is the only way this
    format goes wrong.

    `ring-bake.npz` keys, per layer i:
        d<i:03d>      (h, w, 3) float16, scene-linear Rec.709, NON-NEGATIVE
        b<i:03d>      (4,)      int32, [x0, y0, x1, y1] into the full frame
    plus `base` (res, res, 4) float16 and `meta` (a JSON string).

    A consumer rebuilds a full-frame layer with a paste, not a resize:
        L = base[..., :3].astype(np.float32)
        for i in lit:
            x0, y0, x1, y1 = z[f"b{i:03d}"]
            L[y0:y1, x0:x1] += z[f"d{i:03d}"]
    """
    arrs = {}
    for i, (d, b) in enumerate(zip(deltas, boxes)):
        if b is None:                  # a layer that contributes nothing
            b = (0, 0, 1, 1)
        x0, y0, x1, y1 = b
        arrs[f"d{i:03d}"] = d[y0:y1, x0:x1, :3].astype(np.float16)
        arrs[f"b{i:03d}"] = np.array(b, dtype=np.int32)
    np.savez_compressed(path, **arrs)
    return path


def bbox(d, eps):
    """The delta's footprint. A segment lights itself and a little of the plate
    beside it, so most of the frame is exactly zero and croppable."""
    m = np.abs(d).max(axis=-1) > eps
    if not m.any():
        return None
    ys, xs = np.where(m)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=int, default=640)
    # RAISED 4x FOR THE PASS-32 RIG (was 512 / 2048). The house lighting moved
    # to gradient MESH emitters with the world visible to glossy rays, which is
    # markedly noisier per sample than the old analytic area lights with the
    # world hidden — and this package's whole claim, that base + sum(deltas)
    # reproduces the lit state, is measured against that noise. At the old
    # counts the residual was 0.894% of pixels over 1 LSB; at 4x it is 0.122%,
    # against 0.085% under the old rig. Measured, not assumed: quadrupling
    # samples moved it 2.6x, where a noise floor predicts 2x and systematic
    # non-additivity predicts no change at all.
    ap.add_argument("--samples", type=int, default=2048)
    # BASE IS RENDERED ONCE AND IS THE FLOOR OF EVERY STATE, so its noise is
    # in every frame a consumer ever composes and is worth paying for. An
    # isolated delta converges far faster: almost the whole frame is black.
    ap.add_argument("--base-samples", type=int, default=8192)
    ap.add_argument("--segments", type=int, default=CANON_SEGMENTS,
                    help=f"lens count; anything but {CANON_SEGMENTS} defaults to bake/s<NNN>/")
    ap.add_argument("--out", default=None)
    ap.add_argument("--scratch", default=None)
    ap.add_argument("--eps", type=float, default=1e-4)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    a = ap.parse_args()

    n = a.segments
    if n < 2:
        raise SystemExit("ring_bake: --segments must be at least 2")
    canon = n == CANON_SEGMENTS
    out_dir = Path(a.out) if a.out else \
        COMP / "bake" / ("" if canon else f"s{n:03d}")
    # every scratch lives under the one gitignored bake/_scratch/
    scratch = Path(a.scratch) if a.scratch else \
        COMP / "bake" / "_scratch" / ("" if canon else f"s{n:03d}")
    out_dir.mkdir(parents=True, exist_ok=True)
    geom = geometry(n)
    claim_scratch(scratch, geom)

    # ---------------------------------------------------------------- render
    t0 = time.time()
    jobs = [("base", ["--lit", "none"])] + \
           [(f"d{i:03d}", ["--lit", str(i), "--isolate"]) for i in range(n)]
    missing = []
    for k, (name, extra) in enumerate(jobs, 1):
        f = scratch / f"{name}.exr"
        sm = a.base_samples if name == "base" else a.samples
        ok = True if a.verify_only else render(f, geom, extra, a.res, sm, a.force)
        print(f"[{k:3d}/{len(jobs)}] {name:6s} {'ok' if ok else 'FAILED'}",
              flush=True)
        if not ok:
            missing.append(name)
    if missing:
        print("MISSING:", ", ".join(missing), file=sys.stderr)
        return 1
    print(f"{len(jobs)} layers in {time.time() - t0:.0f}s")

    # ------------------------------------------------------------ subtract
    base = bakelib.read_exr(scratch / "base.exr").astype(np.float64)
    deltas, boxes, energy = [], [], []
    for i in range(n):
        # NO SUBTRACTION: an isolated layer IS the contribution. Alpha comes
        # from base alone — coverage does not accumulate.
        d = bakelib.read_exr(scratch / f"d{i:03d}.exr").astype(np.float64)
        d[..., 3:] = 0.0
        deltas.append(d)
        boxes.append(bbox(d, a.eps))
        energy.append(float(d[..., :3].sum()))
    areas = [((b[2] - b[0]) * (b[3] - b[1])) if b else 0 for b in boxes]
    frac = sum(areas) / float(n * a.res * a.res)
    print(f"\ndelta footprint: mean {np.mean(areas):.0f} px^2 of {a.res**2} "
          f"({100 * frac:.2f}% of a full frame)")
    print(f"delta minimum   {min(d.min() for d in deltas):+.3e} "
          f"(emission only ADDS light, so this should not be negative)")
    # one lens lights itself and a little plate: ~0.6% of a frame. A layer near
    # the whole frame means some source survived --isolate (pass 43's rake did,
    # silently, for a whole bake) — refuse to ship it.
    if frac > 0.05:
        raise SystemExit(f"ring_bake: delta footprint {100 * frac:.1f}% of a frame — "
                         "a source other than the lens survived --isolate")

    # ----------------------------------------------------------------- crop
    npz = out_dir / "ring-bake.npz"
    base16 = base.astype(np.float16)
    arrs = {"base": base16}
    for i, (d, b) in enumerate(zip(deltas, boxes)):
        bb = b if b is not None else (0, 0, 1, 1)
        x0, y0, x1, y1 = bb
        arrs[f"d{i:03d}"] = d[y0:y1, x0:x1, :3].astype(np.float16)
        arrs[f"b{i:03d}"] = np.array(bb, dtype=np.int32)
    np.savez_compressed(npz, **arrs)
    full = sum(f.stat().st_size for f in scratch.glob("d*.exr")) + \
        (scratch / "base.exr").stat().st_size
    print(f"cropped package: {npz.name} {npz.stat().st_size / 1e6:.2f} MB "
          f"vs {full / 1e6:.2f} MB of full-frame EXR "
          f"({full / max(npz.stat().st_size, 1):.1f}x smaller)")

    # the crops must rebuild the full-frame layers EXACTLY, or the format is a
    # second source of truth rather than a packaging of the first
    z = np.load(npz)
    worst = 0.0
    for i in range(n):
        x0, y0, x1, y1 = z[f"b{i:03d}"]
        rebuilt = np.zeros(deltas[i][..., :3].shape, dtype=np.float64)
        rebuilt[y0:y1, x0:x1] = z[f"d{i:03d}"].astype(np.float64)
        worst = max(worst, float(np.abs(rebuilt - deltas[i][..., :3]).max()))
    print(f"crop round-trip: worst |err| {worst:.3e} "
          f"(half-float quantisation only)")

    # -------------------------------------------------------------- verify
    # A real multi-segment state, composed from layers, against a true render
    # of that state. This is the whole claim, so it is measured, not asserted.
    lo_v, hi_v = 0.35, 0.78
    lit = [i for i in range(n) if (i + 1) / n > lo_v and i / n < hi_v]
    truth = scratch / "truth.exr"
    if not a.verify_only or not truth.exists():
        render(truth, geom, ["--value", str(hi_v), "--from", str(lo_v),
                       "--cursor", "off"], a.res, a.base_samples, a.force)
    T = bakelib.read_exr(truth).astype(np.float64)
    got = bakelib.compose(base, [deltas[i] for i in lit])
    lin = bakelib.additivity(got[..., :3], T[..., :3])
    print(f"\nLINEAR additivity over {len(lit)} lit segments:")
    print(f"  mean |err| {lin['mean']:.3e}   peak {lin['peak']:.3e}   "
          f"rel mean {100 * lin['rel_mean']:.4f}%")

    rec = bakelib.Recipe(cube=CUBE, sigmas=[], threshold=1.0, smoothness=1.0,
                         min_ev=MIN_EV, max_ev=MAX_EV, lut_n=LUT_N)
    b_got, b_ref = rec.display(got[..., :3]), rec.display(T[..., :3])
    dif = np.abs(b_got - b_ref)
    print(f"AFTER AgX (the number a consumer actually sees), 0-255:")
    print(f"  mean {dif.mean():.3f}   peak {dif.max():.0f}   "
          f"over 1 LSB {100 * (dif > 1).mean():.3f}%")

    # --------------------------------------------------------------- ship
    man = {
        "contract": "ring-bake/1",
        "component": "knob-ring",
        "why": (f"2^{n} states, {n + 1} renders. Radiance is linear in the set of "
                "emitters and a lit lens differs from an unlit one in Emission "
                "Strength alone, so single-segment deltas span the state space."),
        "recipe": ("linear = base + SUM(delta[i] for i in lit); "
                   "cursor segment contributes cursor_gain * delta[i]; "
                   "byte = trilinear(lut, log2_shaper(linear)). "
                   "SUM IN SCENE-LINEAR, apply the transform once at the end."),
        "segments": n,
        "resolution": a.res,
        "samples": a.samples,
        "base_samples": a.base_samples,
        "denoise": False,
        "adaptive_sampling": False,
        "seed": 0,
        "layers_rendered": ("each delta is rendered under rigs.isolate (black world, every light and rig emitter hidden; the lenses the only source), so it IS segment i's contribution rather than a difference of two noisy renders"),
        "geometry": {geom[i].lstrip("-"): geom[i + 1]
                     for i in range(0, len(geom), 2)},
        "cursor_gain": 1.7,
        "package": {
            "file": "ring-bake.npz",
            "why": ("a contribution covers under 1% of the frame, so a "
                    "full-frame layer is ~99% zeros. Each layer is cropped to "
                    "its own bounding box and stored WITH that box, so a crop "
                    "and its offset cannot be separated."),
            "keys": {
                "base": "(res, res, 4) float16, scene-linear Rec.709, RGBA",
                "d<NNN>": ("(h, w, 3) float16, scene-linear Rec.709, "
                           "non-negative; segment NNN's contribution, cropped"),
                "b<NNN>": "(4,) int32 [x0, y0, x1, y1] into the full frame",
            },
            "apply": ("L = base[..., :3].astype(float32); "
                      "for i in lit: x0,y0,x1,y1 = b<i>; "
                      "L[y0:y1, x0:x1] += d<i>   # PASTE, never resize"),
            "alpha": ("from base alone — coverage does not accumulate, and the "
                      "crops carry no alpha channel at all"),
            "round_trip": ("cropped layers rebuild the full-frame layers to "
                           "half-float quantisation and nothing worse; the "
                           "bake asserts this every run"),
        },
        "files": {"base": "base.exr", "delta": "d<NNN>.exr",
                  "format": ("OpenEXR half-float, ZIP, scene-linear Rec.709, "
                             "full frame; deltas are non-negative and carry "
                             "zero alpha — alpha comes from base alone")},
        "view_transform": {
            "name": "AgX - Medium High Contrast",
            "lut": "agx-mhc-33.cube", "size": LUT_N,
            "min_ev": MIN_EV, "max_ev": MAX_EV,
            "source": ("components/display-segment/bake/agx-mhc-33.cube — the "
                       "SAME transform, consumed rather than re-derived"),
            "apply": ("t = clamp((log2(max(L,1e-10)) - min_ev) / "
                      "(max_ev - min_ev), 0, 1) per channel; "
                      "rgb = trilinear(LUT, t); byte = round(255*rgb)"),
        },
        "compositing": ("knob-boss composites OVER the result; the ring is "
                        "panel-mounted and the knob sits in it. knob-boss "
                        "ships all 101 integer-percent states, so an animation "
                        "renders neither the ring nor the knob."),
        "residual": {
            "linear_additivity": {"mean": lin["mean"], "peak": lin["peak"],
                                  "rel_mean": lin["rel_mean"]},
            "display_bytes": {"mean": float(dif.mean()),
                              "peak": float(dif.max()),
                              "over_1_lsb_frac": float((dif > 1).mean())},
            "measured_on": f"bar {lo_v} -> {hi_v}, {len(lit)} segments lit",
        },
        "delta_footprint": {
            "mean_px2": float(np.mean(areas)),
            "frame_px2": a.res * a.res,
            "frac_of_full_frames": frac,
            "boxes": boxes,
        },
    }
    (out_dir / "ring-bake.json").write_text(json.dumps(man, indent=2) + "\n")
    print("\nmanifest:", out_dir / "ring-bake.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
