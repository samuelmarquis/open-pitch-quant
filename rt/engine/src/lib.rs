//! Real-time port of the opq spectral pitch-mapping engine.
//!
//! Faithful port of `opq/engine.py` (the "champion" configuration only:
//! assign=group, synth=stamp, phase_lock=true — the paths that survived
//! listening batches 001–009). Streaming STFT with N=4096 / hop=1024,
//! reported latency = N samples (matches PITCHMAP's 4096).

use realfft::num_complex::Complex64;
use realfft::{ComplexToReal, RealFftPlanner, RealToComplex};
use std::collections::VecDeque;
use std::sync::Arc;

pub const N_FFT: usize = 4096;
pub const HOP: usize = 1024;
const BINS: usize = N_FFT / 2 + 1;
const N_HARM: usize = 20;
const MAX_H: usize = N_HARM + 2;
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
            glide: 0.06,
            grit: 0.0,
            mode: Mode::Repeat,
            rounding: Rounding::Intelligent,
            hyst_cents: 40.0,
            mix: 1.0,
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

/// Zero-phase Hann window spectrum at fractional bin offset, W(0)=1.
fn hann_kernel(x: f64) -> f64 {
    fn diric(u: f64) -> f64 {
        let den = N_FFT as f64 * (PI * u / N_FFT as f64).sin();
        if den.abs() < 1e-12 {
            1.0
        } else {
            (PI * u).sin() / den
        }
    }
    diric(x) + 0.5 * (diric(x - 1.0) + diric(x + 1.0))
}

fn wmedian(vals: &mut Vec<(f64, f64)>) -> f64 {
    // vals: (value, weight); sorted by value, cumulative weight crossing
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
    win: Vec<f64>,
    fft: Arc<dyn RealToComplex<f64>>,
    ifft: Arc<dyn ComplexToReal<f64>>,
    // streaming state
    in_buf: Vec<f64>,
    pending: Vec<f64>,
    ola: Vec<f64>,
    out_fifo: VecDeque<f64>,
    dry_fifo: VecDeque<f64>,
    // analysis state
    prev_phi: Vec<f64>,
    prev_mag_store: Vec<f64>,
    prev_mag_sum: f64,
    first_frame: bool,
    frame_idx: i64,
    // synthesis state
    note_phase: [f64; 128],
    note_seen: [i64; 128],
    tracks: Vec<Track>,
    // scratch
    fft_in: Vec<f64>,
    spec: Vec<Complex64>,
    mag: Vec<f64>,
    phi: Vec<f64>,
    f_true: Vec<f64>,
    ysyn: Vec<Complex64>,
    spec_scratch: Vec<Complex64>,
    yt: Vec<f64>,
    grid: Vec<f64>,
    peaks: Vec<usize>,
    bounds: Vec<(usize, usize)>,
}

impl Engine {
    pub fn new(sr: f64) -> Self {
        let mut planner = RealFftPlanner::<f64>::new();
        let fft = planner.plan_fft_forward(N_FFT);
        let ifft = planner.plan_fft_inverse(N_FFT);
        let win: Vec<f64> = (0..N_FFT)
            .map(|n| 0.5 - 0.5 * (TWO_PI * n as f64 / (N_FFT as f64 - 1.0)).cos())
            .collect();
        let mut e = Self {
            sr,
            win,
            fft,
            ifft,
            in_buf: vec![0.0; N_FFT],
            pending: Vec::with_capacity(HOP),
            ola: vec![0.0; N_FFT],
            out_fifo: VecDeque::with_capacity(2 * N_FFT),
            dry_fifo: VecDeque::with_capacity(2 * N_FFT),
            prev_phi: vec![0.0; BINS],
            prev_mag_store: vec![0.0; BINS],
            prev_mag_sum: -1.0,
            first_frame: true,
            frame_idx: 0,
            note_phase: [0.0; 128],
            note_seen: [-2; 128],
            tracks: Vec::with_capacity(16),
            fft_in: vec![0.0; N_FFT],
            spec: vec![Complex64::new(0.0, 0.0); BINS],
            mag: vec![0.0; BINS],
            phi: vec![0.0; BINS],
            f_true: vec![0.0; BINS],
            ysyn: vec![Complex64::new(0.0, 0.0); BINS],
            spec_scratch: vec![Complex64::new(0.0, 0.0); BINS],
            yt: vec![0.0; N_FFT],
            grid: Vec::with_capacity(128),
            peaks: Vec::with_capacity(512),
            bounds: Vec::with_capacity(512),
        };
        e.reset();
        e
    }

    pub fn reset(&mut self) {
        self.in_buf.iter_mut().for_each(|v| *v = 0.0);
        self.pending.clear();
        self.ola.iter_mut().for_each(|v| *v = 0.0);
        self.out_fifo.clear();
        self.dry_fifo.clear();
        // prime with N_FFT zeros = constant reported latency
        for _ in 0..N_FFT {
            self.out_fifo.push_back(0.0);
            self.dry_fifo.push_back(0.0);
        }
        self.prev_phi.iter_mut().for_each(|v| *v = 0.0);
        self.prev_mag_sum = -1.0;
        self.first_frame = true;
        self.frame_idx = 0;
        self.note_phase = [0.0; 128];
        self.note_seen = [-2; 128];
        self.tracks.clear();
    }

    pub fn latency_samples(&self) -> usize {
        N_FFT
    }

    /// Process a block in place. `held[n]` = MIDI note n currently held.
    pub fn process_block(&mut self, io: &mut [f32], held: &[bool; 128], p: &EngineParams) {
        for s in io.iter_mut() {
            let x = *s as f64;
            self.dry_fifo.push_back(x);
            self.pending.push(x);
            if self.pending.len() == HOP {
                self.run_frame(held, p);
            }
            let wet = self.out_fifo.pop_front().unwrap_or(0.0);
            let dry = self.dry_fifo.pop_front().unwrap_or(0.0);
            *s = (p.mix * wet + (1.0 - p.mix) * dry) as f32;
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
        for i in 2..BINS - 2 {
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
                BINS - 1
            } else {
                let q = self.peaks[i + 1];
                if q > p + 1 {
                    // valley between the peaks
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

    /// Greedy Klapuri-style multi-F0 over detected peaks.
    /// Returns refined f0 per object and per-peak owner index (-1 = none).
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
        // candidates: semitone grid, 55 Hz .. 1046.5 Hz (midi 33..=84)
        let cands: Vec<f64> = (33..=84).map(|n| midi_freq(n as f64)).collect();
        let w_h: Vec<f64> = (1..=N_HARM).map(|h| 1.0 / (h as f64).powf(0.9)).collect();

        let mut avail = pk_m.clone();
        let mut first_sal = -1.0f64;
        for _ in 0..voices {
            // pick best candidate by harmonic-summation salience
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
                    // nearest available peak
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
            // initial f0: weighted median over LOW harmonics
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
            // re-claim ALL available peaks against the refined comb
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
        (f0s, owner)
    }

    fn run_frame(&mut self, held: &[bool; 128], p: &EngineParams) {
        // slide input history and take the frame
        self.in_buf.copy_within(HOP.., 0);
        let n0 = N_FFT - HOP;
        self.in_buf[n0..].copy_from_slice(&self.pending);
        self.pending.clear();

        let t = self.frame_idx;
        self.frame_idx += 1;
        let bin_hz = self.sr / N_FFT as f64;

        for n in 0..N_FFT {
            self.fft_in[n] = self.in_buf[n] * self.win[n];
        }
        self.fft
            .process(&mut self.fft_in, &mut self.spec)
            .expect("fft");
        let mut mag_sum = 0.0;
        for k in 0..BINS {
            self.mag[k] = self.spec[k].norm();
            self.phi[k] = self.spec[k].arg();
            mag_sum += self.mag[k];
        }

        // instantaneous frequency via phase differences
        if self.first_frame {
            for k in 0..BINS {
                self.f_true[k] = k as f64 * bin_hz;
            }
        } else {
            for k in 0..BINS {
                let expected = TWO_PI * HOP as f64 * k as f64 / N_FFT as f64;
                let mut d = self.phi[k] - self.prev_phi[k] - expected;
                d = (d + PI).rem_euclid(TWO_PI) - PI;
                self.f_true[k] = k as f64 * bin_hz + d / (TWO_PI * HOP as f64 / N_FFT as f64) * bin_hz;
            }
        }
        self.prev_phi.copy_from_slice(&self.phi);

        // spectral flux onset detector
        let flux = if self.prev_mag_sum < 0.0 {
            f64::INFINITY
        } else {
            let mut pos = 0.0;
            for k in 0..BINS {
                let d = self.mag[k] - self.prev_mag_row(k);
                if d > 0.0 {
                    pos += d;
                }
            }
            pos / (self.prev_mag_sum + 1e-12)
        };
        // store current mags for next frame's flux
        self.store_prev_mag(mag_sum);
        let is_transient = p.transient_bypass && flux > p.flux_thresh;

        self.build_grid(held, p.mode);

        if self.grid.is_empty() {
            // no held notes -> silence (PITCHMAP semantics)
            self.note_seen = [-2; 128];
            self.tracks.clear();
            for k in 0..BINS {
                self.ysyn[k] = Complex64::new(0.0, 0.0);
            }
        } else if is_transient || self.first_frame {
            // dry passthrough; re-anchor synthesis state
            self.note_seen = [-2; 128];
            self.tracks.clear();
            self.ysyn.copy_from_slice(&self.spec);
        } else {
            self.map_frame(t, p, bin_hz);
        }
        self.first_frame = false;

        // synthesize, window, overlap-add
        self.spec_scratch.copy_from_slice(&self.ysyn);
        // realfft inverse requires bins 0 and Nyquist to be real
        self.spec_scratch[0].im = 0.0;
        self.spec_scratch[BINS - 1].im = 0.0;
        self.ifft
            .process(&mut self.spec_scratch, &mut self.yt)
            .expect("ifft");
        let inv_n = 1.0 / N_FFT as f64;
        for n in 0..N_FFT {
            self.ola[n] += self.yt[n] * inv_n * self.win[n];
        }
        for n in 0..HOP {
            self.out_fifo.push_back(self.ola[n] / 1.5); // hann^2 COLA @75%
        }
        self.ola.copy_within(HOP.., 0);
        for n in N_FFT - HOP..N_FFT {
            self.ola[n] = 0.0;
        }
    }

    // prev-mag storage (reuses yt scratch would clash; keep a dedicated vec)
    fn prev_mag_row(&self, k: usize) -> f64 {
        self.prev_mag_store[k]
    }
    fn store_prev_mag(&mut self, sum: f64) {
        self.prev_mag_store.copy_from_slice(&self.mag);
        self.prev_mag_sum = sum;
    }

    fn map_frame(&mut self, t: i64, p: &EngineParams, bin_hz: f64) {
        // drop tracks not seen last frame FIRST, so indices taken during
        // matching stay valid through synthesis
        self.tracks.retain(|trk| trk.seen >= t - 1);
        self.find_peaks();
        self.region_bounds();
        let (f0s, owner) = self.harmonic_objects(p.voices.max(1));

        // ---- M3: match objects to tracks ----
        let glide_frames = p.glide * self.sr / HOP as f64;
        let ema_a = 1.0 - (-(HOP as f64 / self.sr) / 0.25).exp();
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
                    let in_grid = self
                        .grid
                        .iter()
                        .any(|&g| ((g / old).ln()).abs() < 1e-9);
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
            let r_to = (trk.tgt / trk.f0).ln();
            let r_eff = if glide_frames > 0.0 {
                let prog = ((t - trk.g0) as f64 / glide_frames).min(1.0);
                trk.r_from + (r_to - trk.r_from) * prog
            } else {
                r_to
            };
            let dev = trk.f0.ln() - trk.lema;
            obj_mult.push((r_eff + p.feel * dev).exp());
            obj_trk.push(ti);
        }
        // ---- region mapping decisions + synthesis ----
        for k in 0..BINS {
            self.ysyn[k] = Complex64::new(0.0, 0.0);
        }
        let gate = p.tonality_gate;
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
                // M0-style treatment for unowned peaks
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
                // beyond phase-table reach: treat as plain mapped partial
                trk_idx = None;
            }

            let dbin = (df / bin_hz).round() as i64;
            let clo = (lo as i64 + dbin).max(1) as usize;
            let chi = ((hi as i64 + dbin).min(BINS as i64 - 1)) as usize;
            if chi <= clo {
                continue;
            }
            if df == 0.0 {
                for k in clo..chi {
                    self.ysyn[k] += self.spec[k]; // verbatim dry
                }
                continue;
            }
            if noisy {
                // mapped noise: fresh phases + deterministic shift ramp
                let ramp = TWO_PI * df * (t as f64 * HOP as f64) / self.sr
                    + PI * dbin as f64;
                for k in clo..chi {
                    let sk = (k as i64 - dbin) as usize;
                    let ph = self.phi[sk] + ramp;
                    self.ysyn[k] +=
                        Complex64::from_polar(self.mag[sk], ph);
                }
                continue;
            }
            // stamped tonal partial
            let ft = fp + df;
            let dsrc = fp / bin_hz - pk as f64;
            let amp = self.mag[pk] / hann_kernel(dsrc).max(0.1);
            let anchor = self.phi[pk] - PI * dsrc;
            let phv = if let Some(ti) = trk_idx {
                let trk = &mut self.tracks[ti];
                let (ph0, seen) = trk.phases[h];
                let phv = if seen == t {
                    ph0
                } else if seen == t - 1 {
                    ph0 + TWO_PI * ft * HOP as f64 / self.sr
                } else {
                    anchor
                };
                trk.phases[h] = (phv, t);
                phv
            } else {
                let ni = ((69.0 + 12.0 * (ft / 440.0).log2()).round() as i64)
                    .clamp(0, 127) as usize;
                if self.note_seen[ni] == t {
                    // already advanced this frame
                } else if self.note_seen[ni] == t - 1 {
                    self.note_phase[ni] += TWO_PI * ft * HOP as f64 / self.sr;
                } else {
                    self.note_phase[ni] = anchor;
                }
                self.note_seen[ni] = t;
                self.note_phase[ni]
            };
            if p.grit > 0.0 {
                let ramp = TWO_PI * df * (t as f64 * HOP as f64) / self.sr
                    + PI * dbin as f64;
                for k in clo..chi {
                    let sk = (k as i64 - dbin) as usize;
                    self.ysyn[k] += Complex64::from_polar(
                        p.grit * self.mag[sk],
                        self.phi[sk] + ramp,
                    );
                }
            }
            let b = ft / bin_hz;
            let k0 = ((b - 4.0).ceil() as i64).max(1) as usize;
            let k1 = ((b + 4.0).floor() as i64).min(BINS as i64 - 2) as usize;
            for k in k0..=k1 {
                let xoff = k as f64 - b;
                self.ysyn[k] += Complex64::from_polar(
                    (1.0 - p.grit) * amp * hann_kernel(xoff),
                    phv - PI * xoff,
                );
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
