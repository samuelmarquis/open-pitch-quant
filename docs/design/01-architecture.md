# Design 01 — Reference Model & v0 Architecture

*2026-07-03. Synthesizes research reports 01–03 (docs/research/). Status:
proposed, pre-implementation.*

## 1. The reference model (what the evidence says PITCHMAP is)

**Pitch-object de-mixing on a chromatic grid.** Not Melodyne-style
note/instrument separation, not naive per-bin snapping — the middle path:

```
audio → [1] TF analysis → [2] tonal/transient/noise split
      → [3] group partials into ≤N pitch objects (fundamental on chromatic grid;
             same-pitch sources FUSE; leftovers → residual layer)
      → [4] per-object mapping: ratio = target(F0)/F0, from map/MIDI
             (+ Threshold / Feel / Glide trajectory shaping)
      → [5] per-object spectral shift, re-place partials
      → Σ objects + transients + residual → OLA → audio
```

Key numbers: 1024-sample internal frames, 4096 samples total latency
(~85–93 ms), native 44.1/48 kHz, 127 source-pitch slots, targets −12…+23 st.

Knob decoder ring (all documented, see report 03): **Electrify** = tracked
object count N, *inverted* (100% ⇒ N=1) · **Purify** = tonal/residual output
balance · **Feel** = re-inject measured micro-pitch deviation post-map ·
**Glide** = per-onset source→target ramp time · **Threshold** = bypass
near-in-tune objects · **Strict** = pitch-track smoothing vs transients ·
**Algorithm** = voice-model off/partial/on.

The characteristic *sound* comes from the failure modes: noise forced into
pitch slots (tonalization), harmonics claimed as ghost objects, same-pitch
fusion, hiss excited into empty MIDI slots. **We are reimplementing the
failure modes as much as the successes.**

## 2. Our v0 engine (offline prototype, Python)

Mono, offline, 48 kHz. WAV in + MIDI in → WAV out, plus debug plots/layers.

- **Front end**: STFT, 4096-sample window (~85 ms, matches PITCHMAP's latency
  budget; ~11.7 Hz raw resolution), hop 1024 (75% overlap), Hann. Per-bin
  instantaneous frequency via frame-to-frame phase difference (Bernsee).
  The CFPC-style super-resolution front end (EP3271736A1) is deliberately
  deferred — see PATHS-NOT-TAKEN 002.
- **Peak/partial detection**: spectral peaks + region-of-influence
  partitioning (Laroche & Dolson 1999).
- **Tonality classification**: per-bin sinusoidality from phase-deviation
  consistency → tonal vs residual masks. Residual passes through unmapped
  (delay-compensated). Purify = output balance between the two.
- **Grouping (the heart)**: harmonic-summation salience over a semitone grid
  → pick top-N slots (N = Electrify⁻¹) → each peak assigned to the slot that
  best explains it (as harmonic k of F0), unclaimed peaks → residual or
  self-owned (parameter). Guitar-beating and ghost-copy artifacts should
  *emerge* here if we've done it faithfully.
- **Mapping**: per-object ratio from the target set. v0 modes: Repeat
  (pitch-class attraction, all octaves) and Custom (exact note); rounding
  Nearest first, then Up/Down/Intelligent (hysteresis). Zero-held-notes →
  SILENCE (PITCHMAP behavior, user-confirmed 2026-07-03 — resolves what
  the manual leaves undocumented).
- **Resynthesis**: per-peak region translation by its object's ratio, rigid
  phase locking within regions, phase re-integration across frames, ISTFT/OLA.
- **Trajectory shaping**: Feel/Glide/Threshold operate on per-object F0
  tracks over time — straightforward once tracks exist.

### Milestones
- **M0 — "everything is a nail"**: no grouping; every peak snaps independently
  to the nearest allowed pitch (pitch-class mode). ~200 lines. Purpose: end-to-
  end plumbing, first sound, lower bound on quality, and a test of how much of
  the PITCHMAP sound is *just this*.
- **M1 — grouping**: salience + top-N objects + per-object ratios. Electrify
  born. A/B against M0 on probes 03/09.
- **M2 — layers**: tonal/residual split (Purify born), transient
  detect & bypass (probe 06).
- **M3 — time**: object tracks across frames; Feel, Glide, Threshold born;
  chord-change smoothing (probe 05).
- **M4 — MIDI semantics**: full mido sidechain parsing, Repeat/Custom,
  rounding modes incl. Intelligent.
- **M5+ — the port**: Rust, nih-plug, CLAP-first (report 01 §5). Not before
  the sound is right.

### Evaluation
- Probe suite (testdata/probes/) + spectrogram diffs as pre-filter.
- Human listening (the user) as the judge — batches of 3–5 variants, specific
  questions, verdicts logged in LISTENING-LOG.md.
- PITCHMAP oracle: direct reference renders are unavailable (iLok
  authorization failed, 2026-07-03). The working oracle is the user's
  mental model — they use PITCHMAP heavily and judge by ear whether our
  failure signatures match. If licensing ever cooperates, render the probe
  suite per testdata/probes/README.md into testdata/reference/.

## 3. Deliberate divergences from the reference (v0)

- Offline-first; latency unconstrained until M5.
- No voice model (Algorithm=Linear only) — defer.
- No GUI, no sliders-per-key: MIDI sidechain is the only map source (per
  project goal); scale macros trivial to add later.
- Extras PITCHMAP lacks, cheap for us, worth exposing early: dry/wet mix,
  per-key detune (microtonal targets!), MPE/pitch-bend target detuning,
  velocity → attraction strength. Log in FUTURE-KNOBS when they occur to us;
  build after M4.

## 4. Licensing & provenance

Clean-room from public documentation and papers: Laroche & Dolson (patent
expired), Bernsee tutorial (WOL), Klapuri salience (paper). No Zynaptiq code,
no decompilation. Oracle renders used for behavioral comparison only, kept
out of the repo. License: TBD (lean permissive; MIT).
