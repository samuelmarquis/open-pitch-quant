//! Real-time port of the opq spectral pitch-mapping engine.
//!
//! Faithful port of `opq/engine.py` (the "champion" configuration:
//! assign=group, synth=stamp, phase_lock — survivors of listening batches
//! 001–009), restructured for streaming and NATIVE MULTICHANNEL operation:
//! all analysis and mapping decisions are made once on the mid (channel
//! average) spectrum; synthesis is per channel with shared partial phase
//! accumulators plus each channel's analysis phase offset — preserving the
//! stereo image (level AND delay panning) through retuning. The
//! `coherence` parameter scales from exact image preservation (1.0) toward
//! static per-partial decorrelation (0.0) as a width control.
//!
//! STFT N=4096 / hop=1024, reported latency = N samples (PITCHMAP's 4096).
//!
//! The per-frame pitch analysis (instantaneous frequency, peaks and
//! regions, the greedy multi-F0) is the family's `audiokit::pitch`, which
//! began here; tracking objects across frames and everything after stays
//! in this engine.

pub mod params;

use audiokit::pitch::{self, midi_freq, princarg};
use audiokit::stft::{Hop, Stft};
use realfft::num_complex::Complex64;
use realfft::{RealFftPlanner, RealToComplex};
use std::collections::VecDeque;
use std::sync::Arc;

pub const N_FFT: usize = 4096; // default window size
pub const HOP: usize = 1024; // default hop (window/4)
/// The most objects one frame can hold (the Voices parameter's maximum).
const MAX_VOICES: usize = 12;
/// Live tracks: last frame's (at most one per object) plus this frame's
/// births, before stale ones are dropped.
const TRACKS: usize = 2 * MAX_VOICES;
/// phase-table reach for owned harmonics (full-comb ownership can claim
/// far beyond pitch::HARMONICS; mis-numbered h up here only re-keys a phase slot)
const MAX_H: usize = 64;
const TWO_PI: f64 = std::f64::consts::TAU;
const PI: f64 = std::f64::consts::PI;

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Unowned {
    Map,
    Dry,
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum TonalityMode {
    Fresh,
    Bypass,
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Repeat,
    Custom,
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Rounding {
    Nearest,
    Intelligent,
}

/// The governing law of the plant. House is the sound this engine grew
/// into through the listening batches — frozen byte-exact by
/// testdata/HOUSE-BASELINE.json, never silently retuned. Oracle is the
/// PITCHMAP-faithful policy set measured in docs/research/04: the
/// remainder is discarded instead of carried, glide is onset-only
/// portamento, feel re-injects the tracker's believed deviation
/// (statics included). Semantics only — Oracle does not chase the
/// reference's defects (first-transient swallow, resonant gain, folded
/// parameters).
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Algorithm {
    House,
    Oracle,
}

/// What regions owned by very young (<2 frames) objects do — i.e., what
/// ambiguous TRANSITION content (mid-portamento, note onsets) sounds like.
/// (A third variant, Mute, was tried and executed by user decree.)
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Newborn {
    /// map immediately (faithful: every moment quantized; slides step)
    Map,
    /// pass dry (source pitch audible through transitions)
    Dry,
}

#[derive(Clone, Copy)]
pub struct EngineParams {
    pub algorithm: Algorithm,
    pub voices: usize,
    pub unowned: Unowned,
    /// 0.0 disables the gate
    pub tonality_gate: f64,
    pub tonality_mode: TonalityMode,
    /// peaks above this (unowned only) pass unmapped; f64::INFINITY = off
    pub fmax_map: f64,
    pub transient_bypass: bool,
    pub flux_thresh: f64,
    pub feel: f64,
    /// seconds
    pub glide: f64,
    pub grit: f64,
    pub mode: Mode,
    pub rounding: Rounding,
    pub hyst_cents: f64,
    /// dry/wet, 1.0 = full wet (dry path is latency-aligned)
    pub mix: f64,
    /// 1.0 = preserve the stereo image exactly; lower values add static
    /// per-partial inter-channel decorrelation (width effect)
    pub coherence: f64,
    /// bypass objects already within this many cents of their (untransposed)
    /// chromatic pitch; 0 = off (PITCHMAP's THRESHOLD, non-global flavor)
    pub threshold_cents: f64,
    /// 0..1 formant preservation: stamped partial amplitudes are corrected
    /// by the source spectral envelope sampled at the OUTPUT frequency
    pub formant: f64,
    /// 0..1 gain on the verbatim carry of stamped regions' non-mainlobe
    /// bins (onset/noise energy). 1 = full onset preservation but a ~-31 dB
    /// source-pitch ghost under partials; 0 = pure stamps (attack holes)
    pub carry: f64,
    /// 0..1 one-sided denoise (the PURIFY fitting, both algorithms):
    /// fades unowned residual, claimed-noise synthesis, and the carry
    /// toward zero — at 1.0 the output is pure stamps, where the
    /// reference's "resonance" character lives. 0 = neutral.
    pub purify: f64,
    pub newborn: Newborn,
    /// Bit n set: an object whose source sits nearest MIDI note n passes
    /// unbent, as Threshold spares it (PITCHMAP's per-key Bypass on the
    /// Lower Keyboard). 0 = none, the HOUSE baseline.
    pub bypass_keys: u128,
}

impl Default for EngineParams {
    fn default() -> Self {
        Self {
            algorithm: Algorithm::House,
            voices: 6,
            unowned: Unowned::Dry,
            tonality_gate: 0.0,
            tonality_mode: TonalityMode::Fresh,
            fmax_map: 5000.0,
            transient_bypass: true,
            flux_thresh: 0.6,
            feel: 0.35,
            glide: 0.0,
            grit: 0.0,
            mode: Mode::Repeat,
            rounding: Rounding::Intelligent,
            hyst_cents: 40.0,
            mix: 1.0,
            coherence: 1.0,
            threshold_cents: 0.0,
            formant: 0.0,
            carry: 1.0,
            purify: 0.0,
            newborn: Newborn::Map,
            bypass_keys: 0,
        }
    }
}

#[derive(Clone)]
struct Track {
    uid: i64,
    f0: f64,
    lema: f64,
    tgt: f64,
    r_from: f64,
    g0: i64,
    seen: i64,
    born: i64,
    cand: f64,
    cand_n: i64,
    /// per harmonic number: (phase, frame last seen, last output freq)
    phases: [(f64, i64, f64); MAX_H + 1],
}

/// Max pitch objects reported per [`VizFrame`].
pub const VIZ_TRACKS: usize = 24;
/// Analysis frames buffered for the GUI between drains.
pub const VIZ_RING: usize = 16;
/// The scope's lowest note (C1) and its resolution: bins per semitone.
pub const SCOPE_FLOOR: f32 = 24.0;
pub const SCOPE_PER_NOTE: usize = 3;
/// The scope's bins: C1 up to C9, a third of a semitone each.
pub const SCOPE_BINS: usize = 96 * SCOPE_PER_NOTE;
/// A scope bin's level: `dB = value / 2 - 120` (0 is silence or above
/// Nyquist; 0 dB is a full-scale sine).
pub const SCOPE_DB_FLOOR: f32 = -120.0;

/// A scope bin's centre note.
pub fn scope_note(bin: usize) -> f32 {
    SCOPE_FLOOR + bin as f32 / SCOPE_PER_NOTE as f32
}

/// A scope bin's level in dB.
pub fn scope_db(value: u8) -> f32 {
    value as f32 * 0.5 + SCOPE_DB_FLOOR
}

/// One tracked pitch object, as seen by the analysis display.
#[derive(Clone, Copy, Default)]
pub struct VizTrack {
    /// Stable identity across frames (monotonic birth counter).
    pub id: i64,
    /// Source fundamental (Hz).
    pub f0: f32,
    /// Mapping target (Hz).
    pub tgt: f32,
    /// Output fundamental actually synthesized this frame (Hz): source times
    /// the exact per-object multiplier (glide progress + feel deviation), or
    /// the source itself when `spared`. This is the bend, not the intent.
    pub out: f32,
    /// Summed magnitude of spectral regions this object claimed this frame.
    pub amp: f32,
    /// Number of harmonic regions claimed this frame.
    pub nh: u16,
    /// Bit h-1 set = harmonic h claimed a region this frame (h 1..=64).
    pub hmask: u64,
    /// Threshold spared this object (already in tune, untransposed target):
    /// multiplier forced to 1.0, no correction applied.
    pub spared: bool,
    /// Inside the newborn window (transition policy applies).
    pub newborn: bool,
}

/// Per-frame analysis snapshot for the GUI. Fixed-size and `Copy` so the
/// audio thread can publish it without allocating.
#[derive(Clone, Copy)]
pub struct VizFrame {
    /// Frame index (hop counter since reset).
    pub t: i64,
    /// Spectral flux (onset detector value; compare to `flux_thresh`).
    pub flux: f32,
    /// Dry blend applied by transient handling this frame (0 = fully mapped,
    /// 1 = fully dry / hard reset).
    pub transient: f32,
    /// Active target grid (bit per MIDI note).
    pub grid_mask: u128,
    /// Total mid-spectrum magnitude.
    pub in_energy: f32,
    /// Magnitude in regions no pitch object claimed (the residual layer).
    pub res_energy: f32,
    /// Residual magnitude by octave band (C0..C8 at index 0..=7; band 7
    /// collects everything above). All zero on non-mapped frames.
    pub res_bands: [f32; 8],
    /// The scope: the mid input spectrum and the mid output (synthesis)
    /// spectrum on a pitch axis, peak level per bin ([`scope_db`]).
    pub scope_in: [u8; SCOPE_BINS],
    pub scope_out: [u8; SCOPE_BINS],
    /// Valid entries in `tracks`.
    pub n: u8,
    pub tracks: [VizTrack; VIZ_TRACKS],
}

impl Default for VizFrame {
    fn default() -> Self {
        Self {
            t: 0,
            flux: 0.0,
            transient: 0.0,
            grid_mask: 0,
            in_energy: 0.0,
            res_energy: 0.0,
            res_bands: [0.0; 8],
            scope_in: [0; SCOPE_BINS],
            scope_out: [0; SCOPE_BINS],
            n: 0,
            tracks: [VizTrack::default(); VIZ_TRACKS],
        }
    }
}

/// Zero-phase Hann window spectrum at fractional bin offset, W(0)=1.
fn hann_kernel(x: f64, n_fft: usize) -> f64 {
    let nf = n_fft as f64;
    let diric = |u: f64| -> f64 {
        let den = nf * (PI * u / nf).sin();
        if den.abs() < 1e-12 {
            1.0
        } else {
            (PI * u).sin() / den
        }
    };
    diric(x) + 0.5 * (diric(x - 1.0) + diric(x + 1.0))
}

/// Deterministic static decorrelation offset in [-1, 1] for (note, channel).
fn decor_offset(ni: usize, ch: usize) -> f64 {
    let h = (ni as u64)
        .wrapping_mul(0x9E3779B97F4A7C15)
        .wrapping_add((ch as u64).wrapping_mul(0xD1B54A32D192ED03));
    ((h >> 40) as f64 / (1u64 << 24) as f64) * 2.0 - 1.0
}

pub struct Engine {
    sr: f64,
    channels: usize,
    n_fft: usize,
    hop: usize,
    bins: usize,
    /// The streaming frame (audiokit): framing, Hann analysis and
    /// synthesis, overlap-add. Home between blocks; taken out while a
    /// block runs so its hop callback can borrow the engine.
    stft: Option<Stft<f64>>,
    /// One sample per channel in and out of the frame.
    sample_in: Vec<f64>,
    sample_out: Vec<f64>,
    dry_fifo: Vec<VecDeque<f64>>,
    // per-channel spectra
    spec: Vec<Vec<Complex64>>,
    phi: Vec<Vec<f64>>,
    magc: Vec<Vec<f64>>,
    ysyn: Vec<Vec<Complex64>>,
    // mid (decision) spectrum
    mag: Vec<f64>,
    phim: Vec<f64>,
    f_true: Vec<f64>,
    prev_phi: Vec<f64>,
    prev_mag_store: Vec<f64>,
    prev_mag_sum: f64,
    first_frame: bool,
    frame_idx: i64,
    // synthesis state (shared across channels)
    note_phase: [f64; 128],
    note_seen: [i64; 128],
    note_ft: [f64; 128],
    /// smoothed recovered-region amplitude per output note (~150 ms EMA):
    /// persistence is what makes PURIFY's recovery read as resonance
    /// rather than flicker
    note_recov: [f64; 128],
    tracks: Vec<Track>,
    // scratch
    fft_s: Arc<dyn RealToComplex<f64>>,
    fft_s_in: Vec<f64>,
    fft_s_scratch: Vec<Complex64>,
    spec_s: Vec<Complex64>,
    mag_s: Vec<f64>,
    win_s: Vec<f64>,
    env: Vec<f64>,
    env_tmp: Vec<f64>,
    grid: Vec<f64>,
    grid_mask: u128,
    prev_grid_mask: u128,
    // the per-frame pitch analysis (audiokit) and its inputs and outputs
    peaks: pitch::Peaks,
    multi_f0: pitch::MultiF0,
    seeds: Vec<f64>,
    obj_mult: Vec<f64>,
    obj_trk: Vec<usize>,
    obj_spared: Vec<bool>,
    // analysis feed for the GUI (all fixed-capacity; no allocation in process)
    next_uid: i64,
    viz_ring: VecDeque<VizFrame>,
    viz_amp: Vec<f64>,
    viz_nh: Vec<u16>,
    viz_mult: Vec<f64>,
    viz_spared: Vec<bool>,
    viz_hmask: Vec<u64>,
    viz_res: f64,
    viz_res_bands: [f64; 8],
    /// Per scope bin, the FFT bins it covers (`lo..hi`), or when it is
    /// narrower than one, the fractional bin it samples between two.
    scope_bins: Vec<(usize, usize, f64)>,
    viz_scope_in: [u8; SCOPE_BINS],
    viz_scope_out: [u8; SCOPE_BINS],
}

impl Engine {
    pub fn new(sr: f64, channels: usize) -> Self {
        Self::new_sized(sr, channels, N_FFT, HOP)
    }

    /// `hop` must be `n_fft / 4` (the COLA factor assumes 75% overlap).
    pub fn new_sized(sr: f64, channels: usize, n_fft: usize, hop: usize) -> Self {
        assert!(hop * 4 == n_fft, "hop must be n_fft/4");
        let channels = channels.max(1);
        let bins = n_fft / 2 + 1;
        let mut planner = RealFftPlanner::<f64>::new();
        let n_s = n_fft / 4; // short (amplitude) window
        let fft_s = planner.plan_fft_forward(n_s);
        let fft_s_scratch = fft_s.make_scratch_vec();
        let win_s: Vec<f64> = (0..n_s)
            .map(|n| 0.5 - 0.5 * (TWO_PI * n as f64 / (n_s as f64 - 1.0)).cos())
            .collect();
        let win: Vec<f64> = (0..n_fft)
            .map(|n| 0.5 - 0.5 * (TWO_PI * n as f64 / (n_fft as f64 - 1.0)).cos())
            .collect();
        let zc = || vec![Complex64::new(0.0, 0.0); bins];
        // Hann/Hann at 75% overlap: hann² sums to 1.5. The wet latency is
        // exactly n_fft (PITCHMAP's 4096), which host PDC relies on.
        let stft = Stft::new(&mut planner, channels, win.clone(), win, hop, 1.5, n_fft);
        let mut e = Self {
            sr,
            channels,
            n_fft,
            hop,
            bins,
            stft: Some(stft),
            sample_in: vec![0.0; channels],
            sample_out: vec![0.0; channels],
            dry_fifo: vec![VecDeque::with_capacity(2 * n_fft); channels],
            spec: vec![zc(); channels],
            phi: vec![vec![0.0; bins]; channels],
            magc: vec![vec![0.0; bins]; channels],
            ysyn: vec![zc(); channels],
            mag: vec![0.0; bins],
            phim: vec![0.0; bins],
            f_true: vec![0.0; bins],
            prev_phi: vec![0.0; bins],
            prev_mag_store: vec![0.0; bins],
            prev_mag_sum: -1.0,
            first_frame: true,
            frame_idx: 0,
            note_phase: [0.0; 128],
            note_seen: [-2; 128],
            note_ft: [0.0; 128],
            note_recov: [0.0; 128],
            tracks: Vec::with_capacity(TRACKS),
            fft_s,
            fft_s_in: vec![0.0; n_fft / 4],
            fft_s_scratch,
            spec_s: vec![Complex64::new(0.0, 0.0); n_fft / 8 + 1],
            mag_s: vec![0.0; n_fft / 8 + 1],
            win_s,
            env: vec![0.0; bins],
            env_tmp: vec![0.0; bins],
            grid: Vec::with_capacity(128),
            grid_mask: 0,
            prev_grid_mask: 0,
            peaks: pitch::Peaks::new(bins),
            multi_f0: pitch::MultiF0::new(sr, bins / 2 + 1, MAX_VOICES),
            seeds: Vec::with_capacity(TRACKS),
            obj_mult: Vec::with_capacity(MAX_VOICES),
            obj_trk: Vec::with_capacity(MAX_VOICES),
            obj_spared: Vec::with_capacity(MAX_VOICES),
            next_uid: 0,
            viz_ring: VecDeque::with_capacity(VIZ_RING),
            viz_amp: Vec::with_capacity(64),
            viz_nh: Vec::with_capacity(64),
            viz_mult: Vec::with_capacity(64),
            viz_spared: Vec::with_capacity(64),
            viz_hmask: Vec::with_capacity(64),
            viz_res: 0.0,
            viz_res_bands: [0.0; 8],
            scope_bins: (0..SCOPE_BINS)
                .map(|b| {
                    let bin_of = |note: f32| midi_freq(note as f64) * n_fft as f64 / sr;
                    let half = 0.5 / SCOPE_PER_NOTE as f32;
                    let (lo, hi) = (bin_of(scope_note(b) - half), bin_of(scope_note(b) + half));
                    let (lo, hi) = (lo.ceil() as usize, (hi.ceil() as usize).min(bins));
                    (lo.min(hi), hi, bin_of(scope_note(b)))
                })
                .collect(),
            viz_scope_in: [0; SCOPE_BINS],
            viz_scope_out: [0; SCOPE_BINS],
        };
        e.reset();
        e
    }

    pub fn reset(&mut self) {
        // The frame primes its wet path to exactly n_fft of latency; the
        // dry path matches it.
        if let Some(stft) = &mut self.stft {
            stft.reset();
        }
        for c in 0..self.channels {
            self.dry_fifo[c].clear();
            for _ in 0..self.n_fft {
                self.dry_fifo[c].push_back(0.0);
            }
        }
        self.prev_phi.iter_mut().for_each(|v| *v = 0.0);
        self.prev_mag_sum = -1.0;
        self.first_frame = true;
        self.frame_idx = 0;
        self.note_phase = [0.0; 128];
        self.note_seen = [-2; 128];
        self.tracks.clear();
        self.viz_ring.clear();
    }

    pub fn latency_samples(&self) -> usize {
        self.n_fft
    }

    /// Drains the oldest buffered analysis frame, if any. Call repeatedly
    /// after `process_block` to feed a display; frames beyond [`VIZ_RING`]
    /// are dropped oldest-first while unread.
    pub fn viz_pop(&mut self) -> Option<VizFrame> {
        self.viz_ring.pop_front()
    }

    /// The scope's two traces for this frame: the mid input spectrum and
    /// the mid of what synthesis made of it, each bin's peak in dB of a
    /// full-scale sine (a Hann window's peak is a quarter of the frame).
    fn measure_scope(&mut self) {
        let full_scale = self.n_fft as f64 / 4.0;
        let level = |magnitude: f64| -> u8 {
            let db = 20.0 * (magnitude / full_scale).max(1e-12).log10();
            ((db - SCOPE_DB_FLOOR as f64) * 2.0).round().clamp(0.0, 255.0) as u8
        };
        let nch = self.channels as f64;
        let out_mag = |ysyn: &[Vec<Complex64>], k: usize| -> f64 {
            ysyn.iter().map(|spectrum| spectrum[k]).sum::<Complex64>().norm() / nch
        };
        for (b, &(lo, hi, centre)) in self.scope_bins.iter().enumerate() {
            let (input, output) = if lo < hi {
                (lo..hi).fold((0.0f64, 0.0f64), |(i, o), k| {
                    (i.max(self.mag[k]), o.max(out_mag(&self.ysyn, k)))
                })
            } else if centre + 1.0 < self.bins as f64 {
                // Narrower than a bin: between its two neighbours.
                let k = centre as usize;
                let a = centre - k as f64;
                let between = |m0: f64, m1: f64| m0 + (m1 - m0) * a;
                (
                    between(self.mag[k], self.mag[k + 1]),
                    between(out_mag(&self.ysyn, k), out_mag(&self.ysyn, k + 1)),
                )
            } else {
                // Above Nyquist.
                self.viz_scope_in[b] = 0;
                self.viz_scope_out[b] = 0;
                continue;
            };
            self.viz_scope_in[b] = level(input);
            self.viz_scope_out[b] = level(output);
        }
    }

    fn push_viz_frame(&mut self, t: i64, flux: f64, transient: f32, mapped: bool, mag_sum: f64) {
        let mut frame = VizFrame {
            t,
            flux: if flux.is_finite() { flux as f32 } else { 99.0 },
            transient,
            grid_mask: self.grid_mask,
            in_energy: mag_sum as f32,
            // on non-mapped frames everything is residual (dry or silent)
            res_energy: if mapped { self.viz_res as f32 } else { mag_sum as f32 },
            res_bands: if mapped {
                std::array::from_fn(|i| self.viz_res_bands[i] as f32)
            } else {
                [0.0; 8]
            },
            scope_in: self.viz_scope_in,
            scope_out: self.viz_scope_out,
            n: 0,
            tracks: [VizTrack::default(); VIZ_TRACKS],
        };
        if mapped {
            let mut n = 0usize;
            for (ti, trk) in self.tracks.iter().enumerate() {
                if trk.seen != t || n == VIZ_TRACKS {
                    continue;
                }
                frame.tracks[n] = VizTrack {
                    id: trk.uid,
                    f0: trk.f0 as f32,
                    tgt: trk.tgt as f32,
                    out: (trk.f0 * self.viz_mult.get(ti).copied().unwrap_or(1.0)) as f32,
                    amp: self.viz_amp.get(ti).copied().unwrap_or(0.0) as f32,
                    nh: self.viz_nh.get(ti).copied().unwrap_or(0),
                    hmask: self.viz_hmask.get(ti).copied().unwrap_or(0),
                    spared: self.viz_spared.get(ti).copied().unwrap_or(false),
                    newborn: t - trk.born < 2,
                };
                n += 1;
            }
            frame.n = n as u8;
        }
        if self.viz_ring.len() == VIZ_RING {
            self.viz_ring.pop_front();
        }
        self.viz_ring.push_back(frame);
    }

    /// Process channel slices in place. All slices must be equal length.
    /// `held[n]` = MIDI note n currently held.
    pub fn process_block(
        &mut self,
        io: &mut [&mut [f32]],
        held: &[bool; 128],
        p: &EngineParams,
    ) {
        let ch = self.channels.min(io.len());
        let len = if ch > 0 { io[0].len() } else { return };
        let mut stft = self.stft.take().expect("the frame is home between blocks");
        let mut input = std::mem::take(&mut self.sample_in);
        let mut output = std::mem::take(&mut self.sample_out);
        for i in 0..len {
            for c in 0..ch {
                let x = io[c][i] as f64;
                self.dry_fifo[c].push_back(x);
                input[c] = x;
            }
            stft.process_sample(&input, &mut output, |hop| self.run_frame(hop, held, p));
            for c in 0..ch {
                let wet = output[c];
                let dry = self.dry_fifo[c].pop_front().unwrap_or(0.0);
                io[c][i] = (p.mix * wet + (1.0 - p.mix) * dry) as f32;
            }
        }
        self.stft = Some(stft);
        self.sample_in = input;
        self.sample_out = output;
    }

    fn build_grid(&mut self, held: &[bool; 128], mode: Mode) {
        self.grid.clear();
        self.grid_mask = held
            .iter()
            .enumerate()
            .filter(|(_, &h)| h)
            .fold(0u128, |m, (n, _)| m | (1u128 << n))
            | (if mode == Mode::Repeat { 1u128 << 127 } else { 0 });
        match mode {
            Mode::Custom => {
                for n in 0..128usize {
                    if held[n] {
                        self.grid.push(midi_freq(n as f64));
                    }
                }
            }
            Mode::Repeat => {
                let mut pcs = [false; 12];
                let mut any = false;
                for n in 0..128usize {
                    if held[n] {
                        pcs[n % 12] = true;
                        any = true;
                    }
                }
                if any {
                    for n in 0..128usize {
                        if pcs[n % 12] {
                            self.grid.push(midi_freq(n as f64));
                        }
                    }
                }
            }
        }
    }

    fn nearest_grid(&self, f: f64) -> f64 {
        let lf = f.ln();
        let mut best = self.grid[0];
        let mut bd = f64::INFINITY;
        for &g in &self.grid {
            let d = (g.ln() - lf).abs();
            if d < bd {
                bd = d;
                best = g;
            }
        }
        best
    }

    /// One hop: the frame has analyzed every channel; decide, map, and
    /// leave each channel's resynthesis spectrum in the hop.
    fn run_frame(&mut self, hop: &mut Hop<'_, f64>, held: &[bool; 128], p: &EngineParams) {
        let t = self.frame_idx;
        self.frame_idx += 1;
        let bin_hz = self.sr / self.n_fft as f64;
        let nch = self.channels;

        // per-channel spectra (the frame's Hann-windowed FFTs)
        for c in 0..nch {
            self.spec[c].copy_from_slice(hop.spectrum(c));
            for k in 0..self.bins {
                self.magc[c][k] = self.spec[c][k].norm();
                self.phi[c][k] = self.spec[c][k].arg();
            }
        }
        // short-window (n_fft/4) magnitudes centered on the frame center:
        // amplitude with ~4x better time resolution than the long window
        // (fixes onset smear: stamped amps otherwise rise over the whole
        // window). Frequency/phase still come from the long window.
        {
            let n_s = self.n_fft / 4;
            let c0 = self.n_fft / 2 - n_s / 2;
            for n in 0..n_s {
                let mut acc = 0.0;
                for c in 0..nch {
                    acc += hop.frame(c)[c0 + n];
                }
                self.fft_s_in[n] = acc / nch as f64 * self.win_s[n];
            }
            self.fft_s
                .process_with_scratch(&mut self.fft_s_in, &mut self.spec_s, &mut self.fft_s_scratch)
                .expect("fft_s");
            for k in 0..self.spec_s.len() {
                self.mag_s[k] = self.spec_s[k].norm();
            }
        }

        // mid (decision) spectrum: complex channel average
        let mut mag_sum = 0.0;
        for k in 0..self.bins {
            let mut acc = Complex64::new(0.0, 0.0);
            for c in 0..nch {
                acc += self.spec[c][k];
            }
            acc /= nch as f64;
            self.mag[k] = acc.norm();
            self.phim[k] = acc.arg();
            mag_sum += self.mag[k];
        }

        // instantaneous frequency (mid) via phase differences
        let previous = (!self.first_frame).then_some(&self.prev_phi[..]);
        pitch::instantaneous_frequency(
            &self.phim,
            previous,
            self.hop,
            self.n_fft,
            self.sr,
            &mut self.f_true,
        );
        self.prev_phi.copy_from_slice(&self.phim);

        // spectral flux onset detector (mid)
        let flux = if self.prev_mag_sum < 0.0 {
            f64::INFINITY
        } else {
            let mut pos = 0.0;
            for k in 0..self.bins {
                let d = self.mag[k] - self.prev_mag_store[k];
                if d > 0.0 {
                    pos += d;
                }
            }
            pos / (self.prev_mag_sum + 1e-12)
        };
        // soft transient handling: moderate onsets crossfade toward dry
        // while the mapped state keeps running underneath (no reset —
        // hard swaps at frame edges read as choppiness); only STRONG
        // onsets reset synthesis state (and thereby retrigger glide)
        // purify raises the hard-reset bar: high purify trades transient
        // fidelity for sustained tone (the reference's documented tradeoff),
        // letting dense percussive material recover onto the grid instead
        // of resetting analysis every frame
        let hard_transient =
            p.transient_bypass && flux > 3.0 * p.flux_thresh * (1.0 + 3.0 * p.purify);

        self.build_grid(held, p.mode);

        let mut viz_transient = 0.0f32;
        let mut viz_mapped = false;
        if self.grid.is_empty() {
            self.note_seen = [-2; 128];
            self.tracks.clear();
            for c in 0..nch {
                self.ysyn[c].iter_mut().for_each(|v| *v = Complex64::new(0.0, 0.0));
            }
        } else if hard_transient || self.first_frame {
            self.note_seen = [-2; 128];
            self.tracks.clear();
            // purify fades even the hard-transient dry pass (the analysis
            // reset above still happens; only the audio thins)
            let g = 1.0 - p.purify;
            for c in 0..nch {
                if p.purify > 0.0 {
                    for k in 0..self.bins {
                        self.ysyn[c][k] = g * self.spec[c][k];
                    }
                } else {
                    self.ysyn[c].copy_from_slice(&self.spec[c]);
                }
            }
            viz_transient = g as f32;
        } else {
            self.map_frame(t, p, bin_hz);
            viz_mapped = true;
            if p.transient_bypass && flux > p.flux_thresh {
                let a = (flux / p.flux_thresh - 1.0).min(1.0) * (1.0 - p.purify);
                viz_transient = a as f32;
                for c in 0..nch {
                    for k in 0..self.bins {
                        self.ysyn[c][k] =
                            a * self.spec[c][k] + (1.0 - a) * self.ysyn[c][k];
                    }
                }
            }
        }
        self.measure_scope();
        self.push_viz_frame(t, flux, viz_transient, viz_mapped, mag_sum);
        self.first_frame = false;
        self.prev_grid_mask = self.grid_mask;
        // store AFTER map_frame so the per-region attack detector compares
        // against the actual previous frame
        self.prev_mag_store.copy_from_slice(&self.mag);
        self.prev_mag_sum = mag_sum;

        // hand each channel's synthesis spectrum back: the frame inverts,
        // windows, overlap-adds and divides by the hann² sum (1.5)
        for c in 0..nch {
            hop.spectrum_mut(c).copy_from_slice(&self.ysyn[c]);
        }
    }

    /// Smoothed spectral envelope of the mid spectrum (formant reference):
    /// 3x box blur of LINEAR magnitude (~41 bins ≈ 480 Hz @48k) — linear
    /// domain so partial energy dominates, not the -180 dB valleys — then
    /// stored as log for cheap ratio math.
    fn compute_envelope(&mut self) {
        const W: usize = 10; // half-width (~245 Hz/pass: resolves
        // formant-scale bumps while bridging harmonic spacing)
        self.env.copy_from_slice(&self.mag);
        for _ in 0..3 {
            let mut acc = 0.0;
            for k in 0..self.bins {
                acc += self.env[k];
                self.env_tmp[k] = acc;
            }
            for k in 0..self.bins {
                let lo = k.saturating_sub(W);
                let hi = (k + W).min(self.bins - 1);
                let sum = self.env_tmp[hi]
                    - if lo > 0 { self.env_tmp[lo - 1] } else { 0.0 };
                self.env[k] = sum / (hi - lo + 1) as f64;
            }
        }
        for k in 0..self.bins {
            self.env[k] = (self.env[k] + 1e-12).ln();
        }
    }

    fn env_at(&self, f: f64, bin_hz: f64) -> f64 {
        let b = (f / bin_hz).clamp(0.0, (self.bins - 2) as f64);
        let k = b as usize;
        let fr = b - k as f64;
        self.env[k] * (1.0 - fr) + self.env[k + 1] * fr
    }

    fn map_frame(&mut self, t: i64, p: &EngineParams, bin_hz: f64) {
        let nch = self.channels;
        // drop stale tracks first so indices stay valid through synthesis
        self.tracks.retain(|trk| trk.seen >= t - 1);
        self.peaks.find(&self.mag);
        if p.formant > 0.0 {
            self.compute_envelope();
        }
        self.seeds.clear();
        self.seeds.extend(self.tracks.iter().map(|trk| trk.f0));
        self.multi_f0.analyze(
            self.peaks.peaks(),
            &self.f_true,
            &self.mag,
            p.voices.max(1),
            &self.seeds,
        );
        let n_obj = self.multi_f0.f0s().len();

        // ---- M3: match objects to tracks ----
        // micro-glide floor (~1.5 frames): even at Glide=0, target changes
        // ramp over ~30 ms so the OLA doesn't tear on a hard retune jump
        let glide_frames = (p.glide * self.sr / self.hop as f64).max(1.5);
        let ema_a = 1.0 - (-(self.hop as f64 / self.sr) / 0.25).exp();
        let hyst = p.hyst_cents / 1200.0 * 2f64.ln();
        let match_tol = 2f64.ln() * 100.0 / 1200.0;
        self.obj_mult.clear();
        self.obj_trk.clear();
        self.obj_spared.clear();
        for oi in 0..n_obj {
            let f0 = self.multi_f0.f0s()[oi];
            let mut best: Option<usize> = None;
            let mut bestd = match_tol;
            for (ti, trk) in self.tracks.iter().enumerate() {
                if trk.seen == t {
                    continue;
                }
                let dd = (f0 / trk.f0).ln().abs();
                if dd < bestd {
                    bestd = dd;
                    best = Some(ti);
                }
            }
            let mut tgt = self.nearest_grid(f0);
            if p.rounding == Rounding::Intelligent {
                if let Some(ti) = best {
                    let old = self.tracks[ti].tgt;
                    let in_grid =
                        self.grid.iter().any(|&g| ((g / old).ln()).abs() < 1e-9);
                    if in_grid && (f0 / old).ln().abs() < (f0 / tgt).ln().abs() + hyst {
                        tgt = old;
                    }
                }
            }
            let ti = match best {
                None => {
                    let uid = self.next_uid;
                    self.next_uid += 1;
                    self.tracks.push(Track {
                        uid,
                        f0,
                        lema: f0.ln(),
                        tgt,
                        r_from: 0.0, // birth: glide starts at SOURCE pitch
                        g0: t,
                        seen: t,
                        born: t,
                        cand: tgt,
                        cand_n: 0,
                        phases: [(0.0, -2, 0.0); MAX_H + 1],
                    });
                    self.tracks.len() - 1
                }
                Some(ti) => {
                    let trk = &mut self.tracks[ti];
                    let r_old = (trk.tgt / trk.f0).ln();
                    let r_now = if glide_frames > 0.0 {
                        let prog = ((t - trk.g0) as f64 / glide_frames).min(1.0);
                        trk.r_from + (r_old - trk.r_from) * prog
                    } else {
                        r_old
                    };
                    if (tgt / trk.tgt).ln().abs() > 1e-6 {
                        // retarget DEBOUNCE: source-motion-driven target
                        // changes must persist 3 frames (~64 ms) before
                        // committing — a singer's portamento no longer
                        // drags the output through intermediate targets.
                        // MIDI-driven changes commit instantly.
                        let grid_changed = self.grid_mask != self.prev_grid_mask;
                        let same_cand = (tgt / trk.cand).ln().abs() < 1e-6;
                        if same_cand {
                            trk.cand_n += 1;
                        } else {
                            trk.cand = tgt;
                            trk.cand_n = 1;
                        }
                        if grid_changed || trk.cand_n >= 3 {
                            trk.r_from = if p.algorithm == Algorithm::Oracle {
                                // Oracle glide is onset-only portamento
                                // (measured: j24≡j30) — retargets land
                                // instantly, births still ramp
                                (tgt / f0).ln()
                            } else {
                                r_now
                            };
                            trk.g0 = t;
                            trk.tgt = tgt;
                            trk.cand_n = 0;
                        } else {
                            tgt = trk.tgt; // hold current target for now
                        }
                    } else {
                        trk.cand = tgt;
                        trk.cand_n = 0;
                    }
                    trk.f0 = f0;
                    trk.lema += ema_a * (f0.ln() - trk.lema);
                    trk.seen = t;
                    ti
                }
            };
            let trk = &self.tracks[ti];
            // THRESHOLD: bypass objects already in tune with their own
            // (untransposed) chromatic pitch — PITCHMAP non-global flavor
            let mut bypass = false;
            if p.threshold_cents > 0.0 {
                let cents = 1200.0 / 2f64.ln();
                let f_chrom =
                    midi_freq((69.0 + 12.0 * (trk.f0 / 440.0).log2()).round());
                let in_tune = (trk.f0 / f_chrom).ln().abs() * cents < p.threshold_cents;
                let untransposed = (trk.tgt / f_chrom).ln().abs() * cents < 1.0;
                bypass = in_tune && untransposed;
            }
            // Per-key Bypass: the source's own nearest note passes unbent.
            if p.bypass_keys != 0 {
                let note = (69.0 + 12.0 * (trk.f0 / 440.0).log2()).round();
                if (0.0..128.0).contains(&note) && p.bypass_keys >> note as u32 & 1 == 1 {
                    bypass = true;
                }
            }
            let r_to = (trk.tgt / trk.f0).ln();
            let r_eff = if glide_frames > 0.0 {
                let prog = ((t - trk.g0) as f64 / glide_frames).min(1.0);
                trk.r_from + (r_to - trk.r_from) * prog
            } else {
                r_to
            };
            let dev = if p.algorithm == Algorithm::Oracle {
                // belief re-injection (the ORACLE feel law, research 04):
                // the tracker's whole believed deviation from the source's
                // own chromatic pitch, statics included, linear in cents
                let f_chrom = midi_freq((69.0 + 12.0 * (trk.f0 / 440.0).log2()).round());
                trk.f0.ln() - f_chrom.ln()
            } else {
                trk.f0.ln() - trk.lema // micro-variation about the track EMA
            };
            self.obj_mult.push(if bypass {
                1.0
            } else {
                (r_eff + p.feel * dev).exp()
            });
            self.obj_trk.push(ti);
            self.obj_spared.push(bypass);
        }

        // reset per-frame viz accumulators (capacity preallocated; track
        // count is bounded by ~2x voices, far below the reserved 64)
        self.viz_amp.clear();
        self.viz_amp.resize(self.tracks.len(), 0.0);
        self.viz_nh.clear();
        self.viz_nh.resize(self.tracks.len(), 0);
        self.viz_mult.clear();
        self.viz_mult.resize(self.tracks.len(), 1.0);
        self.viz_spared.clear();
        self.viz_spared.resize(self.tracks.len(), false);
        self.viz_hmask.clear();
        self.viz_hmask.resize(self.tracks.len(), 0);
        for (i, &ti) in self.obj_trk.iter().enumerate() {
            self.viz_mult[ti] = self.obj_mult[i];
            self.viz_spared[ti] = self.obj_spared[i];
        }
        self.viz_res = 0.0;
        self.viz_res_bands = [0.0; 8];

        // ---- region mapping decisions + per-channel synthesis ----
        for c in 0..nch {
            self.ysyn[c]
                .iter_mut()
                .for_each(|v| *v = Complex64::new(0.0, 0.0));
        }
        let gate = p.tonality_gate;
        let decor_amt = (1.0 - p.coherence).clamp(0.0, 1.0) * PI;
        let n_regions = self.peaks.peaks().len();
        for i in 0..n_regions {
            let pk = self.peaks.peaks()[i];
            let (lo, hi) = self.peaks.regions()[i];
            let owner = self.multi_f0.owner()[i];
            let fp = self.f_true[pk];
            let mut trk_idx: Option<usize> = None;
            let mut h = 0usize;
            let df;
            let mut noisy = false;
            let mut discard = false;
            let mut region_gain = 1.0f64;
            let mut recover = false;
            if owner >= 0 {
                let oi = owner as usize;
                let trk = &self.tracks[self.obj_trk[oi]];
                if t - trk.born < 2 && p.newborn == Newborn::Dry {
                    df = 0.0; // transitions pass at source pitch
                } else {
                    df = fp * (self.obj_mult[oi] - 1.0);
                }
                h = ((fp / trk.f0).round() as i64).max(1) as usize;
                trk_idx = Some(self.obj_trk[oi]);
            } else {
                // unowned region. The valve chooses its fate (House:
                // carry vs map; Oracle: discard vs map) — and PURIFY
                // pulls it toward the grid regardless: recovery, the
                // residual re-pitched rather than merely removed.
                // Beyond the law's reach (floor/ceiling) content always
                // passes; a tonality gate in Bypass is explicit mercy.
                let mut mappable = fp > 30.0 && fp < self.sr / 2.0 * 0.95;
                if p.fmax_map.is_finite() {
                    mappable = mappable && fp <= p.fmax_map;
                }
                if mappable && gate > 0.0 {
                    let mean =
                        self.mag[lo..hi].iter().sum::<f64>() / (hi - lo).max(1) as f64;
                    let peakiness = self.mag[pk] / (mean + 1e-12);
                    noisy = peakiness < gate;
                    if noisy && p.tonality_mode == TonalityMode::Bypass {
                        mappable = false;
                    }
                }
                if p.unowned == Unowned::Map {
                    df = if mappable {
                        self.nearest_grid(fp) - fp
                    } else {
                        0.0
                    };
                } else if mappable && p.purify > 0.0 {
                    // crossfade carry -> recovered-to-grid (Oracle
                    // carries no dry share; its remainder is discarded)
                    let dry_g = if p.algorithm == Algorithm::Oracle {
                        0.0
                    } else {
                        1.0 - p.purify
                    };
                    if dry_g > 0.0 {
                        for c in 0..nch {
                            for k in lo..hi {
                                self.ysyn[c][k] += dry_g * self.spec[c][k];
                            }
                        }
                    }
                    region_gain = p.purify;
                    recover = true;
                    df = self.nearest_grid(fp) - fp;
                } else {
                    df = 0.0;
                    discard = mappable && p.algorithm == Algorithm::Oracle;
                }
            }
            if h > MAX_H {
                trk_idx = None;
            }
            match trk_idx {
                Some(ti) => {
                    self.viz_amp[ti] += self.mag[pk];
                    self.viz_nh[ti] += 1;
                    if h >= 1 {
                        self.viz_hmask[ti] |= 1u64 << (h - 1).min(63);
                    }
                }
                None => {
                    self.viz_res += self.mag[pk];
                    // octave band of the region's dominant partial (C0 base)
                    let band = if fp > 16.35 {
                        ((fp / 16.35).log2() as usize).min(7)
                    } else {
                        0
                    };
                    self.viz_res_bands[band] += self.mag[pk];
                }
            }

            if discard {
                continue; // Oracle: the remainder is not carried
            }
            let dbin = (df / bin_hz).round() as i64;
            let clo = (lo as i64 + dbin).max(1) as usize;
            let chi = ((hi as i64 + dbin).min(self.bins as i64 - 1)) as usize;
            if chi <= clo {
                continue;
            }
            if df == 0.0 {
                for c in 0..nch {
                    for k in clo..chi {
                        self.ysyn[c][k] += self.spec[c][k]; // verbatim dry
                    }
                }
                continue;
            }
            if noisy {
                // mapped noise: per-channel fresh phases + shared ramp
                let ramp =
                    TWO_PI * df * (t as f64 * self.hop as f64) / self.sr + PI * dbin as f64;
                for c in 0..nch {
                    for k in clo..chi {
                        let sk = (k as i64 - dbin) as usize;
                        self.ysyn[c][k] += Complex64::from_polar(
                            region_gain * self.magc[c][sk],
                            self.phi[c][sk] + ramp,
                        );
                    }
                }
                continue;
            }
            // stamped tonal partial: shared accumulator, per-channel
            // amplitude and analysis-phase offset (image preservation)
            let ft = fp + df;
            let dsrc = fp / bin_hz - pk as f64;
            let mut ker_src = hann_kernel(dsrc, self.n_fft).max(0.1);
            // dual-window amplitude: ratio of short-window to long-window
            // partial amplitude (scale-calibrated x4), clamped
            {
                let n_s = self.n_fft / 4;
                let bin_s = fp / (self.sr / n_s as f64);
                let ks = bin_s.round() as usize;
                if fp > 100.0 && ks >= 1 && ks + 1 < self.mag_s.len() {
                    let amp_l = self.mag[pk] / ker_src;
                    let ker_s = hann_kernel(bin_s - ks as f64, n_s).max(0.1);
                    let amp_s = 4.0 * self.mag_s[ks] / ker_s;
                    let r = (amp_s / amp_l.max(1e-9)).clamp(0.25, 4.0);
                    ker_src /= r; // amp_c = mag/ker_src, so /r boosts by r
                }
            }
            // formant preservation: correct amplitude by the source
            // envelope evaluated at the OUTPUT vs SOURCE frequency
            let formant_gain = if p.formant > 0.0 {
                let d_env = (self.env_at(ft, bin_hz) - self.env_at(fp, bin_hz))
                    .clamp(-2.77, 2.77); // +-24 dB safety
                (d_env * p.formant).exp()
            } else {
                1.0
            };
            let anchor = self.phim[pk] - PI * dsrc;
            let ni = ((69.0 + 12.0 * (ft / 440.0).log2()).round() as i64).clamp(0, 127)
                as usize;
            // recovered regions: whole-region energy, smoothed per note
            let recov_mid = if recover {
                let mut e = 0.0;
                for k in lo..hi {
                    e += self.mag[k] * self.mag[k];
                }
                let rss = e.sqrt();
                let prev = if self.note_seen[ni] >= t - 1 {
                    self.note_recov[ni]
                } else {
                    rss
                };
                let ema = prev + 0.15 * (rss - prev);
                self.note_recov[ni] = ema;
                Some((ema, rss.max(1e-12)))
            } else {
                None
            };
            let phv = if let Some(ti) = trk_idx {
                let trk = &mut self.tracks[ti];
                let (ph0, seen, ft_prev) = trk.phases[h];
                let (phv, ft_store) = if seen == t {
                    (ph0, ft_prev) // duplicate h this frame: keep first
                } else if seen == t - 1 {
                    // trapezoidal (chirp-consistent) phase integration
                    (ph0 + TWO_PI * 0.5 * (ft_prev + ft) * self.hop as f64 / self.sr, ft)
                } else {
                    (anchor, ft)
                };
                trk.phases[h] = (phv, t, ft_store);
                phv
            } else {
                if self.note_seen[ni] == t {
                    // already advanced this frame
                } else if self.note_seen[ni] == t - 1 {
                    self.note_phase[ni] += TWO_PI * 0.5 * (self.note_ft[ni] + ft)
                        * self.hop as f64 / self.sr;
                    self.note_ft[ni] = ft;
                } else {
                    self.note_phase[ni] = anchor;
                    self.note_ft[ni] = ft;
                }
                self.note_seen[ni] = t;
                self.note_phase[ni]
            };
            if p.grit > 0.0 {
                let ramp =
                    TWO_PI * df * (t as f64 * self.hop as f64) / self.sr + PI * dbin as f64;
                for c in 0..nch {
                    for k in clo..chi {
                        let sk = (k as i64 - dbin) as usize;
                        self.ysyn[c][k] += Complex64::from_polar(
                            p.grit * self.magc[c][sk],
                            self.phi[c][sk] + ramp,
                        );
                    }
                }
            }
            // carry the region's NON-mainlobe bins verbatim at source
            // position: onset/noise energy living between partials
            // otherwise vanishes entirely (measured as ~25 dB "attack
            // holes" at note starts — the batch-011 choppiness)
            let carry_g = p.carry * (1.0 - p.purify);
            if carry_g > 0.0 {
                for c in 0..nch {
                    for k in lo..hi {
                        if (k as i64 - pk as i64).unsigned_abs() as usize > 4 {
                            self.ysyn[c][k] += carry_g * self.spec[c][k];
                        }
                    }
                }
            }
            let b = ft / bin_hz;
            let k0 = ((b - 4.0).ceil() as i64).max(1) as usize;
            let k1 = ((b + 4.0).floor() as i64).min(self.bins as i64 - 2) as usize;
            for c in 0..nch {
                // channel's own level + phase offset from the mid reference.
                // Recovered regions concentrate: the WHOLE region's energy
                // (RSS) lands in the stamped line — the reference's additive
                // band-bunching, energy-conserving flavor (no gain bloom)
                let amp_c = if let Some((ema, rss_mid)) = recov_mid {
                    let mut e = 0.0;
                    for k in lo..hi {
                        e += self.magc[c][k] * self.magc[c][k];
                    }
                    ema * (e.sqrt() / rss_mid) * formant_gain * region_gain
                } else {
                    self.magc[c][pk] / ker_src * formant_gain * region_gain
                };
                let off_c = if nch > 1 {
                    princarg(self.phi[c][pk] - self.phim[pk])
                        + decor_amt * decor_offset(ni, c)
                } else {
                    0.0
                };
                for k in k0..=k1 {
                    let xoff = k as f64 - b;
                    self.ysyn[c][k] += Complex64::from_polar(
                        (1.0 - p.grit) * amp_c * hann_kernel(xoff, self.n_fft),
                        phv + off_c - PI * xoff,
                    );
                }
            }
        }
    }
}

// -- note-name parsing shared by CLI --
pub fn parse_note(name: &str) -> Option<u8> {
    let bytes = name.trim().as_bytes();
    if bytes.is_empty() {
        return None;
    }
    let pc0: i32 = match bytes[0].to_ascii_uppercase() {
        b'C' => 0,
        b'D' => 2,
        b'E' => 4,
        b'F' => 5,
        b'G' => 7,
        b'A' => 9,
        b'B' => 11,
        _ => return None,
    };
    let mut pc = pc0;
    let mut i = 1;
    while i < bytes.len() && (bytes[i] == b'#' || bytes[i] == b'b') {
        pc += if bytes[i] == b'#' { 1 } else { -1 };
        i += 1;
    }
    let oct: i32 = name[i..].parse().ok()?;
    let n = pc + 12 * (oct + 1);
    (0..=127).contains(&n).then_some(n as u8)
}
