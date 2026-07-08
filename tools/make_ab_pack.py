#!/usr/bin/env python3
"""Build the PITCHMAP reference render pack: testdata/reference/.

Consolidates every probe and every material clip into jobs/ as matched
(WAV, MID) pairs whose shared filename fully documents the PITCHMAP
settings that render should be made with — the filename is the database,
there is nothing to cross-reference. One pair = one bounce. Operator
protocol (settings legend, DAW recipe): testdata/REFERENCE-RENDERS.md,
copied into the pack as _OPERATOR.md so the pack travels self-contained.

Every job WAV is normalized to 48 kHz / mono / 24-bit with 250 ms of
silence baked at both ends, and every job MID raises the target grid at
t=50 ms — before the audio starts — so no DAW-side race decides what the
tracker saw first. These job files are ALSO the canonical inputs for our
own engine's side of each A/B pair: same bytes into both machines.

Run:  nix develop --command python3 tools/make_ab_pack.py
"""

import shutil
import sys
import zipfile
from math import gcd
from pathlib import Path

import mido
import numpy as np
import scipy.signal
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from render_batch import SOURCES  # noqa: E402  — material targets, one source of truth

PROBES = ROOT / "testdata" / "probes"
PACK = ROOT / "testdata" / "reference"
CARD = ROOT / "testdata" / "REFERENCE-RENDERS.md"
ZIP = ROOT / "out" / "opq-pm-refpack.zip"

SR = 48000
LEAD = 0.25   # baked silence before the material
TAIL = 0.25   # baked silence after it (glide ramps / ring-out live here)
GRID_AT = 0.05  # note-ons that opened the original pair land here: grid leads audio

# ------------------------------------------------------------------ notes/midi

PC = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
      "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def note_num(name):
    name = name.strip()
    return 12 * (int(name[-1]) + 1) + PC[name[:-1]]  # C4 = 60


def read_events(path, stretch=1.0):
    """SMF → [(abs_seconds, 'on'|'off', note, velocity)], tempo map honored."""
    evs, t = [], 0.0
    for msg in mido.MidiFile(str(path)):  # iteration yields .time in seconds
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            evs.append((t * stretch, "on", msg.note, msg.velocity))
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            evs.append((t * stretch, "off", msg.note, 0))
    return evs


def hold(notes, start, end):
    return [(start, "on", n, 100) for n in notes] + [(end, "off", n, 0) for n in notes]


def place(evs, content_dur):
    """Shift events into the padded timeline: +LEAD, except opening note-ons
    (t <= 10 ms), which move to GRID_AT so the map exists before the audio;
    closing note-offs (>= content end) hold through the tail."""
    file_end = LEAD + content_dur + TAIL
    out = []
    for t, kind, note, vel in evs:
        if kind == "on" and t <= 0.010:
            tt = GRID_AT
        elif kind == "off" and t >= content_dur - 0.010:
            tt = file_end - 0.010
        else:
            tt = t + LEAD
        out.append((tt, kind, note, vel))
    return out


def write_midi(path, events):
    """events: [(seconds, 'on'|'off', note, velocity)] at 120 bpm / 480 ppq."""
    tpb, tempo = 480, 500000
    mid = mido.MidiFile(ticks_per_beat=tpb)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    last = 0
    for t, kind, note, vel in sorted(events, key=lambda e: (e[0], e[1] == "on")):
        tick = round(t * tpb * 1_000_000 / tempo)
        tr.append(mido.Message("note_on" if kind == "on" else "note_off",
                               note=note, velocity=vel if kind == "on" else 0,
                               time=tick - last))
        last = tick
    tr.append(mido.MetaMessage("end_of_track", time=0))
    mid.save(str(path))


# ---------------------------------------------------------------------- audio

def load_mono48(path):
    x, sr = sf.read(str(path), dtype="float64", always_2d=True)
    x = x.mean(axis=1)
    if sr != SR:
        g = gcd(SR, sr)
        x = scipy.signal.resample_poly(x, SR // g, sr // g)
    peak = np.max(np.abs(x))
    if peak >= 0.999:  # resampler overshoot on hard transients — don't clip
        x *= 0.999 / peak
        print(f"  {path.name}: peak {peak:.3f} → attenuated to 0.999")
    return x


def bake(x):
    return np.concatenate([np.zeros(int(LEAD * SR)), x, np.zeros(int(TAIL * SR))])


# ----------------------------------------------------------------------- jobs

BASE = dict(th=0, fe=0, gl=0, pu=50, el=50)


def knobs(**kw):
    d = dict(BASE)
    d.update(kw)
    return d


def build_jobs():
    jobs, n = [], [0]

    def add(src, mode="repeat", rnd="near", flag=None, tier="B", note="", **kw):
        jobs.append(dict(num=n[0], src=src, mode=mode, rnd=rnd, flag=flag,
                         tier=tier, note=note, knobs=knobs(**kw)))
        n[0] += 1

    def matrix(src):  # the full knob sweep, for the three architecture probes
        add(src, tier="A", note="baseline")
        add(src, el=0, note="max sounds tracked")
        add(src, el=100, note="one sound tracked (mono!)")
        add(src, pu=0, note="residual/noise fully kept")
        add(src, pu=100, note="residual purged, harmonics recovered")
        add(src, fe=100, note="all intonation detail kept")
        add(src, gl=100, note="max polyphonic portamento")
        add(src, mode="custom", note="exact held notes only, no octave attraction")
        add(src, flag="NONOTES", tier="A",
            note="MIDI MAP on, nothing held — undocumented semantics")

    # control
    add("01_noise_vs_Cmaj", flag="NULL", tier="A",
        note="PITCHMAP bypassed/removed — verifies the render path itself")
    # probes
    matrix("01_noise_vs_Cmaj")                                  # j01..j09
    add("02_sweep_vs_A3", tier="A", note="baseline — attraction basins")
    add("02_sweep_vs_A3", mode="custom", note="below/above the exact A3")
    add("02_sweep_vs_A3", rnd="intel", note="hysteresis fingerprint of Intelligent")
    matrix("03_detuned_triad_vs_Cmaj")                          # j13..j21
    add("03_detuned_triad_vs_Cmaj", th=50,
        note="Threshold sweep midpoint — which detunings get spared")
    add("04_crossing_gliss_vs_C4G4", tier="A", note="baseline — voice crossing")
    matrix("05_sustain_vs_chordchange")                         # j24..j32
    add("05_sustain_vs_chordchange", rnd="intel", tier="A",
        note="Intelligent at the chord change — avoid-jumping in action")
    add("06_transients_vs_Cmaj", tier="A", note="baseline — transient survival")
    add("06_transients_vs_Cmaj", pu=0, note="manual claims <50% preserves transients")
    add("07_tritone_C3_to_Fs3", tier="A", note="baseline — worst-case shift damage")
    add("08_vowels_vs_E3", tier="A", note="baseline — vocal-shaped correction")
    add("08_vowels_vs_E3", fe=100, note="does Feel keep the vowel micro-pitch")
    add("09_bell_vs_Cmaj", tier="A", note="baseline — inharmonic partial fate")

    # material: daily-driver comparison → Intelligent rounding baseline
    for slug in ("resoguitar", "audio178", "audio116", "amen", "memories",
                 "when", "falter", "prism", "phylovox"):
        add(slug, rnd="intel", tier="A", note="material baseline")
    add("amen", rnd="intel", pu=0, note="break with residual fully kept")
    add("amen", rnd="intel", pu=100, note="break purified — what dies")
    add("phylovox", rnd="intel", fe=100, note="vocal feel preservation")
    add("phylovox", rnd="intel", gl=100, note="vocal glide behavior")
    add("phylovox", rnd="intel", mode="custom",
        note="moving parts pinned to exact octaves")

    # extras — render only if energy remains
    n[0] = 90
    add("01_noise_vs_Cmaj", flag="algL", tier="C",
        note="ALGORITHM Linear — voice model off, fingerprint on noise")
    add("phylovox", rnd="intel", flag="algN", tier="C",
        note="ALGORITHM Natural on the vocal")
    add("05_sustain_vs_chordchange", flag="strict", tier="C",
        note="STRICT on at the chord change")
    return jobs


def stem(j):
    if j["flag"] == "NULL":
        return f"j{j['num']:02d}__{src_stem(j['src'])}__NULL-CONTROL__plugin-bypassed"
    k = j["knobs"]
    s = (f"j{j['num']:02d}__{src_stem(j['src'])}__{j['mode']}-{j['rnd']}"
         f"__th{k['th']}_fe{k['fe']}_gl{k['gl']}_pu{k['pu']}_el{k['el']}")
    if j["flag"]:
        s += f"__{j['flag']}"
    return s


def src_stem(src):
    if src in SOURCES and not src.startswith("p0"):
        return SOURCES[src][0].stem  # material slug → real file stem
    return src


# ------------------------------------------------------------------- sources

def load_source(src):
    """→ (baked_audio, placed_events). Probes come from their own committed
    pair; material chords come from render_batch.SOURCES; phylovox's MIDI is
    baked at its 0.75 stretch."""
    if src.startswith("0"):  # probe
        audio = load_mono48(PROBES / f"{src}.wav")
        dur = len(audio) / SR
        evs = read_events(PROBES / f"{src}.mid")
    else:
        path, targets = SOURCES[src]
        audio = load_mono48(path)
        dur = len(audio) / SR
        if isinstance(targets, tuple):  # (midi path, stretch)
            evs = read_events(targets[0], stretch=targets[1])
        else:
            evs = hold([note_num(s) for s in targets.split(",")], 0, dur)
    return bake(audio), place(evs, dur)


# ------------------------------------------------------------------ log/card

KNOB_NAMES = dict(th="THRESHOLD", fe="FEEL", gl="GLIDE", pu="PURIFY", el="ELECTRIFY")
MODE = dict(repeat="Repeat", custom="Custom")
RND = dict(near="Nearest", intel="Intelligent")
FLAGS = dict(NONOTES="hold no notes (MIDI MAP stays ON)",
             NULL="PITCHMAP bypassed", algL="ALGORITHM = Linear",
             algN="ALGORITHM = Natural", strict="STRICT = ON")


def render_log(jobs):
    lines = [
        "# Render log — PITCHMAP reference pack",
        "",
        "Fill in as you go. One row per bounce; the row's settings are also in",
        "the filename — the name wins if they ever disagree.",
        "",
        "- PITCHMAP version: `______`   DAW + version: `______`",
        "- OS: `______`   audio buffer: `______`   date: `______`",
        "- Anything global that was weird: `______`",
        "",
        "| done | job | tier | input | Edit Mode · Xclude Round. |"
        " knobs (slider %) | special | displayed values / notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for j in jobs:
        k = j["knobs"]
        kn = " · ".join(f"{KNOB_NAMES[a]} {k[a]}" for a in ("th", "fe", "gl", "pu", "el"))
        if j["flag"] == "NULL":
            mode_s, kn = "—", "—"
        else:
            mode_s = f"{MODE[j['mode']]} · {RND[j['rnd']]}"
        special = FLAGS.get(j["flag"], "") if j["flag"] else ""
        lines.append(f"| [ ] | `j{j['num']:02d}` | {j['tier']} | {src_stem(j['src'])} |"
                     f" {mode_s} | {kn} | {special} | |")
    lines += [
        "",
        "Tier A = the core (do these first). B = the matrix. C = only if",
        "energy remains. Stop anywhere — every completed pair is useful.",
        "",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------- main

def main():
    jobs = build_jobs()
    stems = [stem(j) for j in jobs]
    assert len(set(stems)) == len(stems), "stem collision"
    for s in stems:
        assert len(s) <= 80 and all(c.isalnum() or c in "_-" for c in s), s

    if PACK.exists():
        shutil.rmtree(PACK)
    (PACK / "jobs").mkdir(parents=True)
    (PACK / "renders").mkdir()

    cache = {}
    total = 0
    for j, s in zip(jobs, stems):
        if j["src"] not in cache:
            cache[j["src"]] = load_source(j["src"])
        audio, evs = cache[j["src"]]
        sf.write(PACK / "jobs" / f"{s}.wav", audio, SR, subtype="PCM_24")
        write_midi(PACK / "jobs" / f"{s}.mid",
                   [] if j["flag"] in ("NONOTES", "NULL") else evs)
        total += len(audio)
    shutil.copy(CARD, PACK / "_OPERATOR.md")
    (PACK / "_RENDER-LOG.md").write_text(render_log(jobs))
    (PACK / "renders" / "README.txt").write_text(
        "PITCHMAP bounces land here: one WAV per job, SAME stem as the pair\n"
        "in jobs/ (48 kHz, 32-bit float preferred, never normalized).\n")

    ZIP.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(PACK.rglob("*")):
            if p.is_file():
                z.write(p, Path("opq-pm-refpack") / p.relative_to(PACK))

    tiers = {t: sum(1 for j in jobs if j["tier"] == t) for t in "ABC"}
    mb = sum(f.stat().st_size for f in (PACK / "jobs").iterdir()) / 1e6
    print(f"{len(jobs)} job pairs → {PACK.relative_to(ROOT)}/jobs "
          f"({mb:.0f} MB audio, {total/SR/60:.1f} min)")
    print(f"tiers: A={tiers['A']} B={tiers['B']} C={tiers['C']}")
    print(f"zip for the PITCHMAP machine: {ZIP.relative_to(ROOT)} "
          f"({ZIP.stat().st_size/1e6:.0f} MB)")


if __name__ == "__main__":
    main()
