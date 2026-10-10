//! The board: one canvas, drawn the same mounted and offline.
//!
//! The family's look (OpenCepstrum's rt/panel there): a monitor housing on a
//! black board carries the screen; the infotext line under it says what the
//! pointer is over; baked plates beneath carry baked controls, each with
//! its caption, which shows the value while the control is in use
//! (panelkit's guide); the bottom row (panelkit's strip) carries MIX as
//! text and the product's name.
//!
//! The screen is ink on paper (Sam, 2026-10-10: "it's almost like
//! calligraphy on paper"): a paper-white field with dark markings. Its law,
//! kept from the old panel: everything that indicates, indicates truly. The
//! transect draws only what the engine reported: each object's source pitch
//! (pencil), the pitch it was sung at (ink), and the targets (blue ink).
//! Sepia is spent only on refusal: an object Threshold spared, a bypassed
//! key, and the map ceiling.
use crate::layout::{self, Control, Kind, Plate, Viewer, Widget, INFO, PLOT, RULER, SCREEN, WIDGETS};
use crate::{pack, PanelState, HISTORY};
use opq_engine::params::{self as p, KeyState, SPECS};
use opq_engine::{scope_db, scope_note, VizFrame, SCOPE_BINS, SCOPE_PER_NOTE};
use panelkit::canvas::{opacity, paint, Canvas, Rect};
use panelkit::gpu::Gpu;
use panelkit::hover::HoverInfo;
use panelkit::pack::Pack;
use panelkit::{strip, widgets};
use std::path::Path;

const VERTEX_CAPACITY: usize = 600_000;
use layout::FONT_SIZES;
const VALUE: usize = 0;
const CAPTION: usize = 1;
const TITLE: usize = 2;
const SMALL: usize = 3;

// The board's palette (linear): OpenCepstrum's, for text on the black
// board and the plates.
const WHITE: [f32; 4] = [1.0, 1.0, 1.0, 1.0];
const BLACK: [f32; 4] = [0.0, 0.0, 0.0, 1.0];
const INK: [f32; 4] = [0.70, 0.76, 0.81, 1.0];
const MUTED: [f32; 4] = [0.25, 0.30, 0.35, 1.0];
const MINT: [f32; 4] = [0.12, 0.76, 0.91, 1.0];

// The screen's palette (linear): ink on paper.
/// The paper: a warm off-white (sRGB 237 232 219).
const PAPER: [f32; 4] = [0.846, 0.807, 0.708, 1.0];
/// The white keys, a shade under the paper.
const PAPER_KEY: [f32; 4] = [0.66, 0.62, 0.53, 1.0];
/// Black ink: the sung pitch, rules, figures, the black keys.
const SUMI: [f32; 4] = [0.006, 0.007, 0.011, 1.0];
/// Pencil: the source pitch, what the tracker heard.
const PENCIL: [f32; 4] = [0.16, 0.16, 0.17, 1.0];
/// Blue ink: the targets (sRGB 31 56 140).
const BLUE: [f32; 4] = [0.0137, 0.0395, 0.262, 1.0];
/// Sepia: refusal only (sRGB 158 82 20).
const SEPIA: [f32; 4] = [0.341, 0.0844, 0.007, 1.0];
/// Vermilion: an object being born, an onset (sRGB 204 52 26).
const VERMILION: [f32; 4] = [0.604, 0.034, 0.010, 1.0];

/// OpenCepstrum's knob shadow and fill.
const KNOB_SHADOW: [(f32, f32, f32, f32); 4] = [
    (0.6, 1.0, 1.0, 0.22),
    (1.2, 2.2, 1.03, 0.12),
    (2.0, 3.6, 1.07, 0.07),
    (3.0, 5.2, 1.12, 0.04),
];
const KNOB_FILL: f32 = 1.03;
const SWITCH_SHADOW: [(f32, f32, f32, f32); 2] = [(0.8, 1.6, 1.0, 0.30), (1.8, 3.2, 1.06, 0.12)];

/// The ladders: a second of frames per column (47 a second at 48 kHz),
/// the rungs the tracker reads (audiokit's 20 harmonics), and a column's
/// widest.
const LADDER_FRAMES: usize = 47;
const LADDER_RUNGS: u32 = 20;
const LADDER_COLUMN_MAX: f32 = 156.0;
/// The scope: its level span (the left edge, up to a full-scale sine at
/// the right), frames averaged for its traces, frames its peaks hold.
const SCOPE_DB_MIN: f32 = -96.0;
const SCOPE_AVERAGE_FRAMES: usize = 4;
const SCOPE_PEAK_FRAMES: usize = 47;

const NOTE_NAMES: [&str; 12] = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

/// `a` toward `b` by `t`, opaque.
fn mix(a: [f32; 4], b: [f32; 4], t: f32) -> [f32; 4] {
    [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, 1.0]
}

/// A MIDI note's name, octave signed (note 0 is C-1).
fn note_name(note: u32) -> String {
    format!("{}{}", NOTE_NAMES[(note % 12) as usize], (note / 12) as i32 - 1)
}

/// The bypass modifier, named as the platform's keyboard names it.
const BYPASS_CLICK: &str = if cfg!(target_os = "macos") { "Option-click" } else { "Alt-click" };

/// Texture slots, in upload order after the canvas's white texture and
/// the font.
struct Textures {
    bezel: usize,
    plates: [usize; 3],
    knobs: [usize; 6],
    /// Voices' stepped strip, one cell per step.
    voices: usize,
    selector: [usize; 2],
    toggle: [usize; 2],
    /// The viewer keys' row: each key up, then lit.
    viewer_keys: usize,
}

pub struct Board {
    canvas: Canvas,
    t: Textures,
}

impl std::ops::Deref for Board {
    type Target = Canvas;
    fn deref(&self) -> &Canvas {
        &self.canvas
    }
}

impl std::ops::DerefMut for Board {
    fn deref_mut(&mut self) -> &mut Canvas {
        &mut self.canvas
    }
}

/// A plate's ink: captions are engraved light on the anodized blue and the
/// catalin jade, dark on the brass; the bottom row's text is the board's
/// ink.
fn plate_ink(plate: Plate) -> [f32; 4] {
    match plate {
        Plate::Capture => [0.86, 0.88, 0.90, 1.0],
        Plate::Law => [0.02, 0.012, 0.004, 1.0],
        Plate::Finish => [0.88, 0.90, 0.80, 1.0],
        Plate::Bottom => INK,
    }
}

/// A plate's value ink: the true value, in the plate's accent.
fn value_ink(plate: Plate) -> [f32; 4] {
    match plate {
        Plate::Capture | Plate::Finish => [0.98, 0.80, 0.30, 1.0],
        Plate::Law => [0.16, 0.012, 0.004, 1.0],
        Plate::Bottom => MINT,
    }
}

impl Board {
    pub fn new(gpu: Gpu, pack: &Pack, scale: u32) -> Result<Self, String> {
        let mut canvas = Canvas::new(gpu, (layout::WIDTH, layout::HEIGHT), scale, VERTEX_CAPACITY)?;
        canvas.add_face("Source Sans", &pack.bytes(pack::FONT)?, &FONT_SIZES, &[false, false, true, false])?;
        let mut up = |key: &str| canvas.upload_png(key, &pack.bytes(key)?, true);
        let t = Textures {
            bezel: up(pack::BEZEL)?,
            plates: [up(pack::PLATE_CAPTURE)?, up(pack::PLATE_LAW)?, up(pack::PLATE_FINISH)?],
            knobs: {
                let mut knobs = [0; 6];
                for (slot, key) in knobs.iter_mut().zip(pack::KNOBS) {
                    *slot = up(key)?;
                }
                knobs
            },
            voices: up(pack::KNOB_VOICES)?,
            selector: [up(pack::SELECTOR_HOUSE)?, up(pack::SELECTOR_ORACLE)?],
            toggle: [up(pack::TOGGLE_DOWN)?, up(pack::TOGGLE_UP)?],
            viewer_keys: up(pack::VIEWER_KEYS)?,
        };
        Ok(Self { canvas, t })
    }

    pub fn gpu(&self) -> &Gpu {
        &self.canvas.gpu
    }
    pub fn out_view(&self) -> &wgpu::TextureView {
        self.canvas.view()
    }
    pub fn size(&self) -> (u32, u32) {
        self.canvas.size
    }
    pub fn save_png(&self, path: &Path) -> Result<(), String> {
        self.canvas.save_png(path)
    }
    /// Vertices the last frame drew.
    pub fn vertex_count(&self) -> usize {
        self.canvas.vertices.len()
    }

    pub fn render(&mut self, state: &PanelState) -> Result<(), String> {
        self.begin();
        self.solid(Rect::new(0.0, 0.0, layout::WIDTH as f32, layout::HEIGHT as f32), BLACK);
        // The housing is baked at exactly this monitor, drawn whole.
        let bezel = self.t.bezel;
        let source = Rect::new(0.0, 0.0, self.textures[bezel].width, self.textures[bezel].height);
        self.sprite(bezel, layout::HOUSING, source, WHITE, paint::ART, 0);
        self.solid(SCREEN, PAPER);
        self.transect(state);
        self.viewer_keys(state);
        self.scroll_bar(state);
        self.info(state);
        self.plates();
        for widget in &WIDGETS {
            self.widget(state, widget);
        }
        self.bottom_row(state);
        self.menu(state);
        self.submit()
    }

    /// A value control's right-click menu, over everything: the family's
    /// flat rows (panelkit's text button), the highlighted one lit.
    fn menu(&mut self, state: &PanelState) {
        let Some(menu) = state.menu else { return };
        for (index, label) in layout::MENU_ITEMS.iter().enumerate() {
            let r = layout::menu_item(menu.at, index);
            self.solid(Rect::new(r.x - 1.0, r.y - 1.0, r.w + 2.0, r.h + 2.0), [0.0, 0.0, 0.0, 0.9]);
            let lit = index == menu.index;
            widgets::text_button(&mut self.canvas, r, label, lit, lit, MINT, INK);
        }
    }

    // ---- the screen ------------------------------------------------------

    fn transect(&mut self, state: &PanelState) {
        let held = state.held();
        let view = state.view;
        let y_of = |note: f32| layout::note_y(view, note);
        let visible = || (view.ceil() as u32)..=((view + layout::VIEW_SPAN).floor() as u32).min(127);

        // The key ruler. Under MIDI: held notes inked blue, their Repeat
        // octaves paler. Under Keys it is the Lower Keyboard: a target in
        // blue, a bypassed key in refusal sepia, an excluded one bare.
        self.set_clip(Some(RULER));
        let keys = state.keys_source();
        for note in visible() {
            let (top, bottom) = (y_of(note as f32 + 0.5), y_of(note as f32 - 0.5));
            let black = matches!(note % 12, 1 | 3 | 6 | 8 | 10);
            let bare = if black { SUMI } else { PAPER_KEY };
            let color = if keys {
                if state.keys.get(KeyState::Bypass, note) {
                    SEPIA
                } else if state.keys.get(KeyState::Target, note) {
                    mix(bare, BLUE, 0.85)
                } else {
                    bare
                }
            } else if held >> note & 1 == 1 {
                BLUE
            } else if state.is_target(note) {
                mix(bare, BLUE, 0.5)
            } else {
                bare
            };
            let w = if black { RULER.w * 0.62 } else { RULER.w };
            let key = Rect::new(RULER.x, top + 0.5, w, bottom - top - 0.5);
            self.solid(key, color);
            if state.hover_control == Some(Control::Key(note)) && keys {
                self.outline(key, opacity(SUMI, 0.8));
            }
        }
        self.set_clip(None);
        // Octave rules and their names.
        for octave in 0..=10u32 {
            let note = 12 + octave * 12;
            let y = y_of(note as f32);
            if !(PLOT.y..=PLOT.y + PLOT.h).contains(&y) {
                continue;
            }
            self.solid(Rect::new(PLOT.x, y, PLOT.w, 1.0), opacity(SUMI, 0.10));
            // Under its rule; the floor's would fall off the plot.
            if y + 16.0 <= PLOT.y + PLOT.h {
                self.text(PLOT.x + 4.0, y + 2.0, &format!("C{}", octave), VALUE, opacity(SUMI, 0.5), false);
            }
        }
        if state.viewer == Viewer::Transect {
            self.time_axis(state);
        }
        // The targets: lanes across the plot, named at the right; a held
        // note's lane full, a Repeat octave's fainter. A name that would
        // touch the one above it is left off (its lane still shows), and a
        // held note's name wins over a Repeat octave's.
        // A dense grid (a chromatic keyboard) draws faint lanes and no names:
        // the ruler already says it.
        let dense = visible().filter(|&n| state.is_target(n)).count() > 24;
        let mut named: Vec<f32> = Vec::new();
        for pass_held in [true, false] {
            for note in visible().rev() {
                let is_held = held >> note & 1 == 1;
                if !state.is_target(note) || is_held != pass_held {
                    continue;
                }
                let y = y_of(note as f32);
                let strength = if dense {
                    0.3
                } else if is_held {
                    1.0
                } else {
                    0.45
                };
                self.solid(Rect::new(PLOT.x, y - 0.5, PLOT.w, 1.0), opacity(BLUE, 0.30 * strength));
                if dense || named.iter().any(|&other| (other - y).abs() < 11.0) {
                    continue;
                }
                named.push(y);
                let name = note_name(note);
                self.text(PLOT.x + PLOT.w + 6.0, y - 7.0, &name, VALUE, opacity(BLUE, strength), false);
            }
        }
        // The map ceiling, in refusal ink: above it nothing unowned is bent.
        let ceiling = y_of(layout::hz_note(state.params.get(p::FMAX)));
        if ceiling > PLOT.y && ceiling < PLOT.y + PLOT.h {
            let mut x = PLOT.x;
            while x < PLOT.x + PLOT.w {
                self.solid(Rect::new(x, ceiling - 0.5, 6.0, 1.0), opacity(SEPIA, 0.8));
                x += 12.0;
            }
            self.text(PLOT.x + PLOT.w - 50.0, ceiling - 13.0, "CEILING", VALUE, SEPIA, false);
        }

        if state.history.is_empty() {
            let msg = if keys {
                "NO FEED  —  PLAY AUDIO THROUGH IT; THE KEYS INKED ON THE LEFT ARE THE TARGETS"
            } else {
                "NO FEED  —  PLAY AUDIO THROUGH IT AND HOLD A CHORD ON THE MIDI SIDE CHAIN"
            };
            self.text(PLOT.x + PLOT.w * 0.5, PLOT.y + PLOT.h * 0.5 - 7.0, msg, SMALL, opacity(SUMI, 0.5), true);
            return;
        }

        self.set_clip(Some(PLOT));
        match state.viewer {
            Viewer::Transect => self.paths(state),
            Viewer::Ladders => self.ladders(state),
            Viewer::Scope => self.scope(state),
        }
        self.set_clip(None);
    }

    /// The transect proper: each object's path over the kept history.
    fn paths(&mut self, state: &PanelState) {
        let view = state.view;
        let y_of = |note: f32| layout::note_y(view, note);
        let n = state.history.len();
        let x_of = |i: usize| PLOT.x + PLOT.w - (n - 1 - i) as f32 * (PLOT.w / HISTORY as f32);
        let frames: Vec<&VizFrame> = state.history.iter().collect();
        // Onsets: a faint wash where transient handling went dry.
        for (i, f) in frames.iter().enumerate() {
            if f.transient > 0.0 {
                let x = x_of(i);
                self.solid(Rect::new(x - 1.0, PLOT.y, 2.0, PLOT.h), opacity(VERMILION, 0.07 * f.transient));
            }
        }
        // Each object's path: source (pencil) and sung (ink; sepia if
        // spared, vermilion while newborn).
        for i in 1..n {
            let (prev, cur) = (frames[i - 1], frames[i]);
            let (x0, x1) = (x_of(i - 1), x_of(i));
            let loudest = cur.tracks[..cur.n as usize].iter().map(|t| t.amp).fold(1e-9, f32::max);
            for t in &cur.tracks[..cur.n as usize] {
                let Some(q) = prev.tracks[..prev.n as usize].iter().find(|q| q.id == t.id) else {
                    continue;
                };
                let weight = (t.amp / loudest).sqrt().clamp(0.0, 1.0);
                let (s0, s1) = (y_of(layout::hz_note(q.f0)), y_of(layout::hz_note(t.f0)));
                self.line(x0, s0, x1, s1, 1.0, opacity(PENCIL, 0.15 + 0.35 * weight));
                let (o0, o1) = (y_of(layout::hz_note(q.out)), y_of(layout::hz_note(t.out)));
                let color = if t.spared {
                    SEPIA
                } else if t.newborn {
                    VERMILION
                } else {
                    SUMI
                };
                self.line(x0, o0, x1, o1, 1.6, opacity(color, 0.35 + 0.65 * weight));
            }
        }
        // Now: each object's bend, source to sung, at the right edge.
        let now = frames[n - 1];
        let x = x_of(n - 1);
        for t in &now.tracks[..now.n as usize] {
            let (s, o) = (y_of(layout::hz_note(t.f0)), y_of(layout::hz_note(t.out)));
            self.line(x - 10.0, s, x - 2.0, o, 1.0, opacity(BLUE, 0.7));
            self.disc(x - 10.0, s, 2.0, opacity(PENCIL, 0.8));
            self.disc(x - 2.0, o, 2.6, if t.spared { SEPIA } else { SUMI });
        }
    }

    /// The ladders: one column per live object, low to high, each its
    /// harmonics' rungs over the last second (h·f0 on the pitch axis): ink
    /// where the de-mixer gave it that harmonic's region, pencil where the
    /// harmonic went unclaimed. It shows what the engine believes an
    /// object *is*. At each column's foot, its source and target.
    fn ladders(&mut self, state: &PanelState) {
        let view = state.view;
        let y_of = |note: f32| layout::note_y(view, note);
        let frames: Vec<&VizFrame> = state.history.iter().rev().take(LADDER_FRAMES).rev().collect();
        let now = *frames.last().expect("history is not empty");
        let mut objects: Vec<_> = now.tracks[..now.n as usize].to_vec();
        if objects.is_empty() {
            let msg = if now.grid_mask & !(1u128 << 127) == 0 {
                "NO TARGETS  —  THE TRACKER RESTS UNTIL THERE IS SOMEWHERE TO MAP TO"
            } else {
                "NO PITCH OBJECTS IN THIS FRAME"
            };
            self.text(PLOT.x + PLOT.w * 0.5, PLOT.y + PLOT.h * 0.5 - 7.0, msg, SMALL, opacity(SUMI, 0.5), true);
            return;
        }
        objects.sort_by(|a, b| a.f0.total_cmp(&b.f0));
        let column = (PLOT.w / objects.len() as f32).min(LADDER_COLUMN_MAX);
        let left = PLOT.x + (PLOT.w - column * objects.len() as f32) * 0.5;
        let rung = (column - 24.0) / LADDER_FRAMES as f32;
        let (top, bottom) = (PLOT.y, PLOT.y + PLOT.h);
        for (index, object) in objects.iter().enumerate() {
            let x0 = left + index as f32 * column + 12.0;
            let x_end = x0 + rung * LADDER_FRAMES as f32;
            // The rail: the object's own pencilled fundamental, now.
            let ink = if object.spared {
                SEPIA
            } else if object.newborn {
                VERMILION
            } else {
                SUMI
            };
            let offset = LADDER_FRAMES - frames.len();
            for (i, frame) in frames.iter().enumerate() {
                let Some(t) = frame.tracks[..frame.n as usize].iter().find(|t| t.id == object.id) else {
                    continue;
                };
                let x = x0 + (offset + i) as f32 * rung;
                let base = layout::hz_note(t.f0);
                for h in 1..=LADDER_RUNGS {
                    let y = y_of(base + 12.0 * (h as f32).log2());
                    if y < top {
                        break;
                    }
                    if y > bottom {
                        continue;
                    }
                    let claimed = t.hmask >> (h - 1) & 1 == 1;
                    let (color, alpha) = if claimed { (ink, 0.85) } else { (PENCIL, 0.30) };
                    let thick = if h == 1 { 2.0 } else { 1.0 };
                    self.solid(Rect::new(x, y - thick * 0.5, rung + 0.2, thick), opacity(color, alpha));
                }
            }
            // Now, at the column's right: where the object is pulled (the
            // target, blue) and where it was sung (ink).
            let (s, o, g) = (
                y_of(layout::hz_note(object.f0)),
                y_of(layout::hz_note(object.out)),
                y_of(layout::hz_note(object.tgt)),
            );
            self.solid(Rect::new(x_end + 1.0, g - 0.5, 9.0, 1.0), opacity(BLUE, 0.9));
            self.line(x_end + 1.0, s, x_end + 8.0, o, 1.0, opacity(BLUE, 0.7));
            self.disc(x_end + 8.0, o, 2.4, ink);
            // The foot: heard → target, and how many harmonics it holds.
            let heard = layout::hz_note(object.f0);
            let near = heard.round().clamp(0.0, 127.0) as u32;
            let cents = ((heard - near as f32) * 100.0).round() as i32;
            let target = note_name(layout::hz_note(object.tgt).round().clamp(0.0, 127.0) as u32);
            let cx = left + (index as f32 + 0.5) * column;
            let label = if object.spared {
                format!("{} {cents:+} c spared", note_name(near))
            } else {
                format!("{} {cents:+} c → {target}", note_name(near))
            };
            self.text(cx, bottom - 30.0, &label, VALUE, opacity(ink, 0.8), true);
            self.text(cx, bottom - 17.0, &format!("{} h", object.nh), VALUE, opacity(PENCIL, 0.6), true);
        }
    }

    /// The scope, laid on the pitch axis so the ruler, the targets' lanes
    /// (the grid's teeth) and the ceiling read across it: level runs right.
    /// Pencil is what came in, ink what the map sang (the wet, before MIX),
    /// each averaged over the last few frames; ink dots hold the sung
    /// peaks of the last second.
    fn scope(&mut self, state: &PanelState) {
        let view = state.view;
        let y_of = |note: f32| layout::note_y(view, note);
        let x_of = |db: f32| PLOT.x + PLOT.w * ((db - SCOPE_DB_MIN) / -SCOPE_DB_MIN).clamp(0.0, 1.0);
        // The level rules, every 24 dB, named along the foot.
        let foot = PLOT.y + PLOT.h;
        for step in 0..=4 {
            let db = SCOPE_DB_MIN + step as f32 * 24.0;
            let x = x_of(db);
            self.solid(Rect::new(x - 0.5, PLOT.y, 1.0, PLOT.h), opacity(SUMI, 0.08));
            // The full-scale rule's name sits inside the plot.
            let label_x = if step == 4 { x - 20.0 } else { x };
            if step > 0 {
                self.text(label_x, foot - 18.0, &format!("{db:.0} dB"), VALUE, opacity(SUMI, 0.45), true);
            }
        }
        let frames: Vec<&VizFrame> = state.history.iter().rev().take(SCOPE_PEAK_FRAMES).collect();
        let average = |b: usize, out: bool| -> f32 {
            let recent = &frames[..frames.len().min(SCOPE_AVERAGE_FRAMES)];
            let sum: f32 = recent.iter().map(|f| scope_db(if out { f.scope_out[b] } else { f.scope_in[b] })).sum();
            sum / recent.len() as f32
        };
        let visible = |b: usize| {
            let note = scope_note(b);
            note >= view - 1.0 && note <= view + layout::VIEW_SPAN + 1.0
        };
        let band = PLOT.h / layout::VIEW_SPAN / SCOPE_PER_NOTE as f32;
        let newest = frames[0];
        // A bar per bin, out from the left edge to its level, the bars
        // abutting into one silhouette: a spectrum's valleys stay valleys
        // rather than lines raking across the paper.
        for b in (0..SCOPE_BINS).filter(|&b| visible(b)) {
            let y = y_of(scope_note(b));
            let row = |x: f32| Rect::new(PLOT.x, y - band * 0.5, x - PLOT.x, band);
            // What came in: a pencil wash.
            if newest.scope_in[b] > 0 {
                self.solid(row(x_of(average(b, false))), opacity(PENCIL, 0.14));
            }
            // What was sung: an ink wash over it, and its peak over the
            // last second where that stands clear of now.
            if newest.scope_out[b] > 0 {
                let db = average(b, true);
                if db > SCOPE_DB_MIN {
                    self.solid(row(x_of(db)), opacity(SUMI, 0.38));
                }
                let peak = scope_db(frames.iter().map(|f| f.scope_out[b]).max().unwrap_or(0));
                if peak > SCOPE_DB_MIN && peak > db + 6.0 {
                    self.solid(Rect::new(x_of(peak) - 1.0, y - band * 0.5, 1.0, band), opacity(SUMI, 0.30));
                }
            }
        }
    }

    /// The viewer keys on the top bezel, stacked left from the screen's
    /// top-right edge: DESIGN's baked row (panelkit's Keys), the shown
    /// viewer's key lit.
    fn viewer_keys(&mut self, state: &PanelState) {
        let keys = widgets::Keys {
            sheet: widgets::Sheet { columns: 2 * Viewer::ALL.len() as u32, cell: (128.0, 32.0) },
            states: 2,
        };
        for viewer in Viewer::ALL {
            let lit = u32::from(state.viewer == viewer);
            keys.draw(&mut self.canvas, self.t.viewer_keys, layout::viewer_key(viewer), viewer.index() as u32, lit);
        }
    }

    /// The pitch view's scroll bar, always shown: a pencilled track and an
    /// inked thumb over the notes in view.
    fn scroll_bar(&mut self, state: &PanelState) {
        let track = layout::SCROLL_BAR;
        self.solid(Rect::new(track.x + track.w * 0.5 - 0.5, track.y, 1.0, track.h), opacity(SUMI, 0.18));
        let thumb = layout::scroll_thumb(state.view);
        let held = state.pressed_control == Some(Control::ScrollBar);
        let over = state.hover_control == Some(Control::ScrollBar);
        let ink = if held {
            0.75
        } else if over {
            0.55
        } else {
            0.35
        };
        // A pill, opaque (ink mixed into the paper) so its parts overlap
        // without darkening.
        let color = mix(PAPER, SUMI, ink);
        let r = thumb.w * 0.5;
        let (cx, top, bottom) = (thumb.x + r, thumb.y + r, thumb.y + thumb.h - r);
        self.solid(Rect::new(thumb.x, top, thumb.w, bottom - top), color);
        self.disc(cx, top, r, color);
        self.disc(cx, bottom, r, color);
    }

    /// Seconds before now, along the plot's foot: a tick every second, a
    /// figure every two, from the running engine's frame rate.
    fn time_axis(&mut self, state: &PanelState) {
        let (sr, hop) = state.engine_info;
        let frames_per_second = sr / hop.max(1) as f32;
        let px_per_second = PLOT.w / HISTORY as f32 * frames_per_second;
        if !(px_per_second.is_finite() && px_per_second > 4.0) {
            return;
        }
        let foot = PLOT.y + PLOT.h;
        let right = PLOT.x + PLOT.w;
        let mut second = 0;
        loop {
            let x = right - second as f32 * px_per_second;
            if x < PLOT.x {
                break;
            }
            let major = second % 2 == 0;
            self.solid(Rect::new(x - 0.5, foot - if major { 6.0 } else { 3.0 }, 1.0, if major { 6.0 } else { 3.0 }), opacity(SUMI, 0.45));
            if major && second > 0 && x > PLOT.x + 30.0 {
                let label = format!("-{second} s");
                self.text(x, foot - 18.0, &label, VALUE, opacity(SUMI, 0.45), true);
            }
            second += 1;
        }
    }

    // ---- the rack --------------------------------------------------------

    fn plates(&mut self) {
        let plates = [
            (layout::CAPTURE, "CAPTURE", Plate::Capture),
            (layout::LAW, "LAW", Plate::Law),
            (layout::FINISH, "FINISH", Plate::Finish),
        ];
        for (index, (rect, title, plate)) in plates.into_iter().enumerate() {
            let texture = self.t.plates[index];
            let (w, h) = (self.textures[texture].width, self.textures[texture].height);
            self.sprite(texture, rect, Rect::new(0.0, 0.0, w, h), WHITE, paint::ART, 0);
            let ink = plate_ink(plate);
            // Between the top screws.
            self.text(rect.x + 30.0, rect.y + 8.0, title, TITLE, opacity(ink, 0.9), false);
            // An engraved rule under the title.
            let tw = self.text_width(title, TITLE);
            self.solid(Rect::new(rect.x + 30.0, rect.y + 28.0, tw, 1.0), opacity(ink, 0.45));
        }
    }

    fn widget(&mut self, state: &PanelState, widget: &Widget) {
        let id = widget.id();
        let value = state.params.get(id);
        let (cx, cy) = widget.at;
        let ink = plate_ink(widget.plate);
        let hovered = state.hover_control == Some(widget.control) || state.pressed_control == Some(widget.control);
        match widget.kind {
            Kind::Knob(skin) => {
                let texture = self.t.knobs[skin as usize];
                let size = layout::KNOB * KNOB_FILL;
                let rect = Rect::new(cx - size * 0.5, cy - size * 0.5, size, size);
                let sheet = widgets::Sheet { columns: 11, cell: (120.0, 120.0) };
                let source = sheet.cell(widgets::frame(SPECS[id].normalized(value), 101));
                widgets::cast_shadow(self, texture, rect, source, &KNOB_SHADOW);
                self.sprite(texture, rect, source, WHITE, paint::PREMULTIPLIED, 0);
                self.guided_caption(state, widget, ink, hovered);
            }
            Kind::Stepped => {
                // One baked cell per step; the ring and the knob's own
                // shadow are in the bake.
                let texture = self.t.voices;
                let spec = &SPECS[id];
                let steps = (spec.max - spec.min).round() as usize + 1;
                let step = ((value - spec.min).round().max(0.0) as usize).min(steps - 1);
                let s = layout::STEPPED;
                let rect = Rect::new(cx - s * 0.5, cy - s * 0.5, s, s);
                let cell = self.textures[texture].height;
                let source = Rect::new(step as f32 * cell, 0.0, cell, cell);
                self.sprite(texture, rect, source, WHITE, paint::ART, 0);
                self.guided_caption(state, widget, ink, hovered);
            }
            Kind::Toggle(down, up) => {
                let on = value >= 0.5;
                let texture = self.t.toggle[usize::from(on)];
                let (w, h) = layout::TOGGLE;
                let rect = Rect::new(cx - w * 0.5, cy - h * 0.5, w, h);
                let source = Rect::new(0.0, 0.0, self.textures[texture].width, self.textures[texture].height);
                widgets::cast_shadow(self, texture, rect, source, &SWITCH_SHADOW);
                self.sprite(texture, rect, source, WHITE, paint::ART, 0);
                // The two positions, the live one lit in the value ink.
                let lit = value_ink(widget.plate);
                let (up_ink, down_ink) = if on { (lit, opacity(ink, 0.45)) } else { (opacity(ink, 0.45), lit) };
                self.text(cx, cy - h * 0.5 - 11.0, up, VALUE, up_ink, true);
                self.text(cx, cy + h * 0.5 - 1.0, down, VALUE, down_ink, true);
                self.caption(widget, ink, hovered);
            }
            Kind::Selector => {
                let oracle = value >= 0.5;
                let texture = self.t.selector[usize::from(oracle)];
                let s = layout::SELECTOR_DRAW;
                let rect = Rect::new(cx - s * 0.5, cy - s * 0.5, s, s);
                let source = Rect::new(0.0, 0.0, self.textures[texture].width, self.textures[texture].height);
                widgets::cast_shadow(self, texture, rect, source, &SWITCH_SHADOW);
                self.sprite(texture, rect, source, WHITE, paint::ART, 0);
                let lit = value_ink(widget.plate);
                let dim = opacity(ink, 0.45);
                // Each name sits where the pointer stands for it, clear of
                // the pointer itself.
                let top = cy - layout::SELECTOR_DRAW * 0.5 - 8.0;
                self.text(cx - 40.0, top, "HOUSE", CAPTION, if oracle { dim } else { lit }, true);
                self.text(cx + 40.0, top, "ORACLE", CAPTION, if oracle { lit } else { dim }, true);
                self.caption(widget, ink, hovered);
            }
            Kind::Text => {
                // The family's strip value: its name and value in the
                // accent, white over a glow while hovered or held.
                let r = widget.rect();
                let accent = value_ink(widget.plate);
                // Being typed: the family's entry in its place.
                if let Some(edit) = state.text_edit.as_ref().filter(|edit| edit.id == id) {
                    edit.draw(&mut self.canvas, widget.entry_rect(), accent, VALUE);
                    return;
                }
                let text = format!("{}  {}", widget.caption, SPECS[id].format(value));
                let (ink, glow) = strip::affordance(opacity(accent, 0.9), accent, hovered);
                let at = (r.center().0, strip::text_top(r));
                strip::glow_text(&mut self.canvas, 0, at, &text, VALUE, ink, glow, true);
            }
        }
    }

    /// A knob's caption, giving way to its value while the knob is in use
    /// (the family's guide), or to the value being typed (its menu's "Edit
    /// value...").
    fn guided_caption(&mut self, state: &PanelState, widget: &Widget, ink: [f32; 4], hovered: bool) {
        let id = widget.id();
        if let Some(edit) = state.text_edit.as_ref().filter(|edit| edit.id == id) {
            let r = widget.entry_rect();
            self.solid(r, [0.0, 0.0, 0.0, 0.55]);
            edit.draw(&mut self.canvas, r, value_ink(widget.plate), CAPTION);
            return;
        }
        let (cx, y) = (widget.at.0, widget.caption_y());
        let shown = state.guide(id);
        if shown < 1.0 {
            let alpha = if hovered { 1.0 } else { 0.82 };
            self.text(cx, y, widget.caption, CAPTION, opacity(ink, alpha * (1.0 - shown)), true);
        }
        if shown > 0.0 {
            let text = SPECS[id].format(state.params.get(id));
            self.text(cx, y, &text, CAPTION, opacity(value_ink(widget.plate), shown), true);
        }
    }

    fn caption(&mut self, widget: &Widget, ink: [f32; 4], hovered: bool) {
        let alpha = if hovered { 1.0 } else { 0.82 };
        self.text(widget.at.0, widget.caption_y(), widget.caption, CAPTION, opacity(ink, alpha), true);
    }

    // ---- the infotext and the bottom row ---------------------------------

    /// The infotext line between the monitor and the plates: what the
    /// pointer is over, its value at once, its help typing in (panelkit's
    /// hover line). Over nothing, how the board works, muted.
    fn info(&mut self, state: &PanelState) {
        let y = INFO.y + 2.0;
        match hover_info(state) {
            Some(info) => {
                let line = state.hover_line().text(&info, state.now);
                // The name and value in the accent, the help in ink.
                let head = info.prefix.as_ref();
                self.set_clip(Some(INFO));
                self.text(INFO.x, y, head, VALUE, MINT, false);
                let rest = &line[head.len()..];
                let x = INFO.x + self.text_width(head, VALUE);
                self.text(x, y, rest, VALUE, INK, false);
                self.set_clip(None);
            }
            None => {
                let how = if state.keys_source() {
                    "Keys: the keys inked on the screen's left are the targets; everything pitched is pulled onto them. The wheel scrolls the screen."
                } else {
                    "MIDI: hold a chord on the side chain; everything pitched is pulled onto it. The wheel scrolls the screen."
                };
                self.text(INFO.x, y, how, VALUE, MUTED, false);
            }
        }
    }

    /// The bottom row: the product's name and version for now. MIX and
    /// the family's standard row arrive with panelkit's `strip`.
    /// The bottom row (panelkit's strip), right to left: the product and
    /// its version, then MIX (drawn as its widget).
    fn bottom_row(&mut self, state: &PanelState) {
        let line = format!("{}  {}", crate::PLUGIN_NAME, state.version);
        strip::right_label(&mut self.canvas, layout::VERSION, &line, VALUE, MUTED);
    }

    // ---- submission ------------------------------------------------------

    fn submit(&mut self) -> Result<(), String> {
        self.canvas.write()?;
        let gpu = &self.canvas.gpu;
        let mut encoder = gpu.device.create_command_encoder(&Default::default());
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("OpenPitchQuant board"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: self.canvas.view(),
                    resolve_target: None,
                    ops: wgpu::Operations { load: wgpu::LoadOp::Clear(wgpu::Color::BLACK), store: wgpu::StoreOp::Store },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
            });
            pass.set_vertex_buffer(0, self.canvas.buffer().slice(..));
            for batch in &self.canvas.batches {
                self.canvas.draw(&mut pass, batch, batch.start, batch.end, &|_, _| {});
            }
        }
        gpu.queue.submit([encoder.finish()]);
        Ok(())
    }
}

/// What the infotext says about the target under the pointer (or being
/// dragged): a parameter's name, value and help; a key's note and state;
/// the scroll bar's span.
pub(crate) fn hover_info(state: &PanelState) -> Option<HoverInfo<Control>> {
    let control = state.pressed_control.or(state.hover_control)?;
    match control {
        Control::Param(id) => {
            let spec = &SPECS[id];
            Some(HoverInfo::parameter(control, spec.name, &spec.format(state.params.get(id)), help(id)))
        }
        Control::Key(note) => {
            let name = note_name(note);
            let (head, detail) = if !state.keys_source() {
                let held = if state.held() >> note & 1 == 1 { "held" } else { "not held" };
                (format!("{name}: {held}"), "the notes held on the MIDI side chain; turn SOURCE to KEYS to set them here".to_owned())
            } else {
                let status = if state.keys.get(KeyState::Bypass, note) {
                    "bypassed, passes unbent"
                } else if state.keys.get(KeyState::Target, note) {
                    "a target"
                } else {
                    "excluded, pulled to its neighbours"
                };
                let scope = if state.repeat_scope() { "Repeat: every octave" } else { "Custom: this key only" };
                (format!("{name}: {status}"), format!("click: target or exclude, {BYPASS_CLICK}: bypass; drag to paint ({scope})"))
            };
            Some(HoverInfo::help(control, head, detail))
        }
        Control::ScrollBar => {
            let low = state.view.ceil() as u32;
            let high = ((state.view + layout::VIEW_SPAN).floor() as u32).min(127);
            Some(HoverInfo::help(
                control,
                format!("VIEW: {} to {}", note_name(low), note_name(high)),
                "drag to scroll through all 128 notes; the wheel over the screen scrolls too",
            ))
        }
        Control::Viewer(viewer) => {
            let detail = match viewer {
                Viewer::Transect => "each object's path over time: heard in pencil, sung in ink, the targets in blue",
                Viewer::Ladders => {
                    "each live object's harmonics over the last second: inked where it claimed them, pencilled where it didn't"
                }
                Viewer::Scope => "the spectrum on the pitch axis: what came in (pencil) and what the map sang (ink), before MIX",
            };
            let shown = if state.viewer == viewer { " (showing)" } else { "" };
            Some(HoverInfo::help(control, format!("VIEWER: {}{shown}", viewer.label()), detail))
        }
    }
}

/// Hover help: what a control does, in a line.
fn help(id: usize) -> &'static str {
    match id {
        p::BYPASS => "the plant stops; the sea just plays (latency-aligned, click-free)",
        p::MIX => "sung water braided with the dry",
        p::FEEL => "how much of each object's own wobble survives the pull onto its target",
        p::GLIDE => "how long an object takes to walk to a new target",
        p::GRIT => "sand worked into the coat: the stamps' phase roughened",
        p::VOICES => "how many pitch objects the tracker may believe in at once",
        p::UNOWNED => "spectrum no object claimed: left dry, or mapped with the rest",
        p::GATE => "peakiness below this is weather, not pitch: left alone",
        p::GATE_MODE => "what the gate does to what it lets through: catch it fresh or wave it past",
        p::FMAX => "above this, unowned spectrum is never bent",
        p::TRANSIENT => "hits pass whole, never bent",
        p::SCOPE => "the held notes as played, or every octave of them",
        p::ROUNDING => "nearest tooth, or remember the way you came",
        p::COHERENCE => "how tightly the right channel follows the left",
        p::THRESHOLD => "objects already this close to a target are spared, in cents",
        p::FORMANT => "keep the throat, move the bones",
        p::CARRY => "how much of the refuse rides along under the stamps",
        p::TRANSITIONS => "what a newborn object sounds like: mapped at once, or dry until it settles",
        p::ALGORITHM => "HOUSE: the sound this plant always had   /   ORACLE: the reference's law (map or discard)",
        p::PURIFY => "fade the residue, the noise and the carry toward pure stamps",
        p::SOURCE => "MIDI: the notes held on the side chain are the targets   /   KEYS: the keys inked on the screen's ruler are (SCOPE says how an edit spreads)",
        _ => "",
    }
}

#[cfg(test)]
mod tests {
    use super::note_name;

    #[test]
    fn note_names_sign_their_octave() {
        assert_eq!(note_name(0), "C-1");
        assert_eq!(note_name(2), "D-1");
        assert_eq!(note_name(11), "B-1");
        assert_eq!(note_name(12), "C0");
        assert_eq!(note_name(60), "C4");
        assert_eq!(note_name(127), "G9");
    }
}
