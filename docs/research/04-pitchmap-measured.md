# Research Report 04 — PITCHMAP, Measured

*First ground-truth A/B against the real plugin, 2026-07-20. Everything
below is measured from renders, not read from the manual; report 02 is the
paper spec, this is the bench. Not yet listened — the shortlist at the end
is the listening agenda.*

## Provenance

- Job pack `79465e1` (57 matched WAV+MID pairs, filename = settings sheet;
  `tools/make_ab_pack.py`). Rendered on the Windows machine by a scripted
  REAPER 7.78 bench (ReaScript; every parameter set through the VST3 API
  and read back — `testdata/reference/batch_log.txt`). PITCHMAP VST3,
  binary dated 2017-12-31 (version string not exposed).
- Receiving gate (`tools/check_ab_returns.py`): 57/57 returned, j00
  null-control **bit-perfect at zero lag** — every comparison below is
  sample-aligned.
- Our side: same job files through `opq` at engine `f8dbedf`
  (`tools/render_ab_ours.py`; PITCHMAP→opq translation in its header).
  Battery: `tools/compare_ab.py` → `out/ab-analysis/metrics.md` + the
  plates in [`ab-plates/`](ab-plates/).

## The headline: map-or-discard vs map-or-carry

PITCHMAP forces everything through its de-mix; **what the tracker does not
hold, the output does not contain**. Ours carries the remainder dry. This
one architectural difference explains four independent measurements:

1. **Isolated clicks vanish.** Probe 06 (clicks + noise bursts vs held
   C-maj): PITCHMAP renders at **−28.5 dB** overall; the unit clicks are
   *gone entirely* and only the noise bursts survive — resynthesized as
   pitched swells ([plate C](ab-plates/plateC_transients.png)). "Leaves
   non-pitched signals virtually untouched" is false under MIDI MAP for
   sparse transients. Ours passes the strip at −0.0 dB, clicks intact
   (transient bypass).
2. **Starved voices die.** ELECTRIFY 100 ("one sound tracked") on the
   triad kills the weakest note **−48.5 dB** (j15); our `--voices 1`
   retunes one object and carries the rest dry (−0.8 dB). Their voice cap
   discards; ours releases to the dry path.
3. **Custom mode discards out-of-grid content.** j53 (phylovox, exact-note
   grid): PITCHMAP −7.1 dB and chroma agreement drops to 0.51 — whatever
   can't reach the sparse grid largely disappears. Ours −1.5 dB.
4. **No dry path exists** (manual: no wet/dry, confirmed by conduct).

The panel's plate is therefore a measured fact, not a slogan: PITCHMAP is
the bijection that drops its remainder; NO BIJECTION — REMAINDER IS
CARRIED is the other answer to the same impossibility.

## Where the engines agree

- **Empty grid ⇒ silence.** All three NONOTES jobs: PITCHMAP mutes
  (peak 0.0) — undocumented behavior, now recorded — and our engine
  independently chose the same law (`grid.is_empty()` clears synthesis).
- **Sub-cent retune.** Detuned triad (+35/−40/+20 c), base settings: both
  engines land all three notes within ±0.1 c of target.
- **Attraction staircase.** Log sweep vs held A3, repeat-near
  ([plate A](ab-plates/plateA_basins.png)): our staircase sits on top of
  theirs through the octave ladder. Their **target clamp at −12
  semitones** is visible raw in custom mode (1760 Hz input parks at
  exactly 880 Hz) — the manual's "−12…+23" range, measured.
- **Chord change is instant for both** at GLIDE 0 — and, surprise, at
  GLIDE 100 too (see below). Repeat-mode octave attraction sends the
  moving voice **up** (G4→A4, +200 c), both engines
  ([plate B](ab-plates/plateB_chordchange.png)).
- **Gross tonal agreement** is high where content is stationary: chroma
  cosine ≥ 0.94 on most jobs ([plate D](ab-plates/plateD_chroma.png));
  the exceptions are exactly the divergence probes (el100, custom-grid,
  bell, resoguitar 0.70).

## Where the knobs mean different things

| control | PITCHMAP, measured | ours | verdict |
|---|---|---|---|
| GLIDE | **onset-only portamento**: chord-change retarget is instant even at 100 % (j24≡j30); new-note attacks start ~160 c off, settle ≈¼ s (phylovox j52) | glide smooths **retargets** (the drum's amber bend) | semantic fork; a matching mode needs onset-glide |
| FEEL | 100 % ≈ **leave static detune in place** (C+35→+38, G+20→+20) | preserves micro-*variation* only; static detune still fully corrected (j18: ours lands 0/0/0) | fork; matching mode needs deviation-retention |
| THRESHOLD | th50 spared −40 c and +20 c but **corrected +35 c** — not a symmetric cents rule; estimator-dependent | `--threshold 45` spares all three | partial match; their estimator differs from ground truth |
| ELECTRIFY | tracked-sound count; starved content **discarded** | `--voices`; starved content **carried dry** | count maps, fate of the starved does not |
| PURIFY | **v1 rows void — bench artifact.** The scripted bench set an inert parameter index: pu0 and pu100 renders are magnitude-identical (smoothed-spectrum corr 1.0000; bit-identical on noise) while every other knob measurably moved. Sam confirms the knob is very audible by hand. Pack v2 (`make_ab_pack_p2.py`, dispatched 2026-07-20) re-runs a 5-point sweep on purify-forward material with a parameter-table dump and a self-test gate | no analog | unmeasured pending v2 |
| Edit Mode / Rounding | Repeat/Custom, Nearest/Intelligent behave as documented; intel visibly hunts to avoid jumps (plate A, teal) | `--mode`, `--rounding` direct | matches |

## Conduct notes (for listening and for the comparator)

- **Lookahead pre-bloom**: with PDC alignment, PITCHMAP onsets swell in
  20–60 ms *before* the input everywhere (4096-sample lookahead); visible
  as attack ramps in plate C. Ours does not pre-bloom.
- **First-event swallow**: the transient probe's opening event produces
  ~229 ms of silence before output begins — tracker warm-up.
- **Gain structure**: ±1 dB on stationary tonal material; resonant boosts
  of +2…+4 dB on the tritone remap and vowels; the amen break renders at
  **peak 1.86** (32-float, no in-file clip). Ours runs level-shy on dense
  material: −5.5 dB (audio178), −4.0 dB (prism), −2.0 dB (amen) — voices
  cap and residual handling are the suspects. Listening question, then an
  engineering one.
- The unexplained: at FEEL 100 the E4−40 c voice renders at **+33 c** —
  neither source nor target, rock-steady for the whole take. No theory
  survives contact with this number yet (v2 re-renders the identical job
  to test session stability).
- **Methodological: PITCHMAP re-randomizes synthesis phases per render.**
  Two renders of the same settings share magnitudes but decorrelate in
  waveform (same-input diffs of −1 dB re signal with smoothed-magnitude
  correlation 0.9995+). Null tests and waveform diffs are therefore
  meaningless against this plugin; compare in the magnitude domain only.
  (This is also how the purify bench artifact was caught.)

## Listening shortlist (the second pass, ears only)

1. `j34` transients — the click massacre vs our verbatim carry.
2. `j15` vs `j13` — voice starvation as a *sound* (theirs) vs our carry.
3. `j18` — FEEL 100 on static detune; find the +33 c E by ear.
4. `j53` — custom-grid phylovox: what discarding the remainder does to a
   voice you know intimately.
5. `j36` — tritone remap +2.3 dB resonance: their shift-damage timbre
   vs ours at the same distance.
6. ~~`j43/j49/j50` — the amen at PURIFY 0/50/100~~ — void (bench
   artifact, above); the real purify sweep is pack v2's j100–j126.
7. `j39` — the bell: inharmonic partials, chroma agreement only 0.83 —
   kaleidoscope vs compromise, adjudicated by ear.

## Reproduce

```
nix develop --command python3 tools/make_ab_pack.py       # job pack
nix develop --command python3 tools/check_ab_returns.py   # gate returns
nix develop --command python3 tools/render_ab_ours.py     # our side
nix develop --command python3 tools/compare_ab.py         # battery
```

Standing law, restated for whatever comes next: the current sound ships
as its own algorithm choice; a PITCHMAP-faithful mode (onset-glide,
deviation-retention FEEL, map-or-discard fate for the starved) lands
*beside* it, never over it.
