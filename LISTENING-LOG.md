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

**Verdict (2026-07-03):** "On monophonic input and sound design (falter,
prism) I REALLY like the timbres we're getting. With the vocals, and really
all of the stuff with a lot of harmonic character, there's a lot of that
washy/warbly phase noise; both map and dry have this (and custom is just
way out of whack). With PITCHMAP, if I hold down one note and sing around
it a little bit, I'll get a relatively constant pitch without too much
phase drift (manifesting like beating and amplitude-noise) in the output;
it's quite noticeable here."

**Interpretation:** the remaining washiness is integer-bin TRANSLATION
artifacts on modulated harmonic content: as the source slides across bins,
dbin toggles, magnitude readings scallop, lobe alignment jumps — all AM at
vibrato/frame rate. The vibrato torture metric agrees (peak-to-skirt only
~14 dB in lock mode). Fix: kernel STAMPING — synthesize each tonal mapped
partial from parameters (de-scalloped amplitude, exact fractional output
frequency, accumulator phase) by writing the analytic Hann-transform kernel
at fractional bin positions. Custom-mode "way out of whack" = expected
consequence of register-specific targets vs out-of-register source content;
revisit after a Round/minimal-shift option exists.

---

## Batch 007 — kernel stamping vs the washiness (2026-07-03)

Engine: `synth="stamp"` — tonal mapped partials rendered as frequency-domain
oscillators (analytic Hann kernel at exact fractional bins, de-scalloped
amplitude, accumulator phase). Vibrato torture: skirt 13.7→45.0 dB, AM depth
8.8→0.6 dB, low band −0.9→−0.0 dB. Regressions: fundamentals 0.0¢,
coherence fingerprint intact. `out/listen-007/`: full suite ×
{group-dry-stamp, group-map-stamp} — A/B directly against the same names
in listen-006.

**Specific asks:** (1) vocals/harmonic material — is the washy beating
gone (the sing-around-a-held-note test)? (2) falter & prism — did the
REALLY-liked timbres survive the synthesis change, or did stamping
over-clean them? (3) if stamping wins overall but loses grit somewhere,
`synth` becomes a per-region blend candidate rather than a switch.

**Verdict (2026-07-03):** "YEAH. YEAH. YEAH YEAH YEAH [...] WE HAVE THE
ALGORITHM. THIS IS IT! (maybe there's some subtle refinement you want to
do, but this is basically there). HIT M3 LET'S SEE IT (but a character
blending knob would still probably be cool)."

*(Batches 008/009 verdicts arrived as gameplay: M3 knobs approved, "sounds
really good", intelligent rounding requested & shipped, then RT port
requested: "definitely ready for RT". RT stereo verdict: "totally
left/right decoherent" → native multichannel engine + coherence knob →
"having a TON of fun, damn close to PITCHMAP".)*

**Interpretation:** kernel stamping + grouping + phase lock + transient
bypass + tonality gate = the core engine, confirmed. Direction: M3 (object
tracks → Feel, Glide) plus a `grit` character-blend knob (stamp purity vs
translation crunch, per partial).

---

## Batch 008 — M3: tracks, Feel, Glide + the grit knob (2026-07-03)

Objects now persist across frames as TRACKS (matched by f0, ±100¢), each
carrying a ~250 ms pitch reference, glide state, and per-harmonic phase
accumulators. Three knobs born:
- **feel** (0..1): re-inject the track's micro-pitch deviation on target.
  Verified dose-response: 0 → 1.4¢ output wobble, 0.6 → 23¢, 1.0 → 44¢
  (input ~40¢).
- **glide** (s): ramp source→target at birth, current→new-target on chord
  change; tracks die on transients so glide re-triggers per hit (manual
  semantics). Verified: probe-05 switch goes instant → smooth ramp.
- **grit** (0..1): character blend, stamp purity → translation crunch.

`out/listen-008/`, full suite × {stamp-feel60, stamp-glide120,
stamp-musical (feel .35 + glide .06), stamp-grit35}. Compare against 007's
group-dry-stamp (= all knobs at 0).

**Specific asks:** (1) feel on vocals/phylovox — does 0.6 read as "alive"
vs 007's quantized? where's your taste point? (2) glide-120 on phylovox's
chord moves — musical or seasick? (3) stamp-musical — is this combined
setting the new daily-driver default? (4) grit-35 on falter/prism — is
this the character axis you wanted? (5) any track-instability artifacts
(pitch reference drifting audibly, glide re-triggering mid-note)?

**Verdict:** approved in gameplay (see batch 007 addendum).

---

## Batch 010 — Rust-canonical: full-comb, Threshold, Formant (2026-07-03)

The Rust engine is now the sole canonical implementation; this batch is
the first rendered through it (`tools/render_batch.py` → `rt` CLI).
Engine additions, all measurement-verified:
- **Full-comb ownership**: objects claim their ENTIRE comb (h to Nyquist,
  competitive assignment across objects — greedy version measurably stole
  G's h20 for C, output at 7772 Hz; fixed → 7840/7849/8110 all correctly
  owned). Upper spectrum no longer stranded in the residual.
- **Threshold** (PITCHMAP knob, non-global flavor): +20¢ saw with
  thresh=30 passes at +20.1¢; with thresh=10 corrects to 0.0¢.
- **Formant Preserve** 0..1: source-envelope resampling at output freq
  (linear-domain blur — log-domain first attempt was valley-dominated and
  inert). Test bump at 900 Hz, pitch +500¢: formant 0 → bump moves
  (−4.6 dB ratio), 0.5 → between (−0.9), 1.0 → bump stays (+2.9).
- Regression: triad fundamentals 0.0¢.

`out/listen-010/`: full suite × {champ, formant60, formant100}.

**Specific asks:** (1) vocals/phylovox with full-comb ownership — did the
top end "come along" now (compare against listen-007/009 of same
sources)? (2) formant60/100 on vocals pitched far — chipmunk gone? what's
the taste point? (3) formant on prism/falter — does envelope-locking
change the sound-design character you liked? (4) plugin reinstalled with
Threshold + Formant Preserve params — try Threshold ~20–30¢ on lightly
detuned material.

**Verdict (partial, 2026-07-03):** "Some choppiness on what I suspect are
the edges of the blocks." → batch 011 built to discriminate.

---

## Batch 011 — block-edge choppiness discrimination (2026-07-03)

User hypothesis: choppiness at block edges. STFT block size made runtime
(`--blocksize`, hop = size/4; groundwork for ledger 006). Four phylovox
renders in `out/listen-011/`:

| file | tests |
|---|---|
| `phylovox__bs2048` | half block (hop 11.6 ms @44.1k) |
| `phylovox__bs4096` | reference (hop 23 ms) |
| `phylovox__bs8192` | double block (hop 46 ms) |
| `phylovox__bs4096-notrans` | normal block, TRANSIENT BYPASS OFF — isolates dry↔mapped frame toggling, the prime suspect for "chopped at block edges" |

**How to read it:** if choppiness period scales with block size → frame-
rate mechanism confirmed; if `notrans` kills it at normal size → it's the
transient detector toggling whole frames between dry and mapped (fix:
crossfaded/per-band transient handling, already on the roadmap); if
neither changes it → look at MIDI-boundary re-anchors instead.

Also: Glide default → 0 s engine-wide and in the plugin (user note;
plugin rebuilt + reinstalled).

**Verdict (2026-07-03):** "Definitely worse with half-block; notrans helps
but I'm not sure it's the full story. Especially noticeable as amplitude
instability where the actual pitch is far from the note we're quantizing
to." Then the golden bug report: "I can point to it precisely — 0:09.750
in phylovox, it's very apparent."

**Interpretation & hunt:** the timestamp + measurement chase found FIVE
distinct mechanisms, all fixed:
1. **Semitone dead zones in the multi-F0 candidate grid** — sources
   sitting ~50¢ off every candidate (vs 45¢ claim tolerance) made object
   formation flicker at ~10 Hz. Measured as ripple bursts every ~1 s of a
   scoop (= each half-semitone crossing). Fix: quarter-tone candidates +
   live-track f0 seeding. Burst windows: −18 dB → −51 dB.
2. **Chirp-inconsistent phase advance** — accumulators advanced at
   endpoint frequency; moving pitch made overlapped windows disagree.
   Fix: trapezoidal (midpoint) integration.
3. **Whole-frame transient swaps** — hard dry↔mapped toggling at hop
   boundaries. Fix: soft blend (flux-proportional), state keeps running;
   hard reset only above 3× threshold.
4. **Stamped regions discarded non-peak content** — new-note onset energy
   lives in bins owned by old content's regions and simply vanished
   (measured −51 dB rms where dry had −19: the note was ABSENT for
   ~100 ms). Fixes: dual-window amplitude analysis (short window at frame
   center for amplitudes; long window keeps freq/phase) + carry each
   stamped region's non-mainlobe bins verbatim.
5. **Latency lie** — true engine latency was 2N−hop (7168) while N (4096)
   was reported and trimmed: host PDC and all offline A/Bs were 64 ms
   misaligned (and Mix would have flammed). Fix: prime the output FIFO
   with hop, not N. Click-verified: 0 residual samples.

Post-fix, aligned: phylovox 9.75 attack lands within 2.5 dB of dry
(was: absent). Regressions: tuning +0.2¢, vibrato skirt 48.4 dB (new
best), scoop dead zones gone (single −26 dB event remains at the 400¢
target switch — that's the sound of glide=0; micro-glide floor is a
candidate if it bothers ears).

---

## Batch 012 — all five fixes, full suite (2026-07-03)

`out/listen-012/`: full suite × {champ, formant60} through the repaired
engine. Plugin rebuilt + reinstalled — **Ableton's delay compensation was
64 ms wrong until now; this alone should feel different in the session.**

**Specific asks:** (1) phylovox 9.750 — gone? (2) the far-from-target
amplitude instability on vocals — gone? (3) does anything NEW poke out
(the residual carry adds a subtle dry layer under stamped content;
tonalization purists may notice); (4) in Live: does timing feel tight now
(PDC fix)?

**Verdict (2026-07-03):** "Changes the sound a LOT — not necessarily
displeased. Much SMOOTHER — definitely what I wanted for the vocals, but
almost smear-y at points." Then, after isolating with a tuner in Ableton
(root-only MIDI, F→D movement): "a lot of the pitch movement in the vocal
was making it through via FEEL, and the FORMANT shifting gave it this
sliding character. With formant preserve at 100 and feel at 0, it stops."
The 15.370 'dragged-up' report → decoded as real source portamento being
faithfully re-quantized; retarget debounce kept (chord changes instant via
grid-mask detection, source wobble damped). Transition-content policy:
"map and dry sound subtly different in ways that I like — expose as a
switch! (mute is no good though, nuke that one)."

**Actions:** Newborn::Mute executed. "Transitions" switch (Map/Dry) added
to engine, CLI, and plugin (default Map). Plugin rebuilt + reinstalled.
Character interaction note for the future taste-map: Feel×Formant = the
"sliding" vocal character; feel 0 + formant 100 = locked/hard-cut.

**Verdict:** *(pending)*
