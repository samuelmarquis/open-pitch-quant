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
- Pack v2 (`make_ab_pack_p2.py`, returned 2026-07-20): purify-forward
  material sweep + parameter census (2120 params, `reference-p2/params.txt`)
  + THRESHOLD curve + FEEL midpoint/repro. Pack v3
  (`make_ab_pack_p3.py`, dispatched): GUI-set purify + fold cross-check.

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
| FEEL | **linear re-injection of the believed deviation**: output = target + fe × believed_dev. v2 measured fe50 at exactly half of fe100 (+19.2/+16.8/+10.0 vs +38.2/+33.4/+20.0). The belief vector is session-stable (v1 j18 reproduced to 0.1 c) | preserves micro-*variation* only; static detune still fully corrected | fork; a matching mode needs `out = target + fe·est_dev` with *their* estimator's flavor of belief |
| THRESHOLD | operates on the engine's **believed** deviation, not ground truth — v2's 5-point curve spares G(+20 c) between th25–35, E(−40 c) between th35–50, C(+35 c) between th50–75, which is perfectly monotonic in the estimator's own deviation vector (+20/+33/+38 c, measured via FEEL below). The v1 "asymmetry" dissolves: we ranked by truth, the machine ranks by belief | `--threshold` in true cents of own pitch | same mechanism, different referent: theirs thresholds the estimate, ours the actual detune |
| ELECTRIFY | tracked-sound count; starved content **discarded** | `--voices`; starved content **carried dry** | count maps, fate of the starved does not |
| PURIFY | **closed by v3 (GUI-set sweep + cross-check). One-sided denoise with all the action in the top quarter of knob travel**: GUI 0–75 is neutral (≡ default; hat noise-share 93.6/93.6/93.7/93.8 %), GUI 100 is a transformative denoise/harmonic-recovery state (hat → **7.4 %** — the hat becomes a *tone*; amen 56→31 %; murky 14→10 %). **No noise-increase side exists in this build** — the manual's "below 50 % increases noisy components" is false for this binary; knob-bottom is neutral. Separately, the VST3 *parameter* is folded (normalized 0.0 ≡ 1.0 ≡ GUI-100, verified PARAM-1.0 7.5 % vs GUI-100 7.4 %; GUI 25–75 ≡ param 25–75 ≡ neutral), so purify automation in this build cannot be trusted. v1 purify rows void; v2's {0,100} rows are max-purify duplicates, its {25,50,75} rows neutral | no analog; nearest raw ingredients are `--carry`/`--gate`/unowned | measured and closed; a faithful mode needs a one-sided residual-suppress/harmonic-recover macro with a top-quarter taper |
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
- ~~The unexplained +33 c E4~~ — **solved by v2**: it is the pitch
  estimator's own belief. PITCHMAP believes the −40 c-flat E4 is +33 c
  sharp — stably, across sessions — and both FEEL (which re-injects
  belief×slider) and THRESHOLD (which spares by belief) act on that same
  internal vector. One estimator, two knobs, mutually confirming. Why the
  estimator mis-signs this particular flat detune remains open; that it
  does is now a fixed, reproducible fact.
- **Methodological: PITCHMAP re-randomizes synthesis phases per render.**
  Two renders of the same settings share magnitudes but decorrelate in
  waveform (same-input diffs of −1 dB re signal with smoothed-magnitude
  correlation 0.9995+). Null tests and waveform diffs are therefore
  meaningless against this plugin — v2's waveform-based self-test
  false-passed on exactly this. Compare in the magnitude domain, and
  **time-locally**: time-averaged smoothed spectra are equally blind to
  local energy redistribution (they read purify-different renders as
  identical). The working instrument is HPSS-style noise-share /
  per-frame flatness. Both failure modes are now proven, one per bench.

## Listening shortlist (the second pass, ears only)

1. `j34` transients — the click massacre vs our verbatim carry.
2. `j15` vs `j13` — voice starvation as a *sound* (theirs) vs our carry.
3. `j18` — FEEL 100 on static detune; find the +33 c E by ear.
4. `j53` — custom-grid phylovox: what discarding the remainder does to a
   voice you know intimately.
5. `j36` — tritone remap +2.3 dB resonance: their shift-damage timbre
   vs ours at the same distance.
6. `reference-p3/renders/j202` vs `j204` — the hat at GUI-purify 50 vs
   100: a 94 %-noise hat turned into a tone. The single most dramatic
   knob state measured in this whole campaign.
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
