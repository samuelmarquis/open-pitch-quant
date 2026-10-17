#!/usr/bin/env python3
"""Author the knob's bump/rough maps (4096², band-limited) beside this file.

  python3 make_maps.py

Ring amplitude fades to zero at the center (where polar texels alias) and all
bump fades out over the shoulder (where flat-Z projection stretches; the
shoulder should read as clean polished chrome).
"""

import numpy as np
from pathlib import Path
from PIL import Image

S = 4096
rng = np.random.default_rng(16)
yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
cx = cy = S / 2
r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (S / 2)
az = np.arctan2(yy - cy, xx - cx)

def smooth(x, e0, e1):
    t = np.clip((x - e0) / (e1 - e0 + 1e-9), 0, 1)
    return t * t * (3 - 2 * t)

bump = np.full((S, S), 0.5, np.float32)
# spun grooves: fade in from center (alias guard), fade out at shoulder
center_guard = smooth(r, 0.045, 0.12)
shoulder_fade = 1 - smooth(r, 0.66, 0.80)
grooves = np.sin(r * 150 * 6.28)
az_tab = (0.75 + 0.5 * rng.random(2048)).astype(np.float32)
az_mod = az_tab[((az + np.pi) / (2 * np.pi) * 2047).astype(int)]
amp_tab = (0.3 + 0.7 * rng.random(4096)).astype(np.float32)
bump += (grooves * amp_tab[np.clip((r * 1200).astype(int), 0, 4095)]
         * az_mod * 0.020 * center_guard * shoulder_fade)
# fine knurl on the barrel band only (r > 0.86 in projection)
fine = np.sin(az * 288) * smooth(r, 0.84, 0.90)
bump += fine * 0.030
# faint arc scratches, also guarded
for _ in range(70):
    ang0 = rng.random() * 6.28
    rr0 = 0.15 + rng.random() * 0.5
    length = 0.2 + rng.random() * 0.7
    aa = np.abs(np.mod(az - ang0 + np.pi, 2 * np.pi) - np.pi)
    on = (np.abs(r - rr0) < 0.0009) & (aa < length)
    bump[on] -= 0.08 * rng.random()
Image.fromarray((np.clip(bump, 0, 1) * 65535).astype(np.uint16)).save(
    Path(__file__).parent / "bump.png")

rough = np.full((S, S), 0.12, np.float32)
from PIL import ImageFilter
sm = Image.fromarray((rng.random((256, 256)) * 255).astype(np.uint8))
sm = sm.resize((S, S), Image.BICUBIC).filter(ImageFilter.GaussianBlur(18))
smudge = np.asarray(sm, np.float32) / 255
rough += (smudge - 0.5) * 0.035
rough += np.clip(0.5 - bump, 0, 1) * 0.15
# orange peel: fine micro-noise everywhere (chrome is never perfect)
op = Image.fromarray((rng.random((1024, 1024)) * 255).astype(np.uint8))
op = op.resize((S, S), Image.BICUBIC).filter(ImageFilter.GaussianBlur(2))
bump += (np.asarray(op, np.float32) / 255 - 0.5) * 0.012
rough += (1 - shoulder_fade) * -0.03          # shoulder a touch glossier
Image.fromarray((np.clip(rough, 0.09, 0.5) * 65535).astype(np.uint16)).save(
    Path(__file__).parent / "rough.png")
print("v5 maps authored (smooth smudge, deep scratches, orange peel)")
