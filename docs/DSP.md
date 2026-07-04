# How the DSP works

*The engine as actually built (`rt/engine/src/lib.rs`, ~1200 lines of Rust,
no dependencies beyond an FFT). This is the as-shipped counterpart to the
pre-implementation plan in `design/01-architecture.md`. Everything here
survived double-blind listening against the failure modes it names —
the batch history is in `LISTENING-LOG.md`.*

## The idea in one paragraph

OPQ is a real-time **polyphonic pitch remapper**: audio goes in, MIDI notes
held on a sidechain define a *grid* of allowed pitches, and everything
pitched in the audio gets pulled to the grid — chords to chords, without
splitting the audio into stems first. The trick is the middle path between
two classic approaches that both fail here: full source separation
(Melodyne-style, not real-time-friendly and overkill) and naive per-bin
spectral snapping (destroys everything that makes a sound a sound). Instead
the engine *de-mixes the spectrum into pitch objects*: groups of harmonics
that move together, each owned by one fundamental. Each object gets **one**
transposition ratio; its harmonics are re-placed as a family, so the
timbre's internal structure survives. Whatever no object claims is the
*residual layer* and passes through (nearly) untouched.

```
audio ─ STFT ─ instantaneous freq ─ peak regions ─ multi-F0 grouping ─ tracks
                                                                        │
   output ◄─ iFFT/OLA ◄─ kernel-stamped partials + residual + grit ◄─ ratio per object
                                          ▲
MIDI sidechain ─ held notes ─ chromatic grid (Repeat: all octaves / Custom: exact)
```

No grid held → silence (that's the contract, same as PITCHMAP's MIDI MAP
mode). Latency is exactly one FFT window: 4096 samples.

## 1. Front end

- **STFT**: N = 4096, hop = 1024, Hann analysis and synthesis windows
  (hann² COLA with the 1/1.5 normalizer). At 44.1 kHz that's a ~93 ms
  window and 23 ms frames — PITCHMAP's documented numbers.
- **Instantaneous frequency** per bin via phase differences between frames
  (the Bernsee/phase-vocoder estimator): each bin k gets `f_true[k]`, its
  *actual* frequency, not the bin center. All pitch math downstream uses
  `f_true`, which is why the engine tunes to ±0.0 cents rather than ±5.
- **Stereo**: analysis and every *decision* run once on the **mid**
  spectrum (complex average of channels); synthesis is per channel
  (section 6). This keeps L/R decisions from ever disagreeing.
- **Dual-window amplitude**: a second, short FFT (N/4 = 1024, centered in
  the long window) supplies amplitude with 4× the time resolution. Stamped
  partial amplitudes are corrected by the short/long ratio (clamped
  0.25–4×), which fixes onset smear — without it, note attacks fade in
  over the whole 93 ms window.

## 2. Peaks and regions

Spectral peaks are found on the mid magnitude spectrum, then the spectrum
is partitioned into **regions** at the magnitude minima between adjacent
peaks (Laroche–Dolson style). Every bin belongs to exactly one region;
every region has one dominant partial. Regions are the atomic unit of
synthesis: whatever we decide about a peak, we do to its whole region, so
a partial's skirt travels with its mainlobe.

## 3. Multi-F0: carving pitch objects (`harmonic_objects`)

A Klapuri-flavored **greedy iterative estimator**, up to `voices` times:

1. **Candidates** = a quarter-tone grid (MIDI 33–84 in ¼-tone steps) plus
   the current f0 of every live track (seeds). Quarter-tone matters: with
   semitone candidates and the 45-cent claim tolerance, a source sitting
   between semitones lands in a dead zone and object formation flickers
   at frame rate (audible as ~1 Hz amplitude scooping — measured −18 dB
   flutter, fixed to −51 dB by this grid).
2. Each candidate claims the nearest unclaimed peak within 45 cents of
   each of its first 20 harmonics; salience = Σ claimed magnitude ·
   1/h^0.9. A candidate needs **≥3 harmonic hits** to count (a lone sine
   is not an object — it stays residual unless `Map Unowned` grabs it).
3. The best candidate wins the round. Stop early if its salience is
   < 5% of the first object's (noise floor guard).
4. **f0 refinement**: weighted median of `peak_freq / harmonic_number`
   over claimed peaks with h ≤ 6. Low harmonics only — at high h,
   *another* note's harmonics fall within tolerance (C's 16th harmonic is
   0.4 cents from E's 13th) and pollute a least-squares fit; the median
   over low harmonics is immune. This took the worst-case f0 error from
   +38 cents to sub-cent.
5. **Re-claim** at a tight 30 cents around the refined f0, and *burn only
   confirmed inliers* — everything else returns to the pool for the next
   voice.
6. After all voices: a **competitive full-comb post-pass**. Each leftover
   peak is assigned to whichever object's harmonic comb explains it best
   (within 22 cents, up to Nyquist). Competitive, not first-wins: adjacent
   combs' teeth are ~17 cents apart at high h, and greedy assignment
   measurably stole one object's real harmonics for another.

## 4. Tracks: objects over time

Objects are matched to persistent **tracks** by f0 proximity (100 cents).
Tracks carry the musical state:

- **Target selection**: nearest grid note, with *Intelligent* rounding
  adding 40 cents of hysteresis toward the track's current target (stops
  boundary flapping on vibrato). *Nearest* is the memoryless variant.
- **Retarget debounce**: a target change caused by source motion must
  persist 3 frames (~64 ms) before committing — a singer's portamento no
  longer drags the output through every intermediate semitone. Grid
  changes (you played a new chord) commit instantly.
- **Glide**: log-domain ramp of the transposition ratio over the glide
  time, with a floor of ~1.5 frames even at Glide = 0 so a retune never
  tears the overlap-add.
- **Feel**: each track keeps an EMA (250 ms) of its log-f0; the deviation
  of the instantaneous f0 from that EMA — the vibrato, the scoop, the
  human part — is scaled by Feel and re-added to the mapped ratio.
  Feel = 0 is robotic lock, Feel = 1 re-applies the source's micro-pitch
  in full on top of the new note.
- **Threshold**: objects already within N cents of their own chromatic
  pitch (and mapping to it) bypass mapping entirely.
- **Newborn policy** (*Transitions*): a track's first 2 frames are
  ambiguous (mid-portamento, onset noise). `Map` quantizes them
  immediately; `Dry` lets transitions pass at source pitch. They sound
  subtly, pleasingly different.

## 5. Synthesis: kernel stamping (the heart)

The obvious way to shift a region — translate its bins by an integer
offset and twiddle phases — was tried and listened to death: integer-bin
placement mistunes by up to half a bin (−9.8 cents at low frequencies),
and the frame-rate phase errors produce "washy, warbly" artifacts on
harmonic material (a 45 dB analysis skirt collapsed to 13.7 dB; 8.8 dB of
amplitude modulation at frame rate).

Instead, each owned partial is synthesized as a **frequency-domain
oscillator**: the analytic spectrum of a zero-phase Hann window — the
Dirichlet-kernel expression, exact at fractional bins — is *stamped*
directly onto the output spectrum at the exact target frequency
`f_target = f_peak · ratio`:

- **Amplitude** = source peak magnitude ÷ kernel value at the source's own
  fractional offset (de-scalloping), × the dual-window onset correction,
  × the formant correction (below).
- **Phase** comes from a per-track, **per-harmonic-number phase
  accumulator**, advanced each frame by the *trapezoidal mean* of the
  previous and current target frequency (chirp-consistent integration —
  plain rectangular integration audibly buzzes on vibrato). The stamp
  applies the kernel's `−π·offset` parity term per bin. When a track (re)
  appears, the accumulator seeds from the measured source phase at the
  anchor, so re-entries phase-align with reality instead of resetting.
- This is why held notes are *clean*: the same physical partial keeps the
  same accumulator across frames, so consecutive frames interfere
  constructively in the overlap-add by construction, not by luck.

Around the stamp, three companions:

- **Grit** (0–1) crossfades each owned region from the clean stamp toward
  a raw translated copy of the region with a linear phase ramp — the
  "dirty" mechanism reintroduced deliberately, as a character knob.
- **Residual Carry**: a region's non-mainlobe bins (>4 bins from the
  peak) are added back verbatim at source position. Between-partial noise
  and onset energy otherwise vanish — measured as ~25 dB "attack holes"
  at note starts.
- **Formant Preserve** (0–1): a spectral envelope (3× box blur of the
  *linear* magnitude spectrum, ~½ kHz smoothing) is evaluated at the
  source and target frequencies; the stamped amplitude is corrected by
  the ratio, raised to the knob amount. Partials move; the envelope — the
  vowel — stays.

**Unowned regions** (no object claimed them): with `Map Unowned` off they
pass verbatim (dry). On, they get nearest-grid mapping as whole regions —
gated by the **Tonality Gate** (peak-to-region-mean "peakiness" test;
non-tonal regions either stay fresh/dry or bypass per Gate Mode) and the
**Map Ceiling** (leave the air band alone).

## 6. Stereo without a stereo image blender

All decisions are mid-spectrum; per channel, each stamped partial reuses
the **shared phase accumulator** plus that channel's *measured analysis
phase offset* from the mid reference, and the channel's own magnitude.
Level differences (ILD) and arrival-time differences (ITD, which live in
exactly those phase offsets) both survive retuning. The **Coherence**
knob (1→0) blends in a static per-note, per-channel pseudo-random phase
offset — a width control from "exact image" to "decorrelated wash".

## 7. Transients

A spectral-flux onset detector runs on the mid spectrum. Moderate onsets
(flux > threshold) crossfade the output toward dry for the frame — the
mapped state keeps running underneath, so there's no re-sync click. Strong
onsets (>3× threshold) hard-reset synthesis state entirely (and retrigger
glide). With `Transient Bypass` off, drums get mapped too — worth hearing
once.

## 8. Streaming and latency

Input accumulates in a sliding buffer; every 1024 samples a frame runs and
pushes one hop of overlap-added output into a FIFO. The FIFO is pre-primed
with **one hop** of silence — not one window. (Priming a full window is
the natural-looking mistake; it makes true latency 2N−hop ≈ 163 ms while
reporting 93 ms, and cost us a confused evening inside Ableton's PDC.
Verified since with a click test: reported latency 4096, measured 4096,
residual after alignment: zero.) A parallel dry FIFO with the same delay
feeds the latency-aligned Mix/Bypass path — bypass is a crossfade between
two sample-aligned streams, hence click-free.

## 9. Numbers

| thing | value |
|---|---|
| tuning accuracy (probe suite) | 0.0 ¢ mean error |
| stamped-partial skirt | 45.0 dB (naive translation: 13.7 dB) |
| frame-rate AM on held tones | 0.6 dB (naive: 8.8 dB) |
| dead-zone flutter after ¼-tone grid | −51 dB (was −18 dB) |
| throughput, release build, M-series | 30–160× real-time, one core |
| latency | exactly N_FFT = 4096 samples |

## Provenance

The algorithm was prototyped in Python (`opq/engine.py`, now frozen as a
lab notebook) through nine measured-and-listened iterations, then ported
to Rust with exact-parity verification; the Rust engine is the sole
canonical implementation, shared by the offline CLI (`rt/cli`) and the
plugin (`wrac/plugins/opq`). Design branches we chose *not* to take —
note-object separation, CFPC front ends, a Glue knob, a Purify macro —
are cataloged with reasons in `PATHS-NOT-TAKEN.md`. What PITCHMAP itself
does is reverse-engineered from public documentation and listening; the
evidence corpus is `docs/research/`.
