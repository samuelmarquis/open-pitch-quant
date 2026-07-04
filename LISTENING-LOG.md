# Listening Log

Human verdicts on rendered experiments. The oracle is the user's ear +
mental model of PITCHMAP (no license available). Each batch: what was
rendered, what question each file answers, then the verdict — recorded
verbatim-ish, because taste is data.

---

## Batch 001 — M0 "everything is a nail" (2026-07-03)

Engine: M0 — per-peak nearest-target snapping, no grouping, no residual
layer, no transient handling, no glide. Full wet. `out/listen-001/`.
Dry counterparts live in `testdata/probes/` and `testdata/material/`.

| file | dry source | targets | the question |
|---|---|---|---|
| `01_noise__m0.wav` | pink noise | C-E-G (pc) | Does tonalized noise have the PITCHMAP "breath chord" character, or a different (phasier/ringier?) quality? |
| `03_detuned_triad__m0.wav` | detuned saws | C-E-G (pc) | Fundamentals measure 0.0¢ (verified). By ear: does it read as a *retuned instrument* or a *spectral kaleidoscope*? Upper harmonics snap independently (e.g. 7th harmonic of C jumps ~2 semitones) — audible? bothersome? PITCHMAP-like? |
| `05_chordchange__m0.wav` | in-tune C-maj saws | C-E-G → A-C-E @5s | M0 has no glide/smoothing: how bad is the hard switch vs PITCHMAP's transition feel? |
| `amen_vs_Cmaj__m0.wav` | amen break | C-E-G (pc) | No residual layer: the whole kit gets tonalized. Does it resemble PITCHMAP-on-drums at aggressive settings, or is the flavor wrong? |
| `prism_vs_Csus__m0.wav` | prism scrambler | C-G-D (pc) | Free play: anything musically promising in the wreckage? |

**Specific asks:** (1) rank overall "PITCHMAP-ness" of 01 and amen;
(2) for 03, kaleidoscope-vs-retuned verdict; (3) note any artifact that
feels *categorically* un-PITCHMAP (metallic ringing, pre-echo, warble) —
those point at what M1/M2 must fix first.

**Verdict (2026-07-03):** "High-end is WAY too sharp, and transients are
totally lost."

**Interpretation:** both point at missing M2 machinery, not M1 — (a) HF
content (noise, partials above any plausible fundamental) is being snapped
into sine clusters instead of passing as residual; (b) phase-integration
resynthesis smears onsets and never re-anchors. Action: pull M2-lite forward
— mapping-frequency ceiling + transient detect/bypass with phase re-anchor —
before touching grouping. Also: add resoguitar13 + audio178 (vocal) to the
render set (user request).

---

## Batch 002 — M0.5: mapping ceiling + transient bypass (2026-07-03)

Engine changes vs batch 001: `--fmax-map 5000` (peaks above 5 kHz pass
unmapped) and `--transient-bypass` (spectral-flux onsets pass through dry
and re-anchor synthesis phases; threshold 0.6, calibrated on this material).
Regression: probe 03 still lands at 0.0¢ with fixes on. `out/listen-002/`.

New sources per user request. Targets from quick chroma analysis:
resoguitar13 → A-C#-E (it lives in A-major territory), audio178 → D-F#-A.

| file | vs | the question |
|---|---|---|
| `resoguitar__m0.wav` / `__m0fix.wav` | each other | A/B the two complaints directly on new material: does the high end calm down? does the pluck survive? |
| `audio178__m0.wav` / `__m0fix.wav` | each other | same, on a vocal: consonants/breath vs the 5 kHz ceiling and onset bypass |
| `amen_vs_Cmaj__m0fix.wav` | batch 001 `amen_vs_Cmaj__m0.wav` | does the kit punch again? is the tonal wash now confined to the sustains? |
| `01_noise__m0fix.wav` | batch 001 `01_noise__m0.wav` | tonalized noise with the top octaves left alone — closer to the PITCHMAP "breath chord"? |

**Specific asks:** (1) is 5 kHz the right ceiling by ear (too high/low)?
(2) does transient bypass *flicker* (dry/wet toggling audible as texture)?
(3) with these two fixes, what is now the WORST remaining artifact?

**Verdict (2026-07-03):** "The amen sounds really good." Vocals: "the __fix
variants decidedly sound better, BUT we're totally without the fundamental
frequency in both variants. There's something going on in the high end that
I like, but the lower half of the spectrum feels quite empty."

**Interpretation:** missing-fundamental-on-steady-tones is the signature of
OLA phase cancellation: free-running per-bin synthesis phases go incoherent
within a partial's lobe; a steady fundamental sits on the same bins every
frame → constant destructive interference; wobblier high harmonics escape as
shimmer (which may BE the liked high-end quality — if phase locking kills it,
promote incoherence to a parameter). Action: Laroche-Dolson rigid intra-region
phase locking. NOTE the liked-high-end comment for the character-knob file.

**Measurements (audio178, fix settings):** lows only ~−2 dB on average — the
fundamental's energy survives but its *tone-ness* doesn't (phase mush), while
2.5–5 kHz piled up +3.5 dB and masked further. Vibrato torture test
(harmonic complex, ±40¢ @ 5.5 Hz → D-F#-A): free phases lose 3.4 dB in the
fundamental band; naive bin-keyed locking mistuned by −10¢ (accumulator
identity broken by dbin toggling); final design — per-TARGET-NOTE phase
accumulators + verbatim passthrough for unmapped regions + π·dbin lobe-parity
correction — restores exact pitch (+0.5¢), recovers the low band (−0.9 dB),
and kills the HF pileup (−1.4 dB).

---

## Batch 003 — phase lock A/B (2026-07-03)

Engine change: `phase_lock` (default ON) — per-target-note phase
accumulators, rigid intra-region phases, verbatim passthrough of unmapped
regions. Legacy free-running path kept as `--no-phase-lock`. Regression:
probe 03 at 0.0¢. `out/listen-003/`.

| file | the question |
|---|---|
| `audio178__m0fixlock.wav` vs `__m0fixfree.wav` | THE test: is the fundamental back? And which *character* wins — lock (solid, quantized) or free (watery, shimmery)? |
| `resoguitar__m0fixlock.wav` | vs batch 002's m0fix: same A/B on dense strings |
| `amen_vs_Cmaj__m0fixlock.wav` | regression BY EAR: batch 002's amen was "really good" — did lock change/break its character? |
| `05_chordchange__m0fixlock.wav` | chord transition with note accumulators (new notes re-anchor at the switch) — smoother or harder? |

**Specific asks:** (1) fundamental restored on the vocal? (2) is the
high-end thing you LIKED still present in lock mode — or was it the free-run
shimmer? (If the latter: we make coherence a knob — "lock amount" is a
per-region blend and cheap to build.) (3) amen: unchanged/better/worse?

**Verdict (2026-07-03):** "Much closer. I'm not attached to the phase
shimmer at all, so this is a really solid improvement. The amen does sound
slightly water-ier than the previous iteration, but I'm not too upset with
the change."

**Interpretation:** phase lock confirmed as default. Amen wateriness is
consistent with noise regions being pinned to persistent note accumulators —
noise becomes slowly-warbling pitched content. Next: tonality-aware phase
strategy (noise regions mapped with fresh per-frame phases) vs gate-bypass
(noise passes dry — probably TOO transparent for the liked amen character)
vs status quo.

---

## Batch 004 — proto-Purify: tonality-aware phase strategy (2026-07-03)

The Purify family is born. Peakiness (region peak/mean) measured: tonal
regions median 4.8 (p10 2.85), noise ~1.55 (p90 ~2.0) → gate 2.5 splits
cleanly. Three noise treatments now exist:
- **no gate** (batch 003 renders): noise pinned to note accumulators → warble
- **gate+fresh**: noise still MAPPED but per-frame phases → tonal, no warble
- **gate+bypass**: noise passes dry → transparent (Purify-low territory)

Regression: probe 03 in tune with gate on. `out/listen-004/`.

| file | compare against | question |
|---|---|---|
| `amen__gate-fresh.wav` | 003 `amen_vs_Cmaj__m0fixlock` | wateriness gone, character kept? |
| `amen__gate-bypass.wav` | both amens | or is dry-noise amen actually better? (002's beloved amen was free-phase — closest heir is `gate-fresh`) |
| `audio178__gate-fresh.wav` | 003 lock render | breath/consonant handling |
| `audio178__gate-bypass.wav` | 003 lock render | vocal with transparent noise = most "natural" variant so far? |

**Specific asks:** (1) pick the amen champion of all four variants so far;
(2) on the vocal, does gate-bypass read as "cleaner PITCHMAP" or "less
PITCHMAP"? (3) any flicker from regions toggling tonal↔noise frame to frame?

**Verdict (2026-07-03):** "Gate-bypass on the amen sounds totally dry. On
the vocal — hard to say exactly, the root note sounds very warbly, like
there's some definite phase interaction going on that I don't love in
gate-fresh; I think it's also there in gate-bypass, but perhaps quieter —
though that's because gate-bypass is just a quieter clip in general."
Direction: move into M1, see if grouping rectifies it.

**Interpretation:** (a) amen p90 peakiness = 2.04 < gate 2.5 → the whole
break classifies as noise → bypass = dry; threshold works as measured, but
for drums the useful Purify range needs a lower/softer gate. (b) Root-note
warble = phase interaction between several independent low-frequency regions
(fundamental lobe + neighbors) snapping separately and beating at the shared
destination — the per-peak assignment's structural weakness. M1 grouping
gives those regions one owner, one shift ratio, one phase story; expected to
fix. (c) Gate-bypass clip quieter overall — energy accounting between paths
needs an eye (dry-passthrough vs mapped-region loudness).

---

## Batch 005 — M1: harmonic grouping / objects are born (2026-07-03)

Engine: `--assign group` — greedy Klapuri-style multi-F0 (semitone salience
grid, claim-and-cancel, ≤ `--voices` objects/frame, ≥3 harmonic hits,
robust weighted-median f0 refinement, burn-only-inliers). Each object's
harmonics move together by the FUNDAMENTAL's snap ratio. Unowned peaks:
`--unowned map` (M0 treatment) or `dry` (residual layer). Verified: triad
fundamentals 0.0¢; harmonic coherence fingerprint measured (C's h5 lands at
5×f0, −11¢ off-grid; E's h4 at 4×f0, 0¢ — partials follow their OWNERS now).
`out/listen-005/`.

| file | the question |
|---|---|
| `audio178__group-dry.wav` | THE root-warble test: one owner for the low end — is the phase interaction gone? Residual (breath) stays dry. |
| `audio178__group-map.wav` | same grouping, unowned content mapped (gate 2.5 fresh) — the "PITCHMAP mode" |
| `amen__group-dry.wav` / `__group-map.wav` | drums as objects: kick/tom fundamentals grouped & moved coherently; does map keep the beloved 002 character, does dry sound like PITCHMAP's "leaves drums virtually untouched"? |
| `resoguitar__group-dry.wav` | dense tonal strings: coherent retune vs 003's per-peak kaleidoscope |
| `05_chordchange__group-dry.wav` | transitions with objects: does the switch bloom or lurch now? |

**Specific asks:** (1) vocal root warble — fixed / better / same? (2) which
unowned policy per material (dry for vocals, map for drums?); (3) does group
mode LOSE any of the kaleidoscope magic you liked — should `assign` itself
eventually be a blend knob rather than a switch?

**Verdict:** *(superseded by batch 006 — same engine, full material suite)*

---

## Batch 006 — full suite through M1 (2026-07-03)

Per user request the whole material suite renders every batch from now on:
`tools/render_batch.py <batch>` → 8 sources × variants {group-dry,
group-map}. New sources join with chroma-informed targets: audio116 →
C-E-G; memories & when → their native D-F#-A# AUGMENTED triad; falter →
A-C-E over its big A2 bass; prism → F#2-C#3-G#3. `out/listen-006/`.

Batch 005's asks carry over (root warble; dry-vs-map per material;
does grouping lose kaleidoscope magic), plus:

**New asks:** (4) first impressions on the four never-heard sources —
which material does the engine flatter, which does it embarrass?
(5) the CIRCLES clips retuned toward their own augmented triad — does
near-mapping read as "tightened" or does even this small map feel processed?

**Addendum (same day):** user supplied `phylovox.{wav,mid}` — first paired
time-varying MIDI sidechain test, material they know intimately. Rendered
into this batch as `phylovox__{group-dry, group-map, group-dry-custom}`.
Extra asks: (6) repeat (pitch-class) vs custom (exact-octave) — which
matches the intent of this part? (7) chord-transition feel through the
voice-leading moves (no glide/tracks yet — M3 will own this).

**Fix (same day):** first phylovox renders were misaligned — MIDI span
29.99 s vs audio 22.50 s = exactly 4:3, a 120-vs-160 BPM export mismatch.
MIDI time now scaled by 0.75 (squeeze-to-fit; `midi_breakpoints(stretch=)`).
Also: user confirmed PITCHMAP outputs SILENCE with no held MIDI notes —
engine semantics changed from dry-passthrough to silence (docs updated;
former ask (8) resolved). Phylovox re-rendered with both changes.

**Verdict:** *(pending)*
