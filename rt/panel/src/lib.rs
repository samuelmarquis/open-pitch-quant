//! OpenPitchQuant's editor board, host-free: the mounted board and the
//! offline harness draw the same [`Board`] from the same [`PanelState`].
//!
//! The board is the family idiom: a monitor whose screen carries the
//! display, in three viewers picked by keys on its top bezel (the belief
//! transect: what the tracker believes, where the law sends it, what it
//! actually sings; the ladders: each object's claimed harmonics; the
//! scope: the spectrum in and out), and a rack of solid plates beneath
//! with fixed controls, one per parameter.
//!
//! The mount, per frame (about 30 Hz):
//! 1. `state.params = shared.snapshot().0`;
//! 2. `state.push_frames(..)` with the analysis frames drained since;
//! 3. `state.update(now)`;
//! 4. `board.render(&state)`, then present `board.out_view()`.
//!
//! Input goes to [`Fittings`] (`down`, `drag`, `up`, `scroll`, `hover`,
//! `key`, `cancel`), each returning the [`Edit`]s to deliver to the host in
//! order. The fittings echo every value into `state.params` themselves, so
//! a gesture reads its own edits before the next snapshot.
mod board;
mod fittings;
pub mod layout;
pub mod pack;

pub use board::Board;
pub use fittings::{Fittings, PointerCapture};
pub use layout::{HEIGHT, WIDTH};

use opq_engine::params::{Keys, Params, PARAM_COUNT};
use opq_engine::VizFrame;
use panelkit::hover::{Guide, HoverLine};
use std::collections::VecDeque;
use std::time::Instant;

pub const PLUGIN_NAME: &str = "OpenPitchQuant";

/// Analysis frames the transect keeps: one per two logical px of its plot.
pub const HISTORY: usize = 484;

/// A parameter gesture, plain units. `Begin` and `End` bracket the values
/// of one gesture on one parameter. `Keys` replaces the panel's key states
/// (product state, not a parameter: the mount saves it and marks the
/// host's state dirty).
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Edit {
    Begin(usize),
    Value(usize, f32),
    End(usize),
    Keys(Keys),
    /// HOUSE's Feel law on audition: product state, not a parameter.
    HouseFeel(opq_engine::HouseFeel),
}

/// Keyboard modifiers held with a pointer event or a key: panelkit's
/// (`command` is Command on macOS, Ctrl on Windows).
pub use panelkit::keys::Modifiers;
/// A value typed in place (from a value control's menu, or Enter over
/// it), panelkit's.
pub use panelkit::entry::TextEdit;

/// A drag's or the wheel's scale: Command (Ctrl) is fine adjustment, as
/// everywhere in the family.
pub fn fine(mods: Modifiers) -> f32 {
    if mods.command {
        0.1
    } else {
        1.0
    }
}

/// A value control's right-click menu (layout::MENU_ITEMS): whose it is,
/// where it opened, and the highlighted item.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Menu {
    pub id: usize,
    pub at: (f32, f32),
    pub index: usize,
}

/// Everything the board draws, and the editor-local view state.
pub struct PanelState {
    pub params: Params,
    /// The keys the Keys source maps to (the ruler, when it is the source).
    pub keys: Keys,
    /// The transect's floor (MIDI note at the bottom of the plot); the
    /// wheel over the screen moves it.
    pub view: f32,
    /// What the screen shows: the viewer keys on the top bezel pick it.
    pub viewer: layout::Viewer,
    /// The newest analysis frames, oldest first.
    pub history: VecDeque<VizFrame>,
    /// Sample rate and hop of the running engine (for time captions).
    pub engine_info: (f32, u32),
    pub pointer: Option<(f32, f32)>,
    /// The control under the pointer, and the one pressed.
    pub hover_control: Option<layout::Control>,
    pub pressed_control: Option<layout::Control>,
    /// A value being typed (from a value control's "Edit value...", or
    /// Enter over it), if any.
    pub text_edit: Option<TextEdit>,
    /// A value control's right-click menu, if open.
    pub menu: Option<Menu>,
    /// One of the Key Transform's lists, if open: panelkit's family menu.
    pub list: Option<layout::ChoiceMenu>,
    /// HOUSE's Feel law, on audition (the strip's dropdown).
    pub house_feel: opq_engine::HouseFeel,
    /// Session tallies the LCD reports: objects born, onsets seen.
    pub born: u64,
    pub onsets: u64,
    last_id: i64,
    was_onset: bool,
    pub started: Instant,
    pub now: Instant,
    /// The product's version, for the bottom row: the mount sets the
    /// plugin's (the panel crate's own version is not the product's).
    pub version: &'static str,
    /// The infotext line (panelkit's): which target it describes, since
    /// when, so its help types in.
    hover_line: HoverLine<layout::Control>,
    /// Per parameter, the family's guide: a control shows its value in
    /// place of its caption while in use, and briefly whenever the value
    /// moves any other way (automation, the host's panel, a load).
    guides: [Guide; PARAM_COUNT],
}

impl Default for PanelState {
    fn default() -> Self {
        Self::new(Instant::now())
    }
}

impl PanelState {
    pub fn new(now: Instant) -> Self {
        let params = Params::default();
        Self {
            hover_line: HoverLine::new(now),
            guides: std::array::from_fn(|id| Guide::new(params.get(id))),
            params,
            keys: Keys::default(),
            view: layout::VIEW_DEFAULT,
            viewer: layout::Viewer::default(),
            history: VecDeque::with_capacity(HISTORY),
            engine_info: (48_000.0, opq_engine::HOP as u32),
            pointer: None,
            hover_control: None,
            pressed_control: None,
            text_edit: None,
            menu: None,
            list: None,
            house_feel: opq_engine::HouseFeel::A,
            born: 0,
            onsets: 0,
            last_id: -1,
            was_onset: false,
            started: now,
            now,
            version: "",
        }
    }

    /// Append analysis frames (oldest first), dropping the oldest kept.
    pub fn push_frames(&mut self, frames: impl IntoIterator<Item = VizFrame>) {
        for frame in frames {
            for track in &frame.tracks[..frame.n as usize] {
                if track.id > self.last_id {
                    self.born += 1;
                    self.last_id = track.id;
                }
            }
            let onset = frame.transient > 0.5;
            if onset && !self.was_onset {
                self.onsets += 1;
            }
            self.was_onset = onset;
            if self.history.len() == HISTORY {
                self.history.pop_front();
            }
            self.history.push_back(frame);
        }
    }

    /// The newest frame, if any arrived.
    pub fn latest(&self) -> Option<&VizFrame> {
        self.history.back()
    }

    /// The held notes (bit per MIDI note), as of the newest frame. The
    /// engine's mask carries its Repeat flag in bit 127; that is not a note.
    pub fn held(&self) -> u128 {
        self.latest().map_or(0, |f| f.grid_mask) & !(1u128 << 127)
    }

    /// The scope is Repeat: every octave of a held pitch class is a target.
    pub fn repeat(&self) -> bool {
        self.latest().is_some_and(|f| f.grid_mask >> 127 & 1 == 1)
    }

    /// The pitch classes held, in any octave.
    pub fn classes(&self) -> [bool; 12] {
        let held = self.held();
        std::array::from_fn(|pc| (0..128).step_by(12).any(|o| o + pc < 127 && held >> (o + pc) & 1 == 1))
    }

    /// A note is a target: held, or (in Repeat scope) an octave of one.
    pub fn is_target(&self, note: u32) -> bool {
        self.held() >> note & 1 == 1 || (self.repeat() && note < 127 && self.classes()[(note % 12) as usize])
    }

    /// The grid comes from the panel's keys.
    pub fn keys_source(&self) -> bool {
        self.params.keys_source()
    }

    /// Edits to a key reach every octave of it (the Repeat scope).
    pub fn repeat_scope(&self) -> bool {
        self.params.get(opq_engine::params::SCOPE) < 0.5
    }

    /// One frame: the clock, the infotext's target, and every guide.
    pub fn update(&mut self, now: Instant) {
        self.now = now;
        let info = board::hover_info(self);
        self.hover_line.track(info.as_ref(), now);
        for (id, guide) in self.guides.iter_mut().enumerate() {
            let control = Some(layout::Control::Param(id));
            let active = self.hover_control == control || self.pressed_control == control;
            guide.update(active, self.params.get(id), now);
        }
    }

    /// How far a control's value shows in place of its caption, 0..1.
    pub fn guide(&self, id: usize) -> f32 {
        self.guides[id].opacity(self.now)
    }

    pub(crate) fn hover_line(&self) -> &HoverLine<layout::Control> {
        &self.hover_line
    }

    /// Seconds since the editor opened: the board's animation clock.
    pub fn clock(&self) -> f32 {
        self.now.saturating_duration_since(self.started).as_secs_f32()
    }
}
