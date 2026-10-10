//! The board: one canvas, drawn the same mounted and offline.
//!
//! The family's look (OpenCepstrum's rt/panel there): a monitor housing on a
//! black board carries the screen; baked plates beneath carry baked
//! controls, each with its caption and its true value; a backlit LCD module
//! (panelkit's lcd-module/1) shows the chord; a strip at the bottom says
//! what the pointer is over.
//!
//! The screen's law, kept from the old panel: everything that indicates,
//! indicates truly. The transect draws only what the engine reported: each
//! object's source pitch (dim), the pitch it was sung at (warm), and the
//! held targets (mint). Ochre is spent only on refusal: an object Threshold
//! spared, and the map ceiling.
use crate::layout::{self, Kind, Plate, Widget, LCD, MONITOR, PLOT, RULER, SCREEN, STRIP, WIDGETS};
use crate::{pack, PanelState, HISTORY};
use opq_engine::params::{self as p, KeyState, SPECS};
use opq_engine::VizFrame;
use panelkit::canvas::{opacity, paint, pixel_font, Canvas, Rect, TextGrid, FORMAT};
use panelkit::gpu::Gpu;
use panelkit::lcd::{Lcd, LcdLook};
use panelkit::pack::Pack;
use panelkit::widgets;
use std::path::Path;

const VERTEX_CAPACITY: usize = 600_000;
/// Text sizes (logical px): values and the strip, captions, plate titles,
/// the screen's header.
const FONT_SIZES: [f32; 4] = [10.0, 12.0, 15.0, 11.0];
const VALUE: usize = 0;
const CAPTION: usize = 1;
const TITLE: usize = 2;
const SMALL: usize = 3;

// OpenCepstrum's palette (linear), plus the old panel's refusal ochre.
const WHITE: [f32; 4] = [1.0, 1.0, 1.0, 1.0];
const BLACK: [f32; 4] = [0.0, 0.0, 0.0, 1.0];
const INK: [f32; 4] = [0.70, 0.76, 0.81, 1.0];
const MUTED: [f32; 4] = [0.25, 0.30, 0.35, 1.0];
const MINT: [f32; 4] = [0.12, 0.76, 0.91, 1.0];
const WARM: [f32; 4] = [0.97, 0.88, 0.62, 1.0];
const OCHRE: [f32; 4] = [0.72, 0.40, 0.06, 1.0];
const AMBER: [f32; 4] = [0.98, 0.55, 0.12, 1.0];
const SCREEN_FIELD: [f32; 4] = [0.0045, 0.007, 0.011, 1.0];

/// The housing bake's bezel: 24 logical px (48 at its 2x), its inner
/// corner's rounding inside 36.
const BEZEL_SLICE: f32 = 36.0;
/// OpenCepstrum's knob shadow and fill.
const KNOB_SHADOW: [(f32, f32, f32, f32); 4] = [
    (0.6, 1.0, 1.0, 0.22),
    (1.2, 2.2, 1.03, 0.12),
    (2.0, 3.6, 1.07, 0.07),
    (3.0, 5.2, 1.12, 0.04),
];
const KNOB_FILL: f32 = 1.03;
const SWITCH_SHADOW: [(f32, f32, f32, f32); 2] = [(0.8, 1.6, 1.0, 0.30), (1.8, 3.2, 1.06, 0.12)];

/// The LCD's content layer and its scheme: OpenCepstrum's yellow-green STN
/// (field B4D23C, ink 1E2A1A).
const LCD_LAYER: u8 = 1;
const LCD_LOOK: LcdLook = LcdLook {
    field: [0.4564, 0.6445, 0.0452],
    ink: [0.013, 0.0232, 0.0103],
    cell: layout::LCD_CELL,
};

const NOTE_NAMES: [&str; 12] = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

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
    plates: [usize; 4],
    knobs: [usize; 10],
    selector: [usize; 2],
    toggle: [usize; 2],
    /// Green, amber, red; off and on.
    leds: [[usize; 2]; 3],
}

pub struct Board {
    canvas: Canvas,
    lcd: Lcd,
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

fn lcd_font(size: usize) -> &'static pixel_font::PixelFont {
    if size == TITLE {
        &pixel_font::LARGE
    } else {
        &pixel_font::SMALL
    }
}

/// A plate's ink: captions are engraved light on dark faces, dark on the
/// brass and the verdigris.
fn plate_ink(plate: Plate) -> [f32; 4] {
    match plate {
        Plate::Capture | Plate::Module | Plate::Screen => [0.82, 0.84, 0.86, 1.0],
        Plate::Law => [0.02, 0.012, 0.004, 1.0],
        Plate::Finish => [0.0, 0.012, 0.012, 1.0],
    }
}

/// A plate's value ink: the true value, in the plate's accent.
fn value_ink(plate: Plate) -> [f32; 4] {
    match plate {
        Plate::Capture | Plate::Module | Plate::Screen => MINT,
        Plate::Law => [0.16, 0.012, 0.004, 1.0],
        Plate::Finish => [0.0, 0.018, 0.09, 1.0],
    }
}

impl Board {
    pub fn new(gpu: Gpu, pack: &Pack, scale: u32) -> Result<Self, String> {
        let mut canvas = Canvas::new(gpu, (layout::WIDTH, layout::HEIGHT), scale, VERTEX_CAPACITY)?;
        canvas.add_face("Source Sans", &pack.bytes(pack::FONT)?, &FONT_SIZES, &[false, false, true, false])?;
        let mut up = |key: &str| canvas.upload_png(key, &pack.bytes(key)?, true);
        let t = Textures {
            bezel: up(pack::BEZEL)?,
            plates: [up(pack::PLATE_CAPTURE)?, up(pack::PLATE_LAW)?, up(pack::PLATE_FINISH)?, up(pack::PLATE_MODULE)?],
            knobs: {
                let mut knobs = [0; 10];
                for (slot, key) in knobs.iter_mut().zip(pack::KNOBS) {
                    *slot = up(key)?;
                }
                knobs
            },
            selector: [up(pack::SELECTOR_HOUSE)?, up(pack::SELECTOR_ORACLE)?],
            toggle: [up(pack::TOGGLE_DOWN)?, up(pack::TOGGLE_UP)?],
            leds: [
                [up(pack::LED_GREEN_OFF)?, up(pack::LED_GREEN_ON)?],
                [up(pack::LED_AMBER_OFF)?, up(pack::LED_AMBER_ON)?],
                [up(pack::LED_RED_OFF)?, up(pack::LED_RED_ON)?],
            ],
        };
        let lcd = Lcd::new(&canvas.gpu, FORMAT, canvas.size, scale as f32);
        Ok(Self { canvas, lcd, t })
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
        let bezel = self.t.bezel;
        self.nine_slice(bezel, MONITOR, BEZEL_SLICE, BEZEL_SLICE * 2.0, WHITE, paint::ART);
        self.solid(SCREEN, SCREEN_FIELD);
        self.transect(state);
        self.plates();
        for widget in &WIDGETS {
            self.widget(state, widget);
        }
        self.lamps(state);
        self.lcd_module(state);
        self.strip(state);
        self.submit(state)
    }

    // ---- the screen ------------------------------------------------------

    fn transect(&mut self, state: &PanelState) {
        let held = state.held();
        let view = state.view;
        let y_of = |note: f32| layout::note_y(view, note);
        let visible = || (view.ceil() as u32)..=((view + layout::VIEW_SPAN).floor() as u32).min(127);
        // Header: the Map Source tabs, what this is, and the law in force.
        let source = layout::widget(layout::Control::Param(p::SOURCE)).copied();
        if let Some(widget) = source {
            self.tabs(state, &widget);
        }
        let title_x = layout::SOURCE_TABS.x + layout::SOURCE_TABS.w + 12.0;
        self.text(title_x, SCREEN.y + 4.0, "REC-1859  BELIEF TRANSECT", SMALL, MUTED, false);
        let algorithm = SPECS[p::ALGORITHM].format(state.params.get(p::ALGORITHM)).to_uppercase();
        let law = format!(
            "{algorithm}   /   FEEL {}   /   GLIDE {}   /   {} VOICES",
            SPECS[p::FEEL].format(state.params.get(p::FEEL)),
            SPECS[p::GLIDE].format(state.params.get(p::GLIDE)),
            state.params.get(p::VOICES).round() as usize,
        );
        let lw = self.text_width(&law, SMALL);
        self.text(SCREEN.x + SCREEN.w - 8.0 - lw, SCREEN.y + 4.0, &law, SMALL, MUTED, false);

        // The key ruler. Under MIDI: held notes lit, their Repeat octaves
        // glowing. Under Keys it is the Lower Keyboard: a target lit, a
        // bypassed key in refusal ochre, an excluded one dark.
        self.set_clip(Some(RULER));
        let keys = state.keys_source();
        for note in visible() {
            let (top, bottom) = (y_of(note as f32 + 0.5), y_of(note as f32 - 0.5));
            let black = matches!(note % 12, 1 | 3 | 6 | 8 | 10);
            let bare = if black { [0.012, 0.014, 0.018, 1.0] } else { [0.16, 0.17, 0.18, 1.0] };
            let color = if keys {
                if state.keys.get(KeyState::Bypass, note) {
                    OCHRE
                } else if state.keys.get(KeyState::Target, note) {
                    opacity(MINT, if black { 0.65 } else { 0.9 })
                } else {
                    bare
                }
            } else if held >> note & 1 == 1 {
                MINT
            } else if state.is_target(note) {
                opacity(MINT, 0.45)
            } else {
                bare
            };
            let w = if black { RULER.w * 0.62 } else { RULER.w };
            let key = Rect::new(RULER.x, top + 0.5, w, bottom - top - 0.5);
            self.solid(key, color);
            if state.hover_control == Some(layout::Control::Key(note)) && keys {
                self.outline(key, opacity(WHITE, 0.7));
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
            self.solid(Rect::new(PLOT.x, y, PLOT.w, 1.0), opacity(INK, 0.045));
            // Under its rule, so the top one clears the header; the floor's
            // would fall off the plot.
            if y + 16.0 <= PLOT.y + PLOT.h {
                self.text(PLOT.x + 4.0, y + 2.0, &format!("C{}", octave), VALUE, opacity(INK, 0.35), false);
            }
        }
        self.time_axis(state);
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
                self.solid(Rect::new(PLOT.x, y - 0.5, PLOT.w, 1.0), opacity(MINT, 0.22 * strength));
                if dense || named.iter().any(|&other| (other - y).abs() < 11.0) {
                    continue;
                }
                named.push(y);
                let name = note_name(note);
                self.text(PLOT.x + PLOT.w + 6.0, y - 7.0, &name, VALUE, opacity(MINT, strength), false);
            }
        }
        // The map ceiling, in refusal ink: above it nothing unowned is bent.
        let ceiling = y_of(layout::hz_note(state.params.get(p::FMAX)));
        if ceiling > PLOT.y && ceiling < PLOT.y + PLOT.h {
            let mut x = PLOT.x;
            while x < PLOT.x + PLOT.w {
                self.solid(Rect::new(x, ceiling - 0.5, 6.0, 1.0), opacity(OCHRE, 0.7));
                x += 12.0;
            }
            self.text(PLOT.x + PLOT.w - 50.0, ceiling - 13.0, "CEILING", VALUE, OCHRE, false);
        }

        if state.history.is_empty() {
            let msg = if keys {
                "NO FEED  —  PLAY AUDIO THROUGH IT; THE KEYS LIT ON THE LEFT ARE THE TARGETS"
            } else {
                "NO FEED  —  PLAY AUDIO THROUGH IT AND HOLD A CHORD ON THE MIDI SIDE CHAIN"
            };
            self.text(PLOT.x + PLOT.w * 0.5, PLOT.y + PLOT.h * 0.5 - 7.0, msg, SMALL, MUTED, true);
            return;
        }

        self.set_clip(Some(PLOT));
        let n = state.history.len();
        let x_of = |i: usize| PLOT.x + PLOT.w - (n - 1 - i) as f32 * (PLOT.w / HISTORY as f32);
        let frames: Vec<&VizFrame> = state.history.iter().collect();
        // Onsets: a faint column where transient handling went dry.
        for (i, f) in frames.iter().enumerate() {
            if f.transient > 0.0 {
                let x = x_of(i);
                self.solid(Rect::new(x - 1.0, PLOT.y, 2.0, PLOT.h), opacity(AMBER, 0.05 * f.transient));
            }
        }
        // Each object's path: source (dim) and sung (warm, ochre if spared).
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
                self.line(x0, s0, x1, s1, 1.0, opacity(INK, 0.10 + 0.25 * weight));
                let (o0, o1) = (y_of(layout::hz_note(q.out)), y_of(layout::hz_note(t.out)));
                let color = if t.spared {
                    OCHRE
                } else if t.newborn {
                    WHITE
                } else {
                    WARM
                };
                self.line(x0, o0, x1, o1, 1.6, opacity(color, 0.25 + 0.75 * weight));
            }
        }
        // Now: each object's bend, source to sung, at the right edge.
        let now = frames[n - 1];
        let x = x_of(n - 1);
        for t in &now.tracks[..now.n as usize] {
            let (s, o) = (y_of(layout::hz_note(t.f0)), y_of(layout::hz_note(t.out)));
            self.line(x - 10.0, s, x - 2.0, o, 1.0, opacity(MINT, 0.6));
            self.disc(x - 10.0, s, 2.0, opacity(INK, 0.7));
            self.disc(x - 2.0, o, 2.6, if t.spared { OCHRE } else { WARM });
        }
        self.set_clip(None);
    }

    /// The screen's tabs (Map Source): one flat text button per label, the
    /// live one underlined in mint.
    fn tabs(&mut self, state: &PanelState, widget: &Widget) {
        let Kind::Tabs(labels) = widget.kind else { return };
        let r = widget.rect();
        let value = state.params.get(widget.id()).round() as usize;
        let hovered = state.hover_control == Some(widget.control);
        let w = r.w / labels.len() as f32;
        for (index, label) in labels.iter().enumerate() {
            let tab = Rect::new(r.x + index as f32 * w, r.y, w - 2.0, r.h);
            let over = hovered && state.pointer.is_some_and(|(x, _)| x >= tab.x && x < tab.x + w);
            widgets::text_button(self, tab, label, index == value, over, MINT, INK);
        }
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
            self.solid(Rect::new(x - 0.5, foot - if major { 6.0 } else { 3.0 }, 1.0, if major { 6.0 } else { 3.0 }), opacity(INK, 0.3));
            if major && second > 0 && x > PLOT.x + 30.0 {
                let label = format!("-{second} s");
                self.text(x, foot - 18.0, &label, VALUE, opacity(INK, 0.3), true);
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
            (layout::MODULE, "OUTPUT", Plate::Module),
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
                self.caption(widget, ink, hovered);
                let text = SPECS[id].format(value);
                let y = widget.caption_y() + 14.0;
                self.text(cx, y, &text, VALUE, value_ink(widget.plate), true);
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
            // Drawn with the screen (`tabs`).
            Kind::Tabs(_) => {}
        }
    }

    fn caption(&mut self, widget: &Widget, ink: [f32; 4], hovered: bool) {
        let alpha = if hovered { 1.0 } else { 0.82 };
        self.text(widget.at.0, widget.caption_y(), widget.caption, CAPTION, opacity(ink, alpha), true);
    }

    fn lamps(&mut self, state: &PanelState) {
        let latest = state.latest();
        let voices = state.params.get(p::VOICES).round() as usize;
        let tracking = latest.map_or(0, |f| f.n as usize);
        let lit = [
            state.held() != 0,
            latest.is_some_and(|f| f.transient > 0.5),
            tracking >= voices,
        ];
        let colors = [0, 1, 1];
        let ink = plate_ink(Plate::Module);
        for (index, (name, (x, y))) in layout::LAMPS.into_iter().enumerate() {
            let texture = self.t.leds[colors[index]][usize::from(lit[index])];
            let s = layout::LED;
            let source = Rect::new(0.0, 0.0, self.textures[texture].width, self.textures[texture].height);
            self.sprite(texture, Rect::new(x - s * 0.5, y - s * 0.5, s, s), source, WHITE, paint::ART, 0);
            self.text(x, y + 10.0, name, VALUE, opacity(ink, 0.8), true);
        }
        // Bypass's lamp, beside its toggle: the one red thing.
        let bypass = state.params.get(p::BYPASS) >= 0.5;
        let texture = self.t.leds[2][usize::from(bypass)];
        let s = layout::LED * 0.8;
        let (bx, by) = layout::widget(layout::Control::Param(p::BYPASS)).map_or((0.0, 0.0), |w| w.at);
        let source = Rect::new(0.0, 0.0, self.textures[texture].width, self.textures[texture].height);
        // Left of its toggle, between it and Mix, clear of the lamp row.
        self.sprite(texture, Rect::new(bx - 34.0 - s * 0.5, by - s * 0.5, s, s), source, WHITE, paint::ART, 0);
    }

    // ---- the LCD module --------------------------------------------------

    fn lcd_module(&mut self, state: &PanelState) {
        // The module's housing: a black bezel round the glass.
        let frame = Rect::new(LCD.x - 5.0, LCD.y - 5.0, LCD.w + 10.0, LCD.h + 10.0);
        self.solid(frame, [0.008, 0.008, 0.009, 1.0]);
        self.outline(frame, opacity(WHITE, 0.08));

        // Content, by brightness: black is the backlit field, white is ink.
        self.layer = LCD_LAYER;
        self.grid = Some(TextGrid { origin: (LCD.x, LCD.y), cell: layout::LCD_CELL, face: lcd_font });
        self.solid(LCD, BLACK);
        let cell = |c: f32, r: f32| (LCD.x + c * layout::LCD_CELL, LCD.y + r * layout::LCD_CELL);
        let algorithm = SPECS[p::ALGORITHM].format(state.params.get(p::ALGORITHM)).to_uppercase();
        let (x, y) = cell(2.0, 2.0);
        self.text(x, y, &algorithm, TITLE, WHITE, false);
        let voices = state.params.get(p::VOICES).round() as usize;
        let tracking = state.latest().map_or(0, |f| f.n as usize);
        let vox = format!("{}/{} VOX", tracking.min(99), voices);
        let vw = self.text_width(&vox, VALUE);
        let (x, y) = cell(0.0, 3.0);
        self.text(LCD.x + LCD.w - vw - 4.0, y, &vox, VALUE, WHITE, false);
        let _ = x;

        // The twelve pitch classes: a filled box where any octave is held
        // (or, under Keys, is a target).
        let grid = state.held();
        let keys = state.keys_source();
        let classes = if keys {
            std::array::from_fn(|pc| (pc as u32..128).step_by(12).any(|n| state.keys.get(KeyState::Target, n)))
        } else {
            state.classes()
        };
        for (pc, held) in classes.iter().enumerate() {
            let (x, y) = cell(2.0 + pc as f32 * 8.0, 12.0);
            let r = Rect::new(x, y, 6.0 * layout::LCD_CELL, 6.0 * layout::LCD_CELL);
            if *held {
                self.solid(r, WHITE);
            } else {
                self.outline_cells(r);
            }
            if !NOTE_NAMES[pc].contains('#') {
                self.text(x + 2.0, y + 7.0 * layout::LCD_CELL, NOTE_NAMES[pc], VALUE, WHITE, false);
            }
        }

        // The chord, by name, lowest first; under Keys, the classes set and
        // how many keys are bypassed.
        let held: Vec<String> = if keys {
            let names: Vec<String> =
                (0..12).filter(|&pc| classes[pc]).map(|pc| NOTE_NAMES[pc].to_owned()).collect();
            match names.len() {
                12 => vec!["CHROMATIC".to_owned()],
                _ => names,
            }
        } else {
            (0..128u32)
                .filter(|n| grid >> n & 1 == 1)
                .map(note_name)
                .collect()
        };
        let chord = match (keys, held.is_empty()) {
            (false, true) => "NO CHORD HELD".to_owned(),
            (true, true) => "KEYS: NO TARGETS".to_owned(),
            (true, false) => {
                let bypassed: Vec<&str> = (0..12usize)
                    .filter(|&pc| (pc as u32..128).step_by(12).any(|n| state.keys.get(KeyState::Bypass, n)))
                    .map(|pc| NOTE_NAMES[pc])
                    .collect();
                let tail = if bypassed.is_empty() { String::new() } else { format!(" BYP {}", bypassed.join(" ")) };
                format!("{}{tail}", held.join(" "))
            }
            (false, false) => held.join(" "),
        };
        let (x, y) = cell(2.0, 27.0);
        self.text(x, y, &chord, VALUE, WHITE, false);

        // The mutter: true session arithmetic, crawling.
        let mutter = format!(
            "THE MAP IS {} + {} OF {} VOICES + {} BORN + {} ONSETS + PURIFY {} +   ",
            if held.is_empty() { "SILENT".to_owned() } else { held.join(" ") },
            tracking,
            voices,
            state.born,
            state.onsets,
            SPECS[p::PURIFY].format(state.params.get(p::PURIFY)),
        );
        let row = cell(0.0, 37.0).1;
        let band = Rect::new(LCD.x, row - 1.0, LCD.w, 7.0 * layout::LCD_CELL);
        self.set_clip(Some(band));
        let width = self.text_width(&mutter, VALUE).max(1.0);
        let offset = (state.clock() * 24.0) % width;
        let step = layout::LCD_CELL * 4.0;
        let offset = (offset / step).floor() * step;
        let mut x = LCD.x + 2.0 - offset;
        while x < LCD.x + LCD.w {
            self.text(x, row, &mutter, VALUE, WHITE, false);
            x += width;
        }
        self.set_clip(None);
        self.grid = None;
        self.layer = 0;
    }

    /// A one-cell outline of `r` on the LCD grid.
    fn outline_cells(&mut self, r: Rect) {
        let c = layout::LCD_CELL;
        self.solid(Rect::new(r.x, r.y, r.w, c), WHITE);
        self.solid(Rect::new(r.x, r.y + r.h - c, r.w, c), WHITE);
        self.solid(Rect::new(r.x, r.y, c, r.h), WHITE);
        self.solid(Rect::new(r.x + r.w - c, r.y, c, r.h), WHITE);
    }

    // ---- the strip -------------------------------------------------------

    fn strip(&mut self, state: &PanelState) {
        self.solid(STRIP, BLACK);
        let y = STRIP.y + 3.0;
        if let Some(layout::Control::Key(note)) = state.hover_control {
            let name = note_name(note);
            let (head, line) = if !state.keys_source() {
                (format!("{name}  {}", if state.held() >> note & 1 == 1 { "held" } else { "not held" }),
                 "the notes held on the MIDI side chain; switch MAP SOURCE to KEYS to set them here".to_owned())
            } else {
                let status = if state.keys.get(KeyState::Bypass, note) {
                    "bypassed: passes unbent"
                } else if state.keys.get(KeyState::Target, note) {
                    "a target"
                } else {
                    "excluded: pulled to its neighbours"
                };
                let scope = if state.repeat_scope() { "Repeat: every octave" } else { "Custom: this key only" };
                (format!("{name}  {status}"),
                 format!("click: target or exclude, {BYPASS_CLICK}: bypass; drag to paint ({scope})"))
            };
            self.text(STRIP.x + 4.0, y, &head, VALUE, MINT, false);
            let x = STRIP.x + 4.0 + self.text_width(&head, VALUE) + 14.0;
            self.text(x, y, &line, VALUE, INK, false);
            return;
        }
        let Some(widget) = state.hover_control.and_then(layout::widget) else {
            let how = if state.keys_source() {
                "light keys on the left as targets; everything pitched is pulled onto them; the wheel scrolls the screen"
            } else {
                "hold a chord on the MIDI side chain; everything pitched is pulled onto it; the wheel scrolls the screen"
            };
            let line = format!("{}   /   Version {}   /   {how}", crate::PLUGIN_NAME, state.version);
            self.text(STRIP.x + 4.0, y, &line, VALUE, MUTED, false);
            return;
        };
        let id = widget.id();
        let spec = &SPECS[id];
        let head = format!("{}  {}", spec.name.to_uppercase(), spec.format(state.params.get(id)));
        self.text(STRIP.x + 4.0, y, &head, VALUE, MINT, false);
        let x = STRIP.x + 4.0 + self.text_width(&head, VALUE) + 14.0;
        self.text(x, y, help(id), VALUE, INK, false);
    }

    // ---- submission ------------------------------------------------------

    fn submit(&mut self, state: &PanelState) -> Result<(), String> {
        self.canvas.write()?;
        let gpu = &self.canvas.gpu;
        let mut encoder = gpu.device.create_command_encoder(&Default::default());
        let lcd_start = self.canvas.batches.iter().position(|b| b.layer == LCD_LAYER);
        let scale = self.canvas.scale;
        let scissor = [(LCD.x * scale) as u32, (LCD.y * scale) as u32, (LCD.w * scale) as u32, (LCD.h * scale) as u32];
        if lcd_start.is_some() {
            // The mutter crawls: its pixels follow at once, no smear.
            let instant = [Rect::new(LCD.x, LCD.y + 36.0 * layout::LCD_CELL, LCD.w, 9.0 * layout::LCD_CELL)];
            self.lcd.prepare(gpu, LCD, LCD_LOOK, &instant, state.now);
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("OpenPitchQuant LCD content"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: self.lcd.content(),
                    resolve_target: None,
                    ops: wgpu::Operations { load: wgpu::LoadOp::Clear(wgpu::Color::TRANSPARENT), store: wgpu::StoreOp::Store },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
            });
            pass.set_vertex_buffer(0, self.canvas.buffer().slice(..));
            for batch in self.canvas.batches.iter().filter(|b| b.layer == LCD_LAYER) {
                self.canvas.draw(&mut pass, batch, batch.start, batch.end, &|_, _| {});
            }
            drop(pass);
            self.lcd.advance(&mut encoder);
        }
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
            for (index, batch) in self.canvas.batches.iter().enumerate() {
                if batch.layer == LCD_LAYER {
                    // The treated screen takes the place of its first batch.
                    if lcd_start == Some(index) {
                        self.lcd.composite(&mut pass, scissor);
                    }
                    continue;
                }
                self.canvas.draw(&mut pass, batch, batch.start, batch.end, &|_, _| {});
            }
        }
        gpu.queue.submit([encoder.finish()]);
        Ok(())
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
        p::SOURCE => "MIDI: the notes held on the side chain are the targets   /   KEYS: the keys lit on the screen's ruler are",
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
