//! Pointer and keyboard input: host-free, returning semantic edits.
//!
//! The family's gestures (OpenCepstrum's, as open-eq has them):
//! - Knobs drag vertically and relative: the cursor hides, up is more,
//!   Command is fine, and on release the cursor lands back on the knob.
//!   The drag speeds up with the hand (the family's law, panelkit's
//!   `DragCurve::KNOB`): a full range is 700 px moved slowly and 350 px
//!   moved fast. Double-click resets to the default. Stepped knobs
//!   (Voices) are on the same curve: the drag keeps its own unrounded
//!   position, and only the written value is rounded to a step.
//! - Toggles and the algorithm selector act on the press: one click, one
//!   gesture, the other position.
//! - The wheel over a knob moves it 2% of its travel a notch (a step for a
//!   stepped one); over a switch, it throws it toward the wheel. A burst of
//!   notches is one host gesture (panelkit's `WheelHold`): it ends once the
//!   wheel rests (`tick`, from the mount's timer) or other input comes.
//! - Escape during a drag puts the value back where the drag began.
//! - Double-click resets, right-click edits (the family's law, Sam
//!   2026-10-10): on a value control (a knob, Voices, MIX) a double-click
//!   sets its default, and a right-click opens a menu holding "Edit
//!   value...", the only way into typed entry. Typing happens in place
//!   (MIX's own text, a knob's caption): Enter commits, Escape cancels, a
//!   press anywhere else commits. Which keys the editor takes from the host
//!   is panelkit's policy (`wants_key`).
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
//! - The Key Transform's four lists (source key and scale, destination
//!   key and scale) open on a press and choose on a press or Enter; the
//!   arrows, Home, End and a typed letter move through one. A choice sets
//!   the key states (the destination scale is the targets) and switches
//!   the source to Keys, since the transform is the Keys source's.
//!
//! Every value is echoed into `state.params` (and `state.keys`) before it is
//! returned.
use crate::layout::{self, Chooser, Control, Kind, Slot, MENU_ITEMS};
use crate::{fine, Edit, Menu, Modifiers, PanelState, TextEdit};
use opq_engine::params::{KeyState, SOURCE, SPECS};
use panelkit::entry::EntryKey;
use panelkit::menu::{Key as MenuKeyed, Press};
use panelkit::strip::{self, MenuKey};
use panelkit::{interaction, keys, widgets};
use std::time::Instant;

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
        /// The hand's smoothed speed over this drag (panelkit's).
        speed: widgets::DragSpeed,
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

/// The row a Key Transform list shows as current: its key, its scale, or
/// for the destination scale the one the targets spell (none: a set no
/// scale names, or octaves that differ).
pub fn current_row(state: &PanelState, slot: Slot) -> Option<usize> {
    let transform = state.keys.transform;
    match slot {
        Slot::SrcKey => Some(Slot::key_row(transform.src_key)),
        Slot::SrcScale => Some(transform.src_scale as usize),
        Slot::DstKey => Some(Slot::key_row(transform.dst_key)),
        Slot::DstScale => state.keys.dst_scale(),
    }
}

/// A row chosen in one of the Key Transform's lists. A destination scale
/// is written to the targets, every octave. A key change carries a named
/// destination scale to its new root (a hand-made target set stays as it
/// is). The source becomes Keys if it wasn't: the transform is its.
fn choose_row(state: &mut PanelState, chooser: Chooser, row: usize) -> Vec<Edit> {
    let slot = match chooser {
        Chooser::Transform(slot) => slot,
        Chooser::HouseFeel => {
            state.house_feel = opq_engine::HouseFeel::from_index(row as u8);
            return vec![Edit::HouseFeel(state.house_feel)];
        }
    };
    let mut keys = state.keys;
    let named = keys.dst_scale();
    match slot {
        Slot::SrcKey => keys.transform.src_key = Slot::row_key(row),
        Slot::SrcScale => keys.transform.src_scale = row as u8,
        Slot::DstKey => keys.transform.dst_key = Slot::row_key(row),
        Slot::DstScale => keys.set_dst_scale(row),
    }
    if let (Some(scale), true) = (named, slot != Slot::DstScale) {
        keys.set_dst_scale(scale);
    }
    state.keys = keys;
    let mut edits = vec![Edit::Keys(keys)];
    if !state.keys_source() {
        edits.extend(gesture(state, SOURCE, 1.0));
    }
    edits
}

#[derive(Default)]
pub struct Fittings {
    capture: Option<Capture>,
    /// A wheel gesture held open across a burst of notches: its parameter.
    wheel: Option<(usize, interaction::WheelHold)>,
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

/// A press inside the value being typed (where it is drawn).
fn in_entry(state: &PanelState, x: f32, y: f32) -> bool {
    state.text_edit.as_ref().is_some_and(|edit| {
        layout::widget(Control::Param(edit.id)).is_some_and(|w| w.entry_rect().contains(x, y))
    })
}

/// A value control's menu item `index` chosen for parameter `id`.
fn choose(state: &mut PanelState, id: usize, index: usize) {
    match MENU_ITEMS[index] {
        "Edit value..." => open_entry(state, id),
        other => unreachable!("menu item {other}"),
    }
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
        // An open menu highlights the item under the pointer.
        if let Some(menu) = state.menu.as_mut() {
            if let Some(index) = layout::menu_item_at(menu.at, x, y) {
                menu.index = index;
            }
        }
        if let Some(list) = state.list.as_mut() {
            list.point(x, y, layout::MENU_BOUNDS);
        }
        // Nothing under an open list is hovered: the line keeps its owner.
        let over_list = state.list.as_ref().is_some_and(|list| list.contains(x, y, layout::MENU_BOUNDS));
        if self.capture.is_none() && !over_list {
            state.hover_control = layout::target_at(state.view, x, y);
        }
    }

    pub fn down(&mut self, state: &mut PanelState, x: f32, y: f32, mods: Modifiers, clicks: u32) -> Vec<Edit> {
        let mut edits = self.end_wheel();
        // An open menu takes the press: an item chooses, anywhere else
        // closes it and does nothing more.
        if let Some(menu) = state.menu.take() {
            if let Some(index) = layout::menu_item_at(menu.at, x, y) {
                choose(state, menu.id, index);
            }
            return edits;
        }
        // An open list likewise: a row chooses, a group row opens its
        // scales, anywhere else closes it.
        if let Some(mut list) = state.list.take() {
            match list.press(x, y, layout::MENU_BOUNDS) {
                Press::Chose(row) => edits.extend(choose_row(state, list.target, row)),
                Press::Inside => {
                    if let Some(group) = list.row_at(x, y, layout::MENU_BOUNDS).filter(|&row| list.rows()[row].opens()) {
                        list.open_submenu(group);
                    }
                    state.list = Some(list);
                }
                Press::Outside => {}
            }
            return edits;
        }
        // A value being typed: a press in its box keeps typing; anywhere
        // else commits it (or drops it, when it doesn't parse) and goes on.
        if in_entry(state, x, y) {
            return edits;
        }
        edits.extend(self.down_outside_entry(state, x, y));
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
        if let Control::Viewer(viewer) = control {
            // Editor-local: what the screen shows is no parameter.
            state.viewer = viewer;
            return edits;
        }
        if let Control::Transform(slot) = control {
            // Its list opens on what it shows (a hand-made set: the top).
            state.list = Some(layout::transform_menu(slot, current_row(state, slot)));
            return edits;
        }
        if control == Control::HouseFeel {
            state.list = Some(layout::house_feel_menu(state.house_feel));
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
                    speed: widgets::DragSpeed::default(),
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
        self.drag_at(state, x, y, mods, Instant::now())
    }

    /// A drag move at `at`: a knob's travel follows the hand's speed, so
    /// it needs the move's own time (the mounts' moves arrive between
    /// frames).
    pub fn drag_at(&mut self, state: &mut PanelState, x: f32, y: f32, mods: Modifiers, at: Instant) -> Vec<Edit> {
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
        let Some(Capture::Dial { id, normalized, last_y, speed, .. }) = self.capture.as_mut() else {
            return Vec::new();
        };
        let id = *id;
        // `normalized` is the drag's own position, never rounded: a stepped
        // knob works toward its next step and lands on it (Sam's ruling).
        *normalized = widgets::drag_value_at(*normalized, *last_y, y, fine(mods), &widgets::DragCurve::KNOB, speed, at);
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
    /// being typed and an open menu are dropped.
    pub fn cancel(&mut self, state: &mut PanelState) -> Vec<Edit> {
        state.text_edit = None;
        state.menu = None;
        state.list = None;
        let mut edits = self.end_wheel();
        edits.extend(self.up(state));
        edits
    }

    pub fn focus_lost(&mut self, state: &mut PanelState) -> Vec<Edit> {
        let mut edits = self.end_wheel();
        edits.extend(self.up(state));
        edits
    }

    /// The mount's timer, each frame: a wheel gesture that has rested ends.
    /// An open list's submenu follows a pointer that has rested.
    pub fn tick(&mut self, state: &mut PanelState, now: Instant) -> Vec<Edit> {
        if let Some(list) = state.list.as_mut() {
            list.tick(now);
        }
        let Some((id, hold)) = self.wheel.as_mut() else { return Vec::new() };
        if !hold.expired(now) {
            return Vec::new();
        }
        let id = *id;
        self.wheel = None;
        vec![Edit::End(id)]
    }

    /// Other input came before the wheel rested: its gesture ends now.
    fn end_wheel(&mut self) -> Vec<Edit> {
        let Some((id, mut hold)) = self.wheel.take() else { return Vec::new() };
        if hold.release() {
            vec![Edit::End(id)]
        } else {
            Vec::new()
        }
    }

    /// A right-click: on a value control, its menu ("Edit value...");
    /// anywhere else, an open menu closes.
    pub fn context(&mut self, state: &mut PanelState, x: f32, y: f32) -> Vec<Edit> {
        let mut edits = self.end_wheel();
        edits.extend(self.down_outside_entry(state, x, y));
        state.menu = None;
        state.list = None;
        if let Some(widget) = layout::target_at(state.view, x, y).and_then(layout::widget) {
            if widget.is_value() {
                edits.extend(self.up(state));
                state.menu = Some(Menu { id: widget.id(), at: (x, y), index: 0 });
            }
        }
        edits
    }

    /// What is open, for panelkit's key policy (and Win32's wait for a
    /// typed character).
    pub fn keys_open(&self, state: &PanelState) -> keys::Open {
        keys::Open {
            entry: state.text_edit.is_some(),
            list: state.menu.is_some() || state.list.is_some(),
            cancellable: self.capture.is_some(),
        }
    }

    /// The value control Enter would open typed entry for: the one under
    /// the pointer, while nothing is held (the family's shortcut to its
    /// menu's "Edit value...", Sam 2026-10-10).
    fn enter_target(&self, state: &PanelState) -> Option<usize> {
        if self.capture.is_some() {
            return None;
        }
        let widget = layout::widget(state.hover_control?)?;
        widget.is_value().then(|| widget.id())
    }

    /// Whether the editor takes `key` from the host: panelkit's rules,
    /// plus Enter over a value control, which opens its typed entry.
    pub fn wants_key(&self, state: &PanelState, key: &str, mods: Modifiers) -> bool {
        keys::wants(key, mods, &self.keys_open(state), || {
            key == "Enter" && !mods.command && self.enter_target(state).is_some()
        })
    }

    /// A press outside a value being typed commits it (or drops it when it
    /// doesn't parse); inside, nothing.
    fn down_outside_entry(&mut self, state: &mut PanelState, x: f32, y: f32) -> Vec<Edit> {
        if state.text_edit.is_none() || in_entry(state, x, y) {
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
        if (delta == 0.0 && content == 0.0) || state.menu.is_some() {
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
        if matches!(
            control,
            None | Some(Control::Key(_) | Control::ScrollBar | Control::Viewer(_) | Control::Transform(_))
        ) {
            // (An open list holds the view still under it.)
            if layout::scrolls_view(x, y) && state.list.is_none() {
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
        state.params.set(id, value);
        if let Some(Capture::Dial { normalized: n, .. }) = self.capture.as_mut() {
            *n = normalized(id, value);
            return vec![Edit::Value(id, value)];
        }
        // A burst of notches is one gesture: begun on its first, held open
        // (a notch on another control ends it and begins that one's).
        let mut edits = Vec::new();
        if self.wheel.as_ref().is_none_or(|&(held, _)| held != id) {
            edits.extend(self.end_wheel());
            edits.push(Edit::Begin(id));
        }
        self.wheel.get_or_insert((id, interaction::WheelHold::default())).1.touch(state.now);
        edits.push(Edit::Value(id, value));
        edits
    }

    /// A key the editor took (`wants_key`); any key ends a wheel gesture.
    /// An open menu takes the family's menu keys (panelkit's `menu_key`:
    /// arrows, Enter chooses, Escape closes); the value being typed takes
    /// its editing keys (Enter commits, Escape cancels); Escape during a
    /// knob drag puts it back where the drag began.
    pub fn key(&mut self, state: &mut PanelState, key: &str, mods: Modifiers) -> Vec<Edit> {
        let mut edits = self.end_wheel();
        edits.extend(self.key_taken(state, key, mods));
        edits
    }

    fn key_taken(&mut self, state: &mut PanelState, key: &str, mods: Modifiers) -> Vec<Edit> {
        if let Some(menu) = state.menu.as_mut() {
            if key == "Escape" {
                state.menu = None;
                return Vec::new();
            }
            let label = |i: usize| MENU_ITEMS[i].to_owned();
            if let MenuKey::Chose(index) =
                strip::menu_key(&mut menu.index, MENU_ITEMS.len(), 1, key, mods.shift, mods.command, label)
            {
                let id = menu.id;
                state.menu = None;
                choose(state, id, index);
            }
            return Vec::new();
        }
        if let Some(list) = state.list.as_mut() {
            let chooser = list.target;
            return match list.key(key, mods.shift, mods.command) {
                MenuKeyed::Moved => Vec::new(),
                MenuKeyed::Closed => {
                    state.list = None;
                    Vec::new()
                }
                MenuKeyed::Chose(row) => {
                    state.list = None;
                    choose_row(state, chooser, row)
                }
            };
        }
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
        if key == "Enter" && !mods.command {
            // The shortcut to "Edit value...": as choosing it from the menu.
            if let Some(id) = self.enter_target(state) {
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
        // A drag's first move is at rest: the whole range is 700 px (the
        // family's knob curve), so 70 px up is a tenth.
        let start = Instant::now();
        let drag = f.drag_at(&mut s, x, y - 70.0, Modifiers::default(), start);
        let Edit::Value(id, v) = drag[0] else { panic!("{drag:?}") };
        assert_eq!(id, p::FEEL);
        assert!((v - (before + 0.1)).abs() < 1e-4, "{v}");
        assert_eq!(s.params.get(p::FEEL), v);
        // A fast hand covers more per pixel: 70 px more in 10 ms.
        let later = start + std::time::Duration::from_millis(10);
        f.drag_at(&mut s, x, y - 140.0, Modifiers::default(), later);
        let fast = s.params.get(p::FEEL) - v;
        assert!(fast > 0.11 && fast <= 0.2 + 1e-4, "{fast}");
        assert_eq!(f.up(&mut s), vec![Edit::End(p::FEEL)]);
        assert!(f.capture().is_none());
    }

    #[test]
    fn a_slow_drag_on_the_stepped_knob_works_toward_the_next_step() {
        // Voices: 12 positions on the knobs' curve. At rest speed a step is
        // 700/11 px, about 64: small moves add up to it, none is lost.
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let (x, y) = at(p::VOICES);
        let before = s.params.get(p::VOICES);
        f.down(&mut s, x, y, Modifiers::default(), 1);
        let start = Instant::now();
        let mut edits = Vec::new();
        for i in 1..=8u64 {
            let at = start + std::time::Duration::from_millis(400 * i);
            edits.extend(f.drag_at(&mut s, x, y - 8.0 * i as f32, Modifiers::default(), at));
        }
        // 64 px, slowly: exactly one step, written once.
        assert_eq!(edits, [Edit::Value(p::VOICES, before + 1.0)]);
        f.up(&mut s);
        // A flick crosses the range: 350 px fast is all of it.
        f.down(&mut s, x, y, Modifiers::default(), 1);
        let start = Instant::now();
        for i in 1..=20u64 {
            let at = start + std::time::Duration::from_millis(5 * i);
            f.drag_at(&mut s, x, y + 20.0 * i as f32, Modifiers::default(), at);
        }
        assert_eq!(s.params.get(p::VOICES), SPECS[p::VOICES].min);
        f.up(&mut s);
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
        // 64 px of the 700 at rest is one of Voices' 11 steps: a whole step.
        let drag = f.drag(&mut s, x, y - 64.0, Modifiers::default());
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
    fn a_viewer_key_picks_the_screen_and_edits_nothing() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        assert_eq!(s.viewer, layout::Viewer::Transect);
        for viewer in [layout::Viewer::Scope, layout::Viewer::Ladders, layout::Viewer::Transect] {
            let key = layout::viewer_key(viewer);
            let (x, y) = (key.x + 10.0, key.y + 8.0);
            assert!(f.down(&mut s, x, y, Modifiers::default(), 1).is_empty());
            assert!(f.up(&mut s).is_empty());
            assert_eq!(s.viewer, viewer);
            // The wheel over a key moves nothing.
            assert!(f.scroll(&mut s, x, y, 1.0, 1.0, Modifiers::default()).is_empty());
            assert_eq!(s.view, layout::VIEW_DEFAULT);
        }
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

    /// Right-click, then the menu's "Edit value...": typed entry opens.
    fn edit_value(f: &mut Fittings, s: &mut PanelState, id: usize) {
        let (x, y) = at(id);
        assert!(f.context(s, x, y).is_empty());
        let menu = s.menu.expect("a value control's menu");
        assert_eq!((menu.id, layout::MENU_ITEMS[0]), (id, "Edit value..."));
        assert!(s.text_edit.is_none(), "the menu, not the entry, opens first");
        let item = layout::menu_item(menu.at, 0);
        assert!(f.down(s, item.x + 4.0, item.y + 4.0, Modifiers::default(), 1).is_empty());
        assert!(s.menu.is_none() && s.text_edit.as_ref().is_some_and(|e| e.id == id));
    }

    #[test]
    fn mix_is_typed_in_place_from_its_menu() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let (x, y) = at(p::MIX);
        // Nothing open: the host keeps its keys, but for Enter over a value
        // control (below).
        f.hover(&mut s, x, y);
        assert!(!f.wants_key(&s, "5", Modifiers::default()));
        edit_value(&mut f, &mut s, p::MIX);
        // Space is the host's even while typing.
        assert!(!f.wants_key(&s, " ", Modifiers::default()));
        // A bare number is a percentage, as the value reads (pluginkit
        // 6752fb6).
        assert!(typed(&mut f, &mut s, "50").is_empty());
        assert!(f.wants_key(&s, "Enter", Modifiers::default()));
        let commit = f.key(&mut s, "Enter", Modifiers::default());
        assert_eq!(commit, vec![Edit::Begin(p::MIX), Edit::Value(p::MIX, 0.5), Edit::End(p::MIX)]);
        assert!(s.text_edit.is_none());
        // Nonsense stays open, marked; Escape drops it with no edit.
        edit_value(&mut f, &mut s, p::MIX);
        typed(&mut f, &mut s, "loud");
        assert!(f.key(&mut s, "Enter", Modifiers::default()).is_empty());
        assert!(s.text_edit.as_ref().is_some_and(|e| e.error));
        assert!(f.key(&mut s, "Escape", Modifiers::default()).is_empty());
        assert!(s.text_edit.is_none());
        assert_eq!(s.params.get(p::MIX), 0.5);
        // A press elsewhere commits what was typed, and acts.
        edit_value(&mut f, &mut s, p::MIX);
        typed(&mut f, &mut s, "25%"); // the % sign is fine too
        let (fx, fy) = at(p::FEEL);
        let edits = f.down(&mut s, fx, fy, Modifiers::default(), 1);
        assert_eq!(&edits[..3], &[Edit::Begin(p::MIX), Edit::Value(p::MIX, 0.25), Edit::End(p::MIX)]);
        assert_eq!(edits[3], Edit::Begin(p::FEEL));
    }

    /// Open `slot`'s list with a press and choose the row named `name`.
    fn pick(f: &mut Fittings, s: &mut PanelState, slot: Slot, name: &str) -> Vec<Edit> {
        let r = slot.rect();
        assert!(f.down(s, r.x + 4.0, r.y + 4.0, Modifiers::default(), 1).is_empty());
        f.up(s);
        assert_eq!(s.list.as_ref().map(|list| list.target), Some(Chooser::Transform(slot)));
        let row = (0..slot.rows()).find(|&row| slot.label(row) == name).unwrap();
        let path = layout::menu_path(s.list.as_ref().unwrap(), row);
        for &(x, y) in &path {
            f.hover(s, x, y);
        }
        let (x, y) = *path.last().unwrap();
        let edits = f.down(s, x, y, Modifiers::default(), 1);
        f.up(s);
        assert!(s.list.is_none());
        edits
    }

    fn shown(s: &PanelState) -> [&'static str; 4] {
        Slot::ALL.map(|slot| current_row(s, slot).map_or("*", |row| slot.label(row)))
    }

    #[test]
    fn the_key_transform_is_chosen_from_its_lists() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        assert_eq!(shown(&s), ["*", "CHROMATIC", "*", "CHROMATIC"]);
        assert!(!s.keys_source());
        // "* CHROMATIC to F MAJOR": the first choice turns the source to
        // Keys (one gesture); the scale lands on the keys once F is named.
        let edits = pick(&mut f, &mut s, Slot::DstScale, "MAJOR");
        assert_eq!(edits.len(), 4);
        assert!(matches!(edits[0], Edit::Keys(_)));
        assert_eq!(edits[1..], [Edit::Begin(SOURCE), Edit::Value(SOURCE, 1.0), Edit::End(SOURCE)]);
        assert!(s.keys_source());
        // The key change carries the named scale to its new root.
        let edits = pick(&mut f, &mut s, Slot::DstKey, "F");
        assert_eq!(edits, [Edit::Keys(s.keys)]);
        assert_eq!(shown(&s), ["*", "CHROMATIC", "F", "MAJOR"]);
        assert!((0..128).all(|n| s.keys.get(KeyState::Target, n) == [0, 2, 4, 5, 7, 9, 10].contains(&(n % 12))));
        // Nothing more than the nearest target is asked of the engine.
        assert_eq!(s.keys.remap(), None);
        // A source scale makes it a map; "*" took F for the source's key.
        pick(&mut f, &mut s, Slot::SrcScale, "MINOR");
        let remap = s.keys.remap().expect("F minor to F major");
        assert_eq!(remap.sung(68), 69);

        // A key edited by hand: the destination reads "*", unless the keys
        // happen to spell a listed scale.
        let (x, y) = (layout::RULER.x + 4.0, layout::note_y(s.view, 71.0));
        f.down(&mut s, x, y, Modifiers::default(), 1);
        f.up(&mut s);
        assert_eq!(shown(&s)[3], "*");
        let (x, y) = (layout::RULER.x + 4.0, layout::note_y(s.view, 70.0));
        f.down(&mut s, x, y, Modifiers::default(), 1);
        f.up(&mut s);
        assert_eq!(shown(&s)[3], "LYDIAN");
        // With SCOPE at Custom one key is one note: no scale.
        s.params.set(p::SCOPE, 1.0);
        f.down(&mut s, x, y, Modifiers::default(), 1);
        f.up(&mut s);
        assert_eq!((shown(&s)[3], s.keys.remap()), ("*", None));
    }

    #[test]
    fn the_strip_dropdown_picks_houses_feel_law() {
        use opq_engine::HouseFeel;
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let none = Modifiers::default();
        let (x, y) = layout::HOUSE_FEEL.center();
        assert_eq!(layout::target_at(s.view, x, y), Some(Control::HouseFeel));
        f.down(&mut s, x, y, none, 1);
        f.up(&mut s);
        let menu = s.list.as_ref().unwrap();
        assert_eq!((menu.target, menu.cursor()), (Chooser::HouseFeel, Some(0)));
        // It opens above the strip, inside the board.
        let r = menu.rect(layout::MENU_BOUNDS);
        assert!(r.y + r.h <= layout::HOUSE_FEEL.y && r.y >= 0.0);
        let (bx, by) = layout::menu_path(menu, 1)[0];
        f.hover(&mut s, bx, by);
        assert_eq!(f.down(&mut s, bx, by, none, 1), [Edit::HouseFeel(HouseFeel::B)]);
        assert!(s.list.is_none() && s.house_feel == HouseFeel::B);
        // From the keys: it reopens on B; Down and Enter take C.
        f.down(&mut s, x, y, none, 1);
        f.up(&mut s);
        f.key(&mut s, "ArrowDown", none);
        assert_eq!(f.key(&mut s, "Enter", none), [Edit::HouseFeel(HouseFeel::C)]);
    }

    #[test]
    fn a_key_transform_list_is_worked_from_the_keyboard_and_closes() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let none = Modifiers::default();
        let r = Slot::SrcScale.rect();
        f.down(&mut s, r.x + 4.0, r.y + 4.0, none, 1);
        f.up(&mut s);
        // Open: the editor takes the list's keys, Space stays the host's.
        assert!(f.wants_key(&s, "ArrowDown", none) && f.wants_key(&s, "Enter", none));
        assert!(!f.wants_key(&s, " ", none));
        // It opens on the current scale; a typed letter finds the next
        // row starting with it, and Right opens a group.
        let cursor = |s: &PanelState| s.list.as_ref().unwrap().cursor().unwrap();
        assert_eq!(s.list.as_ref().unwrap().rows()[cursor(&s)].label, "Chromatic");
        f.key(&mut s, "s", none);
        assert_eq!(s.list.as_ref().unwrap().rows()[cursor(&s)].label, "Symmetric");
        f.key(&mut s, "ArrowRight", none);
        let edits = f.key(&mut s, "Enter", none);
        assert!(s.list.is_none() && matches!(edits[0], Edit::Keys(_)));
        assert_eq!(shown(&s)[1], "WHOLE TONE");
        // Reopened, it starts on the group that holds the current scale.
        f.down(&mut s, r.x + 4.0, r.y + 4.0, none, 1);
        f.up(&mut s);
        assert_eq!(s.list.as_ref().unwrap().rows()[cursor(&s)].label, "Symmetric");
        f.key(&mut s, "Home", none);
        f.key(&mut s, "ArrowDown", none);
        let edits = f.key(&mut s, "Enter", none);
        assert!(s.list.is_none() && matches!(edits[0], Edit::Keys(_)));
        assert_eq!(shown(&s)[1], "MAJOR");
        // Escape closes without choosing; so does a press elsewhere, which
        // does nothing more.
        f.down(&mut s, r.x + 4.0, r.y + 4.0, none, 1);
        f.up(&mut s);
        f.key(&mut s, "End", none);
        assert!(f.key(&mut s, "Escape", none).is_empty() && s.list.is_none());
        f.down(&mut s, r.x + 4.0, r.y + 4.0, none, 1);
        f.up(&mut s);
        let (x, y) = at(p::FEEL);
        assert!(f.down(&mut s, x, y, none, 2).is_empty() && s.list.is_none());
        assert_eq!(shown(&s)[1], "MAJOR");
        assert!(!f.wants_key(&s, "ArrowDown", none));
    }

    #[test]
    fn enter_over_a_value_control_opens_its_typed_entry() {
        let enter = |f: &Fittings, s: &PanelState| f.wants_key(s, "Enter", Modifiers::default());
        for w in &layout::WIDGETS {
            let mut s = PanelState::default();
            let mut f = Fittings::default();
            // Off every control the host keeps Enter.
            f.hover(&mut s, 2.0, 2.0);
            assert!(!enter(&f, &s));
            let (x, y) = w.at;
            f.hover(&mut s, x, y);
            // Exactly the controls whose menu holds "Edit value...".
            assert_eq!(enter(&f, &s), w.is_value(), "{}", w.caption);
            assert!(f.key(&mut s, "Enter", Modifiers::default()).is_empty());
            assert_eq!(s.text_edit.as_ref().map(|e| e.id), w.is_value().then(|| w.id()), "{}", w.caption);
            assert!(s.menu.is_none());
        }
        // Not while a knob is held, and Cmd+Enter is the host's.
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let (x, y) = at(p::FEEL);
        f.hover(&mut s, x, y);
        assert!(!f.wants_key(&s, "Enter", Modifiers { command: true, ..Modifiers::default() }));
        f.down(&mut s, x, y, Modifiers::default(), 1);
        assert!(!enter(&f, &s));
        f.key(&mut s, "Enter", Modifiers::default());
        assert!(s.text_edit.is_none());
    }

    #[test]
    fn every_value_control_has_the_menu_and_switches_have_none() {
        for w in &layout::WIDGETS {
            let mut s = PanelState::default();
            let mut f = Fittings::default();
            let (x, y) = w.at;
            f.context(&mut s, x, y);
            assert_eq!(s.menu.is_some(), w.is_value(), "{}", w.caption);
            if w.is_value() {
                // A double-click resets it; it never opens typed entry.
                s.menu = None;
                s.params.set(w.id(), SPECS[w.id()].max);
                let edits = f.down(&mut s, x, y, Modifiers::default(), 2);
                assert!(edits.contains(&Edit::Value(w.id(), SPECS[w.id()].default)), "{}", w.caption);
                assert!(s.text_edit.is_none(), "{}", w.caption);
            }
        }
        // The keyboard works the menu: Enter chooses, Escape closes.
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let (x, y) = at(p::FEEL);
        f.context(&mut s, x, y);
        assert!(f.wants_key(&s, "Enter", Modifiers::default()) && !f.wants_key(&s, " ", Modifiers::default()));
        f.key(&mut s, "Enter", Modifiers::default());
        assert!(s.menu.is_none() && s.text_edit.as_ref().is_some_and(|e| e.id == p::FEEL));
        typed(&mut f, &mut s, "40");
        let commit = f.key(&mut s, "Enter", Modifiers::default());
        let [Edit::Begin(p::FEEL), Edit::Value(p::FEEL, v), Edit::End(p::FEEL)] = commit[..] else { panic!("{commit:?}") };
        assert!((v - 0.4).abs() < 1e-6, "{v}");
        f.context(&mut s, x, y);
        f.key(&mut s, "Escape", Modifiers::default());
        assert!(s.menu.is_none() && s.text_edit.is_none());
    }

    #[test]
    fn a_wheel_burst_is_one_gesture_until_the_wheel_rests() {
        let mut s = PanelState::default();
        let mut f = Fittings::default();
        let t = s.now;
        let (x, y) = at(p::FEEL);
        let first = f.scroll(&mut s, x, y, 1.0, 1.0, Modifiers::default());
        assert!(matches!(first[..], [Edit::Begin(p::FEEL), Edit::Value(p::FEEL, _)]), "{first:?}");
        let second = f.scroll(&mut s, x, y, 1.0, 1.0, Modifiers::default());
        assert!(matches!(second[..], [Edit::Value(p::FEEL, _)]), "{second:?}");
        assert!(f.tick(&mut s, t + interaction::WheelHold::IDLE / 2).is_empty());
        assert_eq!(f.tick(&mut s, t + interaction::WheelHold::IDLE * 2), vec![Edit::End(p::FEEL)]);
        // Another control's notch ends the open gesture and begins its own;
        // a press ends it too.
        f.scroll(&mut s, x, y, 1.0, 1.0, Modifiers::default());
        let (gx, gy) = at(p::GLIDE);
        let moved = f.scroll(&mut s, gx, gy, 1.0, 1.0, Modifiers::default());
        assert!(matches!(moved[..], [Edit::End(p::FEEL), Edit::Begin(p::GLIDE), Edit::Value(p::GLIDE, _)]), "{moved:?}");
        let press = f.down(&mut s, x, y, Modifiers::default(), 1);
        assert_eq!(&press[..2], &[Edit::End(p::GLIDE), Edit::Begin(p::FEEL)]);
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
