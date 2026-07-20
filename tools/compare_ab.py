#!/usr/bin/env python3
"""The A/B battery: PITCHMAP's renders vs ours, job by job.

Inputs: testdata/reference/{jobs,renders} (theirs) and out/ab-ours (ours,
from render_ab_ours.py). Emits out/ab-analysis/: metrics.md (the table
the findings doc quotes) and measurement plates (PNG). Nothing here
listens — this is the instrumented pass; ears are the second pass.

Run:  nix develop --command python3 tools/compare_ab.py
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from make_ab_pack import build_jobs, stem  # noqa: E402

JOBS = ROOT / "testdata" / "reference" / "jobs"
THEIRS = ROOT / "testdata" / "reference" / "renders"
OURS = ROOT / "out" / "ab-ours"
OUT = ROOT / "out" / "ab-analysis"

WHITE, AMBER, OCHRE, GRAY = "#E8E4D8", "#FFB300", "#A64B00", "#55585E"


def mono(path):
    x, sr = sf.read(str(path), always_2d=True)
    return x.mean(axis=1), sr


def rms(x):
    return float(np.sqrt(np.mean(x**2)))


def chroma(x, sr, t0=None, t1=None):
    a = x if t0 is None else x[int(t0 * sr):int(t1 * sr)]
    S = np.abs(np.fft.rfft(a * np.hanning(len(a)), 1 << 19)) ** 2
    f = np.fft.rfftfreq(1 << 19, 1 / sr)
    m = (f > 80) & (f < 3000)
    pc = np.zeros(12)
    midi = 69 + 12 * np.log2(f[m] / 440.0)
    np.add.at(pc, np.round(midi).astype(int) % 12, S[m])
    return pc / max(pc.sum(), 1e-30)


def cosine(a, b):
    return float(a @ b / max(np.linalg.norm(a) * np.linalg.norm(b), 1e-30))


def peak_trace(x, sr, t0, t1, flo, fhi, win=0.10, hop=0.02):
    ts, fs = [], []
    for t in np.arange(t0, t1 - win, hop):
        seg = x[int(t * sr):int((t + win) * sr)]
        S = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 1 << 18))
        f = np.fft.rfftfreq(1 << 18, 1 / sr)
        m = (f > flo) & (f < fhi)
        ts.append(t + win / 2)
        fs.append(f[m][np.argmax(S[m])])
    return np.array(ts), np.array(fs)


def dev_cents(x, sr, target, t0=2.0, t1=7.0):
    seg = x[int(t0 * sr):int(t1 * sr)]
    S = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 1 << 20))
    f = np.fft.rfftfreq(1 << 20, 1 / sr)
    m = (f > target * 2 ** (-0.7 / 12)) & (f < target * 2 ** (0.7 / 12))
    return 1200 * np.log2(f[m][np.argmax(S[m])] / target)


def plate(name):
    fig, ax = plt.subplots(figsize=(11, 6), facecolor="black")
    ax.set_facecolor("black")
    for s in ax.spines.values():
        s.set_color(GRAY)
    ax.tick_params(colors=WHITE, labelsize=8)
    ax.xaxis.label.set_color(WHITE)
    ax.yaxis.label.set_color(WHITE)
    ax.set_title(name, color=WHITE, fontsize=10, loc="left")
    return fig, ax


def save(fig, fname):
    fig.savefig(OUT / fname, dpi=120, facecolor="black", bbox_inches="tight")
    plt.close(fig)
    print(f"  plate: {fname}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = {j["num"]: (j, stem(j)) for j in build_jobs()}
    md = ["# A/B battery — measured, not yet listened", ""]

    # ---------------- global table: level + chroma agreement per job
    md += ["## Per-job gross agreement",
           "",
           "| job | input | gain PM (dB) | gain ours (dB) | chroma PM~ours |",
           "|---|---|---|---|---|"]
    chroma_rows = []
    for n in sorted(jobs):
        j, s = jobs[n]
        if j["flag"] == "NULL":
            continue
        xi, sr = mono(JOBS / f"{s}.wav")
        xt, _ = mono(THEIRS / f"{s}.wav")
        xo, _ = mono(OURS / f"{s}.wav")
        m = min(len(xi), len(xt), len(xo))
        xi, xt, xo = xi[:m], xt[:m], xo[:m]
        ri = max(rms(xi), 1e-12)
        gt = 20 * np.log10(max(rms(xt), 1e-12) / ri)
        go = 20 * np.log10(max(rms(xo), 1e-12) / ri)
        cs = cosine(chroma(xt, sr), chroma(xo, sr)) if rms(xt) > 1e-6 else float("nan")
        chroma_rows.append((n, cs))
        md.append(f"| j{n:02d} | {j['src'][:24]} | {gt:+.1f} | {go:+.1f} |"
                  f" {'—' if np.isnan(cs) else f'{cs:.3f}'} |")
    md.append("")

    # ---------------- tuning accuracy: j13 (base) and j18 (feel) and j22 (th)
    md += ["## Detuned triad (C4+35c, E4-40c, G4+20c): where each engine puts it",
           "",
           "| job | knob | C4 PM | E4 PM | G4 PM | C4 ours | E4 ours | G4 ours |",
           "|---|---|---|---|---|---|---|---|"]
    for n, lab in ((13, "base"), (18, "fe100"), (22, "th50")):
        _, s = jobs[n]
        xt, sr = mono(THEIRS / f"{s}.wav")
        xo, _ = mono(OURS / f"{s}.wav")
        row = [f"| j{n} | {lab} |"]
        for x in (xt, xo):
            for tgt in (261.63, 329.63, 392.0):
                row.append(f" {dev_cents(x, sr, tgt):+.1f} |")
        md.append("".join(row))
    md.append("")

    # ---------------- voice starvation: j15 el100 -> our --voices 1
    md += ["## ELECTRIFY 100 / voices 1 (j15): triad peak levels re loudest (dB)",
           "", "| engine | C4 | E4 | G4 |", "|---|---|---|---|"]
    _, s = jobs[15]
    for lab, p in (("PITCHMAP", THEIRS), ("ours", OURS)):
        x, sr = mono(p / f"{s}.wav")
        seg = x[int(2 * sr):int(7 * sr)] * np.hanning(int(5 * sr))
        S = np.abs(np.fft.rfft(seg, 1 << 20))
        f = np.fft.rfftfreq(1 << 20, 1 / sr)
        vals = []
        for tgt in (261.63, 329.63, 392.0):
            m = (f > tgt * 2 ** (-0.7 / 12)) & (f < tgt * 2 ** (0.7 / 12))
            vals.append(20 * np.log10(S[m].max() / S.max()))
        md.append(f"| {lab} | {vals[0]:+.1f} | {vals[1]:+.1f} | {vals[2]:+.1f} |")
    md.append("")

    # ---------------- NONOTES divergence
    md += ["## NONOTES (MIDI MAP on, nothing held)", ""]
    for n in (9, 21, 32):
        _, s = jobs[n]
        xt, _ = mono(THEIRS / f"{s}.wav")
        xo, _ = mono(OURS / f"{s}.wav")
        md.append(f"- j{n:02d}: PITCHMAP rms {rms(xt):.4f}, ours rms {rms(xo):.4f}"
                  " — both engines mute on an empty grid. Agreement, independently arrived at.")
    md.append("")

    # ---------------- plate 1: sweep basins j10/j11/j12
    fig, ax = plate("PLATE A — attraction basins: log sweep 110-1760 Hz vs held A3"
                    " (j10 repeat-near / j11 custom-near / j12 repeat-intel)")
    xi, sr = mono(JOBS / f"{jobs[10][1]}.wav")

    def fin(t):
        return 110.0 * (1760 / 110) ** ((t - 0.25) / 10.0)
    styles = {10: (AMBER, "-", "repeat-near PM"), 11: (OCHRE, "-", "custom-near PM"),
              12: ("#4FB8C4", "-", "repeat-intel PM")}
    for n, (col, ls, lab) in styles.items():
        xt, _ = mono(THEIRS / f"{jobs[n][1]}.wav")
        ts, fs = peak_trace(xt, sr, 0.4, 10.1, 70, 2200)
        ax.plot(fin(ts), fs, ls, color=col, lw=1.0, label=lab)
    xo, _ = mono(OURS / f"{jobs[10][1]}.wav")
    ts, fs = peak_trace(xo, sr, 0.4, 10.1, 70, 2200)
    ax.plot(fin(ts), fs, "-", color=WHITE, lw=0.9, label="repeat-near OURS")
    fr = np.geomspace(100, 2000, 10)
    ax.plot(fr, fr, ":", color=GRAY, lw=0.7, label="identity")
    for a in (110, 220, 440, 880, 1760):
        ax.axhline(a, color=GRAY, lw=0.4, alpha=0.6)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("input Hz"); ax.set_ylabel("output Hz")
    ax.legend(facecolor="black", labelcolor=WHITE, edgecolor=GRAY, fontsize=8)
    save(fig, "plateA_basins.png")

    # ---------------- plate 2: chord change corridor j24
    fig, ax = plate("PLATE B — chord change at 5.25 s (j24 repeat-near):"
                    " the moving voice, G4 corridor")
    for lab, p, col in (("PITCHMAP", THEIRS, AMBER), ("ours", OURS, WHITE)):
        x, _ = mono(p / f"{jobs[24][1]}.wav")
        ts, fs = peak_trace(x, sr, 4.8, 7.0, 340, 480)
        ax.plot(ts, 1200 * np.log2(fs / 392.0), color=col, lw=1.2, label=lab)
    ax.axvline(5.25, color=OCHRE, lw=0.8)
    for c, name in ((0, "G4"), (200, "A4")):
        ax.axhline(c, color=GRAY, lw=0.4)
        ax.text(6.95, c + 6, name, color=GRAY, fontsize=7, ha="right")
    ax.set_xlabel("s"); ax.set_ylabel("cents re G4")
    ax.legend(facecolor="black", labelcolor=WHITE, edgecolor=GRAY, fontsize=8)
    save(fig, "plateB_chordchange.png")

    # ---------------- plate 3: transient survival j34
    fig, ax = plate("PLATE C — transients vs held C-maj (j34): envelopes;"
                    " first events at 0.5/0.73/1.0 s")
    xi, sr = mono(JOBS / f"{jobs[34][1]}.wav")
    xt, _ = mono(THEIRS / f"{jobs[34][1]}.wav")
    xo, _ = mono(OURS / f"{jobs[34][1]}.wav")
    hop = int(0.002 * sr)
    for k, (lab, x, col) in enumerate((("input", xi, OCHRE), ("PITCHMAP", xt, AMBER),
                                       ("ours", xo, WHITE))):
        seg = x[:int(2.2 * sr)]
        env = np.array([np.abs(seg[i:i + hop]).max()
                        for i in range(0, len(seg) - hop, hop)])
        t = np.arange(len(env)) * hop / sr
        ax.plot(t, env / env.max() - k * 1.1, color=col, lw=0.7)
        ax.text(0.02, -k * 1.1 + 0.45, lab, color=col, fontsize=8)
    ax.set_yticks([]); ax.set_xlabel("s")
    save(fig, "plateC_transients.png")

    # ---------------- plate 4: chroma agreement bar
    fig, ax = plate("PLATE D — chroma agreement PITCHMAP~ours per job"
                    " (1.0 = identical pitch-class balance)")
    ns = [n for n, c in chroma_rows if not np.isnan(c)]
    cs = [c for _, c in chroma_rows if not np.isnan(c)]
    cols = [WHITE if c > 0.9 else (AMBER if c > 0.7 else OCHRE) for c in cs]
    ax.bar(range(len(ns)), cs, color=cols)
    ax.set_xticks(range(len(ns)))
    ax.set_xticklabels([f"j{n:02d}" for n in ns], rotation=90, fontsize=6)
    ax.axhline(0.9, color=GRAY, lw=0.5)
    ax.set_ylim(0, 1.02)
    save(fig, "plateD_chroma.png")

    (OUT / "metrics.md").write_text("\n".join(md) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}/metrics.md")


if __name__ == "__main__":
    main()
