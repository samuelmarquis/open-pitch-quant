# Probe Suite

Synthetic (WAV, MID) pairs, each engineered to answer ONE question about a
pitch-mapping engine — ours as it grows, and PITCHMAP as the reference oracle.
Regenerate any time with `nix develop --command python3 tools/make_probes.py`
(deterministic, seeded). 48 kHz / 24-bit / mono, peaks at −6 dBFS.

## The probes and their questions

| probe | signal | MIDI targets | question |
|---|---|---|---|
| `01_noise_vs_Cmaj` | pink noise | C4+E4+G4 held | Does unpitched input become tonal? How much lands in the residual/unmapped layer vs. gets snapped? (Architecture fingerprint; interacts strongly with Purify/Electrify.) |
| `02_sweep_vs_A3` | log sine sweep 110→1760 Hz | A3 held | Attraction basins: does 110 Hz fold up an octave to 220 (Custom mode) or map to the nearest A per pitch-class (Repeat mode)? Snap boundaries, hysteresis, Glide behavior on a moving source. |
| `03_detuned_triad_vs_Cmaj` | saws at C4+35¢, E4−40¢, G4+20¢ | C4+E4+G4 held | Clean-retune correctness (must land in tune) and harmonic coherence: do a note's harmonics move WITH its fundamental, or snap independently? |
| `04_crossing_gliss_vs_C4G4` | sines 220→440 & 440→220 | C4+G4 held | Voice assignment at the crossing (~311 Hz): swap, hold, or glitch? |
| `05_sustain_vs_chordchange` | in-tune C-major saw triad | C-E-G (0–5 s) → A3-C4-E4 (5–10 s) | Chord-change transition under sustained input: bloom, lurch, or click? Portamento? (Xclude rounding modes matter here — Nearest vs Intelligent.) |
| `06_transients_vs_Cmaj` | clicks + noise bursts | C4+E4+G4 held | Transient handling: pre-echo, smearing, does percussive material survive unmapped? |
| `07_tritone_C3_to_Fs3` | saw C3 | F#3 held | Worst-case large remap (tritone): timbre/formant damage as a function of shift distance. |
| `08_vowels_vs_E3` | synthetic vowels (150 Hz ≈ D3) + noise "consonants" | E3 held | Vocal-shaped content: small correction quality; what happens to unpitched consonants (Purify behavior)? |
| `09_bell_vs_Cmaj` | inharmonic bar partials (1, 2.76, 5.40, 8.93 × C4) | C4+E4+G4 held | Inharmonicity: partials fitting no harmonic comb — per-partial snap (kaleidoscope) or compromise? |

Questions the manual already answers (so listen to *confirm*, not discover):
Repeat mode = pitch-class attraction in all octaves; Custom = exact note only;
Electrify = tracked-voice count (max = mono!); residual layer exists; rounding
modes are Up/Down/Nearest/Intelligent. See `docs/research/02-*.md`.

## Rendering the PITCHMAP references

Superseded by the consolidated job pack: `tools/make_ab_pack.py` bakes
these probes **and** the real material into `testdata/reference/jobs/` as
matched (WAV, MID) pairs whose filenames carry the complete PITCHMAP
settings for each bounce — the render matrix above lives in the names now.
Protocol, settings legend, and DAW recipe: `testdata/REFERENCE-RENDERS.md`
(copied into the pack as `_OPERATOR.md`).

Also welcome in `testdata/material/` (gitignored): any real material you want
this thing to eat — vocals first, then everything else.
