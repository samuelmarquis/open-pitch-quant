# Test Material Manifest

User-supplied material in `testdata/material/` (gitignored — local only).
The offline harness normalizes on load: resample → 48 kHz, sum → mono (v0).

| slug | ch | rate | dur | batch targets | origin |
|---|---|---|---|---|---|
| `resoguitar13.wav` | 1 | 96k | 1.1 s | A3,C#4,E4 | Board Warp Project — RESOGUITAR 13 [2021-07-17] |
| `audio178.wav` | 1 | 48k | 4.5 s | D4,F#4,A4 | Board Warp Project — Audio 178 [2022-09-05] |
| `audio116.wav` | 1 | 96k | 1.5 s | C4,E4,G4 | Board Warp Project — Audio 116 [2021-07-20] |
| `amen02_165.wav` | 2 | 44.1k | 2.9 s | C3,E3,G3 | rhythm-lab.com amen vol.1 — cw_amen02_165 (breakbeat, 165 BPM) |
| `memories.wav` | 2 | 44.1k | 5.1 s | A#3,D4,F#4 | Samuel Marquis — CIRCLES, c2_lust |
| `when.wav` | 2 | 44.1k | 5.7 s | D4,F#4,A#4 | Samuel Marquis — CIRCLES, c9_treachery |
| `falter.wav` | 2 | 44.1k | 1.6 s | A2,C3,E3 | Samuel Marquis — CIRCLES, c4_greed |
| `prism_scrambler_10s.wav` | 2 | 48k | 10 s | F#2,C#3,G#3 | Sound Design — prism scrambler (first 10 s of long original) |
| `phylovox.wav` + `.mid` | 2 | 44.1k | 22.5 s | paired MIDI (moving dyads/triads, F4–D#6, ~30 s) | user-supplied reference pair — material the user knows intimately; includes zero-held-notes gaps |

Batch targets are chroma-informed near-maps (retune material toward its own
tonal center — the fair quality test). Notably: both CIRCLES clips live on a
D–F#–A# AUGMENTED triad. Targets live in `tools/render_batch.py` (SOURCES);
override per experiment as needed.

For PITCHMAP ground-truth renders, `tools/make_ab_pack.py` turns each clip
into 48 kHz/mono job pairs with the batch-target chord baked as a real `.mid`
(phylovox keeps its own MIDI, stretch pre-applied) — see
`testdata/REFERENCE-RENDERS.md`.

Restore/refresh: original paths live in the user's Dropbox; the copy commands
are in the git history (or ask the user). The amen break is the designated
transient/residual torture test; the CIRCLES clips and Board Warp material are
the "real music" core; prism scrambler is the sound-design wildcard.
