//! Where everything is, in logical px, and the one hit test
//! ([`target_at`]) that presses, the wheel and hover help all ask.
//!
//! The board: a monitor across the top (the transect), a rack of four
//! plates beneath in signal order (CAPTURE, LAW, FINISH, then the module
//! with the LCD and the output), and the hover strip along the bottom.
use opq_engine::params as p;
use panelkit::canvas::Rect;

pub const WIDTH: u32 = 1100;
pub const HEIGHT: u32 = 768;

/// The monitor housing (OpenCepstrum's bake, nine-sliced) and its screen.
pub const MONITOR: Rect = Rect::new(16.0, 10.0, 1068.0, 474.0);
pub const SCREEN: Rect = Rect::new(40.0, 34.0, 1020.0, 426.0);
/// The transect's plot inside the screen: the key ruler to its left, note
/// names to its right, a caption row above.
pub const PLOT: Rect = Rect::new(76.0, 54.0, 944.0, 392.0);
pub const RULER: Rect = Rect::new(46.0, 54.0, 24.0, 392.0);
/// The pitch range the transect shows: C2 to C7 (MIDI), where the tracker
/// believes in anything (its claims thin out past both).
pub const LOW_NOTE: f32 = 36.0;
pub const HIGH_NOTE: f32 = 96.0;

/// The rack plates. Their bakes are exactly these sizes at 2x
/// (assets/bake.py's PLATES).
pub const CAPTURE: Rect = Rect::new(16.0, 494.0, 258.0, 250.0);
pub const LAW: Rect = Rect::new(282.0, 494.0, 300.0, 250.0);
pub const FINISH: Rect = Rect::new(590.0, 494.0, 258.0, 250.0);
pub const MODULE: Rect = Rect::new(856.0, 494.0, 228.0, 250.0);

/// The backlit LCD module's aperture and its pixel pitch.
pub const LCD: Rect = Rect::new(872.0, 524.0, 196.0, 92.0);
pub const LCD_CELL: f32 = 2.0;

/// The hover strip: what the pointer is over, its value, and what it does.
pub const STRIP: Rect = Rect::new(16.0, 748.0, 1068.0, 18.0);

/// Knob, toggle and selector draw sizes.
pub const KNOB: f32 = 58.0;
pub const TOGGLE: (f32, f32) = (36.0, 48.0);
pub const SELECTOR: f32 = 96.0;
/// The chickenhead's bake has a wide margin: drawn larger than it presses.
pub const SELECTOR_DRAW: f32 = 128.0;
pub const LED: f32 = 40.0;

/// Row centres in the rack: knobs on the first, switches on the second.
const ROW_1: f32 = 494.0 + 66.0;
const ROW_2: f32 = 494.0 + 178.0;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Control {
    Param(usize),
}

/// The knob bakes, in the pack's KNOBS order.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Skin {
    Handwheel,
    Hifi,
    Witchhat,
    Heady,
    Catalin,
    Leather,
    Ebony,
    HeatTint,
    Davies,
    Cobalt,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Kind {
    Knob(Skin),
    /// A bat toggle: down is the first label, up the second.
    Toggle(&'static str, &'static str),
    /// The algorithm's chickenhead.
    Selector,
}

/// Which plate a control sits on, for its ink.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Plate {
    Capture,
    Law,
    Finish,
    Module,
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
    pub fn id(&self) -> usize {
        let Control::Param(id) = self.control;
        id
    }

    /// The pressable area: the mechanism, generously.
    pub fn rect(&self) -> Rect {
        let (w, h) = match self.kind {
            Kind::Knob(_) => (KNOB, KNOB),
            Kind::Toggle(..) => (TOGGLE.0 + 18.0, TOGGLE.1 + 8.0),
            Kind::Selector => (SELECTOR, SELECTOR),
        };
        Rect::new(self.at.0 - w * 0.5, self.at.1 - h * 0.5, w, h)
    }

    /// The caption's top: under the mechanism.
    pub fn caption_y(&self) -> f32 {
        let half = match self.kind {
            Kind::Knob(_) => KNOB * 0.5,
            Kind::Toggle(..) => TOGGLE.1 * 0.5 + 10.0,
            Kind::Selector => SELECTOR * 0.5 - 4.0,
        };
        self.at.1 + half + 2.0
    }
}

/// The CAPTURE plate's three columns.
const fn c(i: f32) -> f32 {
    CAPTURE.x + 49.0 + i * 80.0
}

const fn w(id: usize, kind: Kind, at: (f32, f32), caption: &'static str, plate: Plate) -> Widget {
    Widget { control: Control::Param(id), kind, at, caption, plate }
}

/// Every control on the board, one per parameter.
pub const WIDGETS: [Widget; p::PARAM_COUNT] = {
    use Kind::*;
    use Plate::*;
    use Skin::*;
    [
        // CAPTURE: what the tracker may hold and hear.
        w(p::VOICES, Knob(Handwheel), (c(0.0), ROW_1), "VOICES", Capture),
        w(p::GATE, Knob(Hifi), (c(1.0), ROW_1), "TONALITY", Capture),
        w(p::FMAX, Knob(Hifi), (c(2.0), ROW_1), "CEILING", Capture),
        w(p::GATE_MODE, Toggle("FRESH", "BYPASS"), (c(0.0), ROW_2), "GATE MODE", Capture),
        w(p::UNOWNED, Toggle("DRY", "MAP"), (c(1.0), ROW_2), "UNOWNED", Capture),
        w(p::TRANSIENT, Toggle("BEND", "PASS"), (c(2.0), ROW_2), "TRANSIENTS", Capture),
        // LAW: where it goes and how it gets there.
        w(p::ALGORITHM, Selector, (LAW.x + 70.0, ROW_1 + 12.0), "ALGORITHM", Law),
        w(p::FEEL, Knob(Witchhat), (LAW.x + 176.0, ROW_1), "FEEL", Law),
        w(p::GLIDE, Knob(Witchhat), (LAW.x + 252.0, ROW_1), "GLIDE", Law),
        w(p::THRESHOLD, Knob(Witchhat), (LAW.x + 176.0, ROW_2), "THRESHOLD", Law),
        w(p::ROUNDING, Toggle("SMART", "NEAREST"), (LAW.x + 252.0, ROW_2), "ROUNDING", Law),
        w(p::SCOPE, Toggle("REPEAT", "CUSTOM"), (LAW.x + 70.0, ROW_2 + 4.0), "SCOPE", Law),
        // FINISH: what the sung result is made of.
        w(p::PURIFY, Knob(Heady), (FINISH.x + 49.0, ROW_1), "PURIFY", Finish),
        w(p::GRIT, Knob(Catalin), (FINISH.x + 129.0, ROW_1), "GRIT", Finish),
        w(p::FORMANT, Knob(Leather), (FINISH.x + 209.0, ROW_1), "FORMANT", Finish),
        w(p::CARRY, Knob(Ebony), (FINISH.x + 49.0, ROW_2), "CARRY", Finish),
        w(p::COHERENCE, Knob(HeatTint), (FINISH.x + 129.0, ROW_2), "COHERENCE", Finish),
        w(p::TRANSITIONS, Toggle("MAP", "DRY"), (FINISH.x + 209.0, ROW_2), "TRANSITIONS", Finish),
        // The module: the output.
        w(p::MIX, Knob(Davies), (MODULE.x + 60.0, ROW_2 + 2.0), "MIX", Module),
        w(p::BYPASS, Toggle("RUN", "BYPASS"), (MODULE.x + 150.0, ROW_2 + 2.0), "BYPASS", Module),
    ]
};

/// The status lamps on the module, under the LCD: name and centre.
pub const LAMPS: [(&str, (f32, f32)); 3] = [
    ("CHORD", (MODULE.x + 40.0, 642.0)),
    ("ONSET", (MODULE.x + 114.0, 642.0)),
    ("FULL", (MODULE.x + 188.0, 642.0)),
];

pub fn widget(control: Control) -> Option<&'static Widget> {
    WIDGETS.iter().find(|w| w.control == control)
}

/// What a press, the wheel or hover help at `(x, y)` acts on.
pub fn target_at(x: f32, y: f32) -> Option<Control> {
    WIDGETS.iter().find(|w| w.rect().contains(x, y)).map(|w| w.control)
}

/// The transect's y for a pitch (MIDI, fractional).
pub fn note_y(note: f32) -> f32 {
    PLOT.y + PLOT.h * (HIGH_NOTE - note) / (HIGH_NOTE - LOW_NOTE)
}

/// A frequency as a fractional MIDI note.
pub fn hz_note(hz: f32) -> f32 {
    69.0 + 12.0 * (hz.max(1.0) / 440.0).log2()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_parameter_has_one_control_and_nothing_overlaps() {
        for id in 0..p::PARAM_COUNT {
            assert_eq!(WIDGETS.iter().filter(|w| w.id() == id).count(), 1, "{id}");
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
                Plate::Module => MODULE,
            };
            let r = w.rect();
            assert!(r.x >= plate.x && r.x + r.w <= plate.x + plate.w, "{}", w.caption);
            assert!(r.y >= plate.y && w.caption_y() + 26.0 <= plate.y + plate.h, "{}", w.caption);
        }
    }
}
