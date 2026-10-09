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
//!
//! Every value is echoed into `state.params` before it is returned.
use crate::layout::{self, Control, Kind};
use crate::{Edit, Modifiers, PanelState};
use opq_engine::params::SPECS;
use panelkit::interaction;
use panelkit::widgets;

/// Vertical travel across a knob's whole range, logical px (OpenCepstrum's).
const DIAL_PX: f32 = 180.0;
/// One wheel notch over a knob, as a fraction of its travel.
const WHEEL_STEP: f32 = 0.02;

/// What a drag asks of the pointer: knobs are relative, a held switch
/// follows the cursor.
pub type PointerCapture = interaction::PointerCapture<ReleaseAnchor>;

/// Where a knob drag's cursor lands: the knob, where it was pressed on it.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ReleaseAnchor {
    control: Control,
    offset: (f32, f32),
}

impl interaction::ReleaseAnchor<PanelState> for ReleaseAnchor {
    fn position(self, _: &PanelState) -> Option<(f32, f32)> {
        let (x, y) = layout::widget(self.control)?.at;
        Some((x + self.offset.0, y + self.offset.1))
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
        anchor: ReleaseAnchor,
    },
    /// A switch held down after its press acted.
    Switch,
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

/// A switch's other position (the selector's too: two positions).
fn thrown(state: &PanelState, id: usize) -> f32 {
    let spec = &SPECS[id];
    widgets::cycle(state.params.get(id), spec.min, spec.max, false)
}

impl Fittings {
    pub fn capture(&self) -> Option<PointerCapture> {
        match self.capture.as_ref()? {
            Capture::Dial { anchor, .. } => Some(PointerCapture::Relative(*anchor)),
            Capture::Switch => Some(PointerCapture::Absolute),
        }
    }

    pub fn hover(&mut self, state: &mut PanelState, x: f32, y: f32) {
        self.hover_with_modifiers(state, x, y, Modifiers::default());
    }

    pub fn hover_with_modifiers(&mut self, state: &mut PanelState, x: f32, y: f32, _mods: Modifiers) {
        state.pointer = (x >= 0.0 && y >= 0.0).then_some((x, y));
        if self.capture.is_none() {
            state.hover_control = layout::target_at(x, y);
        }
    }

    pub fn down(&mut self, state: &mut PanelState, x: f32, y: f32, _mods: Modifiers, clicks: u32) -> Vec<Edit> {
        let mut edits = self.focus_lost(state);
        let Some(control) = layout::target_at(x, y) else {
            return edits;
        };
        let Some(widget) = layout::widget(control) else {
            return edits;
        };
        let id = widget.id();
        state.hover_control = Some(control);
        state.pressed_control = Some(control);
        match widget.kind {
            Kind::Knob(_) if clicks >= 2 => {
                edits.extend(gesture(state, id, SPECS[id].default));
                state.pressed_control = None;
            }
            Kind::Knob(_) => {
                let start = state.params.get(id);
                let (cx, cy) = widget.at;
                self.capture = Some(Capture::Dial {
                    id,
                    start,
                    normalized: normalized(id, start),
                    last_y: y,
                    anchor: ReleaseAnchor { control, offset: (x - cx, y - cy) },
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
        let Some(Capture::Dial { id, normalized, last_y, .. }) = self.capture.as_mut() else {
            return Vec::new();
        };
        let id = *id;
        *normalized = widgets::drag_value(*normalized, *last_y, y, mods.fine(), DIAL_PX);
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

    /// The gesture ends where it is (release outside, focus lost).
    pub fn cancel(&mut self, state: &mut PanelState) -> Vec<Edit> {
        self.up(state)
    }

    pub fn focus_lost(&mut self, state: &mut PanelState) -> Vec<Edit> {
        self.up(state)
    }

    pub fn scroll(&mut self, state: &mut PanelState, x: f32, y: f32, delta: f32, mods: Modifiers) -> Vec<Edit> {
        if delta == 0.0 {
            return Vec::new();
        }
        // During a drag the wheel moves the dragged knob.
        let control = match &self.capture {
            Some(Capture::Dial { id, .. }) => Some(Control::Param(*id)),
            Some(Capture::Switch) => return Vec::new(),
            None => layout::target_at(x, y),
        };
        let Some(widget) = control.and_then(layout::widget) else {
            return Vec::new();
        };
        let id = widget.id();
        let spec = &SPECS[id];
        let now = state.params.get(id);
        let value = match widget.kind {
            Kind::Knob(_) if spec.stepped => spec.clamp(now + delta.signum()),
            Kind::Knob(_) => {
                let n = normalized(id, now) + delta * WHEEL_STEP * mods.fine();
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
    pub fn key(&mut self, state: &mut PanelState, key: &str, _mods: Modifiers) -> Vec<Edit> {
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
        let wheel = f.scroll(&mut s, x, y, 1.0, Modifiers::default());
        assert_eq!(wheel, vec![Edit::Value(p::VOICES, v + 1.0)]);
    }
}
