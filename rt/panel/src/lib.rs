//! OpenPitchQuant's editor board, host-free: the mounted board and the
//! offline harness draw the same [`Board`] from the same [`PanelState`].
//!
//! The board is the family idiom: a monitor whose screen carries the
//! display (the belief transect: what the tracker believes, where the law
//! sends it, what it actually sings), and a rack of solid plates beneath
//! with fixed controls, one per parameter. A backlit LCD module on the
//! last plate carries the chord and the session's small talk.
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

use opq_engine::params::Params;
use opq_engine::VizFrame;
use std::collections::VecDeque;
use std::time::Instant;

pub const PLUGIN_NAME: &str = "OpenPitchQuant";

/// Analysis frames the transect keeps: one per two logical px of its plot.
pub const HISTORY: usize = 484;

/// A parameter gesture, plain units. `Begin` and `End` bracket the values
/// of one gesture on one parameter.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Edit {
    Begin(usize),
    Value(usize, f32),
    End(usize),
}

/// Keyboard modifiers held with a pointer event. Command is fine
/// adjustment, as everywhere in the family.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Modifiers {
    pub shift: bool,
    pub alt: bool,
    pub command: bool,
}

impl Modifiers {
    pub fn fine(self) -> f32 {
        if self.command {
            0.1
        } else {
            1.0
        }
    }
}

/// Everything the board draws, and the editor-local view state.
pub struct PanelState {
    pub params: Params,
    /// The newest analysis frames, oldest first.
    pub history: VecDeque<VizFrame>,
    /// Sample rate and hop of the running engine (for time captions).
    pub engine_info: (f32, u32),
    pub pointer: Option<(f32, f32)>,
    /// The control under the pointer, and the one pressed.
    pub hover_control: Option<layout::Control>,
    pub pressed_control: Option<layout::Control>,
    /// Session tallies the LCD reports: objects born, onsets seen.
    pub born: u64,
    pub onsets: u64,
    last_id: i64,
    was_onset: bool,
    pub started: Instant,
    pub now: Instant,
    /// The product's version, for the strip: the mount sets the plugin's
    /// (the panel crate's own version is not the product's).
    pub version: &'static str,
}

impl Default for PanelState {
    fn default() -> Self {
        Self::new(Instant::now())
    }
}

impl PanelState {
    pub fn new(now: Instant) -> Self {
        Self {
            params: Params::default(),
            history: VecDeque::with_capacity(HISTORY),
            engine_info: (48_000.0, opq_engine::HOP as u32),
            pointer: None,
            hover_control: None,
            pressed_control: None,
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

    pub fn update(&mut self, now: Instant) {
        self.now = now;
    }

    /// Seconds since the editor opened: the board's animation clock.
    pub fn clock(&self) -> f32 {
        self.now.saturating_duration_since(self.started).as_secs_f32()
    }
}
