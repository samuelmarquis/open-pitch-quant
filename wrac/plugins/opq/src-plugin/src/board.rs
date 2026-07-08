//! The panel. 1280x720 fixed pixels: a control board in the dialect of a
//! plant that processes music as if it were gas, collaged with the paper
//! record of people who tried to write sound down before electricity.
//!
//! Everything that indicates, indicates truly: valves stand where the held
//! chord stands, governors spin only for beliefs the tracker holds, tiles
//! alarm only on states the engine actually reaches, and the drum at center
//! draws the belief transect (drum.rs law). Everything else — engravings,
//! the glass specimen, the graffiti — is declared furniture: the remainder
//! any honest mapping carries. NO BIJECTION — REMAINDER IS CARRIED.
//!
//! The board is pure pixels + hit-testing; the Cocoa mount lives in gui.rs.

use opq_engine::VizFrame;

use crate::assets;
use crate::canvas::{Canvas, Ink, Voice};
use crate::drum::{DRUM_H, DRUM_W, Drum};
use crate::plugin::{
    PARAM_BYPASS_ID, PARAM_CARRY_ID, PARAM_COHERENCE_ID, PARAM_FEEL_ID, PARAM_FMAX_ID,
    PARAM_FORMANT_ID, PARAM_GATE_ID, PARAM_GATE_MODE_ID, PARAM_GLIDE_ID, PARAM_GRIT_ID,
    PARAM_MIX_ID, PARAM_ROUNDING_ID, PARAM_SCOPE_ID, PARAM_THRESHOLD_ID, PARAM_TRANSIENT_ID,
    PARAM_TRANSITIONS_ID, PARAM_UNOWNED_ID, PARAM_VOICES_ID, param_minmax, param_value_text,
};

pub(crate) const BOARD_W: usize = 1280;
pub(crate) const BOARD_H: usize = 720;

const DRUM_X: i32 = 136;
const DRUM_Y: i32 = 48;

// Inks. Red exists on this board only as the breaker handle.
const WHITE: Ink = [232, 228, 216];
const AMBER: Ink = [255, 179, 0];
const OCHRE: Ink = [166, 75, 0];
const GREEN: Ink = [55, 200, 79];
const TEAL: Ink = [79, 184, 196];
const GRAY: Ink = [106, 110, 117];
const DIM: Ink = [35, 38, 43];
const PAPER: Ink = [236, 232, 220];
const RED: Ink = [200, 53, 43];

const NOTE_NAMES: [&str; 12] = [
    "C", "C#", "D", "EB", "E", "F", "F#", "G", "AB", "A", "BB", "B",
];
const NOTE_LOWER: [&str; 12] = [
    "c", "c#", "d", "eb", "e", "f", "f#", "g", "ab", "a", "bb", "b",
];

const GRAFFITI: [&str; 7] = [
    "no bait at the stakes",
    "the dark ones offer nothing to stand on",
    "kept and overwritten in the same motion",
    "a soft crowd of tiny deaths",
    "i have not thrown it in some time",
    "closer to true",
    "the width of my own mercy",
];

/// (param, tag, short label, caption line 1, caption line 2, kind)
#[derive(Clone, Copy, PartialEq)]
enum Kind {
    Valve,
    LogValve,
    Wheel,
    Key,
    Breaker,
}
const FITTINGS: [(u32, &str, &str, &str, &str, Kind); 18] = [
    (PARAM_VOICES_ID, "CLW-2205", "VOICES", "FINGERS THE CLAW", "MAY CLOSE", Kind::Wheel),
    (PARAM_UNOWNED_ID, "UNW-2206", "MAP UNOWNED", "RETURN TO ATMOS-", "PHERE WHEN OFF", Kind::Key),
    (PARAM_GATE_ID, "TG-2260", "TONALITY GATE", "PEAKINESS BELOW", "THIS IS WEATHER", Kind::Valve),
    (PARAM_GATE_MODE_ID, "TGM-2261", "GATE MODE", "FRESH CATCH OR", "WAVE IT THROUGH", Kind::Key),
    (PARAM_FMAX_ID, "CEIL-2270", "MAP CEILING", "THE LAW STOPS", "REACHING HERE", Kind::LogValve),
    (PARAM_TRANSIENT_ID, "PRV-2271", "TRANSIENT BYP", "HITS PASS WHOLE", "NEVER BENT", Kind::Key),
    (PARAM_SCOPE_ID, "SCP-2280", "MIDI SCOPE", "AS PLAYED OR", "EVERY OCTAVE", Kind::Key),
    (PARAM_ROUNDING_ID, "RND-2281", "ROUNDING", "NEAREST TOOTH OR", "REMEMBER THE WAY", Kind::Key),
    (PARAM_THRESHOLD_ID, "THR-2282", "THRESHOLD", "WIDTH OF MERCY", "IN CENTS", Kind::Valve),
    (PARAM_FEEL_ID, "FV-2310", "FEEL", "SPRING PRELOAD", "ON EVERY CATCH", Kind::Valve),
    (PARAM_GLIDE_ID, "GLD-2311", "GLIDE", "HOW LONG THE WALK", "TO THE STAKE", Kind::Valve),
    (PARAM_GRIT_ID, "GRT-2312", "GRIT", "SAND WORKED", "INTO THE COAT", Kind::Valve),
    (PARAM_FORMANT_ID, "THX-2240", "FORMANT", "KEEP THE THROAT", "MOVE THE BONES", Kind::Valve),
    (PARAM_CARRY_ID, "RES-2250", "RESIDUAL CARRY", "HOW MUCH REFUSE", "RIDES ALONG", Kind::Valve),
    (PARAM_COHERENCE_ID, "COH-2320", "COHERENCE", "STRAP LEFT HALF", "TO RIGHT", Kind::Valve),
    (PARAM_TRANSITIONS_ID, "TRN-2321", "TRANSITIONS", "SLIDE TO NEW LAW", "OR FALL DRY", Kind::Key),
    (PARAM_MIX_ID, "MIX-2330", "MIX", "SUNG WATER BRAID-", "ED WITH THE DRY", Kind::Valve),
    (PARAM_BYPASS_ID, "BRK-0001", "BYPASS", "THE SEA", "JUST PLAYS", Kind::Breaker),
];

fn wrap20(s: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur = String::new();
    for w in s.split(' ') {
        if !cur.is_empty() && cur.len() + 1 + w.len() > 20 {
            out.push(std::mem::take(&mut cur));
        }
        if !cur.is_empty() {
            cur.push(' ');
        }
        cur.push_str(w);
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    out
}

fn fitting_rect(i: usize) -> (i32, i32, i32, i32) {
    let col = (i % 9) as i32;
    let row = (i / 9) as i32;
    (136 + col * 113, 524 + row * 92, 112, 88)
}

const ANN_LABELS: [&str; 8] = [
    "NO SIDECHAIN",
    "STALE FEED",
    "CUT MID-WORD",
    "PUNCH THRU",
    "CEIL PASS",
    "MERCY HELD",
    "GRID MOVED",
    "VOICES FULL",
];

fn ann_rect(i: usize) -> (i32, i32, i32, i32) {
    let col = (i % 4) as i32;
    let row = (i / 4) as i32;
    (838 + col * 100, 3 + row * 16, 98, 14)
}
const ACK_RECT: (i32, i32, i32, i32) = (1240, 3, 36, 30);

pub(crate) struct MouseEv {
    pub(crate) x: i32,
    pub(crate) y: i32,
    pub(crate) kind: MouseKind,
}
#[derive(PartialEq)]
pub(crate) enum MouseKind {
    Down,
    Drag,
    Up,
}

pub(crate) enum Edit {
    Begin(u32),
    Value(u32, f32),
    End(u32),
}

struct DragState {
    param: u32,
    kind: Kind,
    y0: i32,
    v0: f32,
    moved: bool,
}

pub(crate) struct Board {
    pub(crate) fb: Vec<u8>,
    base: Vec<u8>,
    base_key: (u32, u32),
    drum: Drum,
    tick: u64,
    // annunciator
    latch_cut: bool,
    hold: [u8; 8],
    last_mask: u128,
    rpt_flag: bool,
    // rolling stats
    stat_mercy: u64,
    stat_cut: u64,
    stat_births: u64,
    last_ids: Vec<i64>,
    spared_ids: Vec<i64>,
    weather_acc: f32,
    weather_n: u32,
    live_n: u8,
    mutter: String,
    // instruments
    flux: [f32; 128],
    flux_head: usize,
    last_frame_tick: u64,
    gallery: Vec<(i64, u16, bool, bool, f32)>, // id, nh, spared, newborn, rel
    census: [u64; 12],
    drag: Option<DragState>,
    graffiti_at: usize,
}

impl Board {
    pub(crate) fn new() -> Self {
        let mut fb = vec![0u8; BOARD_W * BOARD_H * 4];
        for px in fb.chunks_exact_mut(4) {
            px[3] = 255;
        }
        Self {
            fb,
            base: Vec::new(),
            base_key: (0, 0),
            drum: Drum::new(),
            tick: 0,
            latch_cut: false,
            hold: [0; 8],
            last_mask: 0,
            rpt_flag: false,
            stat_mercy: 0,
            stat_cut: 0,
            stat_births: 0,
            last_ids: Vec::new(),
            spared_ids: Vec::new(),
            weather_acc: 0.0,
            weather_n: 0,
            live_n: 0,
            mutter: String::from("warming. the sea just plays."),
            flux: [0.0; 128],
            flux_head: 0,
            last_frame_tick: 0,
            gallery: Vec::new(),
            census: [0; 12],
            drag: None,
            graffiti_at: 0,
        }
    }

    /// Digest frames + params, repaint. Params come as plain values indexed
    /// by id (the same table the host sees).
    pub(crate) fn tick(&mut self, frames: &[VizFrame], params: &[f32; 18], sr: f32, hop: u32) {
        self.tick += 1;
        let ceiling = params[PARAM_FMAX_ID as usize];
        let voices_cap = params[PARAM_VOICES_ID as usize].round() as usize;

        if !frames.is_empty() {
            self.last_frame_tick = self.tick;
        }
        for fr in frames {
            let cut = self.drum.push_frame(fr, ceiling);
            self.stat_cut += cut as u64;
            if cut > 0 {
                self.latch_cut = true;
            }
            let mask = fr.grid_mask & !(1u128 << 127);
            if mask != self.last_mask {
                self.hold[6] = 8;
            }
            self.rpt_flag = fr.grid_mask & (1u128 << 127) != 0;
            self.last_mask = mask;
            if fr.transient > 0.5 {
                self.hold[3] = 16;
            }
            // Mercy is an EVENT: an object entering the threshold window.
            let mut now_spared: Vec<i64> = Vec::new();
            for tr in fr.tracks.iter().take(fr.n as usize) {
                if tr.spared {
                    now_spared.push(tr.id);
                    if !self.spared_ids.contains(&tr.id) {
                        self.stat_mercy += 1;
                        self.hold[5] = 16;
                    }
                }
            }
            if !now_spared.is_empty() {
                self.hold[5] = self.hold[5].max(8);
            }
            self.spared_ids = now_spared;
            // births: ids not seen last frame
            for tr in fr.tracks.iter().take(fr.n as usize) {
                if tr.newborn && !self.last_ids.contains(&tr.id) {
                    self.stat_births += 1;
                }
            }
            self.last_ids.clear();
            self.last_ids
                .extend(fr.tracks.iter().take(fr.n as usize).map(|t| t.id));
            self.live_n = fr.n;
            if fr.n as usize >= voices_cap {
                self.hold[7] = 10;
            }
            // weather + ceiling pass
            let in_e = fr.in_energy.max(1e-9);
            self.weather_acc += (fr.res_energy / in_e).clamp(0.0, 1.0);
            self.weather_n += 1;
            let ceil_band = if ceiling > 16.35 {
                ((ceiling / 16.35).log2() as usize).min(7)
            } else {
                0
            };
            let above: f32 = fr.res_bands[ceil_band.min(7)..].iter().sum();
            if above / in_e > 0.25 {
                self.hold[4] = 16;
            }
            for tr in fr.tracks.iter().take(fr.n as usize) {
                if tr.tgt > 0.0 {
                    let n = (69.0 + 12.0 * (tr.tgt / 440.0).log2()).round() as i64;
                    self.census[(n.rem_euclid(12)) as usize] += 1;
                }
            }
            self.flux[self.flux_head] = fr.flux.min(3.0);
            self.flux_head = (self.flux_head + 1) % self.flux.len();
            // gallery occupancy from the newest frame
            self.gallery.clear();
            for tr in fr.tracks.iter().take(fr.n as usize) {
                self.gallery.push((
                    tr.id,
                    tr.nh,
                    tr.spared,
                    tr.newborn,
                    (tr.amp / in_e).clamp(0.0, 1.0),
                ));
            }
        }
        for h in self.hold.iter_mut() {
            *h = h.saturating_sub(1);
        }
        if self.tick % 90 == 0 {
            self.compose_mutter(voices_cap);
            self.graffiti_at = (self.graffiti_at + 1) % GRAFFITI.len();
        }

        self.paint(params, sr, hop, voices_cap);
    }

    fn compose_mutter(&mut self, cap: usize) {
        let weather = if self.weather_n == 0 {
            0.0
        } else {
            self.weather_acc / self.weather_n as f32
        };
        self.weather_acc = 0.0;
        self.weather_n = 0;
        let wtxt = if weather < 0.2 {
            "weather light"
        } else if weather < 0.5 {
            "weather moderate"
        } else {
            "weather heavy"
        };
        let mask = self.last_mask;
        let chord = if mask == 0 {
            String::from("the map is nothing. the sea just plays")
        } else {
            let mut pcs: Vec<&str> = Vec::new();
            for pc in 0..12 {
                for n in (pc..127).step_by(12) {
                    if mask & (1u128 << n) != 0 {
                        pcs.push(NOTE_LOWER[pc]);
                        break;
                    }
                }
            }
            format!("the map is {}", pcs.join(" "))
        };
        self.mutter = format!(
            "{chord} + {} of {cap} voices + {wtxt} + {} mercies + {} cut + {} born",
            self.live_n, self.stat_mercy, self.stat_cut, self.stat_births
        );
    }

    // ------------------------------------------------------------- painting

    /// Static furniture — engravings, plates, tags, captions, print marks —
    /// is painted once and memcpy'd under every frame; paint() then draws
    /// only what moves. Rebuilt if the engine info ever changes.
    fn ensure_base(&mut self, sr: f32, hop: u32) {
        if self.base_key == (sr.to_bits(), hop) && !self.base.is_empty() {
            return;
        }
        self.base_key = (sr.to_bits(), hop);
        let mut base = vec![0u8; BOARD_W * BOARD_H * 4];
        let mut c = Canvas::new(&mut base, BOARD_W, BOARD_H);
        c.clear();

        // Furniture layer (declared remainder): the plunder, dim, under ink.
        c.blit(assets::gray907(), 0, -215, 20, [120, 150, 158], 0.08, 480, 300);
        c.blit(assets::blake_ear(), 0, 900, 396, PAPER, 0.26, 1, 1);
        c.blit(assets::gray907(), 0, 1156, 344, TEAL, 0.42, 124, 300);
        c.blit(assets::redon_ghost(), 0, 1154, 452, [190, 180, 168], 1.0, 124, 300);

        // Header: misregistered under-strike, then the paper hit.
        c.haas(assets::haas30(), "OPEN PITCH QUANT", 10, 29, OCHRE, 0.55, Voice::Crunch);
        c.haas(assets::haas30(), "OPEN PITCH QUANT", 8, 27, PAPER, 0.92, Voice::Crunch);
        let lag_ms = opq_engine::N_FFT as f32 / sr * 1000.0;
        c.text5(&format!("SR {:.0}", sr), 356, 4, TEAL, 200);
        c.text5(&format!("HOP {hop}"), 356, 13, TEAL, 200);
        c.text5(
            concat!("PANEL NO.1 REV ", env!("CARGO_PKG_VERSION")),
            356,
            22,
            TEAL,
            200,
        );
        c.frame(432, 2, 176, 32, GRAY, 140);
        c.text5("NO BIJECTION", 440, 7, OCHRE, 235);
        c.text5("REMAINDER IS CARRIED", 440, 17, OCHRE, 200);
        c.text5("INTAKE>SIEVE>SORT>CLAW>GOV>STAMP>OUT", 616, 6, GRAY, 140);
        c.text5("MIDI IS LAW NOT SIGNAL", 616, 16, TEAL, 120);
        c.haas(
            assets::haas10(),
            "real-time polyphonic pitch remapping - midi sidechain flavor",
            432,
            44,
            GRAY,
            0.9,
            Voice::Slip,
        );

        // Annunciator at rest + ACK key.
        for (i, label) in ANN_LABELS.iter().enumerate() {
            let (x, y, w, h) = ann_rect(i);
            c.fill(x, y, w, h, DIM, 255);
            c.frame(x, y, w, h, GRAY, 90);
            c.text5(label, x + 3, y + 4, GRAY, 120);
        }
        {
            let (x, y, w, h) = ACK_RECT;
            c.fill(x, y, w, h, DIM, 255);
            c.frame(x, y, w, h, TEAL, 180);
            c.text5("ACK", x + 9, y + 12, TEAL, 230);
        }

        // Stencil strip.
        c.text5("MIDI MAP SEMANTICS - EMPTY SET IS SILENCE", 8, 38, TEAL, 150);
        c.text5(&format!("LAG {:.1}MS DO NOT RUSH", lag_ms), 1120, 38, AMBER, 170);

        // Manifold plate: titles + valve bodies (state is painted live).
        c.text5("HDR-2201", 4, 52, TEAL, 220);
        c.text5("TARGET MANIFOLD", 4, 61, GRAY, 170);
        for pc in 0..12usize {
            let y = 74 + (11 - pc) as i32 * 27;
            c.fill(24, y + 6, 34, 8, DIM, 255);
            c.frame(24, y + 6, 34, 8, GRAY, 140);
        }

        // Drum housing (interior is repainted live; the frame is plate).
        c.frame(DRUM_X - 1, DRUM_Y - 1, DRUM_W as i32 + 2, DRUM_H as i32 + 2, GRAY, 120);

        // Right rail plates.
        let rx = 1156;
        c.text5("FLX-2205", rx, 52, TEAL, 200);
        c.text5("ONSET FLUX", rx + 56, 52, GRAY, 150);
        c.frame(rx, 62, 124, 100, GRAY, 120);
        c.text5("SESSION REGISTER", rx, 170, TEAL, 200);
        c.text5("TARGET CENSUS", rx, 226, TEAL, 200);
        c.text5("OSSEOUS LABYRINTH", rx, 330, TEAL, 170);
        c.text5("AFTER GRAY 1858", rx, 339, GRAY, 130);
        c.text5("PANEL NO.1 / SCALE 1:1", rx, 692, GRAY, 140);
        c.text5("DO NOT REDUCE", rx, 701, GRAY, 140);

        // Gallery title (the claw limit is live).
        c.text5("GOV-2230 PHASE GOVERNOR GALLERY", DRUM_X + 2, 440, TEAL, 210);

        // Fittings: flow spine, warning, cell plates, the pasted
        // transparency riding over them, then the static lettering.
        c.hline_dotted(DRUM_X, 1152, 520, GRAY, 110, 2);
        c.text5("DO NOT ADJUST UNDER LOAD", 560, 514, OCHRE, 150);
        for (i, _) in FITTINGS.iter().enumerate() {
            let (x, y, w, h) = fitting_rect(i);
            c.fill(x, y, w, h, [12, 13, 15], 190);
            c.frame(x, y, w, h, GRAY, 110);
        }
        c.blit(assets::phonautograph(), 0, 500, 470, PAPER, 0.20, 1, 1);
        for (i, &(_, tag, label, cap1, cap2, _)) in FITTINGS.iter().enumerate() {
            let (x, y, w, h) = fitting_rect(i);
            c.text5(tag, x + 4, y + 3, TEAL, 200);
            c.text5(label, x + 4, y + 12, WHITE, 230);
            c.text5(cap1, x + 4, y + h - 20, GRAY, 130);
            c.text5(cap2, x + 4, y + h - 11, GRAY, 130);
            c.line(x + w / 2, 520, x + w / 2, y, DIM, 160);
        }

        // Left column lower plates.
        c.text5("PLATE FIGURE", 4, 440, TEAL, 200);
        c.frame(2, 458, 128, 128, GRAY, 130);
        c.text5("SAND ON GLASS", 4, 588, GRAY, 110);
        c.text5("SPECIMEN 001", 4, 600, TEAL, 200);
        c.text5("THE MAP", 4, 609, GRAY, 160);
        c.ring(52, 655, 49, [70, 90, 96], 120);
        c.fill(10, 703, 86, 2, GRAY, 160);
        c.haas(
            assets::haas10(),
            "it does not know it is held",
            6,
            700,
            [150, 145, 135],
            0.7,
            Voice::Slip,
        );

        // Print furniture: crop marks + the ink control strip.
        for &(cx, cy, dx, dy) in
            &[(2i32, 2i32, 1i32, 1i32), (1277, 2, -1, 1), (2, 717, 1, -1), (1277, 717, -1, -1)]
        {
            c.line(cx, cy, cx + dx * 8, cy, GRAY, 150);
            c.line(cx, cy, cx, cy + dy * 8, GRAY, 150);
        }
        for (i, ink) in [WHITE, AMBER, OCHRE, GREEN, TEAL, GRAY, RED, PAPER].iter().enumerate() {
            c.fill(14 + i as i32 * 11, 710, 10, 7, *ink, 255);
        }
        let sig = "org.open-pitch-quant.opq";
        let wsig = assets::haas10().measure(sig) as i32;
        c.haas(assets::haas10(), sig, 1276 - wsig, 716, GRAY, 0.8, Voice::Clean);

        self.base = base;
    }

    fn paint(&mut self, params: &[f32; 18], sr: f32, hop: u32, voices_cap: usize) {
        self.ensure_base(sr, hop);
        let drum_px: Vec<u8> = self.drum.pixels().to_vec();
        let mask = self.last_mask;
        let tick = self.tick;
        let hold = self.hold;
        let latch_cut = self.latch_cut;
        let live_n = self.live_n;
        let stale = tick.saturating_sub(self.last_frame_tick) > 30;
        let gallery = self.gallery.clone();
        let flux = self.flux;
        let flux_head = self.flux_head;
        let mutter = self.mutter.clone();
        let graffiti_at = self.graffiti_at;
        let stats = (self.stat_mercy, self.stat_cut, self.stat_births);
        let census = self.census;
        let drag_param = self.drag.as_ref().map(|d| d.param);
        let rpt = self.rpt_flag;

        self.fb.copy_from_slice(&self.base);
        let mut c = Canvas::new(&mut self.fb, BOARD_W, BOARD_H);

        // Annunciator: only lit tiles overdraw the resting plate.
        let lit = [
            mask == 0 && live_n == 0 && !stale,
            stale,
            latch_cut,
            hold[3] > 0,
            hold[4] > 0,
            hold[5] > 0,
            hold[6] > 0,
            hold[7] > 0,
        ];
        for (i, label) in ANN_LABELS.iter().enumerate() {
            if lit[i] {
                let (x, y, w, h) = ann_rect(i);
                c.fill(x, y, w, h, AMBER, 255);
                c.text5(label, x + 3, y + 4, [20, 16, 4], 255);
            }
        }

        // Manifold state.
        for pc in 0..12usize {
            let y = 74 + (11 - pc) as i32 * 27;
            let open = (0..127).any(|n| n % 12 == pc && mask & (1u128 << n) != 0);
            let ink = if open { AMBER } else { GRAY };
            c.ring(41, y + 10, 8, ink, if open { 255 } else { 90 });
            c.line(41 - 5, y + 10, 41 + 5, y + 10, ink, if open { 255 } else { 90 });
            if open {
                c.fill(40, y - 2, 3, 8, AMBER, 220);
                c.disc(62, y + 10, 2, GREEN, 255);
            } else {
                c.fill(40, y + 4, 3, 4, GRAY, 120);
            }
            c.text5(
                NOTE_NAMES[pc],
                4,
                y + 7,
                if open { WHITE } else { GRAY },
                if open { 255 } else { 120 },
            );
            c.hline_dotted(
                68,
                DRUM_X,
                y + 10,
                if open { AMBER } else { DIM },
                if open { 90 } else { 60 },
                3,
            );
        }
        if rpt {
            c.fill(4, 412, 58, 12, DIM, 255);
            c.text5("RPT OCT", 8, 415, GREEN, 230);
        }

        // The drum (opaque; belief law holds inside this rectangle), then
        // its instrument lettering and depth marks.
        for y in 0..DRUM_H {
            let src = &drum_px[y * DRUM_W * 4..(y + 1) * DRUM_W * 4];
            let dy = DRUM_Y as usize + y;
            let di = (dy * BOARD_W + DRUM_X as usize) * 4;
            c.fb[di..di + DRUM_W * 4].copy_from_slice(src);
        }
        c.text5("REC-1859 BELIEF TRANSECT", DRUM_X + 5, DRUM_Y + 4, TEAL, 170);
        c.text5(
            "C0 FLOOR / C8 ROOF / OCHRE IS EVERY NO",
            DRUM_X + 5,
            DRUM_Y + DRUM_H as i32 - 11,
            GRAY,
            120,
        );
        for oct in 1..8i32 {
            let y = DRUM_Y + (8 - oct) * 48;
            c.text5(&format!("C{oct}"), DRUM_X + 3, y - 3, GRAY, 95);
            c.hline_dotted(DRUM_X + 16, DRUM_X + 40, y, GRAY, 70, 4);
        }

        // Right rail: flux, register, census.
        let rx = 1156;
        for i in 0..122 {
            let v = flux[(flux_head + 128 - 122 + i) % 128];
            let h = (v / 3.0 * 96.0) as i32;
            let x = rx + 1 + i as i32;
            if h <= 0 {
                c.mix(x, 160, GRAY, 90);
            } else {
                c.line(x, 160, x, 160 - h.min(96), WHITE, 110);
            }
        }
        let ty = 160 - (0.6 / 3.0 * 96.0) as i32;
        c.hline_dotted(rx + 1, rx + 123, ty, OCHRE, 220, 3); // flux_thresh 0.6
        c.text5(&format!("MERCIES {:>6}", stats.0), rx, 182, WHITE, 190);
        c.text5(&format!("CUT     {:>6}", stats.1), rx, 192, OCHRE, 220);
        c.text5(&format!("BORN    {:>6}", stats.2), rx, 202, WHITE, 190);
        c.text5(&format!("HELD NOW    {:>2}", live_n), rx, 212, WHITE, 190);
        let cmax = census.iter().copied().max().unwrap_or(1).max(1);
        for pc in 0..12usize {
            let y = 236 + (11 - pc) as i32 * 7;
            c.text5(
                NOTE_NAMES[pc],
                rx,
                y,
                if census[pc] > 0 { WHITE } else { GRAY },
                if census[pc] > 0 { 190 } else { 90 },
            );
            let bar = ((census[pc] as f32 / cmax as f32) * 60.0) as i32;
            if bar > 0 {
                c.fill(rx + 16, y + 1, bar, 4, AMBER, 150);
            }
            if census[pc] > 0 {
                c.text5(&format!("{:>5}", census[pc].min(99999)), rx + 92, y, GRAY, 150);
            }
        }

        // Graffiti over the one-eyed ghost.
        let mut gy = 574;
        for k in 0..3usize {
            let line = GRAFFITI[(graffiti_at + k) % GRAFFITI.len()];
            for piece in wrap20(line) {
                c.haas(assets::haas10(), &piece, rx + 2, gy, [188, 182, 170], 0.75, Voice::Slip);
                gy += 12;
            }
            gy += 5;
        }

        // Governor gallery.
        c.text5(
            &format!("CLAW LIMIT {voices_cap}"),
            DRUM_X + 2 + 200,
            440,
            AMBER,
            190,
        );
        for s in 0..12usize {
            let x = DRUM_X + 2 + s as i32 * 85;
            let y = 452;
            c.frame(x, y, 80, 64, GRAY, if s < voices_cap { 130 } else { 60 });
            if s >= voices_cap {
                c.text5("PLUGGED", x + 18, y + 28, GRAY, 90);
                continue;
            }
            if let Some(&(id, nh, spared, newborn, rel)) = gallery.get(s) {
                let cx = x + 26;
                let cy = y + 30;
                let ring_ink = if spared { OCHRE } else { WHITE };
                if newborn && tick % 2 == 0 {
                    c.ring(cx, cy, 15, ring_ink, 90);
                } else {
                    c.ring(cx, cy, 15, ring_ink, 200);
                }
                let spread = 4.0 + (nh as f32).min(24.0) * 0.42;
                for arm in 0..3 {
                    let a = tick as f32 * 0.35 + arm as f32 * 2.094 + id as f32;
                    let (sx, sy) = (a.cos() * spread, a.sin() * spread * 0.55);
                    c.line(cx, cy, cx + sx as i32, cy + sy as i32, GRAY, 190);
                    c.disc(cx + sx as i32, cy + sy as i32, 2, ring_ink, 230);
                }
                let bar = (rel.sqrt() * 40.0) as i32;
                c.fill(x + 48, y + 50 - bar, 6, bar, AMBER, 180);
                c.text5(&format!("NH{nh:02}"), x + 46, y + 8, GRAY, 160);
                c.text5(&format!("{:03}", (id % 1000).abs()), x + 46, y + 18, TEAL, 170);
                if spared {
                    c.text5("MERCY", x + 6, y + 52, OCHRE, 220);
                }
            } else {
                c.ring(x + 26, y + 30, 15, GRAY, 60);
                c.text5("OPEN", x + 16, y + 52, GREEN, 90);
            }
        }

        // Fittings: live glyphs, readouts, and the active highlight.
        for (i, &(pid, _, _, _, _, kind)) in FITTINGS.iter().enumerate() {
            let (x, y, w, h) = fitting_rect(i);
            let v = params[pid as usize];
            let (lo, hi) = param_minmax(pid);
            let t = if kind == Kind::LogValve {
                ((v / lo.max(1.0)).ln() / (hi / lo.max(1.0)).ln()).clamp(0.0, 1.0)
            } else {
                ((v - lo) / (hi - lo).max(1e-9)).clamp(0.0, 1.0)
            };
            let active = drag_param == Some(pid);
            if active {
                c.frame(x, y, w, h, AMBER, 220);
            }
            let gx = x + 20;
            let gy = y + 44;
            match kind {
                Kind::Valve | Kind::LogValve => {
                    c.ring(gx, gy, 12, GRAY, 200);
                    let a = -2.2 + t * 4.4 + std::f32::consts::FRAC_PI_2;
                    for spoke in 0..4 {
                        let aa = a + spoke as f32 * std::f32::consts::FRAC_PI_2;
                        c.line(
                            gx,
                            gy,
                            gx + (aa.cos() * 11.0) as i32,
                            gy - (aa.sin() * 11.0) as i32,
                            if active { AMBER } else { WHITE },
                            220,
                        );
                    }
                    c.disc(gx, gy, 2, if active { AMBER } else { WHITE }, 255);
                    let stem = (t * 12.0) as i32;
                    c.fill(gx - 1, gy - 14 - stem, 3, stem + 2, GRAY, 200);
                }
                Kind::Wheel => {
                    c.fill(gx - 12, gy - 10, 24, 20, DIM, 255);
                    c.frame(gx - 12, gy - 10, 24, 20, GRAY, 180);
                    for r in 0..5 {
                        c.mix(gx - 12 + 3 + r * 4, gy + 12, GRAY, 150);
                    }
                    c.text5(&format!("{:>2.0}", v), gx - 6, gy - 3, AMBER, 255);
                }
                Kind::Key => {
                    c.fill(gx - 14, gy - 6, 28, 12, DIM, 255);
                    c.frame(gx - 14, gy - 6, 28, 12, GRAY, 180);
                    let on = v >= 0.5;
                    let kx = if on { gx + 6 } else { gx - 6 };
                    c.fill(kx - 4, gy - 4, 8, 8, if on { GREEN } else { GRAY }, 255);
                }
                Kind::Breaker => {
                    c.frame(gx - 10, gy - 14, 20, 28, GRAY, 200);
                    let on = v >= 0.5; // bypass engaged = thrown
                    let hy = if on { gy + 6 } else { gy - 6 };
                    c.fill(gx - 6, hy - 3, 12, 6, RED, 255);
                    c.line(gx, gy - 14, gx, hy, RED, 200);
                    if on {
                        c.text5("THROWN", x + 4, y + 66, RED, 230);
                    }
                }
            }
            let txt = param_value_text(pid, v as f64);
            c.text5(&txt.to_ascii_uppercase(), x + 44, y + 34, AMBER, 235);
        }

        // Chladni sand for the held-tone count, then its corner screws.
        let held_pcs = (0..12usize)
            .filter(|&pc| (0..127).any(|n| n % 12 == pc && mask & (1u128 << n) != 0))
            .count();
        c.text5(&format!("{held_pcs} TONES HELD"), 4, 449, GRAY, 160);
        c.blit(assets::chladni(), held_pcs.min(6), 3, 459, PAPER, 0.95, 126, 128);
        for &(sx, sy) in &[(8, 464), (124, 464), (8, 580), (124, 580)] {
            c.disc(sx, sy, 2, GRAY, 220);
            c.mix(sx, sy, [15, 16, 18], 255);
        }

        // The specimen, tinted by how much of the sung water is in the pipe.
        let mix = params[PARAM_MIX_ID as usize];
        let tint: Ink = [
            (236.0 + (255.0 - 236.0) * mix) as u8,
            (236.0 + (179.0 - 236.0) * mix) as u8,
            (236.0 * (1.0 - mix)) as u8,
        ];
        let bob = ((tick as f32 * 0.05).sin() * 3.0) as i32;
        c.blit(assets::trefoil(), (tick / 3) as usize % 24, 2, 596 + bob, tint, 0.96, 100, 128);

        // Mutter.
        c.fill(DRUM_X, 706, 1016, 14, [0, 0, 0], 255);
        c.haas(assets::haas14(), &mutter, DRUM_X, 716, PAPER, 0.85, Voice::Clean);
    }

    // ------------------------------------------------------------- input


    pub(crate) fn on_mouse(&mut self, ev: MouseEv, params: &[f32; 18]) -> Vec<Edit> {
        let mut out = Vec::new();
        match ev.kind {
            MouseKind::Down => {
                // ACK
                let (ax, ay, aw, ah) = ACK_RECT;
                if ev.x >= ax && ev.x < ax + aw && ev.y >= ay && ev.y < ay + ah {
                    self.latch_cut = false;
                    return out;
                }
                for (i, &(pid, .., kind)) in FITTINGS.iter().enumerate() {
                    let (x, y, w, h) = fitting_rect(i);
                    if ev.x >= x && ev.x < x + w && ev.y >= y && ev.y < y + h {
                        self.drag = Some(DragState {
                            param: pid,
                            kind,
                            y0: ev.y,
                            v0: params[pid as usize],
                            moved: false,
                        });
                        out.push(Edit::Begin(pid));
                        break;
                    }
                }
            }
            MouseKind::Drag => {
                if let Some(d) = &mut self.drag {
                    let dy = (d.y0 - ev.y) as f32;
                    if dy.abs() > 2.0 {
                        d.moved = true;
                    }
                    let (lo, hi) = param_minmax(d.param);
                    let v = match d.kind {
                        Kind::Valve => d.v0 + (hi - lo) * dy / 120.0,
                        Kind::LogValve => d.v0 * (2.0f32).powf(dy / 40.0),
                        Kind::Wheel => d.v0 + dy / 12.0,
                        Kind::Key | Kind::Breaker => return out,
                    }
                    .clamp(lo, hi);
                    out.push(Edit::Value(d.param, v));
                }
            }
            MouseKind::Up => {
                if let Some(d) = self.drag.take() {
                    if !d.moved && matches!(d.kind, Kind::Key | Kind::Breaker) {
                        let (lo, hi) = param_minmax(d.param);
                        let v = if d.v0 >= 0.5 * (lo + hi) { lo } else { hi };
                        out.push(Edit::Value(d.param, v));
                    }
                    out.push(Edit::End(d.param));
                }
            }
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn drag_on_feel_valve_edits_param() {
        let mut b = Board::new();
        let mut params: [f32; 18] = std::array::from_fn(|i| crate::plugin::param_default(i as u32));
        params[PARAM_FEEL_ID as usize] = 0.35;
        let (x, y, w, h) = fitting_rect(9); // FEEL cell (row 2, col 1)
        assert_eq!(FITTINGS[9].0, PARAM_FEEL_ID);
        let (cx, cy) = (x + w / 2, y + h / 2);
        let ev = |kind, dy: i32| MouseEv { x: cx, y: cy - dy, kind };
        let down = b.on_mouse(ev(MouseKind::Down, 0), &params);
        assert!(matches!(down[0], Edit::Begin(id) if id == PARAM_FEEL_ID));
        let drag = b.on_mouse(ev(MouseKind::Drag, 60), &params);
        let Edit::Value(id, v) = drag[0] else { panic!("expected value") };
        assert_eq!(id, PARAM_FEEL_ID);
        assert!((v - 0.85).abs() < 0.01, "60px = half range: {v}");
        let up = b.on_mouse(ev(MouseKind::Up, 60), &params);
        assert!(matches!(up[0], Edit::End(id) if id == PARAM_FEEL_ID));
    }

    #[test]
    fn click_toggles_key_and_breaker() {
        let mut b = Board::new();
        let mut params: [f32; 18] = std::array::from_fn(|i| crate::plugin::param_default(i as u32));
        params[PARAM_TRANSIENT_ID as usize] = 1.0; // On
        let idx = FITTINGS.iter().position(|f| f.0 == PARAM_TRANSIENT_ID).unwrap();
        let (x, y, w, h) = fitting_rect(idx);
        let ev = |kind| MouseEv { x: x + w / 2, y: y + h / 2, kind };
        b.on_mouse(ev(MouseKind::Down), &params);
        let up = b.on_mouse(ev(MouseKind::Up), &params);
        assert!(matches!(up[0], Edit::Value(id, v) if id == PARAM_TRANSIENT_ID && v == 0.0));
        assert!(matches!(up[1], Edit::End(_)));
    }

    #[test]
    fn ack_clears_the_latch() {
        let mut b = Board::new();
        b.latch_cut = true;
        let params: [f32; 18] = std::array::from_fn(|i| crate::plugin::param_default(i as u32));
        let (ax, ay, ..) = ACK_RECT;
        let out = b.on_mouse(MouseEv { x: ax + 5, y: ay + 5, kind: MouseKind::Down }, &params);
        assert!(out.is_empty());
        assert!(!b.latch_cut);
    }

    /// Renders the full panel from the REAL engine for eyeball verification
    /// (the catalogue). Run explicitly:
    /// `cargo test -p opq_plugin_wrac --lib --release -- --ignored render_panel`
    /// Writes $OPQ_PLATE (default /tmp/opq-panel.ppm).
    #[test]
    #[ignore]
    fn render_panel() {
        use crate::plugin::{
            PARAM_FEEL_ID as FEEL, PARAM_GLIDE_ID as GLIDE, PARAM_MIX_ID as MIX,
            PARAM_THRESHOLD_ID as THRESH,
        };
        use opq_engine::{Engine, EngineParams, Mode};

        let sr = 44100.0;
        let hop = 1024usize;
        let mut engine = Engine::new(sr, 2);
        let mut board = Board::new();

        let mut params: [f32; 18] = std::array::from_fn(|i| crate::plugin::param_default(i as u32));
        params[FEEL as usize] = 0.35;
        params[GLIDE as usize] = 0.12;
        params[THRESH as usize] = 15.0;
        params[MIX as usize] = 0.85;

        let ep = EngineParams {
            glide: 0.12,
            feel: 0.35,
            threshold_cents: 15.0,
            mode: Mode::Custom,
            ..EngineParams::default()
        };

        let voices: [(f32, f32); 5] = [
            (110.0, 0.9),
            (196.0, 0.7),
            (293.66, 0.55),
            (441.5, 0.45),
            (660.0, 0.3),
        ];
        let mut held = [false; 128];
        for n in [48usize, 51, 55] {
            held[n] = true;
        }

        let total_hops = 1180usize;
        let mut phases = [[0.0f64; 8]; 5];
        let mut buf_l = vec![0.0f32; hop];
        let mut buf_r = vec![0.0f32; hop];
        let mut rng = 0x2545F491u64;
        let mut pending: Vec<opq_engine::VizFrame> = Vec::new();
        for hi in 0..total_hops {
            if hi == 700 {
                held = [false; 128];
                for n in [53usize, 57, 60] {
                    held[n] = true;
                }
            }
            let silent = (980..1030).contains(&hi);
            for i in 0..hop {
                let t = (hi * hop + i) as f64 / sr;
                let mut s = 0.0f64;
                if !silent {
                    for (vi, &(f, a)) in voices.iter().enumerate() {
                        let vib = 1.0
                            + 0.004
                                * (2.0 * std::f64::consts::PI * (0.7 + vi as f64 * 0.13) * t)
                                    .sin();
                        for h in 1..=6usize {
                            phases[vi][h - 1] +=
                                2.0 * std::f64::consts::PI * f as f64 * vib * h as f64 / sr;
                            s += (a as f64 / h as f64) * 0.10 * phases[vi][h - 1].sin();
                        }
                    }
                }
                if (690 * hop..690 * hop + 1100).contains(&(hi * hop + i)) {
                    rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                    s += 0.7 * ((rng >> 33) as f64 / (1u64 << 31) as f64 - 0.5);
                }
                buf_l[i] = s as f32;
                buf_r[i] = s as f32;
            }
            let mut io: [&mut [f32]; 2] = [&mut buf_l, &mut buf_r];
            engine.process_block(&mut io, &held, &ep);
            while let Some(fr) = engine.viz_pop() {
                pending.push(fr);
            }
            // ~30 Hz cadence vs 43 frames/s: tick with 1-2 frames alternately
            let take = if hi % 3 == 0 { 2 } else { 1 };
            if pending.len() >= take {
                let batch: Vec<_> = pending.drain(..take.min(pending.len())).collect();
                board.tick(&batch, &params, sr as f32, hop as u32);
            }
        }
        board.tick(&pending.drain(..).collect::<Vec<_>>(), &params, sr as f32, hop as u32);

        eprintln!("census: {:?}", board.census);
        eprintln!("hold: {:?} latch_cut: {}", board.hold, board.latch_cut);
        let path =
            std::env::var("OPQ_PLATE").unwrap_or_else(|_| "/tmp/opq-panel.ppm".to_string());
        let mut out = Vec::with_capacity(BOARD_W * BOARD_H * 3 + 32);
        out.extend_from_slice(format!("P6\n{BOARD_W} {BOARD_H}\n255\n").as_bytes());
        for px in board.fb.chunks_exact(4) {
            out.extend_from_slice(&px[..3]);
        }
        std::fs::write(path, out).unwrap();
    }
}
