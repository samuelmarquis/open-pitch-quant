"""Blender half of the bakelib EXR extraction (`nixie-bake/1`, `segment-bake/1`):
pixels in, pixels out.

Everything here needs `bpy` + numpy and nothing else; the driver half (scipy)
runs outside Blender. Three modes, each driven by a JSON job file:

  dump  load scene-linear EXRs (`names`, `inputs`) and write them to `npz`
  pack  the same, minus the `face`, saved back out as the shipped layer EXRs
        (`face_out`, `delta_out` % name) plus `npz`; deltas arrive already
        rendered, nothing is subtracted
  write arrays a driver already processed (`npz`, by name) out as shipped
        half-float ZIP EXRs (`outputs`: name -> path); RGBA keeps its alpha
  lut   bake AgX Medium High Contrast into an N^3 `.cube` over AgX's own log2
        window [`min_ev`, `max_ev`], via `tmp_png`

  BL=~/Applications/Blender.app/Contents/MacOS/Blender
  $BL -b -P bakelib_bl.py -- pack job.json

`blender -b` exits 0 even on a script exception: the driver must check that every
output landed.
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
MODE = argv[0]
JOB = json.loads(Path(argv[1]).read_text())
scene = bpy.context.scene


def load_linear(path):
    """An EXR back as (H, W, 4) float32, TOP-DOWN. Blender's `pixels` are
    bottom-up and that flip is the single easiest thing to get wrong here."""
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = "Linear Rec.709"
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    return np.flipud(buf.reshape(h, w, 4))


def save_exr(arr, path, alpha=False):
    """(H, W, 3|4) float32 -> half-float ZIP OpenEXR, scene-linear.

    Written through `save_render` with the view transform forced to Raw: a
    Blender Image datablock has no depth/codec of its own, those live on
    `scene.render.image_settings`, and save_render is the only saver that reads
    them."""
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :arr.shape[2]] = arr
    img = bpy.data.images.new("out", w, h, alpha=True, float_buffer=True)
    img.colorspace_settings.name = "Linear Rec.709"
    img.pixels.foreach_set(np.flipud(rgba).ravel())
    ims = scene.render.image_settings
    ims.file_format = "OPEN_EXR"
    ims.color_mode = "RGBA" if alpha else "RGB"
    ims.color_depth = "16"
    ims.exr_codec = "ZIP"
    scene.view_settings.view_transform = "Raw"
    scene.view_settings.look = "None"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.save_render(filepath=str(path), scene=scene)
    bpy.data.images.remove(img)


def through_view(arr, tmp_png):
    """(H, W, 3) scene-linear -> the display-referred bytes the canon pipeline
    would have written, as float in 0..1. This is AgX itself, applied by
    Blender, and it is how the LUT gets its ground truth: save the data through
    the view transform at 16 bits, read it straight back as Non-Color."""
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = arr
    img = bpy.data.images.new("lin", w, h, alpha=True, float_buffer=True)
    img.colorspace_settings.name = "Linear Rec.709"
    img.pixels.foreach_set(np.flipud(rgba).ravel())
    ims = scene.render.image_settings
    ims.file_format = "PNG"
    ims.color_mode = "RGB"
    ims.color_depth = "16"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    img.save_render(filepath=str(tmp_png), scene=scene)
    bpy.data.images.remove(img)
    back = bpy.data.images.load(str(tmp_png))
    back.colorspace_settings.name = "Non-Color"
    buf = np.empty(w * h * 4, dtype=np.float32)
    back.pixels.foreach_get(buf)
    bpy.data.images.remove(back)
    return np.flipud(buf.reshape(h, w, 4))[..., :3]


if MODE in ("dump", "pack"):
    names = JOB["names"]
    stack = np.stack([load_linear(JOB["inputs"][n])[..., :3] for n in names])
    alpha = load_linear(JOB["inputs"][names[0]])[..., 3]
    if MODE == "pack":
        # NO SUBTRACTION. A delta arrives already rendered — the scene lit by
        # emitter i and nothing else, which by linearity IS render(i lit) -
        # render(all off), but path-traced directly instead of differenced out
        # of two independent traces.
        face_i = names.index(JOB["face"])
        face = stack[face_i]
        deltas = {n: stack[i] for i, n in enumerate(names) if i != face_i}
        save_exr(np.dstack([face, alpha]), JOB["face_out"], alpha=True)
        for n, d in deltas.items():
            save_exr(d, JOB["delta_out"] % n)
        np.savez_compressed(JOB["npz"], face=face, alpha=alpha,
                            names=np.array(list(deltas)),
                            deltas=np.stack(list(deltas.values())))
    else:
        np.savez_compressed(JOB["npz"], names=np.array(names), stack=stack,
                            alpha=alpha)
    print("bake_bl %s ok -> %s" % (MODE, JOB["npz"]))

elif MODE == "write":
    # arrays a driver has already processed (cropped, a linear glow applied),
    # out as shipped layers: `npz` holds them by name, `outputs` maps name ->
    # EXR path, and a (H, W, 4) array keeps its alpha
    data = np.load(JOB["npz"])
    for name, path in JOB["outputs"].items():
        arr = data[name].astype(np.float32)
        save_exr(arr, path, alpha=arr.shape[2] == 4)
    print("bake_bl write ok -> %d layers" % len(JOB["outputs"]))

elif MODE == "lut":
    # AgX is NOT a per-channel curve — it runs an inset matrix that mixes the
    # channels before its log/sigmoid, which is exactly why the transform has to
    # ship as a 3D LUT and not three 1D ones.
    #
    # The domain is AgX's OWN log2 window, [-12.47393, +4.026069] EV, so the
    # cube covers everything AgX itself resolves and the clamp at each end is
    # the transform's clamp rather than one the LUT invented. `probe` re-measures
    # that claim rather than trusting it.
    N = JOB["n"]
    lo, hi = JOB["min_ev"], JOB["max_ev"]
    t = np.arange(N, dtype=np.float64) / (N - 1)
    lin = (2.0 ** (t * (hi - lo) + lo)).astype(np.float32)
    idx = np.arange(N ** 3)
    cube = np.empty((N ** 3, 3), dtype=np.float32)
    cube[:, 0] = lin[idx % N]                 # red fastest, .cube convention
    cube[:, 1] = lin[(idx // N) % N]
    cube[:, 2] = lin[idx // (N * N)]
    img = cube.reshape(N * N, N, 3)           # W = N, H = N*N
    disp = through_view(img, JOB["tmp_png"]).reshape(N ** 3, 3)

    out = [f"# AgX Medium High Contrast, baked from Blender {bpy.app.version_string}",
           f"# domain: per-channel log2 shaper over [{lo}, {hi}] EV",
           f"# t = clamp((log2(max(linear, 1e-10)) - ({lo})) / ({hi} - ({lo})), 0, 1)",
           "# output: display-encoded sRGB, 0..1 — write straight to 8-bit",
           f"LUT_3D_SIZE {N}", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"]
    out += ["%.6f %.6f %.6f" % tuple(v) for v in disp]
    Path(JOB["cube"]).parent.mkdir(parents=True, exist_ok=True)
    Path(JOB["cube"]).write_text("\n".join(out) + "\n")

    # Does the domain really cover AgX, i.e. is the clamp at each end AgX's own?
    probe = np.array([[2.0 ** (lo - 4), 2.0 ** (lo - 4), 2.0 ** (lo - 4)],
                      [2.0 ** lo, 2.0 ** lo, 2.0 ** lo],
                      [2.0 ** hi, 2.0 ** hi, 2.0 ** hi],
                      [2.0 ** (hi + 4), 2.0 ** (hi + 4), 2.0 ** (hi + 4)],
                      [0.0, 0.0, 0.0]], dtype=np.float32).reshape(5, 1, 3)
    pv = through_view(probe, JOB["tmp_png"]).reshape(5, 3)
    print("lut probe under/lo/hi/over/zero:", json.dumps(pv.round(6).tolist()))
    print("bake_bl lut ok ->", JOB["cube"])

else:
    raise SystemExit(f"unknown mode {MODE!r}")
