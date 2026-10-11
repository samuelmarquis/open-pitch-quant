//! The engine's audio path never allocates or frees once built: every
//! algorithm and the parameter paths that switch code on, stereo, across
//! many hops, a chord change and a reset.

use opq_engine::params::Params;
use opq_engine::{Algorithm, Engine, EngineParams};
use pluginkit::testing::{assert_no_alloc, CountingAllocator};

#[global_allocator]
static ALLOCATOR: CountingAllocator = CountingAllocator;

fn chord(notes: &[usize]) -> [bool; 128] {
    let mut held = [false; 128];
    for &n in notes {
        held[n] = true;
    }
    held
}

/// A few harmonic voices plus a click every so often (onsets, transients).
fn fill(block: &mut [Vec<f32>], start: usize) {
    for (c, ch) in block.iter_mut().enumerate() {
        for (i, x) in ch.iter_mut().enumerate() {
            let t = (start + i) as f32 / 48000.0;
            let mut y = 0.0;
            for (f0, a) in [(196.0, 0.3), (247.0, 0.2), (311.0, 0.15)] {
                for h in 1..6 {
                    y += a / h as f32 * (std::f32::consts::TAU * f0 * h as f32 * t + c as f32).sin();
                }
            }
            if (start + i) % 12000 < 40 {
                y += 0.8;
            }
            *x = y;
        }
    }
}

#[test]
fn process_block_does_not_allocate() {
    let base = Params::default().engine();
    let mut variants = vec![base];
    let mut oracle = base;
    oracle.algorithm = Algorithm::Oracle;
    variants.push(oracle);
    let mut busy = base;
    busy.purify = 0.6;
    busy.grit = 0.3;
    busy.formant = 1.0;
    busy.threshold_cents = 20.0;
    busy.bypass_keys = 1 << 60;
    busy.voices = 12;
    variants.push(busy);
    // The Key Transform's remap (C major to F minor), with unowned peaks
    // mapped too, under both roundings.
    let mut keys = opq_engine::params::Keys::default();
    keys.transform = opq_engine::scales::KeyTransform { src_key: 0, src_scale: 1, dst_key: 5 };
    keys.set_dst_scale(2);
    let mut mapped = base;
    mapped.remap = keys.remap();
    assert!(mapped.remap.is_some());
    mapped.unowned = opq_engine::Unowned::Map;
    variants.push(mapped);
    mapped.rounding = opq_engine::Rounding::Nearest;
    variants.push(mapped);

    for p in variants {
        let p: EngineParams = p;
        let mut engine = Engine::new(48000.0, 2);
        let mut block = vec![vec![0.0f32; 512]; 2];
        let chords = [chord(&[60, 64, 67]), chord(&[62, 65, 69, 72]), chord(&[])];
        // Warm up outside the count: first frames take the reset paths.
        let mut at = 0;
        for _ in 0..40 {
            fill(&mut block, at);
            let mut io: Vec<&mut [f32]> = block.iter_mut().map(|c| c.as_mut_slice()).collect();
            engine.process_block(&mut io, &chords[0], &p);
            at += 512;
        }
        for (round, held) in chords.iter().enumerate() {
            fill(&mut block, at);
            let (left, right) = block.split_at_mut(1);
            let mut io = [left[0].as_mut_slice(), right[0].as_mut_slice()];
            assert_no_alloc(|| {
                for _ in 0..30 {
                    engine.process_block(&mut io, held, &p);
                    while engine.viz_pop().is_some() {}
                }
                if round == 2 {
                    engine.reset();
                }
            });
            at += 30 * 512;
        }
    }
}
