# Research Report 03 — PITCHMAP Internals: Best Public Evidence

*Agent-researched, 2026-07-03. No PITCHMAP-specific patent exists; the
algorithm is a trade secret (Zynaptiq's on-record answer to "how does it
work?": **"Yes. Genuine black art."** — KVR t=390403). Below: documented
facts, behavioral evidence, and the synthesized best-evidence hypothesis.*

## 1. Hard evidence

### Vendor statements
- FAQ: "de-mix your signal into the sounds that make it up, including their harmonics, transients and noise components"; "MAP is based on artificial intelligence technology that models the human auditory system."
- FAQ "Is PITCHMAP a pitch-shifter?": No — it "de-mixes your signal into individual pitches and allows you to correct their tuning and map them to new pitches individually." **Phrasing: "individual pitches," not "individual instruments."**
- Manual: "Sounds to be processed are selected by their fundamental pitch"; 127 mappable input slots (MIDI grid), targets −12…+23 st (staff-confirmed, KVR t=339763).
- **ELECTRIFY (manual): "Technically, this control adjusts how many sounds are being tracked — at maximum position, only one sound is tracked."** ⇒ variable-count discrete tracked "sound objects."
- **PURIFY**: tonal-vs-noise (residual) balance, separately controllable.
- **FEEL**: micro-pitch deviation measured, then optionally re-applied post-mapping.
- **GLIDE**: per-onset pitch ramps source→target ⇒ per-note pitch *trajectories* are synthesized.
- **Per-key MUTE removes a sound's harmonics, transients and noise too** ⇒ components are *grouped to fundamentals* (auditory-scene-analysis-style), not comb-filtered.
- Documented failure modes: guitar-chord beat frequencies "detected as separate pitches and corrected differently"; dense material ⇒ harmonics fall into residual layer; sparse material + low Electrify ⇒ "ghost copies" (too many tracker slots claim harmonics as objects); "sound quality is proportional to pitch-shift factor."
- **Latency 4096 samples; internal frame 1024** (Denis@KVR t=459399: "lowering the buffer results in multiple parallel processes being required, which exponentially increases CPU load").
- **Not full source separation** (staff, KVR): "will always retain the unpitched/drums layer, so you won't get a solo vocal"; "sounds that play the same pitch as the vocal at the same time you won't be able to get rid of" ⇒ **same-pitch sources fuse into one object**.

### Patents & lineage
- **EP3271736A1 / US11079418** (Zynaptiq; Bernsee & Gökdag; priority 2015): "Methods for extending frequency transforms to resolve features in the spatio-temporal domain" — expand each FFT bin into a constant-frequency partial across a time-frequency matrix, then **cross-frequency phase coupling (CFPC)**: EMA smoothing *along the frequency axis* synchronizes adjacent bins into time-localized wave packets ⇒ "sample-accurate" TF magnitudes beating the frame-averaged FFT tradeoff; localization parameter λ (fixed or adaptive). The only public disclosure of Zynaptiq analysis machinery; post-dates PITCHMAP (2012) but matches the "cochlea model" marketing.
- Prosoniq heritage (acquired by Zynaptiq 2013): commercial neural-net audio since the 90s; **MCFE** ("Multiple Component Feature Extraction") — a NN-based *adaptive* time-frequency transform replacing the DFT; sonicWORX Isolate did note-level "pattern detection… extracting, manipulating and suppressing individual notes and sounds within a song." Bernsee (Morph interview): "an adaptive transform… the transform itself depends on the underlying signal," requiring "pattern recognition, comparable to speech recognition in complexity," in real time.
- **Bernsee's public STFT pitch-shifter (smbPitchShift)**: ≥75%-overlap STFT; per-bin true frequency from frame-to-frame phase difference; shift by bin remapping with magnitude accumulation; phase re-integration; OLA. Documented weaknesses: phase beating, one-frequency-per-bin (polyphony/noise), AM on sweeps. The public ancestor of the resynthesis stage.
- Laroche/Dolson per-peak shifting patent US6549884B1 **expired ~2019**.

## 2. Behavioral evidence
- SOS (COLORS): "splitting incoming audio into chromatic pitches, then shifting them to match notes"; "can even apply harmonic characteristics to atonal or noise-like sounds, so even industrial sound recordings can be turned into something melodic."
- KVR: MIDI notes with no corresponding input energy ⇒ "more of a hissing sound" (filtered noise floor excited into the empty slot); kicks sometimes classified as pitched; same-pitch overlaps can't be split.
- KVR speculation on COLORS "gamma": "a change of the window function at spectral peaks… to make them ring via resonance."

## 3. Best-evidence pipeline hypothesis

**PITCHMAP is neither Melodyne-style note-object separation nor naive per-bin
snapping. It is a middle path: pitch-object de-mixing on a chromatic grid.**
Up to N tracked pitched objects (F0 track + grouped harmonics + associated
transient), indexed by fundamental on a 127-slot chromatic grid — all sources
sharing a fundamental fuse into one object — plus an unpitched residual layer
that is never mapped.

Pipeline (confidence):
1. **Front end** (high in outline / medium in detail): frame-based STFT engine, 1024-sample internal frames, heavy overlap, 4096 total latency; on top, a cochlea-inspired super-resolution TF representation — plausibly early CFPC (EP3271736A1) and/or MCFE lineage — plus per-bin instantaneous frequency à la Bernsee.
2. **Tonal/transient/noise split** (high): components classified; transients detected and largely passed/re-injected (COLORS has explicit Transient Bypass); residual level = Purify; drums survive unmapped.
3. **Multi-F0 tracking & grouping** (high that it exists / medium mechanics): pre-deep-learning pattern recognition (heuristic/classical-NN, descended from sonicWORX Isolate) groups partials into ≤N pitch objects, fundamentals quantized to the chromatic grid; **Electrify sets N**; ghost copies & beat-frequency failures fall out of this. Medium/Natural add a voice classifier processed separately.
4. **Mapping logic** (high — essentially documented): per-object ratio = target(F0)/F0 from the 127-slot map (sliders/MIDI/scale macros); Threshold bypasses near-in-tune objects; Feel re-adds measured micro-deviation; Glide ramps per onset; Xclude rounding Up/Down/Nearest/Intelligent (hysteresis to avoid jumping).
5. **Resynthesis** (medium): per-object frequency-domain shifting — each object's grouped partials scaled by its own ratio and re-placed (bin/partial remapping + phase re-integration, per-object smbPitchShift descendant) — objects + transients + residual summed, OLA. Alternative reading: a bank of ~127 chromatic pitch-channel filters whose outputs are individually shifted (channel-vocoder-like) — fits "splits audio into chromatic pitches" and hiss-on-empty-notes; truth plausibly a hybrid.

**Knob → mechanism decoder ring:** Electrify = tracker polyphony N (documented, inverted: max = 1 voice) + synthetic coloration side-effect · Purify = tonal/residual mix (documented) · Feel = correction strength / micro-deviation re-injection (documented) · Glide = per-onset ramp time (documented) · Threshold = in-tune bypass tolerance (documented) · Strict = tighter pitch-track smoothing at transient cost (documented) · Linear/Medium/Natural = voice model off/partial/on (documented).

**Confidence:** pitch-object granularity (not instrument, not bin): high, staff-confirmed · STFT frame engine 1024/4096: documented · CFPC front end in v1: medium (inference) · per-object PV resynthesis from Bernsee lineage: medium · runtime neural nets: low/unclear (2012 CPU budget says classical heuristics).

### Sources
Zynaptiq FAQ (how-it-works; not-a-pitch-shifter; latency) · manual full text (archive.org djvu) · EP3271736A1 (Google Patents) · Bernsee tutorial + time/pitch overview + Morph interview (blogs.zynaptiq.com/bernsee) · KVR threads t=459399, t=390403, t=339763, t=602725 · SOS COLORS review · MusicRadar review + programmer interview · Wikipedia: Prosoniq, Stephan Bernsee, Hartmann Neuron · KVR news: Zynaptiq acquires Prosoniq.
