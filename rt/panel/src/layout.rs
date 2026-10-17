//! Where everything is, in logical px, and the one hit test
//! ([`target_at`]) that presses, the wheel and hover help all ask.
//!
//! The board: a monitor across the top (the transect), the infotext line
//! under it, a rack of four plates beneath in signal order (CAPTURE, LAW,
//! FINISH), and the bottom row (MIX and the version, panelkit's `strip`).
use opq_engine::params as p;
use panelkit::canvas::Rect;

pub const WIDTH: u32 = 1100;
pub const HEIGHT: u32 = 768;

/// The monitor housing and its screen. The housing's bake (bake.py
/// HOUSING_RECT) is drawn whole at HOUSING, the monitor padded 8 px.
pub const MONITOR: Rect = Rect::new(16.0, 10.0, 1068.0, 458.0);
pub const HOUSING: Rect = Rect::new(8.0, 2.0, 1084.0, 474.0);
pub const SCREEN: Rect = Rect::new(40.0, 34.0, 1020.0, 410.0);
/// The transect's plot inside the screen: the key ruler to its left, note
/// names to its right, then the scroll bar.
pub const PLOT: Rect = Rect::new(76.0, 40.0, 936.0, 390.0);
pub const RULER: Rect = Rect::new(46.0, 40.0, 24.0, 390.0);
/// The pitch view's scroll bar, always shown: its thumb is the five
/// octaves in view out of all 128 notes, highest at the top.
pub const SCROLL_BAR: Rect = Rect::new(1046.0, 40.0, 8.0, 390.0);
/// The transect shows five octaves of MIDI notes from a scrollable floor:
/// by default C2 to C7, where the tracker believes in anything; the wheel
/// over the screen and the scroll bar move through all 128.
pub const VIEW_SPAN: f32 = 60.0;
pub const VIEW_DEFAULT: f32 = 36.0;
pub const VIEW_MAX: f32 = 127.0 - VIEW_SPAN;

/// What the screen shows (Sam, 2026-10-10: "let's do ladders and scope as
/// the viewers"). All three share the ruler, the pitch axis and its scroll.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub enum Viewer {
    /// Each object's path over time: heard, sung, and the targets.
    #[default]
    Transect,
    /// Each live object's harmonics, and which of them it claimed.
    Ladders,
    /// The spectrum in and out, on the pitch axis.
    Scope,
}

impl Viewer {
    /// In key order, right to left from the screen's top-right edge.
    pub const ALL: [Viewer; 3] = [Viewer::Transect, Viewer::Ladders, Viewer::Scope];

    pub fn label(self) -> &'static str {
        match self {
            Viewer::Transect => "TRANSECT",
            Viewer::Ladders => "LADDERS",
            Viewer::Scope => "SCOPE",
        }
    }

    pub fn index(self) -> usize {
        self as usize
    }
}

/// A viewer key: on the top bezel, stacked left from the screen's
/// top-right edge (OpenCepstrum's idiom), 64x16 (DESIGN's key cell at
/// 128x32), 4 px apart.
pub const VIEWER_KEY: (f32, f32) = (64.0, 16.0);
pub fn viewer_key(viewer: Viewer) -> Rect {
    let first = Rect::new(
        SCREEN.x + SCREEN.w - VIEWER_KEY.0,
        MONITOR.y + (SCREEN.y - MONITOR.y - VIEWER_KEY.1) * 0.5,
        VIEWER_KEY.0,
        VIEWER_KEY.1,
    );
    panelkit::widgets::key_rect(first, -(VIEWER_KEY.0 + 4.0), viewer.index())
}

/// The infotext line between the monitor and the plates (OpenCepstrum's
/// idiom, panelkit's `hover`): what the pointer is over, its value, and
/// what it does.
pub const INFO: Rect = Rect::new(22.0, 473.0, 1056.0, 16.0);

/// The rack plates, filling the rack in signal order (no output plate:
/// Sam, 2026-10-10, "nix the output panel"). Their bakes are exactly these
/// sizes at 2x (assets/bake.py's PLATES).
pub const CAPTURE: Rect = Rect::new(16.0, 494.0, 336.0, 250.0);
pub const LAW: Rect = Rect::new(360.0, 494.0, 380.0, 250.0);
pub const FINISH: Rect = Rect::new(748.0, 494.0, 336.0, 250.0);

/// Text sizes (logical px): values and the strip, captions, plate titles,
/// the screen's header.
pub const FONT_SIZES: [f32; 4] = [10.0, 12.0, 15.0, 11.0];

/// The bottom row (panelkit's `strip`, the family's): right to left, the
/// product and its version, then MIX as text, one gap apart. Each item is
/// as wide as it looks collapsed (Sam, 2026-10-10): MIX the widest
/// "MIX  value" it can show, so dragging it never moves the row. The
/// version line's slot holds any version up to "88.88.88", and its text
/// starts at the slot's left edge, so MIX never depends on which version
/// it is. The widths are constants so the widgets stay a const table;
/// `the_bottom_row_is_spaced_by_its_collapsed_look` measures them with
/// panelkit's TextMetrics.
pub const BOTTOM: Rect = Rect::new(16.0, 750.0, 1068.0, 16.0);
const VERSION_W: f32 = 109.0;
const MIX_W: f32 = 43.0;
/// HOUSE's Feel on audition (Sam, 2026-10-16): "HOUSE FEEL D" and its
/// chevron, open-eq's strip dropdown (13 px for the chevron).
const HOUSE_FEEL_W: f32 = 74.0;
/// A strip dropdown's chevron: its centre in from the item's right edge,
/// and the room it takes after the text (open-eq's).
pub const STRIP_CHEVRON_INSET: f32 = 4.0;
pub const STRIP_CHEVRON_W: f32 = 13.0;
/// The family's one gap, panelkit's `strip::GAP` (Sam, 2026-10-10: 12 px).
const ROW: [Rect; 3] = panelkit::strip::place(BOTTOM, 6.0, panelkit::strip::GAP, [VERSION_W, MIX_W, HOUSE_FEEL_W]);
pub const VERSION: Rect = ROW[0];
pub const MIX_TEXT: Rect = ROW[1];
pub const HOUSE_FEEL: Rect = ROW[2];

/// The strip dropdown's text for HOUSE's Feel law.
pub fn house_feel_text(feel: opq_engine::HouseFeel) -> String {
    format!("HOUSE FEEL {:?}", feel)
}

/// Knob, toggle and selector draw sizes.
pub const KNOB: f32 = 58.0;
/// A switch's extent: toggle-tab fitted at 30 px wide, its lever reaching
/// 31 px either side of centre (Sam, p214 D; measured in pass 51).
pub const TOGGLE: (f32, f32) = (30.0, 62.0);
pub const SELECTOR: f32 = 96.0;
/// The chickenhead's drawn box, which its legends clear.
pub const SELECTOR_DRAW: f32 = 88.0;
/// The rack-baked parts' windows (bake.py TAB_WINDOW, SELECTOR_WINDOW):
/// dx, dy, w, h from the part's centre. A part's change between its states
/// runs well past it under the rack light (its shadow streaks down and
/// right); inside its window it keeps only what its states change, as
/// alpha, so windows may overlap. The import checks nothing spills out.
pub const TAB_WINDOW: (f32, f32, f32, f32) = (-64.0, -56.0, 144.0, 136.0);
pub const SELECTOR_WINDOW: (f32, f32, f32, f32) = (-70.0, -70.0, 160.0, 160.0);
/// Voices' window: its boss and lens ring, stepping together (bake.py
/// VOICES_WINDOW).
pub const VOICES_WINDOW: (f32, f32, f32, f32) = (-72.0, -68.0, 160.0, 150.0);
/// A continuous knob's window, through its 101 positions (bake.py
/// KNOB_WINDOW).
pub const KNOB_WINDOW: (f32, f32, f32, f32) = (-60.0, -60.0, 140.0, 140.0);
/// The rack bakes (rack_layout.rs, the template's rack_bake.py): a bake
/// region is its rect grown by a pad; a part's fades out over its outer
/// BAKE_FEATHER px (open-conv's and open-spectrum's values). A part's region
/// is its window above.
pub const fn bake_region(r: Rect, pad: f32) -> Rect {
    Rect::new(r.x - pad, r.y - pad, r.w + 2.0 * pad, r.h + 2.0 * pad)
}
pub const PLATE_PAD: f32 = 6.0;
pub const KEY_PAD: f32 = 8.0;
pub const BAKE_FEATHER: f32 = 6.0;
/// A continuous knob's positions (frame i at value i/100), 11 to a row.
pub const KNOB_FRAMES: usize = 101;
pub const KNOB_GRID: (usize, usize) = (11, 10);
/// Voices' detents.
pub const VOICES_STEPS: usize = 12;
/// The chickenhead's fitted diameter: its drum is the 43 px the sprite
/// board drew (DESIGN's refit, pass 54).
pub const SELECTOR_FIT: f32 = 102.0;

/// A plate's rect.
pub const fn plate_rect(plate: Plate) -> Rect {
    match plate {
        Plate::Capture => CAPTURE,
        Plate::Law => LAW,
        Plate::Finish => FINISH,
        Plate::Bottom => BOTTOM,
    }
}

/// A viewer key's bake region: its rect grown by KEY_PAD, out to whole
/// logical px so the 2x cells are whole pixels on the board's grid.
pub fn viewer_key_region(viewer: Viewer) -> Rect {
    let r = bake_region(viewer_key(viewer), KEY_PAD);
    let (x, y) = (r.x.floor(), r.y.floor());
    Rect::new(x, y, (r.x + r.w).ceil() - x, (r.y + r.h).ceil() - y)
}

/// A plate control's rack rect: what the composer fits it to (a knob's
/// circle, the tab's width, the boss inside Voices' ring).
pub fn rack_rect(widget: &Widget) -> Rect {
    let d = match widget.kind {
        Kind::Knob(_) => KNOB,
        Kind::Stepped => VOICES_BOSS,
        Kind::Selector => SELECTOR_FIT,
        _ => TOGGLE.0,
    };
    let (cx, cy) = widget.at;
    Rect::new(cx - d * 0.5, cy - d * 0.5, d, d)
}
/// Voices' boss and its lens ring, fitted by diameter (DESIGN's fits).
pub const VOICES_BOSS: f32 = 55.0;
pub const VOICES_RING: f32 = 70.0;

/// A plate control's bake region: its rack rect grown by its pad (open-
/// conv's and open-spectrum's: a knob's shadow, a lever's throw).
pub fn part_region(widget: &Widget) -> Rect {
    let pad = match widget.kind {
        Kind::Toggle(..) => LEVER_PAD,
        _ => PART_PAD,
    };
    bake_region(rack_rect(widget), pad)
}
pub const PART_PAD: f32 = 32.0;
pub const LEVER_PAD: f32 = 40.0;

/// The parts baked into the plates through their states, in pack::RACK_PARTS
/// order.
pub const RACK_PARTS: [usize; 19] = [
    p::GATE_MODE, p::UNOWNED, p::TRANSIENT, p::SOURCE, p::SCOPE, p::ROUNDING, p::TRANSITIONS, p::ALGORITHM,
    p::VOICES, p::GATE, p::FMAX, p::FEEL, p::GLIDE, p::THRESHOLD, p::PURIFY, p::GRIT, p::FORMANT,
    p::CARRY, p::COHERENCE,
];
/// A stepped knob's drawn cell: its knob at the knobs' scale, its ring
/// round it (bake.py STEPPED: 144 px at 2x).
pub const STEPPED: f32 = 72.0;

/// A knob's typed value, over its caption.
const ENTRY_W: f32 = 84.0;

/// A value control's right-click menu (the family's law): its items, each
/// row's size, opening at the pointer (below it, or above where the board
/// ends).
pub const MENU_ITEMS: [&str; 1] = ["Edit value..."];
pub const MENU_ROW: (f32, f32) = (120.0, 20.0);
pub fn menu_item(at: (f32, f32), index: usize) -> Rect {
    let anchor = Rect::new(at.0, at.1, 0.0, 0.0);
    let board = Rect::new(0.0, 0.0, WIDTH as f32, HEIGHT as f32);
    let (count, (w, h)) = (MENU_ITEMS.len(), MENU_ROW);
    if at.1 + 2.0 + count as f32 * h <= board.h {
        panelkit::strip::menu_item_below(anchor, count, index, h, 2.0, w, board)
    } else {
        panelkit::strip::menu_item(anchor, count, index, h, 2.0, w, board)
    }
}

/// The Key Transform's four lists, inside the screen at the plot's top
/// right (the transect's oldest corner, under the viewer keys): the
/// source's key and scale, an arrow, the destination's key and scale
/// (Sam, 2026-10-11).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Slot {
    SrcKey,
    SrcScale,
    DstKey,
    DstScale,
}

const SLOT_H: f32 = 16.0;
const SLOT_KEY_W: f32 = 34.0;
const SLOT_SCALE_W: f32 = 128.0;
const SLOT_GAP: f32 = 4.0;
const SLOT_ARROW_W: f32 = 18.0;

impl Slot {
    pub const ALL: [Slot; 4] = [Slot::SrcKey, Slot::SrcScale, Slot::DstKey, Slot::DstScale];

    pub fn is_key(self) -> bool {
        matches!(self, Slot::SrcKey | Slot::DstKey)
    }

    /// How many rows its list has: "*" and the twelve keys, or the scales.
    pub fn rows(self) -> usize {
        if self.is_key() {
            opq_engine::scales::KEY_NAMES.len()
        } else {
            opq_engine::scales::SCALES.len()
        }
    }

    /// A row's label. A key list starts at "*".
    pub fn label(self, row: usize) -> &'static str {
        if self.is_key() {
            opq_engine::scales::KEY_NAMES[Self::row_key(row) as usize]
        } else {
            opq_engine::scales::SCALES[row].name
        }
    }

    /// A key list's row as a key: row 0 is "*" (12), then C..B.
    pub fn row_key(row: usize) -> u8 {
        if row == 0 {
            opq_engine::scales::ANY_KEY
        } else {
            row as u8 - 1
        }
    }

    /// The row a key sits on in a key list.
    pub fn key_row(key: u8) -> usize {
        if key >= opq_engine::scales::ANY_KEY {
            0
        } else {
            key as usize + 1
        }
    }

    /// Where it sits: the four end 8 px inside the plot's right edge.
    pub const fn rect(self) -> Rect {
        let right = PLOT.x + PLOT.w - 8.0;
        let dst_scale = right - SLOT_SCALE_W;
        let dst_key = dst_scale - SLOT_GAP - SLOT_KEY_W;
        let src_scale = dst_key - SLOT_ARROW_W - SLOT_SCALE_W;
        let src_key = src_scale - SLOT_GAP - SLOT_KEY_W;
        let (x, w) = match self {
            Slot::SrcKey => (src_key, SLOT_KEY_W),
            Slot::SrcScale => (src_scale, SLOT_SCALE_W),
            Slot::DstKey => (dst_key, SLOT_KEY_W),
            Slot::DstScale => (dst_scale, SLOT_SCALE_W),
        };
        Rect::new(x, PLOT.y + 4.0, w, SLOT_H)
    }
}

/// The arrow between the source and the destination: its centre.
pub fn transform_arrow() -> (f32, f32) {
    let (src, dst) = (Slot::SrcScale.rect(), Slot::DstKey.rect());
    ((src.x + src.w + dst.x) * 0.5, src.y + src.h * 0.5)
}

/// The paper behind the four, so the plot's ink doesn't run under them.
pub fn transform_backing() -> Rect {
    let (first, last) = (Slot::SrcKey.rect(), Slot::DstScale.rect());
    Rect::new(first.x - 4.0, first.y - 2.0, last.x + last.w - first.x + 8.0, first.h + 4.0)
}

/// The menu item under the pointer, for a menu opened at `at`.
pub fn menu_item_at(at: (f32, f32), x: f32, y: f32) -> Option<usize> {
    (0..MENU_ITEMS.len()).find(|&i| menu_item(at, i).contains(x, y))
}

/// Row centres in the rack: knobs on the first, switches on the second.
const ROW_1: f32 = 494.0 + 66.0;
const ROW_2: f32 = 494.0 + 178.0;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Control {
    Param(usize),
    /// A key of the ruler (MIDI note): the Keys source's Lower Keyboard.
    Key(u32),
    /// The pitch view's scroll bar.
    ScrollBar,
    /// A viewer key on the top bezel.
    Viewer(Viewer),
    /// One of the Key Transform's four lists.
    Transform(Slot),
    /// HOUSE's Feel law, on audition: a dropdown on the bottom strip.
    HouseFeel,
}

/// A knob's skin, as bake.py's KNOB_PARTS bakes it (the record of which
/// knob is which). Hifi, the plain black knob, is for continuous controls.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Skin {
    Hifi,
    Heady,
    Catalin,
    Leather,
    Ebony,
    HeatTint,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Kind {
    Knob(Skin),
    /// A stepped knob (Voices): DESIGN's boss over its lens ring, one baked
    /// cell per step, drawn at STEPPED (the ring rings the knob). Drags
    /// and wheels like a knob, in whole steps.
    Stepped,
    /// A bat toggle: down is the first label, up the second.
    Toggle(&'static str, &'static str),
    /// The algorithm's chickenhead.
    Selector,
    /// A value as text in the bottom row (MIX): drags, wheels, resets and
    /// glows like the family's strip values.
    Text,
}

/// Where a control sits, for its ink: a plate, or the bottom row.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Plate {
    Capture,
    Law,
    Finish,
    Bottom,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Widget {
    pub control: Control,
    pub kind: Kind,
    /// The mechanism's centre.
    pub at: (f32, f32),
    pub caption: &'static str,
    pub plate: Plate,
}

impl Widget {
    /// Every widget is a parameter's.
    pub fn id(&self) -> usize {
        match self.control {
            Control::Param(id) => id,
            Control::Key(_) | Control::ScrollBar | Control::Viewer(_) | Control::Transform(_) | Control::HouseFeel => {
                unreachable!("only parameters are widgets")
            }
        }
    }

    /// The pressable area: the mechanism, generously.
    pub fn rect(&self) -> Rect {
        let (w, h) = match self.kind {
            Kind::Knob(_) => (KNOB, KNOB),
            Kind::Stepped => (STEPPED, STEPPED),
            Kind::Toggle(..) => (TOGGLE.0 + 18.0, TOGGLE.1 + 4.0),
            Kind::Selector => (SELECTOR, SELECTOR),
            Kind::Text => (MIX_TEXT.w, MIX_TEXT.h),
        };
        Rect::new(self.at.0 - w * 0.5, self.at.1 - h * 0.5, w, h)
    }

    /// A value control: double-click resets it, and its right-click menu
    /// holds "Edit value..." (the family's law, Sam 2026-10-10). Switches
    /// and the selector are positions, thrown on a click.
    pub fn is_value(&self) -> bool {
        matches!(self.kind, Kind::Knob(_) | Kind::Stepped | Kind::Text)
    }

    /// Where its value is typed: MIX in its own place, a knob over its
    /// caption.
    pub fn entry_rect(&self) -> Rect {
        match self.kind {
            Kind::Text => MIX_TEXT,
            _ => Rect::new(self.at.0 - ENTRY_W * 0.5, self.caption_y() - 1.0, ENTRY_W, 17.0),
        }
    }

    /// The caption's top: under the mechanism (a text control has none).
    pub fn caption_y(&self) -> f32 {
        let half = match self.kind {
            Kind::Knob(_) => KNOB * 0.5,
            Kind::Stepped => STEPPED * 0.5 - 6.0,
            Kind::Toggle(..) => TOGGLE.1 * 0.5 + 9.0,
            Kind::Selector => SELECTOR * 0.5 - 7.0,
            Kind::Text => MIX_TEXT.h * 0.5,
        };
        self.at.1 + half + 2.0
    }
}

/// The CAPTURE and FINISH plates' three columns.
const fn c(i: f32) -> f32 {
    CAPTURE.x + 62.0 + i * 106.0
}
const fn f(i: f32) -> f32 {
    FINISH.x + 62.0 + i * 106.0
}

const fn w(id: usize, kind: Kind, at: (f32, f32), caption: &'static str, plate: Plate) -> Widget {
    Widget { control: Control::Param(id), kind, at, caption, plate }
}

const fn centre(r: Rect) -> (f32, f32) {
    (r.x + r.w * 0.5, r.y + r.h * 0.5)
}

/// Every control on the board: one per parameter, except Bypass, which
/// the host owns (Sam, 2026-10-10).
pub const WIDGETS: [Widget; p::PARAM_COUNT - 1] = {
    use Kind::*;
    use Plate::*;
    use Skin::*;
    [
        // CAPTURE: what the tracker may hold and hear.
        // The stepped knob (Sam on DESIGN's p180: boss-ivory with the
        // knob-ring).
        w(p::VOICES, Stepped, (c(0.0), ROW_1), "VOICES", Capture),
        w(p::GATE, Knob(Hifi), (c(1.0), ROW_1), "TONALITY", Capture),
        w(p::FMAX, Knob(Hifi), (c(2.0), ROW_1), "CEILING", Capture),
        w(p::GATE_MODE, Toggle("FRESH", "BYPASS"), (c(0.0), ROW_2), "GATE MODE", Capture),
        w(p::UNOWNED, Toggle("DRY", "MAP"), (c(1.0), ROW_2), "UNOWNED", Capture),
        w(p::TRANSIENT, Toggle("BEND", "PASS"), (c(2.0), ROW_2), "TRANSIENTS", Capture),
        // LAW: where it goes and how it gets there. The grid's source and
        // its scope sit together on the lower row.
        w(p::ALGORITHM, Selector, (LAW.x + 76.0, ROW_1 + 16.0), "ALGORITHM", Law),
        w(p::FEEL, Knob(Hifi), (LAW.x + 220.0, ROW_1), "FEEL", Law),
        w(p::GLIDE, Knob(Hifi), (LAW.x + 312.0, ROW_1), "GLIDE", Law),
        // A two-position control is a switch (Sam, 2026-10-10).
        w(p::SOURCE, Toggle("MIDI", "KEYS"), (LAW.x + 52.0, ROW_2 + 4.0), "SOURCE", Law),
        w(p::SCOPE, Toggle("REPEAT", "CUSTOM"), (LAW.x + 132.0, ROW_2 + 4.0), "SCOPE", Law),
        w(p::THRESHOLD, Knob(Hifi), (LAW.x + 220.0, ROW_2), "THRESHOLD", Law),
        w(p::ROUNDING, Toggle("SMART", "NEAREST"), (LAW.x + 312.0, ROW_2), "ROUNDING", Law),
        // FINISH: what the sung result is made of.
        w(p::PURIFY, Knob(Heady), (f(0.0), ROW_1), "PURIFY", Finish),
        w(p::GRIT, Knob(Catalin), (f(1.0), ROW_1), "GRIT", Finish),
        w(p::FORMANT, Knob(Leather), (f(2.0), ROW_1), "FORMANT", Finish),
        w(p::CARRY, Knob(Ebony), (f(0.0), ROW_2), "CARRY", Finish),
        w(p::COHERENCE, Knob(HeatTint), (f(1.0), ROW_2), "COHERENCE", Finish),
        w(p::TRANSITIONS, Toggle("MAP", "DRY"), (f(2.0), ROW_2), "TRANSITIONS", Finish),
        // The bottom row: MIX as text (Sam, 2026-10-10).
        w(p::MIX, Text, centre(MIX_TEXT), "MIX", Bottom),
    ]
};

/// A rack-baked part's index in RACK_PARTS and its window.
pub fn rack_cell(widget: &Widget) -> Option<(usize, Rect)> {
    let index = RACK_PARTS.iter().position(|&id| id == widget.id())?;
    let (dx, dy, w, h) = match widget.kind {
        Kind::Selector => SELECTOR_WINDOW,
        Kind::Stepped => VOICES_WINDOW,
        Kind::Knob(_) => KNOB_WINDOW,
        _ => TAB_WINDOW,
    };
    let (cx, cy) = widget.at;
    Some((index, Rect::new(cx + dx, cy + dy, w, h)))
}

pub fn widget(control: Control) -> Option<&'static Widget> {
    WIDGETS.iter().find(|w| w.control == control)
}

/// What a press, the wheel or hover help at `(x, y)` acts on, with the
/// transect's floor at `view` (for the ruler's keys).
pub fn target_at(view: f32, x: f32, y: f32) -> Option<Control> {
    if scroll_bar_hit().contains(x, y) {
        return Some(Control::ScrollBar);
    }
    if let Some(index) = panelkit::widgets::key_at(Viewer::ALL.map(viewer_key), x, y) {
        return Some(Control::Viewer(Viewer::ALL[index]));
    }
    if let Some(slot) = Slot::ALL.into_iter().find(|slot| slot.rect().contains(x, y)) {
        return Some(Control::Transform(slot));
    }
    if HOUSE_FEEL.contains(x, y) {
        return Some(Control::HouseFeel);
    }
    WIDGETS
        .iter()
        .find(|w| w.rect().contains(x, y))
        .map(|w| w.control)
        .or_else(|| RULER.contains(x, y).then(|| note_at(view, y)).flatten().map(Control::Key))
}

/// The scroll bar's pressable area: its track, a little wider.
pub fn scroll_bar_hit() -> Rect {
    Rect::new(SCROLL_BAR.x - 4.0, SCROLL_BAR.y, SCROLL_BAR.w + 8.0, SCROLL_BAR.h)
}

/// The scroll bar's thumb for a view floor: the span in view out of the
/// whole range, the top of the track being the highest notes.
pub fn scroll_thumb(view: f32) -> Rect {
    let whole = VIEW_MAX + VIEW_SPAN;
    let h = SCROLL_BAR.h * VIEW_SPAN / whole;
    let y = SCROLL_BAR.y + (SCROLL_BAR.h - h) * (1.0 - view / VIEW_MAX);
    Rect::new(SCROLL_BAR.x, y, SCROLL_BAR.w, h)
}

/// The view floor that puts the thumb's top at `top`.
pub fn view_for_thumb(top: f32) -> f32 {
    let travel = SCROLL_BAR.h - scroll_thumb(0.0).h;
    (VIEW_MAX * (1.0 - (top - SCROLL_BAR.y) / travel)).clamp(0.0, VIEW_MAX)
}

/// The transect's y for a pitch (MIDI, fractional), floor at `view`.
pub fn note_y(view: f32, note: f32) -> f32 {
    PLOT.y + PLOT.h * (view + VIEW_SPAN - note) / VIEW_SPAN
}

/// The MIDI note whose key holds `y`, floor at `view`.
pub fn note_at(view: f32, y: f32) -> Option<u32> {
    let note = (view + VIEW_SPAN - (y - PLOT.y) / PLOT.h * VIEW_SPAN).round();
    (0.0..128.0).contains(&note).then_some(note as u32)
}

/// Whose an open choice menu is.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Chooser {
    /// A Key Transform list, choosing a row of [`Slot::label`]'s.
    Transform(Slot),
    /// HOUSE's Feel law, choosing a [`opq_engine::HouseFeel`] by index.
    HouseFeel,
}

/// An open choice menu: panelkit's family menu (Sam, 2026-10-16: "the new
/// house-style dropdowns").
pub type ChoiceMenu = panelkit::menu::ContextMenu<Chooser, usize>;
/// The menus open on the board; the Key Transform's stay on the screen.
pub const MENU_BOUNDS: Rect = Rect::new(0.0, 0.0, WIDTH as f32, HEIGHT as f32);
/// The menus' size: the family's 12 px serif.
pub const MENU_SIZE: usize = 1;

/// The scales' groups below the three plain ones, by index into
/// [`opq_engine::scales::SCALES`]: each a submenu, so the list fits the
/// screen at the family's row height.
pub const SCALE_GROUPS: [(&str, &[usize]); 5] = [
    ("Modes", &[3, 4, 5, 6, 7]),
    ("Harmonic & melodic", &[8, 9, 10, 11, 12, 13]),
    ("Pentatonic & blues", &[20, 21, 22, 27, 28, 29]),
    ("Symmetric", &[23, 24, 25, 26]),
    ("Exotic", &[14, 15, 16, 17, 18, 19, 30]),
];
/// The scales listed at the top, ungrouped.
pub const SCALES_PLAIN: [usize; 3] = [0, 1, 2];

/// The family's serif (panelkit's `menu::SERIF`) for measuring the menus.
pub fn serif() -> &'static panelkit::canvas::TextMetrics {
    static SERIF: std::sync::OnceLock<panelkit::canvas::TextMetrics> = std::sync::OnceLock::new();
    SERIF.get_or_init(|| panelkit::canvas::TextMetrics::new(panelkit::menu::SERIF, &FONT_SIZES).expect("a readable font"))
}

/// A list label as the menu sets it: words capitalised ("HARMONIC MINOR"
/// is "Harmonic Minor"), a key and "W-H" as they are.
pub fn menu_label(label: &str) -> String {
    label
        .split(' ')
        .map(|word| match word.len() > 1 && word.chars().all(|c| c.is_ascii_alphabetic()) {
            true => word[..1].to_owned() + &word[1..].to_ascii_lowercase(),
            false => word.to_owned(),
        })
        .collect::<Vec<_>>()
        .join(" ")
}

/// `slot`'s list opened, its cursor on `current` (the row the slot shows;
/// none for a hand-made target set). The current row is marked with a dot,
/// and a scale group with the current scale shows its name.
pub fn transform_menu(slot: Slot, current: Option<usize>) -> ChoiceMenu {
    use panelkit::menu::Row;
    const MARK: &str = "\u{2022}";
    let row = |index: usize| {
        let row = Row::new(menu_label(slot.label(index)), index);
        if current == Some(index) { row.value(MARK) } else { row }
    };
    let mut rows: Vec<Row<usize>> = Vec::new();
    let mut cursor = None;
    if slot.is_key() {
        rows.extend((0..slot.rows()).map(row));
        cursor = current;
    } else {
        for index in SCALES_PLAIN {
            if current == Some(index) {
                cursor = Some(rows.len());
            }
            rows.push(row(index));
        }
        for (group, (name, members)) in SCALE_GROUPS.iter().enumerate() {
            let held = current.filter(|index| members.contains(index));
            if held.is_some() {
                cursor = Some(rows.len());
            }
            // A group row's action names it and is never chosen.
            let mut item = Row::submenu(*name, usize::MAX - group, members.iter().map(|&index| row(index)).collect());
            if let Some(index) = held {
                item = item.value(menu_label(slot.label(index)));
            }
            rows.push(if group == 0 { item.separated() } else { item });
        }
    }
    let r = slot.rect();
    let serif = serif();
    let menu = ChoiceMenu::open(Chooser::Transform(slot), (r.x, r.y + r.h + 2.0), rows, |text| serif.width(text, MENU_SIZE));
    match cursor {
        Some(cursor) => menu.with_cursor(cursor),
        None => menu,
    }
}

/// HOUSE's Feel menu, over the strip: the four laws, the current one
/// dotted and under the cursor.
pub fn house_feel_menu(current: opq_engine::HouseFeel) -> ChoiceMenu {
    use opq_engine::HouseFeel;
    use panelkit::menu::{Row, PAD, ROW_H};
    let rows: Vec<Row<usize>> = HouseFeel::ALL
        .iter()
        .map(|&feel| {
            let label = match feel {
                HouseFeel::A => "A: as frozen",
                HouseFeel::B => "B: capped at 50 cents",
                HouseFeel::C => "C: restarts on a new note",
                HouseFeel::D => "D: B and C",
            };
            let row = Row::new(label, feel.index() as usize);
            if feel == current { row.value("\u{2022}") } else { row }
        })
        .collect();
    let r = HOUSE_FEEL;
    let h = 2.0 * PAD + rows.len() as f32 * ROW_H;
    let serif = serif();
    ChoiceMenu::open(Chooser::HouseFeel, (r.x, r.y - h - 2.0), rows, |text| serif.width(text, MENU_SIZE))
        .with_cursor(current.index() as usize)
}

/// Where the pointer goes to choose `row` in an open list: the row, or its
/// scale group's row (which opens the group) and then the row in the
/// submenu. For the tests and the offline harness.
pub fn menu_path(menu: &ChoiceMenu, row: usize) -> Vec<(f32, f32)> {
    let rows = menu.rows();
    if let Some(index) = rows.iter().position(|item| !item.opens() && item.action == row) {
        return vec![menu.row(index, MENU_BOUNDS).center()];
    }
    let group = rows.iter().position(|item| item.children.iter().any(|child| child.action == row)).expect("a listed row");
    let mut open = menu.clone();
    open.open_submenu(group);
    let index = open.submenu_rows().iter().position(|child| child.action == row).unwrap();
    vec![menu.row(group, MENU_BOUNDS).center(), open.submenu_row(index, MENU_BOUNDS).unwrap().center()]
}

/// The transect's area for the wheel: anywhere on the screen.
pub fn scrolls_view(x: f32, y: f32) -> bool {
    SCREEN.contains(x, y)
}

/// A frequency as a fractional MIDI note.
pub fn hz_note(hz: f32) -> f32 {
    69.0 + 12.0 * (hz.max(1.0) / 440.0).log2()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_key_transform_sits_in_the_plot_and_its_lists_in_the_screen() {
        let inside = |outer: Rect, r: Rect| {
            r.x >= outer.x && r.y >= outer.y && r.x + r.w <= outer.x + outer.w && r.y + r.h <= outer.y + outer.h
        };
        let mut right = PLOT.x;
        for slot in Slot::ALL {
            let r = slot.rect();
            assert!(inside(PLOT, r) && r.x >= right, "{slot:?}");
            right = r.x + r.w;
            assert_eq!(target_at(VIEW_DEFAULT, r.x + 2.0, r.y + 2.0), Some(Control::Transform(slot)));
            // Its menu lists every row once, all on the screen, every
            // scale group's submenu too.
            let mut menu = transform_menu(slot, None);
            assert!(inside(SCREEN, menu.rect(MENU_BOUNDS)), "{slot:?}");
            let mut listed: Vec<usize> = Vec::new();
            for index in 0..menu.rows().len() {
                if menu.rows()[index].opens() {
                    menu.open_submenu(index);
                    assert!(inside(SCREEN, menu.submenu_rect(MENU_BOUNDS).unwrap()), "{slot:?} group {index}");
                    listed.extend(menu.submenu_rows().iter().map(|row| row.action));
                } else {
                    listed.push(menu.rows()[index].action);
                }
            }
            listed.sort();
            assert_eq!(listed, (0..slot.rows()).collect::<Vec<_>>(), "{slot:?}");
        }
        // A key list is "*" then C to B.
        assert_eq!((Slot::SrcKey.label(0), Slot::SrcKey.label(1), Slot::DstKey.label(12)), ("*", "C", "B"));
        assert!((0..13).all(|row| Slot::key_row(Slot::row_key(row)) == row));
        // The widest scale name fits its slot beside the chevron, set as
        // the slot sets it.
        let widest = (0..Slot::DstScale.rows())
            .map(|row| serif().width(&menu_label(Slot::DstScale.label(row)), MENU_SIZE))
            .fold(0.0, f32::max);
        assert!(widest + 3.0 + 14.0 <= SLOT_SCALE_W, "{widest}");
    }

    #[test]
    fn the_bottom_row_is_spaced_by_its_collapsed_look() {
        let bytes = crate::pack::embedded().bytes(crate::pack::FONT).unwrap();
        let metrics = panelkit::canvas::TextMetrics::new(&bytes, &FONT_SIZES).unwrap();
        let text = |t: &str| metrics.width(t, 0);
        // Any version the row may show: three two-digit parts, each digit
        // at the widest digit's width.
        let widest_digit = ('0'..='9').max_by(|a, b| text(&a.to_string()).total_cmp(&text(&b.to_string()))).unwrap();
        let version = "88.88.88".replace('8', &widest_digit.to_string());
        let line = text(&format!("{}  {}", crate::PLUGIN_NAME, version));
        let spec = &p::SPECS[p::MIX];
        let mix = (0..=200)
            .map(|i| text(&format!("MIX  {}", spec.format(spec.plain(i as f32 / 200.0)))))
            .fold(0.0, f32::max);
        assert_eq!(VERSION_W, line.ceil(), "the version line's slot");
        assert_eq!(MIX_W, mix.ceil(), "MIX's widest look");
        let feel = opq_engine::HouseFeel::ALL.map(|f| text(&house_feel_text(f))).into_iter().fold(0.0, f32::max);
        assert_eq!(HOUSE_FEEL_W, (feel + STRIP_CHEVRON_W).ceil(), "HOUSE FEEL's widest look");
    }

    #[test]
    fn every_parameter_but_bypass_has_one_control_and_nothing_overlaps() {
        for id in 0..p::PARAM_COUNT {
            let want = usize::from(id != p::BYPASS);
            assert_eq!(WIDGETS.iter().filter(|w| w.id() == id).count(), want, "{id}");
        }
        for (i, a) in WIDGETS.iter().enumerate() {
            for b in &WIDGETS[i + 1..] {
                let (ra, rb) = (a.rect(), b.rect());
                let apart = ra.x + ra.w <= rb.x || rb.x + rb.w <= ra.x || ra.y + ra.h <= rb.y || rb.y + rb.h <= ra.y;
                assert!(apart, "{} overlaps {}", a.caption, b.caption);
            }
        }
    }

    #[test]
    fn controls_sit_on_their_plates() {
        for w in &WIDGETS {
            let plate = match w.plate {
                Plate::Capture => CAPTURE,
                Plate::Law => LAW,
                Plate::Finish => FINISH,
                Plate::Bottom => {
                    let r = w.rect();
                    assert!(r.y >= BOTTOM.y && r.x + r.w <= BOTTOM.x + BOTTOM.w, "{}", w.caption);
                    continue;
                }
            };
            let r = w.rect();
            assert!(r.x >= plate.x && r.x + r.w <= plate.x + plate.w, "{}", w.caption);
            assert!(r.y >= plate.y && w.caption_y() + 26.0 <= plate.y + plate.h, "{}", w.caption);
        }
    }

    #[test]
    fn the_ruler_answers_its_notes_and_the_view_scrolls_them() {
        let y = note_y(VIEW_DEFAULT, 60.0);
        assert_eq!(target_at(VIEW_DEFAULT, RULER.x + 4.0, y), Some(Control::Key(60)));
        assert_eq!(note_at(VIEW_DEFAULT + 12.0, note_y(VIEW_DEFAULT + 12.0, 80.0)), Some(80));
        assert_eq!(note_at(VIEW_MAX, PLOT.y), Some(127));
        assert_eq!(note_at(0.0, PLOT.y + PLOT.h), Some(0));
    }

    #[test]
    fn the_scroll_bar_thumb_spans_the_view_and_round_trips() {
        let top = scroll_thumb(VIEW_MAX);
        assert_eq!(top.y, SCROLL_BAR.y);
        let bottom = scroll_thumb(0.0);
        assert!((bottom.y + bottom.h - (SCROLL_BAR.y + SCROLL_BAR.h)).abs() < 1e-3);
        for view in [0.0, 12.5, VIEW_DEFAULT, VIEW_MAX] {
            assert!((view_for_thumb(scroll_thumb(view).y) - view).abs() < 1e-3, "{view}");
        }
        assert_eq!(target_at(VIEW_DEFAULT, SCROLL_BAR.x + 2.0, SCROLL_BAR.y + 100.0), Some(Control::ScrollBar));
        // Clear of the plot and the note names.
        assert!(scroll_bar_hit().x >= PLOT.x + PLOT.w + 26.0);
    }

    #[test]
    fn the_viewer_keys_stack_left_on_the_top_bezel() {
        let keys = Viewer::ALL.map(viewer_key);
        assert_eq!(keys[0].x + keys[0].w, SCREEN.x + SCREEN.w);
        for pair in keys.windows(2) {
            assert!(pair[1].x + pair[1].w < pair[0].x);
        }
        for (key, viewer) in keys.iter().zip(Viewer::ALL) {
            assert!(key.y >= MONITOR.y && key.y + key.h <= SCREEN.y);
            assert_eq!(target_at(VIEW_DEFAULT, key.x + 4.0, key.y + 4.0), Some(Control::Viewer(viewer)));
        }
    }

    // The scroll bar stays on the screen; the infotext sits between the
    // monitor and the plates.
    const _: () = assert!(SCROLL_BAR.x + SCROLL_BAR.w <= SCREEN.x + SCREEN.w);
    const _: () = assert!(INFO.y >= MONITOR.y + MONITOR.h && INFO.y + INFO.h <= CAPTURE.y);
}
