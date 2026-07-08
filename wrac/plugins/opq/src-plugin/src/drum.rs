//! The drum: the plugin's one eye. A fixed-pixel, unclickable transect —
//! log-frequency vertical (C1 at the floor, C8 at the roof), time scrolling
//! leftward, one column per analysis frame.
//!
//! It draws the tracker's BELIEF, never the signal: pitch objects as white
//! combs (spine at f0, teeth only at harmonics the grouper actually claimed
//! this frame), the synthesis bend as an amber trace walking onto lit rails,
//! and refusal in ochre — transient punch-through veils, threshold mercies,
//! ended beliefs, the map ceiling. Unclaimed spectrum appears only as gray
//! sediment, binned the way the engine itself bins it. Where the model
//! believes nothing, the field stays black.

use opq_engine::VizFrame;

pub(crate) const DRUM_W: usize = 1016;
pub(crate) const DRUM_H: usize = 384; // 8 octaves x 48 px

const PX_PER_OCT: f32 = 48.0;
const F_TOP: f32 = 4186.009; // C8; C0 lands exactly on the bottom row

// The night's palette: black field; bone white for belief; aviation amber
// for the law and the bend; rust ochre for every refusal; gray for weather.
const WHITE: [u8; 3] = [232, 228, 216];
const AMBER: [u8; 3] = [255, 179, 0];
const RAIL: [u8; 3] = [64, 45, 0];
const OCHRE: [u8; 3] = [166, 75, 0];
const WEATHER: [u8; 3] = [56, 59, 64];

pub(crate) struct Drum {
    /// RGBA, row-major, DRUM_W x DRUM_H. Alpha is always 255.
    fb: Vec<u8>,
    /// Beliefs alive in the previous column: (id, row, relative amplitude).
    prev: Vec<(i64, usize, f32)>,
}

impl Drum {
    pub(crate) fn new() -> Self {
        let mut fb = vec![0u8; DRUM_W * DRUM_H * 4];
        for px in fb.chunks_exact_mut(4) {
            px[3] = 255;
        }
        Self {
            fb,
            prev: Vec::with_capacity(24),
        }
    }

    pub(crate) fn pixels(&self) -> &[u8] {
        &self.fb
    }

    fn row(f: f32) -> Option<usize> {
        if f <= 0.0 {
            return None;
        }
        let y = ((F_TOP / f).log2() * PX_PER_OCT).round();
        (y >= 0.0 && y < DRUM_H as f32).then(|| y as usize)
    }

    fn add(&mut self, x: usize, y: usize, c: [u8; 3], s: f32) {
        let i = (y * DRUM_W + x) * 4;
        for k in 0..3 {
            let v = (c[k] as f32 * s) as u16;
            self.fb[i + k] = (self.fb[i + k] as u16 + v).min(255) as u8;
        }
    }

    /// Advance one analysis frame: scroll left a pixel, draw the new column.
    /// Returns the count of loud beliefs that ended this frame (the panel's
    /// annunciator and counters feed on it).
    pub(crate) fn push_frame(&mut self, fr: &VizFrame, ceiling_hz: f32) -> u32 {
        // Whole-buffer shift: row seams leak one pixel from the next row
        // into column W-1, which is exactly the column repainted below.
        self.fb.copy_within(4.., 0);
        let x = DRUM_W - 1;
        for y in 0..DRUM_H {
            let i = (y * DRUM_W + x) * 4;
            self.fb[i..i + 4].copy_from_slice(&[0, 0, 0, 255]);
        }

        let in_e = fr.in_energy.max(1e-9);

        // Weather: residual magnitude, stippled into the engine's own octave
        // bands (band b spans C_b..C_{b+1}; all eight are on the drum).
        for b in 0..8usize {
            let w = (fr.res_bands[b] / in_e).clamp(0.0, 1.0);
            if w < 1e-3 {
                continue;
            }
            let y0 = (7 - b) * PX_PER_OCT as usize;
            for y in y0..y0 + PX_PER_OCT as usize {
                if hash01(fr.t, y as u64) < w * 0.85 {
                    self.add(x, y, WEATHER, 0.35 + 0.65 * w);
                }
            }
        }

        // Rails: the law. Bit 127 flags Repeat scope — the engine's real grid
        // repeats held pitch-classes across every octave, so the rails must too.
        let repeat = fr.grid_mask & (1u128 << 127) != 0;
        let mut pcs = [false; 12];
        for n in 0..127usize {
            if fr.grid_mask & (1u128 << n) != 0 {
                pcs[n % 12] = true;
            }
        }
        for n in 0..127usize {
            let lit = if repeat {
                pcs[n % 12]
            } else {
                fr.grid_mask & (1u128 << n) != 0
            };
            if !lit {
                continue;
            }
            if let Some(y) = Self::row(midi_hz(n)) {
                self.add(x, y, RAIL, 1.0);
            }
        }

        // Map Ceiling: the reach of the law, dotted ochre (a refusal boundary;
        // everything above it passes unbent).
        if fr.t % 3 == 0 {
            if let Some(y) = Self::row(ceiling_hz) {
                self.add(x, y, OCHRE, 0.8);
            }
        }

        // Transient punch-through: the frame's dry blend as a full-height
        // ochre veil. At 1.0 the hit went through whole; the veil says so.
        if fr.transient > 0.01 {
            let s = 0.12 + 0.45 * fr.transient;
            for y in (0..DRUM_H).step_by(2) {
                self.add(x, y, OCHRE, s);
            }
        }

        // Beliefs.
        let mut now: Vec<(i64, usize, f32)> = Vec::with_capacity(fr.n as usize);
        for tr in fr.tracks.iter().take(fr.n as usize) {
            let rel = (tr.amp / in_e).clamp(0.0, 1.0);
            let s = 0.28 + 0.72 * rel.sqrt();
            let spine = Self::row(tr.f0);
            if let Some(y) = spine {
                now.push((tr.id, y, rel));
            }
            // Newborns dash (and hide their bend): the transition policy may
            // synthesize them dry, so the amber would overstate the pull.
            let dashed_out = tr.newborn && fr.t % 2 == 0;
            if dashed_out {
                continue;
            }
            // The comb: spine plus only the teeth actually claimed this frame.
            for h in 1..=64u32 {
                if tr.hmask & (1u64 << (h - 1)) == 0 {
                    continue;
                }
                if let Some(y) = Self::row(tr.f0 * h as f32) {
                    self.add(x, y, WHITE, if h == 1 { s } else { s * 0.30 });
                }
            }
            if tr.spared {
                // Threshold mercy: no correction exists; stamp the tolerance.
                if let Some(y) = spine {
                    if y >= 2 {
                        self.add(x, y - 2, OCHRE, 0.9);
                    }
                }
            } else if let Some(y) = Self::row(tr.out) {
                // The bend: where synthesis actually put the spine this frame.
                self.add(x, y, AMBER, 0.35 + 0.65 * rel.sqrt());
            }
        }

        // Ended beliefs: a track present last column and gone now, while it
        // was still loud, was cut mid-word (starved, gated, or stopped) —
        // it gets the ochre terminal tick. Quiet ends are natural fades.
        let prev = std::mem::replace(&mut self.prev, now);
        let mut cut = 0u32;
        for &(id, y, rel) in &prev {
            if rel > 0.15 && !self.prev.iter().any(|&(nid, _, _)| nid == id) {
                cut += 1;
                for dy in y.saturating_sub(1)..=(y + 1).min(DRUM_H - 1) {
                    self.add(x, dy, OCHRE, 1.0);
                }
            }
        }
        cut
    }
}

fn midi_hz(n: usize) -> f32 {
    440.0 * ((n as f32 - 69.0) / 12.0).exp2()
}

/// Deterministic stipple: cheap integer mix of (frame, row) into [0, 1).
fn hash01(t: i64, y: u64) -> f32 {
    let mut h = (t as u64).wrapping_mul(0x9E3779B97F4A7C15) ^ y.wrapping_mul(0xD1B54A32D192ED03);
    h ^= h >> 32;
    h = h.wrapping_mul(0xD6E8FEB86659FD93);
    h ^= h >> 32;
    (h & 0xFFFFFF) as f32 / 16_777_216.0
}

#[cfg(test)]
mod tests {
    use super::*;
    use opq_engine::{VIZ_TRACKS, VizTrack};

    fn frame(t: i64) -> VizFrame {
        VizFrame {
            t,
            flux: 0.0,
            transient: 0.0,
            grid_mask: (1u128 << 60) | (1u128 << 64), // C4 + E4, Custom scope
            in_energy: 1.0,
            res_energy: 0.1,
            res_bands: [0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0],
            n: 1,
            tracks: {
                let mut tr = [VizTrack::default(); VIZ_TRACKS];
                tr[0] = VizTrack {
                    id: 7,
                    f0: 261.63,
                    tgt: 261.63,
                    out: 261.63,
                    amp: 0.8,
                    nh: 3,
                    hmask: 0b111,
                    spared: false,
                    newborn: false,
                };
                tr
            },
        }
    }

    #[test]
    fn draws_rails_spine_and_bend() {
        let mut drum = Drum::new();
        for t in 0..4 {
            drum.push_frame(&frame(t), 5000.0);
        }
        let x = DRUM_W - 1;
        let at = |y: usize| {
            let i = (y * DRUM_W + x) * 4;
            &drum.pixels()[i..i + 3]
        };
        // C4 rail row must be lit (rail + spine + bend all land there).
        let y_c4 = Drum::row(261.63).unwrap();
        assert!(at(y_c4).iter().any(|&v| v > 0), "C4 row dark");
        // E4 rail row lit by the rail alone.
        let y_e4 = Drum::row(midi_hz(64)).unwrap();
        assert!(at(y_e4).iter().any(|&v| v > 0), "E4 rail dark");
        // Second harmonic tooth (C5) lit, dimmer than the spine.
        let y_c5 = Drum::row(523.26).unwrap();
        assert!(at(y_c5).iter().any(|&v| v > 0), "tooth dark");
        // A row far from everything stays black.
        let y_dark = Drum::row(1975.5).unwrap(); // B6, no content
        assert!(at(y_dark).iter().all(|&v| v == 0), "empty row lit");
    }

    /// Renders a full plate from the REAL engine analyzing synthesized audio,
    /// for eyeball verification. Run explicitly:
    /// `cargo test -p opq_plugin_wrac --lib -- --ignored render_plate`
    /// Writes /tmp/opq-drum-plate.ppm (convert: sips -s format png).
    #[test]
    #[ignore]
    fn render_plate() {
        use opq_engine::{Engine, EngineParams, Mode};

        let sr = 44100.0;
        let hop = 1024usize;
        let mut engine = Engine::new(sr, 2);
        let mut drum = Drum::new();

        let p = EngineParams {
            glide: 0.12,
            feel: 0.35,
            threshold_cents: 15.0,
            mode: Mode::Custom,
            ..EngineParams::default()
        };

        // Four detuned pitched voices with slow vibrato, plus one noise burst.
        let voices: [(f32, f32); 4] =
            [(110.0, 0.9), (196.0, 0.7), (293.66, 0.55), (441.5, 0.45)];
        let mut held = [false; 128];
        for n in [48usize, 51, 55] {
            held[n] = true; // C minor, low
        }

        let total_hops = 1080usize;
        let mut phases = [[0.0f64; 8]; 4];
        let mut buf_l = vec![0.0f32; hop];
        let mut buf_r = vec![0.0f32; hop];
        let mut rng = 0x2545F491u64;
        for hi in 0..total_hops {
            // Chord change two-thirds through: C minor -> F major.
            if hi == 420 {
                held = [false; 128];
                for n in [53usize, 57, 60] {
                    held[n] = true;
                }
            }
            // A second of silence near the end: loud beliefs end mid-word.
            let silent = (560..600).contains(&hi);
            for i in 0..hop {
                let t = (hi * hop + i) as f64 / sr as f64;
                let mut s = 0.0f64;
                if !silent {
                    for (vi, &(f, a)) in voices.iter().enumerate() {
                        let vib = 1.0 + 0.004 * (2.0 * std::f64::consts::PI * (0.7 + vi as f64 * 0.13) * t).sin();
                        for h in 1..=6usize {
                            phases[vi][h - 1] +=
                                2.0 * std::f64::consts::PI * f as f64 * vib * h as f64 / sr;
                            s += (a as f64 / h as f64) * 0.12 * phases[vi][h - 1].sin();
                        }
                    }
                }
                // One 25 ms noise burst at ~9.3 s (transient punch-through).
                if (410 * hop..410 * hop + 1100).contains(&(hi * hop + i)) {
                    rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                    s += 0.7 * ((rng >> 33) as f64 / (1u64 << 31) as f64 - 0.5);
                }
                buf_l[i] = s as f32;
                buf_r[i] = s as f32;
            }
            let mut io: [&mut [f32]; 2] = [&mut buf_l, &mut buf_r];
            engine.process_block(&mut io, &held, &p);
            while let Some(fr) = engine.viz_pop() {
                drum.push_frame(&fr, 5000.0);
            }
        }

        let mut out = Vec::with_capacity(DRUM_W * DRUM_H * 3 + 32);
        out.extend_from_slice(format!("P6\n{DRUM_W} {DRUM_H}\n255\n").as_bytes());
        for px in drum.pixels().chunks_exact(4) {
            out.extend_from_slice(&px[..3]);
        }
        std::fs::write("/tmp/opq-drum-plate.ppm", out).unwrap();
    }

    #[test]
    fn loud_death_gets_terminal_tick() {
        let mut drum = Drum::new();
        drum.push_frame(&frame(0), 5000.0);
        let mut dead = frame(1);
        dead.n = 0; // the belief is not continued into this frame
        drum.push_frame(&dead, 5000.0);
        let x = DRUM_W - 1;
        let y = Drum::row(261.63).unwrap();
        let i = (y * DRUM_W + x) * 4;
        let px = &drum.pixels()[i..i + 3];
        // Ochre tick: red strongly above blue.
        assert!(px[0] > 100 && px[2] < 60, "no ochre terminal tick: {px:?}");
    }
}
