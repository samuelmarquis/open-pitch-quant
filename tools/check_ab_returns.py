#!/usr/bin/env python3
"""Receiving gate for PITCHMAP reference renders.

Run when a rendered pack (or partial pack) lands back in
testdata/reference/renders/. Verifies the returns against the job table
in make_ab_pack.py (stems are the contract), reports what's present by
tier, checks formats, and — using j00, the plugin-bypassed control —
measures the residual latency of the remote render path. If j00 shows a
lag, every render carries it; correct globally, don't re-render.

Hard failures: unreadable files, wrong sample rate, unknown stems.
Everything else (missing jobs, duration drift, odd leading silence) is
reported, not fatal — partial returns are allowed by the protocol.

Run:  nix develop --command python3 tools/check_ab_returns.py
"""

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from make_ab_pack import SR, build_jobs, stem  # noqa: E402

PACK = ROOT / "testdata" / "reference"


def load(path):
    x, sr = sf.read(str(path), dtype="float64", always_2d=True)
    return x.mean(axis=1), sr


def leading_silence(x, thresh_db=-60.0):
    thresh = 10 ** (thresh_db / 20)
    idx = np.flatnonzero(np.abs(x) > thresh)
    return int(idx[0]) if len(idx) else len(x)


def xcorr_lag(a, b, window=None):
    """Lag of b relative to a (positive = b is late), via FFT cross-corr."""
    n = min(len(a), len(b)) if window is None else min(window, len(a), len(b))
    a, b = a[:n], b[:n]
    size = 1 << (2 * n - 1).bit_length()
    A = np.fft.rfft(a, size)
    B = np.fft.rfft(b, size)
    c = np.fft.irfft(A.conj() * B, size)
    c = np.concatenate([c[-(n - 1):], c[:n]])
    return int(np.argmax(c)) - (n - 1)


def main():
    jobs = {stem(j): j for j in build_jobs()}
    rdir = PACK / "renders"
    returned = sorted(p for p in rdir.glob("*.wav"))
    if not returned:
        sys.exit(f"no .wav returns in {rdir.relative_to(ROOT)} — nothing to check")

    failures, notes = [], []
    present = {}
    for p in returned:
        if p.stem not in jobs:
            failures.append(f"{p.name}: stem matches no job — misnamed?")
            continue
        try:
            x, sr = load(p)
        except Exception as e:  # noqa: BLE001
            failures.append(f"{p.name}: unreadable ({e})")
            continue
        if sr != SR:
            failures.append(f"{p.name}: {sr} Hz, expected {SR}")
            continue
        present[p.stem] = x
        job_wav = PACK / "jobs" / f"{p.stem}.wav"
        jx, _ = load(job_wav)
        d = len(x) - len(jx)
        if abs(d) > SR // 2:
            notes.append(f"{p.stem}: duration off by {d:+d} samples ({d/SR:+.2f}s)")
        elif d != 0:
            notes.append(f"{p.stem}: duration off by {d:+d} samples")
        ls = leading_silence(x) - leading_silence(jx)
        if abs(ls) > 1000:
            notes.append(f"{p.stem}: leading silence differs by {ls:+d} samples "
                         f"({ls/SR*1000:+.0f} ms) — latency suspect")

    # the oracle: j00 is the bare render path, must null against its job wav
    null_stem = next(s for s, j in jobs.items() if j["flag"] == "NULL")
    print(f"returns: {len(present)}/{len(jobs)} jobs", end="")
    for t in "ABC":
        tot = [s for s, j in jobs.items() if j["tier"] == t]
        got = [s for s in tot if s in present]
        print(f"   {t}: {len(got)}/{len(tot)}", end="")
    print()
    if null_stem in present:
        jx, _ = load(PACK / "jobs" / f"{null_stem}.wav")
        x = present[null_stem]
        lag = xcorr_lag(jx, x, window=min(len(jx), len(x)))
        n = min(len(jx), len(x))
        a = jx[max(0, -lag):n - max(0, lag)] if lag < 0 else jx[:n - lag]
        b = x[lag:n] if lag >= 0 else x[:n + lag]
        m = min(len(a), len(b))
        num = np.sqrt(np.mean((a[:m] - b[:m]) ** 2))
        den = np.sqrt(np.mean(a[:m] ** 2))
        null_db = 20 * np.log10(max(num, 1e-12) / max(den, 1e-12))
        print(f"j00 control: lag {lag:+d} samples ({lag/SR*1000:+.1f} ms), "
              f"null {null_db:.1f} dB "
              f"{'— CLEAN' if lag == 0 and null_db < -60 else '— APPLY GLOBAL CORRECTION'}")
    else:
        print("j00 control not returned — render-path latency UNVERIFIED")

    missing = [s for s in jobs if s not in present]
    if missing:
        print(f"missing ({len(missing)}):")
        for s in missing:
            print(f"  {s}")
    for n_ in notes:
        print(f"note: {n_}")
    for f in failures:
        print(f"FAIL: {f}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
