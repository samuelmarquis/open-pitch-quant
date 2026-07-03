#!/usr/bin/env python3
"""Measure dominant spectral peaks and report cents offsets vs expected notes.

  python3 tools/check_tuning.py out/x.wav --expect C4,E4,G4 --band 200,450
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opq import io  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--expect", required=True, help="note names, e.g. C4,E4,G4")
    ap.add_argument("--band", default="60,1200", help="fmin,fmax Hz")
    args = ap.parse_args()

    x = io.load_audio(args.input)
    fmin, fmax = (float(v) for v in args.band.split(","))
    targets = {
        n.strip(): 440.0 * 2 ** ((io.parse_note(n) - 69) / 12)
        for n in args.expect.split(",")
    }

    # long FFT over the central chunk for fine frequency resolution
    n = min(len(x), 8 * io.SR)
    seg = x[(len(x) - n) // 2 :][:n] * np.hanning(n)
    spec = np.abs(np.fft.rfft(seg))
    freqs = np.fft.rfftfreq(n, 1 / io.SR)
    sel = (freqs >= fmin) & (freqs <= fmax)

    for name, ft in sorted(targets.items(), key=lambda kv: kv[1]):
        # strongest bin within ±80 cents of target, parabolic refine
        near = sel & (np.abs(1200 * np.log2(freqs / ft)) < 80)
        if not near.any():
            print(f"  {name}: no energy near {ft:.1f} Hz")
            continue
        i = np.flatnonzero(near)[np.argmax(spec[near])]
        a, b, c = spec[i - 1], spec[i], spec[i + 1]
        denom = a - 2 * b + c
        delta = 0.5 * (a - c) / denom if abs(denom) > 1e-12 else 0.0
        f = freqs[i] + delta * (freqs[1] - freqs[0])
        cents = 1200 * np.log2(f / ft)
        db = 20 * np.log10(max(spec[i], 1e-12) / spec[sel].max())
        print(f"  {name} ({ft:7.2f} Hz): measured {f:7.2f} Hz  "
              f"{cents:+6.1f} cents  [{db:+5.1f} dB rel]")


if __name__ == "__main__":
    main()
