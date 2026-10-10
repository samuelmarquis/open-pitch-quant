//! Pointer and keyboard input: host-free, returning semantic edits.
//!
//! The family's gestures (OpenCepstrum's, as open-eq has them):
//! - Knobs drag vertically and relative: the cursor hides, up is more, a
//!   full range is `DIAL_PX` of travel, Command is fine, and on release the
//!   cursor lands back on the knob. Double-click resets to the default.
//!   Stepped knobs (Voices) move in whole steps.
//! - Toggles and the algorithm selector act on the press: one click, one
//!   gesture, the other position.
//! - The wheel over a knob moves it 2% of its travel a notch (a step for a
//!   stepped one); over a switch, it throws it toward the wheel.
//! - Escape during a drag puts the value back where the drag began.
//! - MIX's value can be typed (the family's entry): right-click it, or press
//!   Enter while over it; Enter commits, Escape cancels, a press anywhere
//!   else commits. Which keys the editor takes from the host is panelkit's
//!   policy (`wants_key`).
//! - With the Keys source, the ruler is PITCHMAP's Lower Keyboard: a click
//!   toggles a key as a target, Option/Alt-click its Bypass, and a drag
//!   paints the same state over the keys it crosses; in Repeat scope an
//!   edit reaches every octave of the key. With the MIDI source the keys
//!   only show the held notes.
//! - The wheel over the screen (plot or ruler) scrolls the pitch view as
//!   content: the system's natural-scrolling setting applies, unlike the
//!   knobs (Sam, 2026-10-10; the mount passes both deltas).
//! - The scroll bar's thumb drags the view; a press on its track brings
//!   the thumb's centre there and keeps dragging.
//!
//! Every value is echoed into `state.params` (and `state.keys`) before it is
//! returned.
use crate::layout::{self, Control, Kind};
use crate::{fine, Edit, Modifiers, PanelState, TextEdit};
use opq_engine::params::{KeyState, SPECS};
use panelkit::entry::EntryKey;
use panelkit::{interaction, keys, widgets};

/// Vertical travel across a knob's whole range, logical px (OpenCepstrum's).
const DIAL_PX: f32 = 180.0;
/// One wheel notch over a knob, as a fraction of its travel.
const WHEEL_STEP: f32 = 0.02;
/// One wheel notch over the screen, in semitones.
const VIEW_STEP: f32 = 2.0;

/// What a drag asks of the pointer: knobs are relative and release where
/// they were grabbed (panelkit's `Grabbed`, the family's ruling), a held
/// switch or a key paint follows the cursor.
pub type PointerCapture = interaction::PointerCapture<interaction::Grabbed<Knob>>;

/// A knob, as a release target: its centre.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Knob(Control);

impl interaction::ReleaseAnchor<PanelState> for Knob {
    fn position(self, _: &PanelState) -> Option<(f32, f32)> {
        layout::widget(self.0).map(|w| w.at)
    }
}

enum Capture {
    /// A knob drag: the value it began at, the travel so far (0..1 space),
    /// and the pointer's last y.
    Dial {
        id: usize,
        start: f32,
        normalized: f32,
        last_y: f32,
        anchor: interaction::Grabbed<Knob>,
    },
    /// A switch held down after its press acted.
    Switch,
    /// Painting keys: the state and the value every key crossed takes, and
    /// the last key painted.
    Keys { state: KeyState, on: bool, last: u32 },
    /// Dragging the scroll bar's thumb, held this far below its top.
    Thumb { grab: f32 },
}

/// Set `note`'s `state` to `on` (every octave in Repeat scope), as an edit.
fn paint(state: &mut PanelState, key_state: KeyState, note: u32, on: bool) -> Edit {
    let repeat = state.repeat_scope();
    state.keys.set(key_state, note, on, repeat);
    Edit::Keys(state.keys)
}

#[derive(Default)]
pub struct Fittings {
    capture: Option<Capture>,
}

fn normalized(id: usize, value: f32) -> f32 {
    SPECS[id].normalized(value)
}

/// A knob's plain value for a travel position: stepped knobs land on
/// whole steps.
fn plain(id: usize, normalized: f32) -> f32 {
    SPECS[id].plain(normalized)
}

/// One whole gesture setting `id` to `value`.
fn gesture(state: &mut PanelState, id: usize, value: f32) -> Vec<Edit> {
    let value = SPECS[id].clamp(value);
    state.params.set(id, value);
    vec![Edit::Begin(id), Edit::Value(id, value), Edit::End(id)]
}

/// Start typing `id`'s value: its text, all selected.
fn open_entry(state: &mut PanelState, id: usize) {
    state.text_edit = Some(TextEdit::new(id, SPECS[id].format(state.params.get(id))));
}

/// The text value (MIX) under the pointer, if one is.
fn hovered_text(state: &PanelState) -> Option<usize> {
    let widget = state.hover_control.and_then(layout::widget)?;
    (widget.kind == Kind::Text).then(|| widget.id())
}

/// A switch's other position (the selector's too: two positions).
fn thrown(state: &PanelState, id: usize) -> f32 {
    let spec = &SPECS[id];
    widgets::cycle(state.params.get(id), spec.min, spec.max, false)
}

impl Fittings {
    pub fn capture(&self) -> Option<PointerCapture> {
        match self.capture.as_ref()? {
            Capture::Dial { anchor, .. } => Some(PointerCapture::Relative(*anchor)),
            Capture::Switch | Capture::Keys { .. } | Capture::Thumb { .. } => Some(PointerCapture::Absolute),
        }
    }

    pub fn hover(&mut self, state: &mut PanelState, x: f32, y: f32) {
        self.hover_with_modifiers(state, x, y, Modifiers::default());
    }

    pub fn hover_with_modifiers(&mut self, state: &mut PanelState, x: f32, y: f32, _mods: Modifiers) {
        state.pointer = (x >= 0.0 && y >= 0.0).then_some((x, y));
        if self.capture.is_none() {
            state.hover_control = layout::target_at(state.view, x, y);
        }
    }

    pub fn down(&mut self, state: &mut PanelState, x: f32, y: f32, mods: Modifiers, clicks: u32) -> Vec<Edit> {
        // A value being typed: a press in its box keeps typing; anywhere
        // else commits it (or drops it, when it doesn't parse) and goes on.
        if state.text_edit.as_ref().is_some_and(|edit| {
            layout::widget(Control::Param(edit.id)).is_some_and(|w| w.rect().contains(x, y))
        }) {
            return Vec::new();
        }
        let mut edits = self.down_outside_entry(state, x, y);
        edits.extend(self.focus_lost(state));
        let Some(control) = layout::target_at(state.view, x, y) else {
            return edits;
        };
        if control == Control::ScrollBar {
            let thumb = layout::scroll_thumb(state.view);
            let grab = if (thumb.y..thumb.y + thumb.h).contains(&y) {
                y - thumb.y
            } else {
                // The track: centre the thumb on the press, then drag.
                state.view = layout::view_for_thumb(y - thumb.h * 0.5);
                thumb.h * 0.5
            };
            self.capture = Some(Capture::Thumb { grab });
            state.pressed_control = Some(control);
            return edits;
        }
        if let Control::Key(note) = control {
            // The keys are the Keys source's to edit; under MIDI they show
            // the held notes only.
            if state.keys_source() {
                let key_state = if mods.alt { KeyState::Bypass } else { KeyState::Target };
                let on = !state.keys.get(key_state, note);
                edits.push(paint(state, key_state, note, on));
                self.capture = Some(Capture::Keys { state: key_state, on, last: note });
                state.pressed_control = Some(control);
            }
            return edits;
        }
        let Some(widget) = layout::widget(control) else {
            return edits;
        };
        let id = widget.id();
        state.hover_control = Some(control);
        state.pressed_control = Some(control);
        match widget.kind {
            Kind::Knob(_) | Kind::Stepped | Kind::Text if clicks >= 2 => {
                edits.extend(gesture(state, id, SPECS[id].default));
                state.pressed_control = None;
            }
            Kind::Knob(_) | Kind::Stepped | Kind::Text => {
                let start = state.params.get(id);
                // Measured against where the knob is drawn (panelkit's rule).
                let anchor = interaction::Grabbed::press(Knob(control), (x, y), &*state);
                self.capture = Some(Capture::Dial {
                    id,
                    start,
                    normalized: normalized(id, start),
                    last_y: y,
                    anchor,
                });
                edits.push(Edit::Begin(id));
            }
            Kind::Toggle(..) | Kind::Selector => {
                let value = thrown(state, id);
                edits.extend(gesture(state, id, value));
                self.capture = Some(Capture::Switch);
            }
        }
        edits
    }

    pub fn drag(&mut self, state: &mut PanelState, x: f32, y: f32, mods: Modifiers) -> Vec<Edit> {
        state.pointer = Some((x, y));
        if let Some(Capture::Thumb { grab }) = self.capture {
            state.view = layout::view_for_thumb(y - grab);
            return Vec::new();
        }
        if let Some(Capture::Keys { state: key_state, on, last }) = self.capture.as_mut() {
            // Paint every key between the last and this one, so a fast
            // drag leaves no gaps.
            let Some(note) = layout::note_at(state.view, y) else {
                return Vec::new();
            };
            if note == *last {
                return Vec::new();
            }
            let (from, to) = ((*last).min(note), (*last).max(note));
            let (key_state, on) = (*key_state, *on);
            *last = note;
            let repeat = state.repeat_scope();
            for n in from..=to {
                state.keys.set(key_state, n, on, repeat);
            }
            return vec![Edit::Keys(state.keys)];
        }
        let Some(Capture::Dial { id, normalized, last_y, .. }) = self.capture.as_mut() else {
            return Vec::new();
        };
        let id = *id;
        *normalized = widgets::drag_value(*normalized, *last_y, y, fine(mods), DIAL_PX);
        *last_y = y;
        let value = plain(id, *normalized);
        if value == state.params.get(id) {
            return Vec::new();
        }
        state.params.set(id, value);
        vec![Edit::Value(id, value)]
    }

    pub fn up(&mut self, state: &mut PanelState) -> Vec<Edit> {
        state.pressed_control = None;
        match self.capture.take() {
            Some(Capture::Dial { id, .. }) => vec![Edit::End(id)],
            _ => Vec::new(),
        }
    }

    /// The gesture ends where it is (release outside, focus lost); a value
    /// being typed is dropped.
    pub fn cancel(&mut self, state: &mut PanelState) -> Vec<Edit> {
        state.text_edit = None;
        self.up(state)
    }

    pub fn focus_lost(&mut self, state: &mut PanelState) -> Vec<Edit> {
        self.up(state)
    }

    /// A right-click: on a text value (MIX), start typing it.
    pub fn context(&mut self, state: &mut PanelState, x: f32, y: f32) -> Vec<Edit> {
        let mut edits = self.down_outside_entry(state, x, y);
        if let Some(widget) = layout::target_at(state.view, x, y).and_then(layout::widget) {
            if widget.kind == Kind::Text {
                edits.extend(self.up(state));
                open_entry(state, widget.id());
            }
        }
        edits
    }

    /// What is open, for panelkit's key policy (and Win32's wait for a
    /// typed character).
    pub fn keys_open(&self, state: &PanelState) -> keys::Open {
        keys::Open { entry: state.text_edit.is_some(), list: false, cancellable: self.capture.is_some() }
    }

    /// Whether the editor takes `key` from the host: panelkit's rules, plus
    /// Enter over a text value (to start typing it).
    pub fn wants_key(&self, state: &PanelState, key: &str, mods: Modifiers) -> bool {
        keys::wants(key, mods, &self.keys_open(state), || key == "Enter" && hovered_text(state).is_some())
    }

    /// A press outside a value being typed commits it (or drops it when it
    /// doesn't parse); inside, nothing.
    fn down_outside_entry(&mut self, state: &mut PanelState, x: f32, y: f32) -> Vec<Edit> {
        let Some(edit) = &state.text_edit else { return Vec::new() };
        if layout::widget(Control::Param(edit.id)).is_some_and(|w| w.rect().contains(x, y)) {
            return Vec::new();
        }
        let edits = self.commit_entry(state);
        state.text_edit = None;
        edits
    }

    /// Parse the typed value and set it as one gesture; on a parse failure
    /// the entry stays open, marked.
    fn commit_entry(&mut self, state: &mut PanelState) -> Vec<Edit> {
        let Some(edit) = state.text_edit.as_mut() else { return Vec::new() };
        match SPECS[edit.id].parse(&edit.text) {
            Some(value) => {
                let id = edit.id;
                state.text_edit = None;
                gesture(state, id, value)
            }
            None => {
                edit.error = true;
                Vec::new()
            }
        }
    }

    /// The wheel. `delta` is in physical notches (positive is up: values
    /// rise); `content` is the same event for scrolling a view, after the
    /// system's natural-scrolling setting (positive toward the top: higher
    /// notes). panelkit's `scroll_notches` and `scroll_content_notches`.
    pub fn scroll(
        &mut self,
        state: &mut PanelState,
        x: f32,
        y: f32,
        delta: f32,
        content: f32,
        mods: Modifiers,
    ) -> Vec<Edit> {
        if delta == 0.0 && content == 0.0 {
            return Vec::new();
        }
        // During a drag the wheel moves the dragged knob.
        let control = match &self.capture {
            Some(Capture::Dial { id, .. }) => Some(Control::Param(*id)),
            Some(Capture::Switch | Capture::Keys { .. } | Capture::Thumb { .. }) => return Vec::new(),
            None => layout::target_at(state.view, x, y),
        };
        // Over the screen (the plot, a key, the scroll bar), the wheel
        // scrolls the view.
        if matches!(control, None | Some(Control::Key(_) | Control::ScrollBar)) {
            if layout::scrolls_view(x, y) {
                state.view = (state.view + content * VIEW_STEP).clamp(0.0, layout::VIEW_MAX);
            }
            return Vec::new();
        }
        if delta == 0.0 {
            return Vec::new();
        }
        let Some(widget) = control.and_then(layout::widget) else {
            return Vec::new();
        };
        let id = widget.id();
        let spec = &SPECS[id];
        let now = state.params.get(id);
        let value = match widget.kind {
            Kind::Knob(_) | Kind::Stepped | Kind::Text if spec.stepped => spec.clamp(now + delta.signum()),
            Kind::Knob(_) | Kind::Stepped | Kind::Text => {
                let n = normalized(id, now) + delta * WHEEL_STEP * fine(mods);
                plain(id, n.clamp(0.0, 1.0))
            }
            Kind::Toggle(..) | Kind::Selector => {
                if delta > 0.0 {
                    spec.max
                } else {
                    spec.min
                }
            }
        };
        if value == now {
            return Vec::new();
        }
        if let Some(Capture::Dial { normalized: n, .. }) = self.capture.as_mut() {
            *n = normalized(id, value);
            state.params.set(id, value);
            return vec![Edit::Value(id, value)];
        }
        gesture(state, id, value)
    }

    /// Escape during a knob drag puts it back where the drag began.
    /// A key the editor took (`wants_key`): the value being typed takes its
    /// editing keys (Enter commits, Escape cancels); Enter over a text
    /// value starts typing it; Escape during a drag undoes it.
    pub fn key(&mut self, state: &mut PanelState, key: &str, mods: Modifiers) -> Vec<Edit> {
        if let Some(edit) = state.text_edit.as_mut() {
            if key == "Escape" {
                state.text_edit = None;
                return Vec::new();
            }
            return match edit.key(key, mods.shift, mods.command) {
                EntryKey::Edited => Vec::new(),
                EntryKey::Commit | EntryKey::Next { .. } => self.commit_entry(state),
            };
        }
        if key == "Enter" {
            if let Some(id) = hovered_text(state) {
                open_entry(state, id);
            }
            return Vec::new();
        }
        if key != "Escape" {
            return Vec::new();
        }
        state.pressed_control = None;
        match self.capture.take() {
            Some(Capture::Dial { id, start, .. }) => {
                state.params.set(id, start);
                vec![Edit::Value(id, start), Edit::End(id)]
            }
            _ => Vec::new(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use opq_engine::params as p;

    fn at(id: usize) -> (f32, f32) {
        layout::WIDGETS.iter().find(|w| w.id() == id).unwrap().at
    }

    #[test]
    fn a_knob_drags_up_for_more_and_closes_its_gesture() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let (x, y) = at(p::FEEL);
        let before = s.params.get(p::FEEL);
        let down = f.down(&mut s, x, y, Modifiers::default(), 1);
        assert_eq!(down, vec![Edit::Begin(p::FEEL)]);
        assert!(f.capture().is_some_and(|c| c.is_relative()));
        let drag = f.drag(&mut s, x, y - 18.0, Modifiers::default());
        let Edit::Value(id, v) = drag[0] else { panic!("{drag:?}") };
        assert_eq!(id, p::FEEL);
        assert!((v - (before + 0.1)).abs() < 1e-4, "{v}");
        assert_eq!(s.params.get(p::FEEL), v);
        assert_eq!(f.up(&mut s), vec![Edit::End(p::FEEL)]);
        assert!(f.capture().is_none());
    }

    #[test]
    fn escape_restores_the_start_and_a_double_click_resets() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let (x, y) = at(p::MIX);
        f.down(&mut s, x, y, Modifiers::default(), 1);
        f.drag(&mut s, x, y + 60.0, Modifiers::default());
        assert!(s.params.get(p::MIX) < 1.0);
        let back = f.key(&mut s, "Escape", Modifiers::default());
        assert_eq!(back, vec![Edit::Value(p::MIX, 1.0), Edit::End(p::MIX)]);
        s.params.set(p::FEEL, 0.9);
        let (x, y) = at(p::FEEL);
        let reset = f.down(&mut s, x, y, Modifiers::default(), 2);
        assert_eq!(reset[1], Edit::Value(p::FEEL, SPECS[p::FEEL].default));
    }

    #[test]
    fn switches_throw_on_the_press_and_voices_steps_whole() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let (x, y) = at(p::ALGORITHM);
        let edits = f.down(&mut s, x, y, Modifiers::default(), 1);
        assert_eq!(edits, vec![Edit::Begin(p::ALGORITHM), Edit::Value(p::ALGORITHM, 1.0), Edit::End(p::ALGORITHM)]);
        assert!(f.up(&mut s).is_empty());
        let (x, y) = at(p::VOICES);
        f.down(&mut s, x, y, Modifiers::default(), 1);
        // 20 px of 180 is 1.2 of Voices' 11 steps: one whole step.
        let drag = f.drag(&mut s, x, y - 20.0, Modifiers::default());
        let Edit::Value(_, v) = drag[0] else { panic!() };
        assert_eq!(v, v.round());
        let wheel = f.scroll(&mut s, x, y, 1.0, -1.0, Modifiers::default());
        assert_eq!(wheel, vec![Edit::Value(p::VOICES, v + 1.0)], "a knob reads the physical delta");
    }

    fn key_point(s: &PanelState, note: u32) -> (f32, f32) {
        (layout::RULER.x + 6.0, layout::note_y(s.view, note as f32))
    }

    #[test]
    fn keys_edit_only_under_the_keys_source_and_paint_on_a_drag() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let (x, y) = key_point(&s, 61);
        assert!(f.down(&mut s, x, y, Modifiers::default(), 1).is_empty(), "MIDI source: the keys only show");
        s.params.set(p::SOURCE, 1.0);
        s.params.set(p::SCOPE, 1.0); // Custom: one key at a time
        let edits = f.down(&mut s, x, y, Modifiers::default(), 1);
        assert_eq!(edits, vec![Edit::Keys(s.keys)]);
        assert!(!s.keys.get(KeyState::Target, 61) && s.keys.get(KeyState::Target, 73));
        // Drag down to 58: 60, 59 and 58 are excluded too.
        let (_, y58) = key_point(&s, 58);
        f.drag(&mut s, x, y58, Modifiers::default());
        assert!((58..=61).all(|n| !s.keys.get(KeyState::Target, n)));
        assert!(s.keys.get(KeyState::Target, 57) && s.keys.get(KeyState::Target, 62));
        assert!(f.up(&mut s).is_empty());
        // Alt-click bypasses, in Repeat scope across the octaves.
        s.params.set(p::SCOPE, 0.0);
        let (x, y) = key_point(&s, 64);
        f.down(&mut s, x, y, Modifiers { alt: true, ..Modifiers::default() }, 1);
        assert!(s.keys.get(KeyState::Bypass, 64) && s.keys.get(KeyState::Bypass, 76));
    }

    #[test]
    fn the_wheel_over_the_screen_scrolls_the_view_as_content() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let (x, y) = (layout::PLOT.x + 100.0, layout::PLOT.y + 100.0);
        // Natural scrolling: fingers up (physical +1) moves the content up,
        // toward lower notes (content -1).
        assert!(f.scroll(&mut s, x, y, 1.0, -1.0, Modifiers::default()).is_empty());
        assert_eq!(s.view, layout::VIEW_DEFAULT - VIEW_STEP);
        f.scroll(&mut s, x, y, 0.0, 100.0, Modifiers::default());
        assert_eq!(s.view, layout::VIEW_MAX);
    }

    #[test]
    fn the_scroll_bar_drags_its_thumb_and_pages_on_the_track() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let thumb = layout::scroll_thumb(s.view);
        let x = layout::SCROLL_BAR.x + 2.0;
        // Grab the thumb mid-way and drag it to the top: the highest view.
        f.down(&mut s, x, thumb.y + 5.0, Modifiers::default(), 1);
        assert!(f.capture().is_some_and(|c| !c.is_relative()));
        f.drag(&mut s, x, layout::SCROLL_BAR.y - 50.0, Modifiers::default());
        assert_eq!(s.view, layout::VIEW_MAX);
        f.up(&mut s);
        // A press low on the track brings the thumb there.
        f.down(&mut s, x, layout::SCROLL_BAR.y + layout::SCROLL_BAR.h - 2.0, Modifiers::default(), 1);
        assert_eq!(s.view, 0.0);
        f.up(&mut s);
    }

    fn typed(f: &mut Fittings, s: &mut PanelState, text: &str) -> Vec<Edit> {
        let mut edits = Vec::new();
        for c in text.chars() {
            let key = c.to_string();
            assert!(f.wants_key(s, &key, Modifiers::default()), "{key:?}");
            edits.extend(f.key(s, &key, Modifiers::default()));
        }
        edits
    }

    #[test]
    fn mix_is_typed_in_place_after_a_right_click_or_enter() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let (x, y) = at(p::MIX);
        // Nothing open: the host keeps its keys, Enter included.
        assert!(!f.wants_key(&s, "5", Modifiers::default()));
        assert!(!f.wants_key(&s, "Enter", Modifiers::default()));
        assert!(f.context(&mut s, x, y).is_empty());
        assert!(s.text_edit.is_some());
        // Space is the host's even while typing.
        assert!(!f.wants_key(&s, " ", Modifiers::default()));
        // pluginkit's rule: a percentage typed with its % sign (a bare
        // number is the plain 0..1 value).
        assert!(typed(&mut f, &mut s, "50%").is_empty());
        assert!(f.wants_key(&s, "Enter", Modifiers::default()));
        let commit = f.key(&mut s, "Enter", Modifiers::default());
        assert_eq!(commit, vec![Edit::Begin(p::MIX), Edit::Value(p::MIX, 0.5), Edit::End(p::MIX)]);
        assert!(s.text_edit.is_none());
        // Enter over MIX opens it too; nonsense stays open, marked; Escape
        // drops it with no edit.
        f.hover(&mut s, x, y);
        assert!(f.wants_key(&s, "Enter", Modifiers::default()));
        f.key(&mut s, "Enter", Modifiers::default());
        typed(&mut f, &mut s, "loud");
        assert!(f.key(&mut s, "Enter", Modifiers::default()).is_empty());
        assert!(s.text_edit.as_ref().is_some_and(|e| e.error));
        assert!(f.key(&mut s, "Escape", Modifiers::default()).is_empty());
        assert!(s.text_edit.is_none());
        assert_eq!(s.params.get(p::MIX), 0.5);
        // A press elsewhere commits what was typed, and acts.
        f.context(&mut s, x, y);
        typed(&mut f, &mut s, "25%");
        let (fx, fy) = at(p::FEEL);
        let edits = f.down(&mut s, fx, fy, Modifiers::default(), 1);
        assert_eq!(&edits[..3], &[Edit::Begin(p::MIX), Edit::Value(p::MIX, 0.25), Edit::End(p::MIX)]);
        assert_eq!(edits[3], Edit::Begin(p::FEEL));
    }

    #[test]
    fn map_source_is_a_switch() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let (x, y) = at(p::SOURCE);
        let edits = f.down(&mut s, x, y, Modifiers::default(), 1);
        assert_eq!(edits, vec![Edit::Begin(p::SOURCE), Edit::Value(p::SOURCE, 1.0), Edit::End(p::SOURCE)]);
        assert!(s.keys_source());
        f.up(&mut s);
    }
}
