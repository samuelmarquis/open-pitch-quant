# Research Report 01 — Prior Art & Building Blocks Survey

*Agent-researched survey, 2026-07-03. Target: polyphonic audio in → every
perceived pitch remapped to nearest pitch in a MIDI-sidechain-defined target
set → audio out, real-time.*

## 0. The reference product and the patent landscape

- **Zynaptiq PITCHMAP** — Commercial (closed), the only shipping product doing exactly this. Built on "MAP" (Mixed-Signal Audio Processing): claims to *de-mix* the input into individual pitched elements (with their harmonics and transients) in real time, then remap each element's pitch to targets supplied by MIDI keyboard or a GUI pitch map. Founded/designed by **Stephan M. Bernsee** (of smbPitchShift fame) — strong hint the core is an evolved STFT peak/partial-tracking system, not source separation by NN. https://www.zynaptiq.com/pitchmap/
- **Celemony Melodyne DNA** — patented polyphonic note-level editing (Neubäcker, ~2008–2009), but **offline/ARA**, not streaming real-time. Its patents (and possibly Zynaptiq's) are still potentially in force — worth a freedom-to-operate skim before commercializing, though a streaming STFT approach differs materially from DNA's offline note-object decomposition. https://www.celemony.com/en/service1/about-celemony/technologies
- **Laroche/Dolson phase-vocoder pitch-shifting patent US6549884B1** (filed 1999) — **expired** (~2019), so the core per-peak shifting technique is free to use. https://patents.google.com/patent/US6549884B1/en

## 1. Polyphonic / spectral pitch-shifting techniques

- **Laroche & Dolson, "New phase-vocoder techniques for pitch-shifting, harmonizing and other exotic effects" (WASPAA 1999)** — *The* foundational paper for this plugin. Peak detection in each STFT frame; each peak + its "region of influence" (surrounding bins) is translated to a new frequency as a block, with phase rotation `exp(jΔω·t)` applied per region; phases within a region stay locked to the peak (rigid phase locking). Crucially it explicitly discusses **frequency-dependent shift ratios β(ω)** — shifting different spectral regions by *different* ratios in one frame — which is exactly the "remap each pitch independently" primitive. Cheap (one FFT/IFFT per frame, no resampling), real-time. PDF: https://www.ee.columbia.edu/~dpwe/papers/LaroD99-pvoc.pdf. Companion: Laroche & Dolson, "Improved phase vocoder time-scale modification" (IEEE TSAP 1999) for identity phase locking.
- **Bernsee, "Pitch Shifting Using The Fourier Transform" + smbPitchShift.cpp** — classic tutorial STFT shifter (analysis with phase-difference frequency estimation, spectral bin translation, resynthesis). License: **WOL (Wide Open License, permissive)**. Global-ratio only and known for smearing (no phase locking), but the standard pedagogical baseline; PITCHMAP's author. http://blogs.zynaptiq.com/bernsee/pitch-shifting-using-the-ft/
- **jurihock/stftPitchShift** — modern C++17/Python reimplementation of Bernsee, **MIT**, real-time capable, adds **"poly pitch shifting": multiple simultaneous pitch ratios combined in a single DFT frame** (multiple resampled magnitude/frequency vectors merged) plus cepstral formant preservation. Not note-aware (applies all ratios to the whole spectrum, harmonizer-style) but the frame plumbing for "several ratios at once" already exists here. There is also a JUCE-based `stftPitchShiftPlugin` by the same author. https://github.com/jurihock/stftPitchShift
- **Multi-band / channelized shifting** — thin as academic literature; mostly patents: US6868377 (multiband phase vocoder, Creative) and US8793123 (bandpass-parameterized modification). The practically useful formulation is Laroche & Dolson's β(ω) per-region ratio above; "split into bands with crossovers, shift each band" also appears in DIY/Eurorack contexts (spectral multiband shifters) but crossover-band boundaries cut through harmonics — per-STFT-peak regions are strictly better for this use case.
- **Sinusoidal modeling (SMS / McAulay-Quatieri)** — partial tracking + per-partial oscillator-bank resynthesis; the cleanest conceptual fit for "move this note's harmonics coherently," and how one would do highest-quality harmonic gluing. **MTG/sms-tools** (Serra, Python): great for learning/prototyping, **AGPL-3.0**, offline research code, not real-time. https://github.com/MTG/sms-tools. **libsms** (C, GPL) exists but is stale. Real-time SMS is feasible (frame-by-frame with birth/death partial tracking) but you'd write it yourself; expect transient smearing unless you add transient detection/bypass (SMS's residual model exists precisely because pure-sinusoidal fails on noise/transients).

## 2. Open-source pitch/time libraries

- **Signalsmith Stretch** — C++11, **MIT**, polished, actively maintained; the standout. Phase-vocoder-family spectral processor (per the author's ADC22 talk "Four Ways To Write A Pitch-Shifter"). Real-time: yes — reports `inputLatency()`/`outputLatency()`, has a split-computation flag for even CPU spread; latency is on the order of 100–150 ms at the default preset (configurable smaller via `configure()` at quality cost). **Key feature for this project: beyond global shift it accepts a *custom frequency map* (input freq → output freq, normalized), used internally for its "tonality limit"** — i.e., non-linear per-frequency remapping is already a supported API concept, not a hack. A piecewise map built each block from (detected pitches → target pitches) gets you a long way; true note-aware gluing would require forking its internals (map per harmonic-comb rather than per absolute frequency). Ports: WASM/npm, Python (PyPI), Rust wrapper on crates.io. https://github.com/Signalsmith-Audio/signalsmith-stretch, docs: https://signalsmith-audio.co.uk/code/stretch/
- **Rubber Band** — C++, **GPL (or paid commercial license)**, very mature. R3/"Finer" engine is high quality; true lock-free real-time mode; `RubberBandLiveShifter` (v3.3+) gives lower-latency block-by-block global pitch shift. **Global ratio only — no per-band/per-peak hook** without forking (GPL fork = plugin becomes GPL). Good as a quality yardstick. https://github.com/breakfastquay/rubberband
- **SoundTouch** — C++, **LGPL-2.1**. Time-domain WSOLA — inherently a *global* shifter and mediocre on dense polyphony; wrong tool here except as a cheap baseline. https://www.surina.net/soundtouch/
- **WORLD** — C++, **modified BSD-3**. High-quality **monophonic speech/voice** vocoder (F0 + spectral envelope + aperiodicity); not applicable to polyphonic input, but relevant as Outotune's engine and for a mono-voice mode. Not designed for streaming (Outotune found it expensive/laggy in real time). https://github.com/mmorise/World
- **Rust ecosystem** — nothing mature natively; crates mostly wrap the C/C++ libs above (including a `signalsmith-stretch` binding).

## 3. Multi-pitch estimation (for note segmentation / harmonic gluing)

- **Klapuri iterative estimation + cancellation** ("Multiple fundamental frequency estimation based on harmonicity and spectral smoothness," IEEE TSAP 2003; and "…by summing harmonic amplitudes," ISMIR 2006 salience method) — classic DSP multi-F0: estimate strongest F0 via harmonic summation salience, subtract its (smoothness-constrained) harmonic pattern from the spectrum, iterate. Frame-based → real-time implementable; no license issue (it's a paper). PDF: https://www.ee.columbia.edu/~dpwe/papers/Klap03-multif0.pdf. Reference implementation: **Essentia `MultiPitchKlapuri`** — but Essentia is **AGPL-3.0** (and its Melodia salience code has research-only restrictions) → use for prototype ground truth, reimplement for the plugin. https://essentia.upf.edu/reference/std_MultiPitchKlapuri.html
- **Spotify basic-pitch** (ICASSP 2022) — **Apache-2.0**, polyphonic, instrument-agnostic; outputs onset/note/multipitch posteriorgrams. **Tiny: <17k parameters, <20 MB peak memory, faster than real time.** Caveat for a live plugin: its harmonic-CQT front end needs >1 s of context for low bins, so *latency* (not throughput) is the problem — NeuralNote explicitly gave up on real-time for this reason. Usable at ~100–300 ms lookahead-style latency budgets or with a truncated/reworked front end. https://github.com/spotify/basic-pitch
- **CREPE / torchcrepe / penn(FCNF0++)** — **monophonic only** — fine for a vocal mode, useless for chords. CREPE MIT. https://github.com/marl/crepe
- **aubio / pYIN / zita-at1's detector** — monophonic, GPL(-ish); pYIN is the standard mono tracker for prototyping.
- Realistic take: for the *remap* task you don't need full transcription — you need per-frame spectral-peak salience grouping ("which peaks belong to one note"), which Klapuri-style harmonic summation over the STFT you already computed gives you nearly for free.

## 4. Existing open plugins near this space

**Nothing open does MIDI-driven *polyphonic* retuning. This plugin would be first.** Closest neighbors:

- **autotalent** (Tom Baran) — LADSPA, **GPL-2**, monophonic autotune. **TalentedHack** (LV2 fork, GPL) adds MIDI target-note input. http://tombaran.info/autotalent.html
- **fat1.lv2** (x42/Robin Gareus port of Fons Adriaensen's zita-at1) — LV2, **GPL-2+**, monophonic autotuner where **MIDI input has true sidechain semantics feeding the allowed-note set, with latency reporting** — the best existing structural reference for MIDI-sidechain → target-pitch-set plumbing, even though its DSP is mono. https://github.com/x42/fat1.lv2
- **GSnap (GVST)** — freeware autotune with a MIDI target mode, **closed source** — feature reference only.
- **Outotune** (Richard Hladík, bachelor-thesis project) — **DPF** harmonizer: mono voice in, MIDI note set in, synthesizes one WORLD-resynthesized voice per held note. Nearest open project *in spirit* but mono-in/additive-out, CPU-heavy. Mine for plugin topology, not DSP. https://github.com/RichardHladik/outotune
- **NeuralNote** — JUCE plugin embedding basic-pitch via RTNeural + ONNXRuntime, **Apache-2.0**. Not a retuner (audio→MIDI), but a proven recipe for *running basic-pitch inside a plugin*, and documents the CQT-latency limitation. https://github.com/DamRsn/NeuralNote
- **stftPitchShiftPlugin** (jurihock) — MIT, real-time STFT shifter plugin; see §1.
- **Vital / Surge XT** (GPL-3) — useful only as examples of serious open plugin infrastructure/packaging (both in nixpkgs).
- Cheap musical fallback worth knowing: a **MIDI-driven vocoder** (e.g., Calf Vocoder, LGPL) imposes target pitches via a synthesized carrier — different effect, overlapping use cases.

## 5. Plugin frameworks (MIDI + audio sidechain, Linux/nix)

- **nih-plug** (Rust) — **ISC**; exports **CLAP** (permissive) and **VST3** (via GPLv3 `vst3-sys` → distributed VST3 build must be GPLv3-compatible; CLAP-only avoids this). **Simultaneous audio + MIDI in is first-class**: `AuxiliaryBuffers` for sidechain audio, `MidiConfig::Basic` for sample-accurate `NoteEvent`s in `process()` — exactly the PITCHMAP topology. Standalone JACK export for fast iteration. No stable release (git dependency), but widely used. Most nix-friendly option (plain Cargo workspace, crane/naersk). https://github.com/robbert-vdh/nih-plug
- **JUCE** (C++) — dual **AGPLv3 / commercial**; VST3/AU/LV2/standalone (+CLAP via extensions). Richest ecosystem. Nix: workable, mildly annoying (configure-time fetches).
- **DPF** (C++) — **ISC**; JACK-standalone, LV2, VST2/VST3, CLAP. Plain-Makefile builds → very nix-friendly. Supports MIDI-input effects with multiple audio ports; Outotune used it for exactly this topology. https://github.com/DISTRHO/DPF
- Note: **LV2** is where "audio effect with MIDI sidechain" is most idiomatic on Linux (see fat1.lv2); CLAP handles it cleanly; VST3 note-input-on-an-effect is fussier but supported by nih-plug and JUCE.

## 6. Prototyping stack (Python, offline)

- **numpy/scipy** — STFT/ISTFT (or hand-rolled OLA), peak picking, resampling.
- **librosa** (ISC) — CQT, `piptrack`/salience, reference `phase_vocoder`.
- **soundfile** (BSD) — WAV I/O.
- **mido** (MIT) / **pretty_midi** (MIT) — parse the target-note MIDI sidechain into per-frame allowed-pitch sets.
- **basic-pitch** (Apache-2.0) — off-the-shelf multi-F0 ground truth for the prototype.
- **stftpitchshift** (PyPI, MIT) — ready-made Bernsee-style shifter to sanity-check against.

---

## Recommended building blocks

**(a) Quick offline prototype (Python, days not weeks):**
1. numpy/scipy STFT → **Laroche & Dolson per-peak shifting**: detect spectral peaks, group into harmonic combs (Klapuri-style harmonic summation salience, reimplemented — avoid AGPL Essentia), assign each comb the ratio `nearest_target(f0)/f0` from the mido-parsed MIDI note set, translate each peak's region of influence with locked phases, ISTFT.
2. Use **basic-pitch** posteriorgrams as an alternative/oracle note-segmenter to isolate "is my remapper or my detector the problem."
3. Baseline comparisons: `stftpitchshift` (poly-ratio mode) and **Signalsmith Stretch via its Python binding using the custom frequency-map API** — the latter tells you how far a *map-based* (non-note-aware) approach alone gets, which may be surprisingly far.

**(b) Real-time plugin:**
- **Framework: nih-plug (Rust), CLAP-first** — ISC, native audio+MIDI-in topology, JACK standalone for development, best nix story. (C++ alternative with identical topology support: DPF, ISC.)
- **DSP core, pragmatic path: Signalsmith Stretch (MIT)** driven by a per-block piecewise-linear frequency map from our own multi-F0 front end (Klapuri harmonic summation on shared STFT data; optionally basic-pitch via RTNeural/ONNX for a "studio" mode, per NeuralNote's recipe). MIT permits forking its internals later to make region mapping note-aware (true harmonic gluing) — that fork is the moat.
- **DSP core, from-scratch path:** implement Laroche & Dolson per-peak shifting with per-comb ratios directly (patent expired, paper is a complete spec, ~500 lines over an FFT) — more control over transient handling and phase locking than any wrapper.
- **Avoid as core:** Rubber Band (GPL + global-only), SoundTouch (time-domain, global-only), WORLD/SMS-tools (mono / AGPL / not real-time). Reference for MIDI-sidechain semantics + latency reporting: **fat1.lv2**.

**Key single fact:** no open-source project currently does MIDI-driven polyphonic pitch remapping; the two enabling primitives both already exist under MIT (Signalsmith's custom frequency map, jurihock's multi-ratio STFT frames), and the missing piece is a real-time note-segmentation front end that assigns each spectral peak region to a note-source ratio.
