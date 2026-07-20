#!/usr/bin/env python3
"""Pack v2: the PURIFY batch (plus THRESHOLD curve + FEEL repro).

Pack v1's purify rows are void — the scripted bench set an inert
parameter index for PURIFY (proof: pu0 and pu100 renders are
magnitude-identical, bit-identical on noise) while every other knob
measurably moved. v2 re-runs purify properly on purify-forward material
(breath, hats, noisy sustain, drum loops) as a 5-point sweep, and the
operator protocol now requires (a) a full VST3 parameter-table dump in
the return and (b) a purify self-test render pair that must FAIL
magnitude-identity before the batch may run. Ride-alongs while the bench
is hot: a THRESHOLD 5-point curve and a FEEL midpoint + repro of the
unexplained +33 c E4 (research 04).

Job numbers start at 100 — v1 stems (j00-j92) stay unique forever.

Sources outside the repo are pilfered from ~/Dropbox/Samples (Sam's
invitation, 2026-07-20) with trim offsets recorded below; targets are
chroma-informed near-maps (top pitch classes of the clip itself), the
MATERIAL.md philosophy. Everything else — normalization, padding,
grid-leads-audio, stem grammar — is v1 machinery, imported.

Run:  nix develop --command python3 tools/make_ab_pack_p2.py
"""

import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from make_ab_pack import (  # noqa: E402
    GRID_AT, LEAD, SR, TAIL, bake, hold, knobs, load_mono48, place,
    read_events, write_midi,
)

PROBES = ROOT / "testdata" / "probes"
PACK = ROOT / "testdata" / "reference-p2"
ZIP = ROOT / "out" / "opq-pm-refpack-p2.zip"
DBX = Path.home() / "Dropbox" / "Samples"

# slug -> (source path, trim (start_s, dur_s) or None, forced chord or None)
PILFER = {
    "catsum_leadvoc": (DBX / "Stems/catsum/catsum lead voc 4.wav", None, None),
    "catsum_hat": (DBX / "Stems/catsum/catsum Hat.wav", None, "C3,E3,G3"),
    "murky_sustain": (DBX / "Sound Design/murky sustain.wav", None, None),
    "aphex_loop": (DBX / "Drums/100/ANGELO_MIDES_DRUMLOOP_APHEX_90.wav",
                   None, "C3,E3,G3"),
    "amen02_165": (ROOT / "testdata/material/amen02_165.wav", None, "C3,E3,G3"),
}
MAX_DUR = 10.0

NAMES = "C C# D D# E F F# G G# A A# B".split()


def best_window(x, dur=MAX_DUR):
    """Deterministic trim: the max-energy dur-long window, 1 s hop."""
    n = int(dur * SR)
    if len(x) <= n:
        return 0.0, x
    hops = range(0, len(x) - n, SR)
    e = [float(np.sum(x[i:i + n] ** 2)) for i in hops]
    i0 = list(hops)[int(np.argmax(e))]
    return i0 / SR, x[i0:i0 + n]


def chroma_chord(x):
    """Top-3 pitch classes of the clip -> held near-map chord; octave by
    spectral centroid; drums fall back to C3,E3,G3 upstream."""
    S = np.abs(np.fft.rfft(x * np.hanning(len(x)), 1 << 19)) ** 2
    f = np.fft.rfftfreq(1 << 19, 1 / SR)
    m = (f > 80) & (f < 2500)
    pc = np.zeros(12)
    midi = 69 + 12 * np.log2(f[m] / 440.0)
    np.add.at(pc, np.round(midi).astype(int) % 12, S[m])
    top = []
    for cand in np.argsort(pc)[::-1]:  # greedy, no adjacent semitones
        if all(min((cand - t) % 12, (t - cand) % 12) >= 2 for t in top):
            top.append(int(cand))
        if len(top) == 3:
            break
    top = sorted(top)
    centroid = float((f[m] * S[m]).sum() / S[m].sum())
    octv = 3 if centroid < 300 else 4
    return ",".join(f"{NAMES[p]}{octv}" for p in top)


def build_jobs_p2():
    jobs, n = [], [100]

    def add(src, mode="repeat", rnd="near", flag=None, tier="A", note="", **kw):
        jobs.append(dict(num=n[0], src=src, mode=mode, rnd=rnd, flag=flag,
                         tier=tier, note=note, knobs=knobs(**kw)))
        n[0] += 1

    # the point: PURIFY 5-point sweep on purify-forward material
    for slug in PILFER:
        for pu in (0, 25, 50, 75, 100):
            add(slug, rnd="intel", pu=pu,
                note="PURIFY sweep" + (" (v1 re-run)" if slug == "amen02_165" else ""))
    # noise re-test: the pair that came back bit-identical in v1
    add("01_noise_vs_Cmaj", pu=0, note="v1 purify re-test")
    add("01_noise_vs_Cmaj", pu=100, note="v1 purify re-test")
    # THRESHOLD curve on the detuned triad (+35/-40/+20 c)
    for th in (10, 25, 35, 50, 75):
        add("03_detuned_triad_vs_Cmaj", th=th, tier="B", note="THRESHOLD curve")
    # FEEL midpoint + exact repro of v1 j18 (the +33 c E4)
    add("03_detuned_triad_vs_Cmaj", fe=50, tier="B", note="FEEL midpoint")
    add("03_detuned_triad_vs_Cmaj", fe=100, tier="B",
        note="repro of v1 j18 — is the +33 c E4 stable across sessions?")
    return jobs


def stem_p2(j):
    k = j["knobs"]
    return (f"j{j['num']}__{j['src']}__{j['mode']}-{j['rnd']}"
            f"__th{k['th']}_fe{k['fe']}_gl{k['gl']}_pu{k['pu']}_el{k['el']}")


OPERATOR_DELTA = """\
# Pack v2 — PURIFY batch: READ BEFORE RENDERING

Protocol is pack v1's (_OPERATOR-V1.md, included) with TWO NEW MANDATORY
STEPS. v1's purify rows came back with PURIFY never actually moved — the
script set an inert parameter index and read the same wrong index back.

## Step 0 — parameter census (goes in the return)

Dump PITCHMAP's COMPLETE VST3 parameter table to `params.txt`: for every
parameter — index, id, name, and the DISPLAYED value string at
normalized 0.0 / 0.5 / 1.0. This locates PURIFY's true handle and
retro-validates every other knob.

## Step 1 — purify self-test (gate; the batch may not run until it passes)

Render ~3 s of `SELFTEST__catsum_leadvoc` (any pu job's WAV+MID) twice:
once at PURIFY 0.0, once at PURIFY 1.0, via whatever handle Step 0
found. Compare smoothed magnitude spectra. They must DIFFER audibly and
numerically (smoothed-spectrum correlation < 0.999). If they do not:
the param API cannot reach PURIFY — set it by GUI (mouse) per job
instead, and write `purify=GUI` in the log. Do not proceed on a failing
self-test.

## Then

Run the jobs exactly as v1 (one pair = one bounce; the filename is the
settings sheet; renders/<same stem>.wav; fill _RENDER-LOG.md). Purify
sweeps are tier A. If a knob value can't be reached exactly, closest +
log. Zip the folder back including params.txt.
"""


def render_log_p2(jobs, chords):
    lines = ["# Render log — pack v2 (PURIFY batch)", "",
             "- params.txt dumped: `___`  self-test result: `___` (corr: `___`)",
             "- PURIFY set via: `param API / GUI`   PITCHMAP/DAW/date: `___`",
             "",
             "| done | job | tier | input | held chord | knobs delta | notes |",
             "|---|---|---|---|---|---|---|"]
    for j in jobs:
        k = j["knobs"]
        delta = " ".join(f"{a}{k[a]}" for a in ("th", "fe", "gl", "pu", "el")
                         if k[a] != dict(th=0, fe=0, gl=0, pu=50, el=50)[a]) or "base"
        lines.append(f"| [ ] | `j{j['num']}` | {j['tier']} | {j['src']} |"
                     f" {chords.get(j['src'], 'probe mid')} | {delta} | {j['note']} |")
    return "\n".join(lines) + "\n"


def main():
    jobs = build_jobs_p2()
    stems = [stem_p2(j) for j in jobs]
    assert len(set(stems)) == len(stems)

    if PACK.exists():
        shutil.rmtree(PACK)
    (PACK / "jobs").mkdir(parents=True)
    (PACK / "renders").mkdir()

    cache, chords = {}, {}
    for j, s in zip(jobs, stems):
        src = j["src"]
        if src not in cache:
            if src.startswith("0"):  # probe
                audio = load_mono48(PROBES / f"{src}.wav")
                evs = read_events(PROBES / f"{src}.mid")
                dur = len(audio) / SR
            else:
                path, trim, forced = PILFER[src]
                x = load_mono48(path)
                t0, x = best_window(x) if trim is None else (
                    trim[0], x[int(trim[0] * SR):int((trim[0] + trim[1]) * SR)])
                chord = forced or chroma_chord(x)
                chords[src] = chord
                print(f"  {src}: {path.name} @ {t0:.0f}s, chord {chord}")
                from make_ab_pack import note_num
                dur = len(x) / SR
                audio, evs = x, hold([note_num(c) for c in chord.split(",")], 0, dur)
            cache[src] = (bake(audio), place(evs, dur))
        audio, evs = cache[src]
        sf.write(PACK / "jobs" / f"{s}.wav", audio, SR, subtype="PCM_24")
        write_midi(PACK / "jobs" / f"{s}.mid", evs)

    (PACK / "_OPERATOR.md").write_text(OPERATOR_DELTA)
    shutil.copy(ROOT / "testdata" / "REFERENCE-RENDERS.md", PACK / "_OPERATOR-V1.md")
    (PACK / "_RENDER-LOG.md").write_text(render_log_p2(jobs, chords))
    (PACK / "renders" / "README.txt").write_text(
        "v2 bounces land here, same stem as jobs/. params.txt goes in the"
        " folder root.\n")

    ZIP.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(PACK.rglob("*")):
            if p.is_file():
                z.write(p, Path("opq-pm-refpack-p2") / p.relative_to(PACK))
    mb = sum(f.stat().st_size for f in (PACK / "jobs").iterdir()) / 1e6
    print(f"{len(jobs)} job pairs -> {PACK.relative_to(ROOT)} ({mb:.0f} MB);"
          f" zip {ZIP.relative_to(ROOT)} ({ZIP.stat().st_size/1e6:.0f} MB)")


if __name__ == "__main__":
    main()
