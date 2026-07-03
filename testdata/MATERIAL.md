# Test Material Manifest

User-supplied material in `testdata/material/` (gitignored — local only).
The offline harness normalizes on load: resample → 48 kHz, sum → mono (v0).

| slug | ch | rate | dur | origin |
|---|---|---|---|---|
| `resoguitar13.wav` | 1 | 96k | 1.1 s | Board Warp Project — RESOGUITAR 13 [2021-07-17] |
| `audio178.wav` | 1 | 48k | 4.5 s | Board Warp Project — Audio 178 [2022-09-05] |
| `audio116.wav` | 1 | 96k | 1.5 s | Board Warp Project — Audio 116 [2021-07-20] |
| `amen02_165.wav` | 2 | 44.1k | 2.9 s | rhythm-lab.com amen vol.1 — cw_amen02_165 (breakbeat, 165 BPM) |
| `memories.wav` | 2 | 44.1k | 5.1 s | Samuel Marquis — CIRCLES, c2_lust |
| `when.wav` | 2 | 44.1k | 5.7 s | Samuel Marquis — CIRCLES, c9_treachery |
| `falter.wav` | 2 | 44.1k | 1.6 s | Samuel Marquis — CIRCLES, c4_greed |
| `prism_scrambler_10s.wav` | 2 | 48k | 10 s | Sound Design — prism scrambler (first 10 s of long original) |

Restore/refresh: original paths live in the user's Dropbox; the copy commands
are in the git history (or ask the user). The amen break is the designated
transient/residual torture test; the CIRCLES clips and Board Warp material are
the "real music" core; prism scrambler is the sound-design wildcard.
