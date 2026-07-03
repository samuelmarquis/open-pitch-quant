# Research Report 02 — PITCHMAP Condensed Functional Specification

*Agent-researched, 2026-07-03. Primary source: official manual v1.6.2p (48 pp.),
archived at https://archive.org/download/pitchmap-vst/PitchMap%20VST/PITCHMAP/Zynaptiq%20PITCHMAP%20Manual.pdf.
All unattributed quotes are from the manual.*

**Terminology correction:** there is **no "Glue" parameter**. The fifth Process
knob is **GLIDE** (polyphonic portamento). There is also **no dry/wet mix** and
**no per-key detune** — tuning offsets are global only (Input Ref. Tuning /
Output Tuning, in Hz).

## 1. What it is / signal flow / MAP technology

- "PITCHMAP is the world's first and only real-time, polyphonic pitch correction and pitch mapping plug-in."
- "Based on our proprietary MAP (Mixed-Signal Audio Processing) technology, PITCHMAP does all that by separating a musical signal into individual elements/sounds, including their associated harmonics and transients. Sounds to be processed are selected by their fundamental pitch, and their tuning can then be corrected or their pitches arbitrarily mapped individually, using pitch maps the user creates from within the GUI, or real-time MIDI data."
- FAQ: "PITCHMAP uses our MAP technology to de-mix your signal into the sounds that make it up, including their harmonics, transients and noise components." / "MAP is based on artificial intelligence technology that models the human auditory system."
- Overview: the algorithm models "the human perceptive system, including the cochlea and the brain region responsible for interpreting its data"; voice is recognized and "processed separately" (see ALGORITHM §8).
- Unpitched content: pitch processing "leaves non-pitched signals like drums virtually untouched"; there is a **residual layer** — "PITCHMAP may sometimes fail to recognize all harmonics and may move some of them to a residual layer (which typically holds drum transients and the like)."

## 2. Latency, sample rates, channels, CPU

- **Latency: 4096 samples** (~93 ms @ 44.1 kHz; third-party PDC measurement "92.9ms" in Bitwig, KVR t=407732). **Internal buffer 1024 samples**; host buffer ≥512 recommended, ideally ≥2048 (smaller ⇒ CPU spikes).
- Sample rates: natively 44.1/48 kHz; since v1.7.0 higher rates via internal SRC.
- Mono/stereo, 32-bit float. Current v1.9.2, Apple Silicon native since 1.9.0.
- CPU is parameter-dependent: very low ELECTRIFY → more sounds tracked → more CPU; very high PURIFY → more CPU.

## 3–4. GUI / Display / Mapping Editor

- Display: 3 octaves, scrolling piano-roll-spectrogram: "What we display are detected sounds, including their harmonics, transients and noise components, whose fundamental pitch we map horizontally. Absolute pitch is coded into the color, and amplitude is displayed using the width of the symbols."
- **Low-Cut/High-Cut sliders** + **Mute switch**: sounds whose *fundamental* is out of bounds are bypassed or muted. "THESE ARE NOT FILTERS! … any sound that has its base pitch in the area that is Muted will be removed, including its harmonics, transients and noise components. Think in terms of muting channels on a mixing desk."
- **Lower Keyboard** (source pitches): per-key **Bypass** (passes unprocessed) / **Xclude** (pitch removed from allowed destination grid; sounds "forced to one of the neighboring, un-Xcluded pitches" per Xclude Round. Mode). Shift-click a key plays a sine reference.
- **Pitch Mapping Sliders** — one vertical slider per source semitone ("a routing matrix or patchbay, 'this goes there'"), body doubles as a per-pitch level meter; while dragging, that pitch is soloed; alt-drag edits the pitch class across all octaves. **127 mappable source slots; targets −12…+23 semitones.** Slider-head modes (shift-click):
  - **Square**: map within the source octave exactly (WYSIWYG).
  - **Round**: map "towards the nearest octave … to keep transposition as low as possible to maximize sound quality."
  - **Down/Up-triangle**: always an octave below/above the set value.
- **Reset**: all sliders to chromatic identity map.

## 5. Edit Mode (octave-scope semantics)

- **Repeat**: "any value edited is copied to all octaves… When using MIDI MAP, playing a chord results in the entire range being mapped to that harmony." (pitch-class semantics)
- **Visible**: like Repeat within the visible 3 octaves; outside splits into two Custom zones.
- **Custom**: "only the exact key/slider/note that you edit is changed… In MIDI MAP mode, this allows playing completely independent phrases in varying parts of the MIDI keyboard. This even allows mapping all source pitches to a single destination pitch."
- **Key Edit Mode** (Bypass/Xclude): "When in MIDI MAP mode, selects whether MIDI notes are used to map the pitches (Xclude) or to un-mute a pitch (Bypass)".

## 6. MIDI behavior

Two modes:
- **Regular** (MIDI MAP off): note-ons **latch-toggle** the Lower-Keyboard key states (note-off irrelevant).
- **MIDI MAP**: "the Lower Keyboard, including all associated Bypass and Xclude states, is ignored. Instead, live MIDI input is used to set values." With Key Edit = **Xclude**: **held notes define the grid of allowed target notes** ("instead of mapping each possible pitch to a specified target pitch, MIDI MAP mode simply sets up a grid of allowed target notes and everything just slides into place"); with **Bypass**: held notes gate which pitches pass at all (de-mix by playing). Respects Repeat/Visible/Custom for octave scope.
  - Octave attraction: Repeat ⇒ held C = allowed pitch class in all octaves; Custom ⇒ only the exact held note.
  - Zero-held-notes semantics: undocumented for Xclude; for Bypass implies output muted.
  - **No documented velocity/pitch-bend/CC response.** "MIDI functionality depends on the implementation of the Host software."
  - Recommended workflow: reset sliders, MIDI MAP on, Repeat mode (preset "01 MIDI Map Template - Medium").
- **EXT. MIDI** (AU only): for hosts that can't route MIDI to effects; in Logic inserted as "AU MIDI-controlled Effect" with audio as side-chain.

## 7. Process knobs (defaults: Purify 50%, Electrify 50%)

- **THRESHOLD**: "automatically Bypassing notes that are detuned less than an amount set with this control." Label click toggles Threshold/Global Threshold (whether *transposed* notes are also bypassed).
- **FEEL**: "re-introducing micro-variations in pitch, such as vibrato, after correction is applied." 0% = fully quantized; high = preserve all intonation detail while still mapping.
- **PURIFY**: "adjusts the amount of noisy components. Values higher than the default 50% reduce noisy components and introduce an effect reminiscent of resonance, values below 50% increase the level of noisy components." High values also recover harmonics from the residual layer; <50% improves transient preservation.
- **GLIDE**: "length of polyphonic glide/portamento… Whenever a new sound starts, the pitch ramps up/down from the source pitch to the destination pitch over an amount of time set with this slider. Subsequent sounds on the same pitch do not trigger the Glide again, unless interrupted by a non-pitched transient."
- **ELECTRIFY**: "High values make results sound electric, low values can actually improve processing quality but may introduce unexpected harmonics when working with sparse recordings… **Technically, this control adjusts how many sounds are being tracked — at maximum position, only one sound is tracked.**"

## 8. Algorithm & Macro section

- **KEY TRANSFORM**: root+scale pull-downs that just *set the sliders* (stateless macro). **Input key is never detected** — transforms are "relative to a C chromatic scale". **Voicing arrows** rotate all sliders ±1 semitone (chord-inversion-like).
- **ALGORITHM Linear/Medium/Natural**: "In Medium and Natural modes, the analysis engine uses a perceptive model to discern voice components in the input signal, and process these separately."
- **STRICT**: "removes more pitch variation, but may reduce transient crispness."
- **XCLUDE ROUND. MODE**: Up / Down / Nearest / **Intelligent** ("tries to avoid jumping as much as possible"; Nearest = "typical (and quite popular) tuning-effects").

## 9. Footer

- **INPUT REF. TUNING** (analyzer A4, Hz) / **OUTPUT TUNING** (output only, "does not affect Bypassed components").
- **Snapshots**: 8 slots storing sliders + Lower-Keyboard states only; recall is automatable (per-song-section maps).

## 10. PITCHMAP::COLORS (2023 sibling)

Same core engine ("separating the input audio into separate sounds based on their pitch, then shifting each up or down to fit a pitch grid individually"). Grid-only model (no per-source sliders); **Pitch Rounding** nearest/up/down; chord memory A–D; **SCALE SHIFT** (sweep through grid, no octave wrap); **FORMANT SHIFT** (±2 oct, 0.01 st) + **FORMANT GAMMA** (exaggerates formant peaks/troughs); **TRANSIENT BYPASS** ("dial in the amount of transients to take out of the pitch mapping and mix back in afterwards", up to 200%); HP/LP filters. Three modes replacing Linear/Medium/Natural+Electrify: **SICK** (smoothest/closest), **NSANE** (resonant shimmer, best harmonics, misses transients, most CPU), **WTF** (reedy/robotic). Dropped: Threshold, Feel, Glide, Purify/Electrify, Edit Modes, Snapshots.

## 11. Gotchas for reimplementation

- No wet/dry, no per-key detune, no velocity/PB response, no input key detection, no formant control (original PITCHMAP).
- "Sound quality is proportional to pitch-shift factor" — minimal-shift strategies (Round mode, MIDI MAP+Repeat, voicing rotation) are the documented mitigations.
- CPU overload ⇒ "drop-outs/ring-modulation/distortion".

### Sources
Manual PDF (archive.org, above) · zynaptiq.com/pitchmap/ (overview, specs, FAQ, downloads) · KVR t=407732 (latency measurement) · SOS review of COLORS (soundonsound.com/reviews/zynaptiq-pitchmap-colors) · zynaptiq.com/pitchmapcolors/
