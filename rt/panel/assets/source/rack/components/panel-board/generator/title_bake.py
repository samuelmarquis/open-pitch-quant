"""`title-bake/1` — the additive layer bake for a panel's backlit `--title`.

  python3 components/panel-board/generator/title_bake.py OUTDIR \
      [--scene SCENE.py] [--px-per-unit N] [--samples N] -- [scene flags, --title ...]

A title of N letters has 2^N lit sets and any RGB per letter, so it ships as
N+1 layers. A lit letter differs from an unlit one ONLY in its insert's
emission, so radiance is linear in the letters' light:

    linear = plate + SUM(w_i x letter_i)       w_i: any RGB per letter, per frame

`plate` is the consumer's own panel render with the title unlit (their base;
this bake also ships the title band of it as `face`). `letter_i` is rendered
DARK (`--dark --title-lit i`: the rig off), so it is that letter's light and
nothing else — the lit insert and its light on the metal around it — never a
difference of two renders. Rendered denoise off and adaptive off; both break
additivity.

GLOW: each letter layer is convolved with a point-spread (a sum of Gaussians,
energy-preserving) BEFORE it ships. A blur with no threshold is linear, so a
glowing layer still adds exactly; it is the light radiating out of the cut onto
the metal. Sam, p129: soft glow (35 % at 1.25 logical px + 12 % at 4.5).

`--scene` is the panel scene the consumer bakes through (its own framing
wrapper, e.g. open-cepstrum's panel_board_bake.py), so the layers register
with its plate pixel for pixel; default panel_scene.py. Layers are cropped to
the title band (every letter's light > 1e-5, padded), offset in the manifest.

Needs numpy and PIL only (the glow's Gaussian is numpy; no scipy).

Outputs in OUTDIR: `face.exr` (RGBA, the band of the unlit render),
`letter_<i>.exr` (RGB, glow applied), `title.json` (the manifest).
NB (Blender 5.2): `blender -b` exits 0 even on a script exception — every
render is checked for its output file.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1] / "_studio"
sys.path.insert(0, str(STUDIO))
import bakelib  # noqa: E402

ROOT = HERE.parents[2]
BL = Path.home() / "Applications/Blender.app/Contents/MacOS/Blender"
BL_HALF = STUDIO / "bakelib_bl.py"
CUBE = HERE.parents[1] / "display-segment" / "bake" / "agx-mhc-33.cube"
LUT_N, MIN_EV, MAX_EV = 33, -12.47393, 4.026069
GLOW = ((1.25, 0.35), (4.5, 0.12))   # (sigma in LOGICAL px = 0.01 unit, share of the light)
CROP_EPS, CROP_PAD = 1e-5, 4


def gaussian(img, sigma):
    """Separable Gaussian, zero outside the frame, kernel to 4 sigma (numpy
    only, so the bake runs on a plain numpy install)."""
    r = max(int(np.ceil(4.0 * sigma)), 1)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    img = np.apply_along_axis(np.convolve, 0, img, k, mode="same")
    return np.apply_along_axis(np.convolve, 1, img, k, mode="same")


def glow(layer, px_per_logical):
    out = layer * (1.0 - sum(k for _, k in GLOW))
    for s, k in GLOW:
        sig = s * px_per_logical
        out += k * np.stack([gaussian(layer[..., c], sig) for c in range(3)], -1)
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cut = argv.index("--") if "--" in argv else len(argv)
    p = argparse.ArgumentParser()
    p.add_argument("outdir", type=Path)
    p.add_argument("--scene", type=Path, default=HERE / "panel_scene.py")
    p.add_argument("--px-per-unit", type=float, default=200.0)
    p.add_argument("--samples", type=int, default=1024)
    a = p.parse_args(argv[:cut])
    flags = argv[cut + 1:]
    if "--title" not in flags:
        raise SystemExit("title_bake: pass the scene's --title (and its other flags) after --")
    word = flags[flags.index("--title") + 1]
    n = len(word)
    common = [*flags, "--samples", str(a.samples), "--denoise", "off", "--adaptive", "off"]
    a.outdir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="title-bake-") as tmp:
        tmp = Path(tmp)
        jobs = [("base", ["--title-lit", "none"]), ("truth", ["--title-lit", "all"])]
        jobs += [(f"L{i}", ["--title-lit", str(i), "--dark"]) for i in range(1, n + 1)]
        for name, extra in jobs:
            out = tmp / f"{name}.exr"
            bakelib.run([BL, "-b", "-P", a.scene, "--", out, *common, *extra], out)
            print(f"  rendered {name}", flush=True)
        base = bakelib.read_exr(tmp / "base.exr").astype(np.float64)
        truth = bakelib.read_exr(tmp / "truth.exr")[..., :3].astype(np.float64)
        raw = [bakelib.read_exr(tmp / f"L{i}.exr")[..., :3].astype(np.float64)
               for i in range(1, n + 1)]

    px_per_logical = a.px_per_unit / 100.0
    lit = [glow(l, px_per_logical) for l in raw]
    energy = [float(g.sum() / max(r.sum(), 1e-12)) for g, r in zip(lit, raw)]
    lit = [np.maximum(g, 0.0) for g in lit]
    mask = np.zeros(base.shape[:2], bool)
    for g in lit:
        mask |= g.max(-1) > CROP_EPS
    ys, xs = np.nonzero(mask)
    h, w = mask.shape
    y0, y1 = max(ys.min() - CROP_PAD, 0), min(ys.max() + 1 + CROP_PAD, h)
    x0, x1 = max(xs.min() - CROP_PAD, 0), min(xs.max() + 1 + CROP_PAD, w)
    kept = sum(float(g[y0:y1, x0:x1].sum()) for g in lit) / max(sum(float(g.sum()) for g in lit), 1e-12)
    # additivity over the crop, where the layers apply: outside it the consumer's
    # plate is used as rendered, and there base and truth differ only by the
    # path-trace noise Cycles reshuffles when a mesh turns emissive
    band = (slice(y0, y1), slice(x0, x1))
    add = bakelib.additivity(bakelib.compose(base[band][..., :3], [r[band] for r in raw]),
                             truth[band])

    arrays = {"face": base[y0:y1, x0:x1].astype(np.float32)}
    outputs = {"face": str(a.outdir / "face.exr")}
    for i, g in enumerate(lit, 1):
        arrays[f"letter_{i}"] = g[y0:y1, x0:x1].astype(np.float32)
        outputs[f"letter_{i}"] = str(a.outdir / f"letter_{i}.exr")
    npz = a.outdir / "_layers.npz"
    np.savez_compressed(npz, **arrays)
    job = a.outdir / "_write.json"
    job.write_text(json.dumps({"npz": str(npz), "outputs": outputs}))
    bakelib.run([BL, "-b", "-P", BL_HALF, "--", "write", job], outputs[f"letter_{n}"])
    npz.unlink()
    job.unlink()

    back = [bakelib.read_exr(outputs[f"letter_{i}"])[..., :3] for i in range(1, n + 1)]
    roundtrip = max(float(np.abs(b - arrays[f"letter_{i}"]).max()) for i, b in enumerate(back, 1))
    manifest = {
        "contract": "title-bake/1",
        "title": word,
        "scene": str(a.scene.relative_to(ROOT)) if a.scene.is_relative_to(ROOT) else a.scene.name,
        "scene_flags": flags,
        "samples": a.samples,
        "frame_px": [w, h],
        "px_per_unit": a.px_per_unit,
        "crop": {"x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0),
                 "note": "layer pixel (0,0) is frame pixel (x, y); frame rows top-down"},
        "layers": {"face": "face.exr", "letters": [f"letter_{i}.exr" for i in range(1, n + 1)],
                   "format": "scene-linear half-float ZIP OpenEXR; face RGBA, letters RGB"},
        "unit": "a letter layer at weight 1 is its insert at white emission 1.0 "
                "(--title-emit); weights are any RGB per letter, per frame",
        "composite": "linear = plate + SUM(w_i * letter_i) over the crop, in scene-linear; "
                     "then the view transform. plate = the consumer's own render of the "
                     "panel with the title unlit (face.exr is its band, for checking)",
        "glow": {"model": "energy-preserving sum of Gaussians, applied to each letter layer "
                          "before shipping (linear: the layers still add)",
                 "terms": [{"sigma_logical_px": s, "share": k} for s, k in GLOW],
                 "energy_kept_in_crop": round(kept, 6),
                 "energy_ratio_per_letter": [round(e, 4) for e in energy]},
        "view_transform": {"lut": str(CUBE.relative_to(ROOT)), "size": LUT_N,
                           "min_ev": MIN_EV, "max_ev": MAX_EV,
                           "shaper": "t = clamp((log2(max(L, 1e-10)) - min_ev) / (max_ev - min_ev), 0, 1)",
                           "apply": "trilinear per channel into the cube; outputs display sRGB"},
        "residual": {"linear_additivity": {k: round(v, 6) for k, v in add.items()},
                     "note": "over the crop: face + SUM(raw letter layers) vs a true all-lit "
                             "render, before the glow (the glow is linear and "
                             "energy-preserving)",
                     "exr_roundtrip_peak": roundtrip},
        "disk_bytes": {k: Path(v).stat().st_size for k, v in outputs.items()},
    }
    (a.outdir / "title.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"title-bake/1 {word}: {n} letters, crop {x1 - x0}x{y1 - y0} at ({x0},{y0}), "
          f"additivity {100 * add['rel_mean']:.2f}% mean -> {a.outdir}")


if __name__ == "__main__":
    main()
