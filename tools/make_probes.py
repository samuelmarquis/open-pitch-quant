#!/usr/bin/env python3
"""Generate the probe suite: synthetic test signals + MIDI target-note files.

Each probe is a (WAV, MID) pair engineered to answer ONE question about a
pitch-mapping engine — ours as we build it, and Zynaptiq PITCHMAP as the
reference oracle (render the WAV through PITCHMAP with the MID feeding its
MIDI sidechain; drop results in testdata/reference/).

See testdata/probes/README.md for the per-probe questions and the suggested
reference render matrix.

Run:  nix develop --command python3 tools/make_probes.py
"""

from pathlib import Path

import mido
import numpy as np
import scipy.signal
import soundfile as sf

SR = 48000
PEAK = 0.5  # ~ -6 dBFS
OUT = Path(__file__).resolve().parent.parent / "testdata" / "probes"

rng = np.random.default_rng(20260703)  # deterministic corpus


# ---------------------------------------------------------------- utilities

def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def norm(x, peak=PEAK):
    return x * (peak / max(1e-9, np.max(np.abs(x))))


def fade(x, ms=20):
    n = int(ms / 1000 * SR)
    x = x.copy()
    x[:n] *= np.linspace(0, 1, n)
    x[-n:] *= np.linspace(1, 0, n)
    return x


def sine(freq, dur):
    return np.sin(2 * np.pi * freq * t_axis(dur))


def saw_additive(freq, dur, nharm=None, rolloff=1.0):
    """Additive sawtooth: exact, alias-free, harmonics 1/k^rolloff."""
    t = t_axis(dur)
    n = nharm or int((SR / 2 * 0.9) / freq)
    x = np.zeros_like(t)
    for k in range(1, n + 1):
        x += np.sin(2 * np.pi * freq * k * t) / (k ** rolloff)
    return x


def pink_noise(dur):
    """White noise through the standard pink IIR approximation."""
    white = rng.standard_normal(int(dur * SR))
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1, -2.494956002, 2.017265875, -0.522189400]
    return scipy.signal.lfilter(b, a, white)


def cents(freq, c):
    return freq * 2 ** (c / 1200)


NOTE_FREQ = lambda m: 440.0 * 2 ** ((m - 69) / 12)  # noqa: E731

# MIDI note numbers for readability
C3, Fs3, A3, C4, Cs4, E4, G4, A4 = 48, 54, 57, 60, 61, 64, 67, 69
E3, G3, A2 = 52, 55, 45


def write_midi(path, events):
    """events: list of (time_seconds, 'on'|'off', midi_note)."""
    tpb, tempo = 480, 500000  # 120 bpm
    mid = mido.MidiFile(ticks_per_beat=tpb)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

    def s2t(sec):
        return round(sec * tpb * 1_000_000 / tempo)

    last = 0
    # at equal times, note_offs before note_ons
    for t, kind, note in sorted(events, key=lambda e: (e[0], e[1] == "on")):
        tick = s2t(t)
        tr.append(
            mido.Message(
                "note_on" if kind == "on" else "note_off",
                note=note,
                velocity=100 if kind == "on" else 0,
                time=tick - last,
            )
        )
        last = tick
    tr.append(mido.MetaMessage("end_of_track", time=0))
    mid.save(path)


def hold(notes, start, end):
    return [(start, "on", n) for n in notes] + [(end, "off", n) for n in notes]


def emit(name, audio, midi_events, dur):
    wav = OUT / f"{name}.wav"
    mid = OUT / f"{name}.mid"
    sf.write(wav, fade(norm(audio)), SR, subtype="PCM_24")
    write_midi(mid, midi_events)
    print(f"  {name}: {dur:.0f}s")


# ------------------------------------------------------------------- probes

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"writing probes to {OUT}")

    # 01 — pure pink noise vs C major triad.
    # THE architecture discriminator: a channelized engine will make the noise
    # audibly pitched (a C-major "breath chord"); a note-object engine would
    # pass it through (or gate it).
    dur = 6
    emit("01_noise_vs_Cmaj", pink_noise(dur), hold([C4, E4, G4], 0, dur), dur)

    # 02 — log sine sweep 110→1760 Hz vs a single held A3 (220 Hz).
    # Attraction-basin probe: does 110 Hz get pulled UP an octave to 220, or
    # does pitch-class matching leave it at 110? Where are the snap
    # boundaries? Is there hysteresis / glide ("Feel")?
    dur = 10
    sweep = scipy.signal.chirp(
        t_axis(dur), f0=110, f1=1760, t1=dur, method="logarithmic"
    )
    emit("02_sweep_vs_A3", sweep, hold([A3], 0, dur), dur)

    # 03 — detuned saw triad vs in-tune C major targets.
    # Clean-retune probe: C4+35c, E4-40c, G4+20c must land in tune. Also the
    # "Glue" discriminator: do a note's harmonics move WITH its fundamental
    # (coherent shift) or does each harmonic get snapped independently?
    dur = 8
    tri = (
        saw_additive(cents(NOTE_FREQ(C4), +35), dur)
        + saw_additive(cents(NOTE_FREQ(E4), -40), dur)
        + saw_additive(cents(NOTE_FREQ(G4), +20), dur)
    )
    emit("03_detuned_triad_vs_Cmaj", tri, hold([C4, E4, G4], 0, dur), dur)

    # 04 — two sines crossing (220→440 up, 440→220 down) vs {C4, G4}.
    # Voice-assignment probe: at the crossing (~311 Hz) do the mapped outputs
    # swap targets, hold, or glitch?
    dur = 8
    up = scipy.signal.chirp(t_axis(dur), 220, dur, 440, method="logarithmic")
    down = scipy.signal.chirp(t_axis(dur), 440, dur, 220, method="logarithmic")
    emit("04_crossing_gliss_vs_C4G4", up + down, hold([C4, G4], 0, dur), dur)

    # 05 — sustained in-tune C major saw triad, MIDI changes under it.
    # Chord-change probe: targets C-E-G for 5 s, then A3-C4-E4 (A minor).
    # Does the transition bloom, lurch, or click? Is there portamento?
    dur = 10
    tri = sum(saw_additive(NOTE_FREQ(n), dur) for n in [C4, E4, G4])
    emit(
        "05_sustain_vs_chordchange",
        tri,
        hold([C4, E4, G4], 0, 5) + hold([A3, C4, E4], 5, dur),
        dur,
    )

    # 06 — clicks + noise bursts vs C major triad.
    # Transient probe: pre-echo, smearing, and what a mapper does to
    # percussive/unpitched events. Clicks every 0.5 s, snare-ish bursts at
    # 1 s intervals.
    dur = 6
    x = np.zeros(int(dur * SR))
    for sec in np.arange(0.25, dur, 0.5):
        x[int(sec * SR)] = 1.0  # unit click
    x = scipy.signal.lfilter(*scipy.signal.butter(2, 8000 / (SR / 2)), x) * 4
    burst_len = int(0.08 * SR)
    env = np.exp(-np.linspace(0, 6, burst_len))
    for sec in np.arange(0.5, dur, 1.0):
        i = int(sec * SR)
        x[i : i + burst_len] += pink_noise(0.08)[:burst_len] * env * 0.7
    emit("06_transients_vs_Cmaj", x, hold([C4, E4, G4], 0, dur), dur)

    # 07 — saw C3 mapped a tritone away to F#3.
    # Large-interval probe: timbre/formant damage on a worst-case (tritone)
    # remap of a harmonically dense tone.
    dur = 8
    emit(
        "07_tritone_C3_to_Fs3",
        saw_additive(NOTE_FREQ(C3), dur),
        hold([Fs3], 0, dur),
        dur,
    )

    # 08 — crude synthetic "vocal": saw at 150 Hz (≈D3) through vowel formant
    # filters (a-e-i-o-u, 1.2 s each), noise bursts between vowels as
    # consonant stand-ins. Target E3: small upward correction.
    # Purify probe: what happens to the unpitched consonant bursts?
    formants = {  # (F1, F2, F3)
        "a": (800, 1150, 2900),
        "e": (400, 1600, 2700),
        "i": (250, 1750, 3600),
        "o": (400, 800, 2600),
        "u": (350, 600, 2700),
    }
    seg_d, gap_d = 1.2, 0.15
    pieces = []
    for v, (f1, f2, f3) in formants.items():
        src = saw_additive(150.0, seg_d, rolloff=0.7)
        y = np.zeros_like(src)
        for fc, gain in [(f1, 1.0), (f2, 0.63), (f3, 0.35)]:
            lo = fc * 0.85 / (SR / 2)
            hi = min(fc * 1.15 / (SR / 2), 0.99)
            b, a = scipy.signal.butter(2, [lo, hi], btype="band")
            y += scipy.signal.lfilter(b, a, src) * gain
        pieces.append(fade(norm(y, 1.0), ms=30))
        pieces.append(fade(pink_noise(gap_d) * 0.4, ms=10))
    voc = np.concatenate(pieces)
    dur = len(voc) / SR
    emit("08_vowels_vs_E3", voc, hold([E3], 0, dur), dur)

    # 09 — inharmonic "bar/bell" tone (clamped-bar partial ratios) vs C major.
    # Inharmonicity probe: partials that fit NO harmonic comb — does the
    # engine snap each partial separately (kaleidoscope) or find a compromise?
    dur = 8
    f0 = NOTE_FREQ(C4)
    x = np.zeros(int(dur * SR))
    strike_t = np.arange(0.5, dur - 1.5, 2.0)
    ratios = [1.0, 2.76, 5.40, 8.93]
    amps = [1.0, 0.6, 0.35, 0.2]
    decays = [1.2, 2.0, 3.2, 4.5]  # 1/e seconds, brighter dies faster
    for st in strike_t:
        i = int(st * SR)
        seg_t = t_axis(dur - st)
        seg = np.zeros_like(seg_t)
        for r, a, d in zip(ratios, amps, decays):
            if f0 * r < SR / 2:
                seg += a * np.exp(-seg_t * d) * np.sin(2 * np.pi * f0 * r * seg_t)
        x[i:] += seg
    emit("09_bell_vs_Cmaj", x, hold([C4, E4, G4], 0, dur), dur)

    print("done.")


if __name__ == "__main__":
    main()
