# Paths Not Taken

A ledger of design branches we consciously walked past. Not rejections —
deferrals. Each entry records what the path is, why we didn't take it at the
time, and what sound design might be hiding down there, so that future-us can
come back with a lantern.

Format per entry: **what / why deferred / what hides there / re-entry notes**.

---

## 001 — Note-object source separation ("the Melodyne way")

**What:** True polyphonic decomposition: multi-F0 estimation → group partials
into note objects → reshift each note *coherently* (fundamental + all its
harmonics move together as one thing) → resynthesize. The architecture of
Melodyne DNA.

*(Evidence update, same day: research shows PITCHMAP itself is a middle path —
"pitch-object de-mixing" on a chromatic grid, where all sources sharing a
fundamental fuse into ONE object and an unpitched residual layer passes
unmapped. See `docs/research/03-internals-best-evidence.md`. So true
note/instrument-object separation is a path not taken even by Zynaptiq; this
entry stands, and the gap between "pitch-object" and "note-object" is exactly
where Melodyne-grade cleanliness hides.)*

**Why deferred (2026-07-03):** Chosen against as the *first* architecture, in
favor of the channelized/spectral-band mapping hypothesis, because: (a) it's
dramatically harder in real time — multi-F0 tracking is fragile, latency-hungry,
and octave-error-prone; (b) it isn't what PITCHMAP sounds like — our first goal
is to land in that sonic territory, and note-object separation would overshoot
into "clean retuner" land; (c) the note-tracking layer is a research project
unto itself and would starve the fun mapping/resynthesis work.

**What hides there:**
- *Clean* polyphonic retuning — chord-quality reharmonization without the
  spectral-kaleidoscope timbre. A genuinely different instrument, not a better
  PITCHMAP.
- Per-note routing: retune only the third of the chord; send the bass note
  somewhere else; different target scales per detected voice.
- Note-level gestures: glissandi between chord changes, note freeze/sustain,
  arpeggiating a held chord *inside* the audio, audio-to-polyphonic-MIDI out.
- Selective transparency: leave unpitched content (breath, hats, room)
  genuinely untouched instead of gating or snapping it.
- Hybrid potential: even a *coarse, laggy* note tracker could run alongside the
  channelized engine and bias its band→target assignment toward harmonic
  coherence. This is the most likely re-entry point. (Correction: we
  originally attributed this to a PITCHMAP knob called "Glue" — no such knob
  exists; the fifth knob is GLIDE, polyphonic portamento. Harmonic coherence
  in PITCHMAP lives in its grouping stage, not on a knob.)

**Re-entry notes:** Look at salience-based multi-F0 (Klapuri), neural options
(basic-pitch-class models) if a ~50–100 ms latency budget is acceptable. Start
as an *offline* analysis pass feeding the existing engine before attempting
real time. The band-mapping engine we're building remains the resynthesis
back end either way — this path replaces the *assignment* logic, not the
signal path.

---

## 002 — CFPC super-resolution front end (the Zynaptiq patent)

**What:** Zynaptiq's only public technical disclosure (EP3271736A1 /
US11079418, Bernsee & Gökdag 2015): expand each FFT bin into a
constant-frequency partial across a time-frequency matrix, then apply
**cross-frequency phase coupling** — EMA smoothing along the *frequency* axis
— synchronizing adjacent bins into time-localized wave packets. Claims
"sample-accurate" time-frequency magnitudes that beat the windowed-FFT
resolution tradeoff. Likely (medium confidence) a formalization of PITCHMAP's
"cochlea model" front end.

**Why deferred (2026-07-03):** v0 uses a plain STFT + instantaneous-frequency
front end because (a) it's a known quantity and the interesting risk lives in
the grouping/mapping stages, (b) the patent is *alive* (priority 2015) — using
its specific method in distributed software needs a freedom-to-operate think
first, (c) we can't tell yet whether front-end resolution is even our
bottleneck.

**What hides there:** better low-end separation (close bass partials inside
one bin-width), crisper transient localization inside long analysis windows —
i.e., exactly the two places STFT engines hurt. Possibly the gap between
"sounds like our thing" and "sounds like their thing" at the low end.

**Re-entry notes:** Only revisit after A/B against oracle renders shows a
front-end-resolution failure signature (bass smearing we can't fix with window
tricks). Non-infringing alternatives to evaluate first: reassignment/synchro-
squeezing transforms, multi-resolution STFT (dual window sizes), constant-Q.
Patent expires ~2035.

---

## 003 — The Glue knob (a control that never existed)

**What:** A user-facing knob for *harmonic-coherence strength* in the mapping
stage. At 100% ("full glue"), every partial moves with its owning object's
fundamental — fully coherent M1 behavior, "retuned instrument." At 0%, every
spectral peak snaps independently to the nearest allowed pitch — M0 behavior,
"spectral kaleidoscope." In between: per-partial interpolation of the two
shift ratios (in log-frequency). Born from our own confabulation — we
mis-remembered PITCHMAP as having this knob (it doesn't; its coherence is
baked into the grouping stage, not exposed) — then decided the mistake was a
good idea. Endorsed by the user 2026-07-03; bracketed by the user same day.

**Why deferred (2026-07-03):** Requires M1 grouping to exist before there are
two behaviors to blend. And v0 discipline is *faithful-first*: land in
PITCHMAP's sonic territory before inventing controls it never had, so we can
tell whether divergences are choices or bugs.

**What hides there:**
- The continuous morph itself — automating glue across a phrase (kaleidoscope
  wash resolving into a coherent chord) is an obvious *gesture*, not just a
  setting.
- Frequency-dependent glue: full coherence below N kHz, freedom above —
  shimmer/halo effects; or glue by harmonic index (fundamental+low harmonics
  locked, high harmonics free).
- Negative glue: push partials *away* from their comb positions —
  an inharmonicizer/bell-ifier driven by the same analysis.
- Per-object glue: bass object fully glued, everything else loose.

**Re-entry notes:** Post-M1 this is nearly free:
`ratio(peak) = lerp(snap(peak.freq), object.ratio, glue)` per peak. Prime
candidate for the first FUTURE-KNOBS batch after M4. Test with probes 03
(detuned triad) and 09 (inharmonic bell), where the two extremes sound
maximally different.

---

*(next entry goes here)*
