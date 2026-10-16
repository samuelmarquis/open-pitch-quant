//! Renders the board offline, for review: the same Board the plugin mounts,
//! fed by the engine itself. The material is synthetic: three harmonic
//! voices (one with vibrato, one gliding a fourth) under a held chord.
//!
//! Usage: panel-render [--out DIR] [--scale N] [SCENARIO...]
//!        panel-render --geometry   (the family probe's geometry, JSON)
//! Scenarios: house, oracle, keys, empty, drag, typing, menu, ladders,
//! scope, transform, transform-list, house-feel (default: all).
use opq_engine::params::{self as p, KeyState, Keys, Params};
use opq_engine::Engine;
use opq_panel::layout;
use opq_panel::{pack, Board, Fittings, Modifiers, PanelState};
use panelkit::gpu::Gpu;
use std::f64::consts::TAU;
use std::path::PathBuf;
use std::time::{Duration, Instant};

const SR: f64 = 48_000.0;
const SCENARIOS: [&str; 12] = [
    "house", "oracle", "keys", "empty", "drag", "typing", "menu", "ladders", "scope", "transform", "transform-list", "house-feel",
];

fn midi_hz(note: f64) -> f64 {
    440.0 * ((note - 69.0) / 12.0).exp2()
}

/// A harmonic voice: pitch over time (MIDI), level, partials falling off.
struct Voice {
    phase: [f64; 8],
    pitch: fn(f64) -> f64,
    level: f64,
}

impl Voice {
    fn sample(&mut self, t: f64) -> f64 {
        let f0 = midi_hz((self.pitch)(t));
        let mut out = 0.0;
        for (h, phase) in self.phase.iter_mut().enumerate() {
            let k = (h + 1) as f64;
            *phase = (*phase + TAU * f0 * k / SR) % TAU;
            out += phase.sin() / k.powf(1.3);
        }
        out * self.level
    }
}

/// Runs `seconds` of the material through an engine with `params` and
/// `held` notes, handing its analysis frames to `state` as the mount does.
fn feed(state: &mut PanelState, held: &[u8], seconds: f64) {
    let params: Params = state.params;
    let mut engine = Engine::new(SR, 2);
    // As the plugin does: the Keys source's targets, or the held notes.
    let keys = if params.keys_source() {
        state.keys.held()
    } else {
        let mut keys = [false; 128];
        for &n in held {
            keys[n as usize] = true;
        }
        keys
    };
    let mut voices = [
        // A3 a little sharp, singing with vibrato.
        Voice { phase: [0.0; 8], pitch: |t| 57.3 + 0.35 * (TAU * 5.5 * t).sin(), level: 0.16 },
        // A slow walk from D4 up to G4 and back.
        Voice { phase: [0.0; 8], pitch: |t| 62.0 + 2.5 * (1.0 - (TAU * t / 9.0).cos()), level: 0.12 },
        // A flat B4 that comes and goes.
        Voice { phase: [0.0; 8], pitch: |_| 70.7, level: 0.10 },
    ];
    let block = 512;
    let (mut l, mut r) = (vec![0.0f32; block], vec![0.0f32; block]);
    let mut engine_params = params.engine();
    if params.keys_source() {
        engine_params.bypass_keys = state.keys.bypass;
        engine_params.remap = state.keys.remap();
    }
    let mut t = 0.0f64;
    for _ in 0..(seconds * SR / block as f64) as usize {
        for i in 0..block {
            let gate = if (t % 3.0) < 2.2 { 1.0 } else { 0.0 };
            // Plucked onsets every 1.5 s on the first voice.
            let pluck = (-((t % 1.5) * 9.0)).exp();
            let s = voices[0].sample(t) * (0.4 + 0.6 * pluck) + voices[1].sample(t) + voices[2].sample(t) * gate;
            l[i] = s as f32;
            r[i] = (s * 0.97) as f32;
            t += 1.0 / SR;
        }
        let mut io: [&mut [f32]; 2] = [&mut l[..], &mut r[..]];
        engine.process_block(&mut io, &keys, &engine_params);
        state.push_frames(std::iter::from_fn(|| engine.viz_pop()));
    }
    state.engine_info = (SR as f32, opq_engine::HOP as u32);
}

/// The version the plugin shows (its manifest's), so a still's bottom row
/// is the plugin's.
fn product_version() -> &'static str {
    include_str!("../../../../wrac/plugins/opq/src-plugin/Cargo.toml")
        .lines()
        .find_map(|line| line.strip_prefix("version = \""))
        .and_then(|rest| rest.strip_suffix('"'))
        .expect("the plugin manifest's version")
}

fn scenario(name: &str) -> PanelState {
    let start = Instant::now();
    let mut state = PanelState::new(start);
    state.version = product_version();
    let chord = [60u8, 64, 67, 71];
    match name {
        "house" => {
            feed(&mut state, &chord, 11.0);
        }
        "oracle" => {
            state.params.set(p::ALGORITHM, 1.0);
            state.params.set(p::PURIFY, 0.4);
            state.params.set(p::FEEL, 0.6);
            state.params.set(p::VOICES, 3.0);
            feed(&mut state, &[57, 60, 64, 69, 72], 11.0);
            let (x, y) = layout::WIDGETS.iter().find(|w| w.id() == p::PURIFY).unwrap().at;
            Fittings::default().hover(&mut state, x, y);
        }
        "keys" => {
            // The Keys source: C major in every octave, E bypassed, the view
            // scrolled up an octave, the pointer on a key.
            state.params.set(p::SOURCE, 1.0);
            state.keys = Keys { target: 0, ..Keys::default() };
            for pc in [0, 2, 4, 5, 7, 9, 11] {
                state.keys.set(KeyState::Target, pc, true, true);
            }
            state.keys.set(KeyState::Bypass, 4, true, true);
            state.view = layout::VIEW_DEFAULT + 12.0;
            feed(&mut state, &[], 11.0);
            let (x, y) = (layout::RULER.x + 6.0, layout::note_y(state.view, 69.0));
            Fittings::default().hover(&mut state, x, y);
        }
        "drag" => {
            // TRANSIENTS thrown, then FEEL held mid-drag: its caption
            // shows its value.
            feed(&mut state, &chord, 11.0);
            let mut f = Fittings::default();
            let (x, y) = layout::WIDGETS.iter().find(|w| w.id() == p::TRANSIENT).unwrap().at;
            f.down(&mut state, x, y, Modifiers::default(), 1);
            f.up(&mut state);
            let (x, y) = layout::WIDGETS.iter().find(|w| w.id() == p::FEEL).unwrap().at;
            f.down(&mut state, x, y, Modifiers::default(), 1);
            f.drag(&mut state, x, y - 60.0, Modifiers::default());
        }
        "typing" => {
            // GLIDE's "Edit value..." chosen and half typed: the family's
            // entry over its caption.
            feed(&mut state, &chord, 11.0);
            let mut f = Fittings::default();
            let (x, y) = layout::WIDGETS.iter().find(|w| w.id() == p::GLIDE).unwrap().at;
            f.hover(&mut state, x, y);
            f.context(&mut state, x, y);
            f.key(&mut state, "Enter", Modifiers::default());
            for key in ["2", "5", "0"] {
                f.key(&mut state, key, Modifiers::default());
            }
        }
        "transform" | "transform-list" => {
            // The Key Transform, chosen through its lists as a user would
            // (from the MIDI source, so the first choice turns it to
            // Keys): A minor to A major, so the walking voice's C5 is
            // sung at C sharp. In "transform-list" the destination's
            // scale list is open with the pointer down it.
            let mut f = Fittings::default();
            let rows = |slot: layout::Slot, name: &str| (0..slot.rows()).find(|&row| slot.label(row) == name).unwrap();
            for (slot, name) in [
                (layout::Slot::SrcKey, "A"),
                (layout::Slot::SrcScale, "MINOR"),
                (layout::Slot::DstScale, "MAJOR"),
            ] {
                let at = slot.rect();
                f.down(&mut state, at.x + 4.0, at.y + 4.0, Modifiers::default(), 1);
                f.up(&mut state);
                let path = layout::menu_path(state.list.as_ref().unwrap(), rows(slot, name));
                for &(x, y) in &path {
                    f.hover(&mut state, x, y);
                }
                let (x, y) = *path.last().unwrap();
                f.down(&mut state, x, y, Modifiers::default(), 1);
                f.up(&mut state);
            }
            feed(&mut state, &[], 11.0);
            let slot = layout::Slot::DstScale;
            let at = slot.rect();
            f.hover(&mut state, at.x + 20.0, at.y + 8.0);
            if name == "transform-list" {
                f.down(&mut state, at.x + 20.0, at.y + 8.0, Modifiers::default(), 1);
                f.up(&mut state);
                // The pointer down the modes to Lydian.
                for &(x, y) in &layout::menu_path(state.list.as_ref().unwrap(), rows(slot, "LYDIAN")) {
                    f.hover(&mut state, x, y);
                }
            }
        }
        "house-feel" => {
            // The strip's HOUSE FEEL dropdown open, the pointer on B.
            feed(&mut state, &chord, 11.0);
            let mut f = Fittings::default();
            let (x, y) = layout::HOUSE_FEEL.center();
            f.hover(&mut state, x, y);
            f.down(&mut state, x, y, Modifiers::default(), 1);
            f.up(&mut state);
            let (bx, by) = layout::menu_path(state.list.as_ref().unwrap(), 1)[0];
            f.hover(&mut state, bx, by);
        }
        "menu" => {
            // FEEL right-clicked: its menu open, the pointer on its item.
            feed(&mut state, &chord, 11.0);
            let mut f = Fittings::default();
            let (x, y) = layout::WIDGETS.iter().find(|w| w.id() == p::FEEL).unwrap().at;
            f.hover(&mut state, x, y);
            f.context(&mut state, x, y);
            let item = layout::menu_item((x, y), 0);
            f.hover(&mut state, item.x + 20.0, item.y + 8.0);
        }
        "ladders" | "scope" => {
            // The house material, its viewer picked by its key, the
            // pointer resting on that key.
            feed(&mut state, &chord, 11.0);
            let viewer = if name == "ladders" { layout::Viewer::Ladders } else { layout::Viewer::Scope };
            let key = layout::viewer_key(viewer);
            let (x, y) = (key.x + key.w * 0.5, key.y + key.h * 0.5);
            let mut f = Fittings::default();
            f.hover(&mut state, x, y);
            f.down(&mut state, x, y, Modifiers::default(), 1);
            f.up(&mut state);
        }
        _ => {}
    }
    // Frames as the mount would tick them: the scenario's own settings
    // show and fade like any other change, a hovered control's help types
    // in, and a knob held in a drag keeps showing its value.
    for t in [0.0, 1.0, 2.0, 3.0, 3.3] {
        state.update(start + Duration::from_secs_f64(t));
    }
    state
}

/// The editor as the family probe's generic checks see it
/// (`../open-wrac/tools/native-probe`, schema family-probe/1): every value
/// control (a knob: vertical drag, wheel, double-click reset, the cursor
/// back at the grab), and typed entry opened both ways the law gives:
/// MIX from its right-click menu, FEEL by Enter over it.
fn family_geometry() -> String {
    let state = PanelState::new(Instant::now());
    // The bottom row's bare left: a press there acts on nothing.
    let quiet = (20.0, layout::BOTTOM.y + layout::BOTTOM.h * 0.5);
    assert!(layout::target_at(state.view, quiet.0, quiet.1).is_none(), "the quiet point is on a control");
    let name = |id: usize| p::SPECS[id].name;
    let controls: Vec<String> = layout::WIDGETS
        .iter()
        .filter(|w| w.is_value())
        .map(|w| {
            let r = w.rect();
            // A stepped knob's check drag must cross a step on the knob
            // curve: 1.4 steps of the 700 px a slow drag takes.
            let spec = &p::SPECS[w.id()];
            let drag_px = match w.kind {
                layout::Kind::Stepped => format!(r#", "drag_px": {}"#, (700.0 / (spec.max - spec.min) * 1.4).round()),
                _ => String::new(),
            };
            format!(
                r#"{{"id": {}, "name": "{}", "rect": [{}, {}, {}, {}], "drag": "vertical"{drag_px}, "release": "grab", "wheel": true, "reset": "double-click"}}"#,
                w.id(), name(w.id()), r.x, r.y, r.w, r.h
            )
        })
        .collect();
    let entry = |id: usize, open: &str, text: &str| {
        let at = layout::WIDGETS.iter().find(|w| w.id() == id).expect("a widget").at;
        let expect = p::SPECS[id].parse(text).expect("the probe's text parses");
        format!(
            r#"{{"id": {id}, "name": "{}", "at": [{}, {}], "open": {open}, "type": "{text}", "expect": {expect}}}"#,
            name(id), at.0, at.1
        )
    };
    format!(
        r#"{{"schema": "family-probe/1", "view_class": "OpenPitchQuant", "canvas": {{"w": {}, "h": {}}}, "quiet": [{}, {}],
 "controls": [
  {}],
 "lists": [],
 "entries": [
  {},
  {}]}}"#,
        opq_panel::WIDTH,
        opq_panel::HEIGHT,
        quiet.0,
        quiet.1,
        controls.join(",\n  "),
        entry(p::MIX, r#"["right-click", "enter"]"#, "50"),
        entry(p::FEEL, r#"["hover", "enter"]"#, "40"),
    )
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--geometry") {
        println!("{}", family_geometry());
        return;
    }
    let mut out = PathBuf::from("../out/panel");
    let mut scale = 2;
    let mut names = Vec::new();
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--out" => {
                out = PathBuf::from(&args[i + 1]);
                i += 1;
            }
            "--scale" => {
                scale = args[i + 1].parse().expect("--scale N");
                i += 1;
            }
            name => names.push(name.to_owned()),
        }
        i += 1;
    }
    if names.is_empty() {
        names = SCENARIOS.iter().map(|s| s.to_string()).collect();
    }
    std::fs::create_dir_all(&out).expect("out dir");
    let gpu = Gpu::new().expect("gpu");
    let mut board = Board::new(gpu, &pack::embedded(), scale).expect("board");
    for name in names {
        let state = scenario(&name);
        board.render(&state).expect("render");
        let path = out.join(format!("{name}.png"));
        board.save_png(&path).expect("png");
        println!("{} ({} frames, {} vertices)", path.display(), state.history.len(), board.vertex_count());
    }
}
