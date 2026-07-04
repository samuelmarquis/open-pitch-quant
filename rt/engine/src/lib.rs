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

use realfft::num_complex::Complex64;
use realfft::{ComplexToReal, RealFftPlanner, RealToComplex};
use std::collections::VecDeque;
use std::sync::Arc;

pub const N_FFT: usize = 4096; // default window size
pub const HOP: usize = 1024; // default hop (window/4)
const N_HARM: usize = 20;
/// phase-table reach for owned harmonics (full-comb ownership can claim
/// far beyond N_HARM; mis-numbered h up here only re-keys a phase slot)
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

#[derive(Clone, Copy)]
pub struct EngineParams {
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
}

impl Default for EngineParams {
    fn default() -> Self {
        Self {
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
        }
    }
}

#[derive(Clone)]
struct Track {
    f0: f64,
    lema: f64,
    tgt: f64,
    r_from: f64,
    g0: i64,
    seen: i64,
    /// per harmonic number: (phase, frame last seen)
    phases: [(f64, i64); MAX_H + 1],
}

fn midi_freq(n: f64) -> f64 {
    440.0 * ((n - 69.0) / 12.0).exp2()
}

fn princarg(x: f64) -> f64 {
    (x + PI).rem_euclid(TWO_PI) - PI
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

fn wmedian(vals: &mut Vec<(f64, f64)>) -> f64 {
    vals.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    let total: f64 = vals.iter().map(|v| v.1).sum();
    let mut cw = 0.0;
    for &(v, w) in vals.iter() {
        cw += w;
        if cw >= 0.5 * total {
            return v;
        }
    }
    vals.last().map(|v| v.0).unwrap_or(0.0)
}

pub struct Engine {
    sr: f64,
    channels: usize,
    n_fft: usize,
    hop: usize,
    bins: usize,
    win: Vec<f64>,
    fft: Arc<dyn RealToComplex<f64>>,
    ifft: Arc<dyn ComplexToReal<f64>>,
    // streaming state (per channel where applicable)
    in_buf: Vec<Vec<f64>>,
    fill: usize,
    ola: Vec<Vec<f64>>,
    out_fifo: Vec<VecDeque<f64>>,
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
    tracks: Vec<Track>,
    // scratch
    fft_in: Vec<f64>,
    spec_scratch: Vec<Complex64>,
    yt: Vec<f64>,
    env: Vec<f64>,
    env_tmp: Vec<f64>,
    grid: Vec<f64>,
    peaks: Vec<usize>,
    bounds: Vec<(usize, usize)>,
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
        let fft = planner.plan_fft_forward(n_fft);
        let ifft = planner.plan_fft_inverse(n_fft);
        let win: Vec<f64> = (0..n_fft)
            .map(|n| 0.5 - 0.5 * (TWO_PI * n as f64 / (n_fft as f64 - 1.0)).cos())
            .collect();
        let zc = || vec![Complex64::new(0.0, 0.0); bins];
        let mut e = Self {
            sr,
            channels,
            n_fft,
            hop,
            bins,
            win,
            fft,
            ifft,
            in_buf: vec![vec![0.0; n_fft]; channels],
            fill: 0,
            ola: vec![vec![0.0; n_fft]; channels],
            out_fifo: vec![VecDeque::with_capacity(2 * n_fft); channels],
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
            tracks: Vec::with_capacity(16),
            fft_in: vec![0.0; n_fft],
            spec_scratch: zc(),
            yt: vec![0.0; n_fft],
            env: vec![0.0; bins],
            env_tmp: vec![0.0; bins],
            grid: Vec::with_capacity(128),
            peaks: Vec::with_capacity(512),
            bounds: Vec::with_capacity(512),
        };
        e.reset();
        e
    }

    pub fn reset(&mut self) {
        for c in 0..self.channels {
            self.in_buf[c].iter_mut().for_each(|v| *v = 0.0);
            self.ola[c].iter_mut().for_each(|v| *v = 0.0);
            self.out_fifo[c].clear();
            self.dry_fifo[c].clear();
            for _ in 0..self.n_fft {
                self.out_fifo[c].push_back(0.0);
                self.dry_fifo[c].push_back(0.0);
            }
        }
        self.fill = 0;
        self.prev_phi.iter_mut().for_each(|v| *v = 0.0);
        self.prev_mag_sum = -1.0;
        self.first_frame = true;
        self.frame_idx = 0;
        self.note_phase = [0.0; 128];
        self.note_seen = [-2; 128];
        self.tracks.clear();
    }

    pub fn latency_samples(&self) -> usize {
        self.n_fft
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
        for i in 0..len {
            for c in 0..ch {
                let x = io[c][i] as f64;
                self.dry_fifo[c].push_back(x);
                self.in_buf[c][self.n_fft - self.hop + self.fill] = x;
            }
            self.fill += 1;
            if self.fill == self.hop {
                self.run_frame(held, p);
                self.fill = 0;
                for c in 0..ch {
                    self.in_buf[c].copy_within(self.hop.., 0);
                }
            }
            for c in 0..ch {
                let wet = self.out_fifo[c].pop_front().unwrap_or(0.0);
                let dry = self.dry_fifo[c].pop_front().unwrap_or(0.0);
                io[c][i] = (p.mix * wet + (1.0 - p.mix) * dry) as f32;
            }
        }
    }

    fn build_grid(&mut self, held: &[bool; 128], mode: Mode) {
        self.grid.clear();
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

    fn find_peaks(&mut self) {
        self.peaks.clear();
        let mag = &self.mag;
        let mx = mag.iter().cloned().fold(0.0f64, f64::max);
        let floor = (mx * 10f64.powf(-60.0 / 20.0)).max(1e-7);
        for i in 2..self.bins - 2 {
            let m = mag[i];
            if m > mag[i - 1]
                && m >= mag[i + 1]
                && m > mag[i - 2]
                && m >= mag[i + 2]
                && m > floor
            {
                self.peaks.push(i);
            }
        }
    }

    fn region_bounds(&mut self) {
        self.bounds.clear();
        let np = self.peaks.len();
        for i in 0..np {
            let p = self.peaks[i];
            let lo = if i == 0 { 1 } else { self.bounds[i - 1].1 };
            let hi = if i == np - 1 {
                self.bins - 1
            } else {
                let q = self.peaks[i + 1];
                if q > p + 1 {
                    let mut vm = f64::INFINITY;
                    let mut vi = p + 1;
                    for j in p + 1..=q {
                        if self.mag[j] < vm {
                            vm = self.mag[j];
                            vi = j;
                        }
                    }
                    vi
                } else {
                    q
                }
            };
            self.bounds.push((lo, hi));
        }
    }

    /// Greedy Klapuri-style multi-F0 over detected (mid-spectrum) peaks.
    fn harmonic_objects(&self, voices: usize) -> (Vec<f64>, Vec<i32>) {
        let pk_f: Vec<f64> = self.peaks.iter().map(|&p| self.f_true[p]).collect();
        let pk_m: Vec<f64> = self.peaks.iter().map(|&p| self.mag[p]).collect();
        let n_pk = pk_f.len();
        let mut owner = vec![-1i32; n_pk];
        let mut f0s: Vec<f64> = Vec::new();
        if n_pk == 0 {
            return (f0s, owner);
        }
        let log_pk: Vec<f64> = pk_f.iter().map(|&f| f.max(1e-9).ln()).collect();
        let tol = 45.0 / 1200.0 * 2f64.ln();
        let tol_re = 30.0 / 1200.0 * 2f64.ln();
        let cands: Vec<f64> = (33..=84).map(|n| midi_freq(n as f64)).collect();
        let w_h: Vec<f64> = (1..=N_HARM).map(|h| 1.0 / (h as f64).powf(0.9)).collect();

        let mut avail = pk_m.clone();
        let mut first_sal = -1.0f64;
        for _ in 0..voices {
            let mut best_sal = 0.0;
            let mut best_c = usize::MAX;
            let mut best_claim: Vec<usize> = Vec::new();
            let mut claim: Vec<usize> = Vec::new();
            for (ci, &c) in cands.iter().enumerate() {
                let mut sal = 0.0;
                let mut hits = 0usize;
                claim.clear();
                for h in 1..=N_HARM {
                    let lfh = (c * h as f64).ln();
                    let mut bd = f64::INFINITY;
                    let mut bj = usize::MAX;
                    for j in 0..n_pk {
                        if avail[j] <= 0.0 {
                            continue;
                        }
                        let d = (log_pk[j] - lfh).abs();
                        if d < bd {
                            bd = d;
                            bj = j;
                        }
                    }
                    if bj != usize::MAX && bd < tol {
                        sal += avail[bj] * w_h[h - 1];
                        hits += 1;
                        claim.push(bj);
                    }
                }
                if hits >= 3 && sal > best_sal {
                    best_sal = sal;
                    best_c = ci;
                    best_claim = claim.clone();
                }
            }
            if best_c == usize::MAX || best_sal <= 0.0 {
                break;
            }
            if first_sal < 0.0 {
                first_sal = best_sal;
            } else if best_sal < 0.05 * first_sal {
                break;
            }
            best_claim.sort_unstable();
            best_claim.dedup();
            let cand_f = cands[best_c];
            let mut est: Vec<(f64, f64)> = Vec::new();
            for &j in &best_claim {
                let hh = (pk_f[j] / cand_f).round().max(1.0);
                if hh <= 6.0 {
                    est.push((pk_f[j] / hh, avail[j]));
                }
            }
            if est.len() < 2 {
                est.clear();
                for &j in &best_claim {
                    let hh = (pk_f[j] / cand_f).round().max(1.0);
                    est.push((pk_f[j] / hh, avail[j]));
                }
            }
            let f0e = wmedian(&mut est);
            let mut inl: Vec<usize> = Vec::new();
            let mut est2: Vec<(f64, f64)> = Vec::new();
            for j in 0..n_pk {
                if avail[j] <= 0.0 {
                    continue;
                }
                let hh = (pk_f[j] / f0e).round();
                if hh < 1.0 || hh > N_HARM as f64 {
                    continue;
                }
                let dev = (pk_f[j].max(1e-9) / (hh * f0e)).ln().abs();
                if dev < tol_re {
                    inl.push(j);
                    est2.push((pk_f[j] / hh, avail[j]));
                }
            }
            if inl.len() < 3 {
                for &j in &best_claim {
                    avail[j] = 0.0; // burn the evidence, try next candidate
                }
                continue;
            }
            let f0r = wmedian(&mut est2);
            let oi = f0s.len() as i32;
            for &j in &inl {
                if owner[j] == -1 {
                    owner[j] = oi;
                }
                avail[j] = 0.0; // burn ONLY confirmed inliers
            }
            f0s.push(f0r);
        }
        // FULL-COMB ownership post-pass: assign each leftover peak to the
        // object whose comb explains it best (COMPETITIVE, not greedy —
        // adjacent combs' teeth are only ~17 cents apart at high h, so
        // first-object-wins steals other objects' genuine harmonics).
        // A mis-numbered h only re-keys a phase slot — df comes from f0.
        let tol_ext = 22.0 / 1200.0 * 2f64.ln();
        let nyq = self.sr / 2.0 * 0.95;
        for j in 0..n_pk {
            if avail[j] <= 0.0 {
                continue;
            }
            let mut best_o = -1i32;
            let mut best_d = tol_ext;
            for (oi, &f0r) in f0s.iter().enumerate() {
                let hh = (pk_f[j] / f0r).round();
                if hh < 1.0 || hh * f0r > nyq {
                    continue;
                }
                let dev = (pk_f[j].max(1e-9) / (hh * f0r)).ln().abs();
                if dev < best_d {
                    best_d = dev;
                    best_o = oi as i32;
                }
            }
            if best_o >= 0 {
                owner[j] = best_o;
                avail[j] = 0.0;
            }
        }
        (f0s, owner)
    }

    fn run_frame(&mut self, held: &[bool; 128], p: &EngineParams) {
        let t = self.frame_idx;
        self.frame_idx += 1;
        let bin_hz = self.sr / self.n_fft as f64;
        let nch = self.channels;

        // per-channel FFT
        for c in 0..nch {
            for n in 0..self.n_fft {
                self.fft_in[n] = self.in_buf[c][n] * self.win[n];
            }
            self.fft
                .process(&mut self.fft_in, &mut self.spec[c])
                .expect("fft");
            for k in 0..self.bins {
                self.magc[c][k] = self.spec[c][k].norm();
                self.phi[c][k] = self.spec[c][k].arg();
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
        if self.first_frame {
            for k in 0..self.bins {
                self.f_true[k] = k as f64 * bin_hz;
            }
        } else {
            for k in 0..self.bins {
                let expected = TWO_PI * self.hop as f64 * k as f64 / self.n_fft as f64;
                let d = princarg(self.phim[k] - self.prev_phi[k] - expected);
                self.f_true[k] =
                    k as f64 * bin_hz + d / (TWO_PI * self.hop as f64 / self.n_fft as f64) * bin_hz;
            }
        }
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
        self.prev_mag_store.copy_from_slice(&self.mag);
        self.prev_mag_sum = mag_sum;
        let is_transient = p.transient_bypass && flux > p.flux_thresh;

        self.build_grid(held, p.mode);

        if self.grid.is_empty() {
            self.note_seen = [-2; 128];
            self.tracks.clear();
            for c in 0..nch {
                self.ysyn[c].iter_mut().for_each(|v| *v = Complex64::new(0.0, 0.0));
            }
        } else if is_transient || self.first_frame {
            self.note_seen = [-2; 128];
            self.tracks.clear();
            for c in 0..nch {
                self.ysyn[c].copy_from_slice(&self.spec[c]);
            }
        } else {
            self.map_frame(t, p, bin_hz);
        }
        self.first_frame = false;

        // synthesize, window, overlap-add, emit — per channel
        let inv_n = 1.0 / self.n_fft as f64;
        for c in 0..nch {
            self.spec_scratch.copy_from_slice(&self.ysyn[c]);
            self.spec_scratch[0].im = 0.0;
            self.spec_scratch[self.bins - 1].im = 0.0;
            self.ifft
                .process(&mut self.spec_scratch, &mut self.yt)
                .expect("ifft");
            for n in 0..self.n_fft {
                self.ola[c][n] += self.yt[n] * inv_n * self.win[n];
            }
            for n in 0..self.hop {
                self.out_fifo[c].push_back(self.ola[c][n] / 1.5); // hann^2 COLA
            }
            self.ola[c].copy_within(self.hop.., 0);
            for n in self.n_fft - self.hop..self.n_fft {
                self.ola[c][n] = 0.0;
            }
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
        self.find_peaks();
        self.region_bounds();
        if p.formant > 0.0 {
            self.compute_envelope();
        }
        let (f0s, owner) = self.harmonic_objects(p.voices.max(1));

        // ---- M3: match objects to tracks ----
        let glide_frames = p.glide * self.sr / self.hop as f64;
        let ema_a = 1.0 - (-(self.hop as f64 / self.sr) / 0.25).exp();
        let hyst = p.hyst_cents / 1200.0 * 2f64.ln();
        let match_tol = 2f64.ln() * 100.0 / 1200.0;
        let mut obj_mult: Vec<f64> = Vec::with_capacity(f0s.len());
        let mut obj_trk: Vec<usize> = Vec::with_capacity(f0s.len());
        for &f0 in &f0s {
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
                    self.tracks.push(Track {
                        f0,
                        lema: f0.ln(),
                        tgt,
                        r_from: 0.0, // birth: glide starts at SOURCE pitch
                        g0: t,
                        seen: t,
                        phases: [(0.0, -2); MAX_H + 1],
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
                        trk.r_from = r_now;
                        trk.g0 = t;
                        trk.tgt = tgt;
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
            let r_to = (trk.tgt / trk.f0).ln();
            let r_eff = if glide_frames > 0.0 {
                let prog = ((t - trk.g0) as f64 / glide_frames).min(1.0);
                trk.r_from + (r_to - trk.r_from) * prog
            } else {
                r_to
            };
            let dev = trk.f0.ln() - trk.lema;
            obj_mult.push(if bypass {
                1.0
            } else {
                (r_eff + p.feel * dev).exp()
            });
            obj_trk.push(ti);
        }

        // ---- region mapping decisions + per-channel synthesis ----
        for c in 0..nch {
            self.ysyn[c]
                .iter_mut()
                .for_each(|v| *v = Complex64::new(0.0, 0.0));
        }
        let gate = p.tonality_gate;
        let decor_amt = (1.0 - p.coherence).clamp(0.0, 1.0) * PI;
        let n_regions = self.peaks.len();
        for i in 0..n_regions {
            let pk = self.peaks[i];
            let (lo, hi) = self.bounds[i];
            let fp = self.f_true[pk];
            let mut trk_idx: Option<usize> = None;
            let mut h = 0usize;
            let df;
            let mut noisy = false;
            if owner[i] >= 0 {
                let oi = owner[i] as usize;
                let trk = &self.tracks[obj_trk[oi]];
                df = fp * (obj_mult[oi] - 1.0);
                h = ((fp / trk.f0).round() as i64).max(1) as usize;
                trk_idx = Some(obj_trk[oi]);
            } else if p.unowned == Unowned::Dry {
                df = 0.0;
            } else {
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
                df = if mappable {
                    self.nearest_grid(fp) - fp
                } else {
                    0.0
                };
            }
            if h > MAX_H {
                trk_idx = None;
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
                            self.magc[c][sk],
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
            let ker_src = hann_kernel(dsrc, self.n_fft).max(0.1);
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
            let phv = if let Some(ti) = trk_idx {
                let trk = &mut self.tracks[ti];
                let (ph0, seen) = trk.phases[h];
                let phv = if seen == t {
                    ph0
                } else if seen == t - 1 {
                    ph0 + TWO_PI * ft * self.hop as f64 / self.sr
                } else {
                    anchor
                };
                trk.phases[h] = (phv, t);
                phv
            } else {
                if self.note_seen[ni] == t {
                    // already advanced this frame
                } else if self.note_seen[ni] == t - 1 {
                    self.note_phase[ni] += TWO_PI * ft * self.hop as f64 / self.sr;
                } else {
                    self.note_phase[ni] = anchor;
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
            let b = ft / bin_hz;
            let k0 = ((b - 4.0).ceil() as i64).max(1) as usize;
            let k1 = ((b + 4.0).floor() as i64).min(self.bins as i64 - 2) as usize;
            for c in 0..nch {
                // channel's own level + phase offset from the mid reference
                let amp_c = self.magc[c][pk] / ker_src * formant_gain;
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
