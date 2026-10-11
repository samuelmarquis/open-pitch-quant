//! The Key Transform through the engine: a sung note lands where the map
//! sends its source degree, and with no remap the engine is as it was.

use opq_engine::params::{Keys, Params};
use opq_engine::scales::{KeyTransform, ANY_KEY, SCALES};
use opq_engine::Engine;

const SR: f64 = 48000.0;

fn scale(name: &str) -> usize {
    SCALES.iter().position(|s| s.name == name).unwrap()
}

fn hz(note: f64) -> f64 {
    440.0 * ((note - 69.0) / 12.0).exp2()
}

/// A harmonic voice at `note` through the engine under `keys`; the target
/// (MIDI) its object settles on.
fn settled_target(note: f64, keys: &Keys) -> f64 {
    let mut params = Params::default().engine();
    params.remap = keys.remap();
    let mut engine = Engine::new(SR, 1);
    let held = keys.held();
    let mut block = vec![0.0f32; 512];
    let mut target = None;
    for b in 0..80 {
        for (i, x) in block.iter_mut().enumerate() {
            let t = (b * 512 + i) as f64 / SR;
            *x = (1..6).map(|h| 0.3 / h as f64 * (std::f64::consts::TAU * hz(note) * h as f64 * t).sin()).sum::<f64>() as f32;
        }
        engine.process_block(&mut [block.as_mut_slice()], &held, &params);
        while let Some(frame) = engine.viz_pop() {
            if frame.n > 0 {
                target = Some(frame.tracks[0].tgt as f64);
            }
        }
    }
    69.0 + 12.0 * (target.expect("the voice was tracked") / 440.0).log2()
}

fn near(a: f64, b: f64) -> bool {
    (a - b).abs() < 0.01
}

#[test]
fn a_note_is_sung_where_the_map_sends_its_degree() {
    // C major to C minor: E4 is sung at E flat 4, and C4 stays.
    let mut keys = Keys::default();
    keys.transform = KeyTransform { src_key: 0, src_scale: scale("MAJOR") as u8, dst_key: ANY_KEY };
    keys.set_dst_scale(scale("MINOR"));
    assert!(near(settled_target(64.0, &keys), 63.0));
    assert!(near(settled_target(60.0, &keys), 60.0));
    // A flat E (30 cents under) is still the third degree.
    assert!(near(settled_target(63.7, &keys), 63.0));

    // C major to F major: C4 goes up a fourth, to F4.
    keys.transform.dst_key = 5;
    keys.set_dst_scale(scale("MAJOR"));
    assert!(near(settled_target(60.0, &keys), 65.0));
}

#[test]
fn a_chromatic_source_only_pulls_to_the_nearest_target() {
    // "* CHROMATIC to F MAJOR": F stays, and a pitch between two targets
    // goes to the nearer.
    let mut keys = Keys::default();
    keys.transform.dst_key = 5;
    keys.set_dst_scale(scale("MAJOR"));
    assert_eq!(keys.remap(), None);
    assert!(near(settled_target(65.0, &keys), 65.0));
    assert!(near(settled_target(66.3, &keys), 67.0));
    assert!(near(settled_target(65.7, &keys), 65.0));
}
