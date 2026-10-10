//! Renders the board offline, for review: the same Board the plugin mounts,
//! fed by the engine itself. The material is synthetic: three harmonic
//! voices (one with vibrato, one gliding a fourth) under a held chord.
//!
//! Usage: panel-render [--out DIR] [--scale N] [SCENARIO...]
//! Scenarios: house, oracle, keys, empty, drag, typing, menu, ladders,
//! scope (default: all).
use opq_engine::params::{self as p, KeyState, Keys, Params};
use opq_engine::Engine;
use opq_panel::layout;
use opq_panel::{pack, Board, Fittings, Modifiers, PanelState};
use panelkit::gpu::Gpu;
use std::f64::consts::TAU;
use std::path::PathBuf;
use std::time::{Duration, Instant};

const SR: f64 = 48_000.0;
const SCENARIOS: [&str; 9] = ["house", "oracle", "keys", "empty", "drag", "typing", "menu", "ladders", "scope"];

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

fn scenario(name: &str) -> PanelState {
    let start = Instant::now();
    let mut state = PanelState::new(start);
    state.version = "(offline render)";
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
            state.keys = Keys { target: 0, bypass: 0 };
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

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
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
