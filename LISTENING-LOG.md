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

---

## Panel round 1 — the family-idiom rebuild's look test (2026-10-10)

`catalogue/v07.png` … `v10-keys.png` (0.3.0–0.4.0, the first pass of
the rebuilt panel). **Question:** after the first pass of the rebuild,
what reads wrong?

**Verdict (2026-10-10), verbatim:**
- "The display panel's bezel is so dark I can barely see it. Honestly,
  looking at this display, it's almost like calligraphy on paper; so
  maybe use a ligher texture there and a paper-white screen background
  with dark markings instead of the dark-mode thing you have going on
  right now"
- "the placement of custom/repeat relative to MIDI/KEYS makes their
  relation non-obvious. I'd say MIDI/KEYS should move to a knob in that
  space"
- "bypass does not need a control, it's owned by the host"
- "honestly nix the output panel; the MIX knob should be text in the
  bottom right (ask terrible-cepstra about the standardized bottom-row
  controls) next to the info-panel/preset-switcher/whatever else they
  have down there that's applicable to us"
- "knobs should not display their value all the time; we want
  scrolling infotext between the display panel and the control panels
  (defer to opencepstrum's idiom)"
- "switch the capture panel to anodized-blue"
- "always show vertical scroll bar in the main window"
- "scrolling direction in the main window, unlike the knobs, should
  respect natural scrolling"
- "hate the witchhat knob. nix it"
- "voices and tonality are both discrete knobs but don't share a style;
  not sure What Is To Be Done there but they should have the same style
  which will be neither of their current styles (the black knobs should
  be for the continuous controls, the handwheel is only for a One Knob
  kind of situation)"
- "switch from verdigris to a different texture on the finish panel"
- "ditch the REC-1859... and HOUSE / FEEL ... info text in the display
  panel"
- "if you want to have multiple different display modes (which I am in
  favor of!) the idiomatic way to handle that is panel buttons stacked
  left from the top-right edge (as cep does it) that switch the panel's
  display style to a different viewer"

**Interpretation and action:**
- *Light screen:* the transect becomes ink on paper: a paper-white field
  with dark markings, and a lighter monitor housing baked as our own
  matte. DESIGN was asked for the housing recipe.
- *Controls:* Map Source becomes a knob on the LAW plate beside MIDI
  Scope. The bypass control goes; the host owns Bypass.
- *Bottom row:* the OUTPUT plate goes and MIX becomes bottom-row text, on
  panelkit `strip` when terrible-cepstra lands it.
- *Infotext:* knob values show only while in use, and the infotext line
  between the display and the plates is panelkit's `hover`.
- *Plates and knobs:* CAPTURE goes anodized-blue and FINISH gets a new
  face. The witchhat goes; the black knob is for continuous controls. The
  stepped controls (Voices, Tonality Gate, Map Source) get one new
  stepped style, which DESIGN was asked for.
- *Screen:* a scroll bar is always shown, and the wheel follows the
  system's natural scrolling. The display's info texts go. Display modes
  come later, as viewer keys at the top right (DESIGN recipe).

**Built (0.5.0, catalogue/v11, v11-keys, v11-drag):**
- Done: everything that needs no new art or kit.
- Still waiting:
  - for Sam's pick of DESIGN's option plates: the housing, the stepped
    knob, the FINISH face, and the viewer-key recipe;
  - for panelkit `strip`: MIX in the bottom row.
- Interim: Voices and SOURCE wear the black knob, and SOURCE prints no
  positions yet.
- Found on the way: Tonality Gate was never stepped. It's a continuous
  peakiness ratio that only *read* as whole numbers, so it now shows one
  decimal and keeps a continuous black knob.

**Ruling (2026-10-10), verbatim:** "If it truly is a continuous
control--it should be displayed as such". Tonality Gate stays
continuous. The stepped style is for Voices and Source only; DESIGN has
been told.

**DESIGN's option plates (2026-10-10), Sam verbatim:**
- p179 (housing): "beige plastic is best, but let them know that the
  panel buttons are hovering *way* above the actual surface of the bezel
  (and if this is a problem on other panels it should be fixed there
  too)"
- p180 (stepped knob): "uhg, none of these. Maybe boss-ivory with the
  knob-ring, but it looks ridiculous for the two-point controls (just
  use a switch for those!)"
- p181 (FINISH face): "let's go catalin jade"

**Action:** SOURCE became a MIDI/KEYS bat switch (0.5.1). The picks and
the hovering-key bug went to DESIGN with a request for recipes. Voices
gets boss-ivory with knob-ring.

**Built:**
- 0.5.2 (catalogue/v12): the beige-plastic housing and the catalin-jade
  FINISH.
- 0.6.0 (catalogue/v13): no OUTPUT plate; MIX as bottom-row text
  (panelkit strip); three wider plates; Voices as the boss-ivory stepped
  knob with its amber lens ring. Plates and knob were rendered on
  DESIGN's farm (Sam's no-local-Blender order).
- Gone with the OUTPUT plate: the backlit LCD module (algorithm, pitch
  classes, chord, the mutter) and its three lamps. Their content could
  return as a display mode.

**Verdict:** *(pending)*

## Panel round 1, the viewers (2026-10-10)

`catalogue/v14.png`, `v14-ladders.png`, `v14-scope.png` (0.7.0).
**Question:** which viewers beside the transect get keys? Claude offered
ladders, residue and scope (docs/design/04-panel-ideas.md).

**Sam, verbatim:** "let's do ladders and scope as the viewers?"

**Interpretation and action:** three keys on the top bezel, stacked
left from the screen's top-right edge (cep's idiom): TRANSECT, LADDERS,
SCOPE. All three keep the ruler, the pitch axis, the target lanes and
the ceiling, so Keys editing and scrolling work in every viewer.
- LADDERS: one column per live object. Its h·f0 rungs over the last
  second are inked where the de-mixer gave the object that harmonic and
  pencilled where it didn't. Each column also shows the target, the sung
  pitch, and "heard ±cents → target, N h".
- SCOPE: the spectrum turned sideways onto the pitch axis. The input is
  a pencil wash and the wet output an ink wash, each averaged over 4
  frames, with a one-second sung peak hold.
  - A first try with edge lines raked across the paper at every
    valley, so it became abutting bars.
  - The engine now ships `scope_in`/`scope_out` (288 bins, a third of a
    semitone each, u8 at 0.5 dB) with each frame; HOUSE byte-identical.
- The keys are panelkit `text_button` stand-ins. DESIGN has the baked
  row queued behind the p183 key fixes.
- 0.7.3 (`catalogue/v15*`): the baked keys, on pre-p183 canon (Sam to
  DESIGN: "why are we waiting on bakes? The render farm exists now to
  get around this. Go, go, go!"), and the housing rebaked without the
  rack light's band. One rebake follows p189.
- 0.7.5 (`catalogue/v16*`): the post-p189 keys (Sam on DESIGN's p189:
  "189 B, ship it"), through-mounted, one legend size, sRGB LEDs.
- 0.7.12 (`catalogue/v18*`): the keys re-baked on the panel key row
  standard (DESIGN's p197, which Sam ratified per DESIGN), each exactly
  on its rect: about 2 px left and 1 px down from v16.

**Verdict (Sam, 2026-10-11, on 0.7.14 in Ableton Live on the Mac):**
"Ableton live passes the sniff test; baked keys are black, they should
be white/match the panel's material (ask DESIGN about this). Put a note
in your TODO that I think 'ORACLE' needs a little more work; the phase
sounds much smearier than HOUSE, and much smearier than I remember
pitchmap sounding. I also think the TRANSCET display should move in the
opposite direction, starting at the left and scrolling out to the
right, so that we can see what notes things clip to (it's non-obvious
with the current controls)."

**Reading and action:** the editor works in Live. Three things follow.
The keys take the housing's beige with a dark legend (DESIGN's p200 B,
0.7.15, `catalogue/v19*`); Sam on p200, via DESIGN: "B is the one I
would've picked, so all good there". The transect is flipped so now sits against the key ruler
(0.7.15). ORACLE's phase smear is an open engine item in TODO, not
started. The viewers themselves drew no objection.

## The Key Transform, first build (0.8.0, 2026-10-11)

**Question:** does naming the source key and scale, beside the
destination's, do what PITCHMAP's scale presets don't: move material
into a key without assuming it began in C major? And are Claude's
choices where Sam left them open the right ones: nearest with ties
down as the one rounding, degree-to-degree for same-sized scales, the
lists inside the screen at the plot's top right?

**Config:** Sam's brief is verbatim in TODO ("I want to handle this
differently than PM..."). Four lists, source key and scale then
destination key and scale, default `* CHROMATIC → * CHROMATIC`; 31
scales; the destination scale written to and read from the key ruler;
a source scale as a 12-entry remap in the engine; product state, not
parameters. Stills: `catalogue/v20-transform.png` (A MINOR → * MAJOR
on the harness's three voices) and `v20-transform-list.png` (the
destination's scale list open). HOUSE byte-identical with no remap.

**Verdict (Sam, 2026-10-16, in a host):** "The phasing issue with HOUSE
has been solved imo; key transform sounds fine, but use a darker
lettering and the new house-style dropdowns"

**Interpretation + action:** the transform's sound and its rules pass
as built. The look does not: the lists were OPQ's own dark rows in the
10 px sans, and the closed slots' lettering read grey. 0.8.10 opens
each list as panelkit's family menu (shaded white paper, the Tinos
serif, the family's row height, the current choice marked with a
dot, the cursor starting on it); the 31 scales would not fit the
screen at that row height, so CHROMATIC, MAJOR and MINOR stand at the
top and the rest open from five groups (Modes, Harmonic & melodic,
Pentatonic & blues, Symmetric, Exotic). The slots are set in the same
serif in full ink (pencil at 85% under MIDI, was 55%). Stills:
`catalogue/v21-transform.png`, `v21-transform-list.png`. The first
clause, about HOUSE's phasing, is recorded in TODO with a question:
which open item it closes.

## HOUSE's Feel, second round (2026-10-16)

**Sam, first:** "The phasing issue with HOUSE has been solved imo",
then, correcting it: "I meant ORACLE's phase smear; HOUSE's feel still
has the same problem (on phylovox, you can hear--literally, the second
note--that it warbles up and down on HOUSE with feel at 40% but does
not on oracle)--sorry, got those two mixed up!"

**Interpretation:** ORACLE's phase smear is closed. HOUSE's Feel
deviation (from a 250 ms average of the voice's pitch, unbounded) lags
a note change and swings the output while it catches up.

**Question:** which fix takes the warble out of phylovox's second note
at Feel 40% while changing HOUSE least?

**Config:** phylovox, its MIDI at 0.75, ROUNDING Smart, Feel 0.40,
0.8.11 engine. A: HOUSE now. B: the deviation capped at ±50 c
(ORACLE's bound). C: the average restarts when a voice commits to a new
note. D: B and C. REF: ORACLE. Renders: `out/feel-ab-2/` (gitignored).
Output pitch by YIN at 10 ms, in cents (6000 = C4):

| t (s) | A | B | C | D | ORACLE |
|---|---|---|---|---|---|
| 0.80 | 5555 | 5515 | 5555 | 5515 | 5508 |
| 0.95 | 6101 | 6006 | 6037 | 6006 | 6016 |
| 1.00 | 6090 | 6027 | 6027 | 6027 | 5996 |
| 1.05 | 6037 | 6006 | 5985 | 5985 | - |

Frozen renders each fix changes: B 30 of 56, C 37, D 40. Every fix
retunes HOUSE broadly, because the champion settings run Feel at 0.35.

**Recommendation:** B. It is ORACLE's own bound, takes the overshoot out
of the second note, and changes the fewest renders. C barely helps: by
the time a note change commits, the lag has already played.

**Sam, next:** "Put a small dropdown on the command strip to switch
between A(old behavior)/B/C/D; I'll try it on a bunch of audio and lyk
which one's good"

**Action:** 0.8.13 adds HOUSE FEEL A/B/C/D on the bottom strip (product
state, saved with the project; not a host parameter). A is byte-identical
to the frozen HOUSE (fence intact); B, C and D through the switch are
byte-identical to this round's renders. The CLI takes `--house-feel
a|b|c|d`. Still: `catalogue/v22-house-feel.png`.

**Verdict:** *(pending: Sam trying the four on his own material)*

## The family's screen glass (0.8.15, 2026-10-16)

**Question:** should OPQ's paper screen carry the family's glass (the
screen-monitor vignette, plus the reflection at 1/3)? Sam's family ruling,
relayed by DESIGN (p211 C): "reduce the glass reflection intensity to 1/3
and make that the default, then tell everyone to pick it up".

**Config:** DESIGN's farm baked screen_scene.py at our HOUSING_FLAGS (sid
opq-screen). The board draws col × vig, then + refl, in linear light over
the screen's content and under the menus. The first vig read 0.81 on
clear glass, a template bug (AgX view), which dimmed the paper about 19%.
DESIGN fixed it (template 7244624) and re-baked ours. On the fixed layer,
clear paper reads 234–238 sRGB against 237 before; only the lip darkens.

**Sam (p212, via DESIGN), verbatim:** "212, Yeah, sure, C is fine, it
looks a little better. Make sure everyone's on that & canonize / 210,
hate everything-lean. it's gotta be deadon-everything for consistency's
sake"

**Action:** C is the fixed vig. 0.8.15 is installed, and validate passes
11 ok. Still: `catalogue/v23-glass.png`. Under p210 B (every raised part
in the rack is dead-on), the viewer keys need a farm re-bake. The housing
doesn't: it is already orthographic. The plan and a proposal to move the
plates and knobs into the rack went to DESIGN.

## Dead-on viewer keys (0.8.17, 2026-10-16)

**Question:** p210 B ("it's gotta be deadon-everything for consistency's
sake"). The viewer keys are button-bezel raised parts, so the rack used to
lean them. The question was how they look drawn dead-on.

**Config:** DESIGN's farm re-baked keys.json (unchanged) at template 73fa7f3.
Before and after, the cells differ only slightly: the cap's shading and the
lip.

**Verdict:** Sam's ruling covers this (p210). It's applied, and the still
is `catalogue/v24-deadon-keys.png`.

## The FINISH rack pilot (p213, 2026-10-16)

**Question:** FINISH as one rack scene: the plate with its TRANSITIONS
bat switch, dead-on under the rack light (pass 50, template 73fa7f3),
compared with today's per-part plate. The rack light reads brighter and
greener on the jade.

**Sam, verbatim:** "B is way better, so no need to change anything on
DESIGN's end. Well, actually there is something that has to change there;
if you zoom way in on the bat switch you can see that right around the
base we can get a good look at the panel material. No good! Fix that
geometry; and also there's like a dozen new switches so go see if you
like any of the other ones"

**Interpretation:** the rack bake wins as it is, light included.

**The bat flaw, measured:** toggle-bat's lathes are open rings with no
floor. The bushing starts at z=0.072, its bore (r 0.085) is open, and
there's a 0.105–0.115 gap to the nut's bore over the washer's hole. So the
host shows round the lever's base and inside the nut. That's template
geometry, so the fix went to DESIGN: a bushing from the panel up, filling
the nut, and a dark bore floor under the pivot.

**The switches:** the template's canon has six: bat, rocker, slide, key,
tab and guard. Claude's picks for this board are slide and key, with tab
as a long shot. The rocker is out: its states barely differ at 1x, and
its I/O marks clash with the legends. The guard is out too: it has three
states, made for a protected action, and we have none.
DESIGN is asked to plate them on the FINISH pilot: A the fixed bat, B
slide, C key, D tab. Our 44 px-tall slot is the size limit. The FINISH
import, and the CAPTURE and LAW pilots, wait on the switch.

**p214 check (DESIGN):** I asked about the green inside the tab's slot.
DESIGN re-baked D with a matte white cap (pass 51 Dmatte), and every part
of the slot that shows beside the tab reads pure black. The green is the
brushed tab's face mirroring the jade, so it's not an open slot. p214
stands as sent.

## The switch: toggle-tab (p214, 2026-10-16)

**Question:** which of the template's switches should replace the bat
on the board?

**Sam, verbatim:** "214, I need to see that plate with the other knobs on
it before I can decide." Then, after whole-board stills of A–D in both
states: "214, D".

**Action:** all seven two-way switches are toggle-tab, fitted at 30 px.
Each plate is its own rack scene: the plate, its tabs and LAW's
chickenhead, dead-on under the rack light (pass 54 on DESIGN's farm;
bake.py RACK_PLATES, `--only rack --renders DIR`).

Two findings shaped the import:
- The tab's change between states runs far past it: a long shadow streak
  down and right to the plate's corner, plus soft shade to the left. So
  each part is drawn as a masked window, the feathered region its states
  change, cut from frames that share the plate's noise (the far-off
  difference between frames is at most 2 of 255).
- The tab reaches ±31 px, against the bat's ±22. Its legends move out to
  ±43 px, and on LAW, SOURCE and SCOPE move 8 px right (clear of the
  screw) and the chickenhead moves 6 px up (clear of their legends).

**Sam's standing ruling (via DESIGN, 05a5502), verbatim:** "Yeah just
bring everybody/everything into the new render idioms and don't block on
me--if I dislike it, I'll point it out from the plugin interface later".
From here, migrating into the house idioms ships without a plate. Claude
picks the house default and logs it here.

**0.9.0 (installed):** the three plates are rack scenes (pass 54), still
`catalogue/v25-rack-plates.png`. Two new looks surfaced:
- LAW's mirror brass reads as cream with a dark band under the rack light.
  It's asked for as a plate (brass against brass-bare), and LAW ships as ruled
  until Sam picks.
- CAPTURE's anodized blue and FINISH's jade read as in the pilot.

## LAW's brass under the rack light (p217, 2026-10-16)

**Question:** LAW's mirror brass reads cream, with a dark room band under
the rack light. Should it stay, or go to brass-bare (an even satin gold)?
DESIGN called brass-bare under the standing ruling, and it shipped in 0.9.2.

**Sam, verbatim:** "217 I actually kind of prefer the as-shipped/mirror to
satin."

**Action:** LAW goes back to --face brass. bake.py is set; DESIGN re-runs
LAW's jobs after the knob batch, and the plate ships with step (c).

## The knobs in the rack (step c, 0.9.6, 2026-10-16)

**Question:** none for Sam (standing ruling 05a5502: migration into the
house idioms ships without a plate). Do the ten knobs read right as parts
of their plates' renders, and does LAW's mirror brass (p217) hold up?

**Config:** pass 54, template a61c9df. CAPTURE and FINISH are farm
20261016-141117-44140, and LAW is 20261016-150829-56920 (--face brass).
1038 frames in all. Still: `catalogue/v27-rack-knobs.png`.

**Claude's read:**
- The knobs sit in the plates' light: real shadows, and COHERENCE's chrome
  mirrors its neighbours.
- A ghost of each black knob's zero indicator showed at every other value.
  That was an int16 overflow in the import: every rack cell was 253/255
  opaque, and linear-light blending made that 1% visible on black. It is
  fixed.
- On the mirror brass, the dark legends over the room band (SOURCE, SCOPE,
  THRESHOLD, ROUNDING, and the red MIDI and REPEAT) are low-contrast. This
  is noted for Sam, and their colour is unchanged unless he asks.

**0.9.7:** DESIGN found that rack's fit shrank a knob without scaling its
world-space AO and subsurface distances, so the catalin GRIT rendered pale
and pink. That is fixed at template 263c15b. FINISH is re-run (farm
20261016-165330-3022) and GRIT reads deep amber. `v27-rack-knobs.png` is
re-rendered in place.

