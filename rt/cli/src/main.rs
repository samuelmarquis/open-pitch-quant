//! Offline parity harness: WAV in → engine → WAV out (channel count
//! preserved; stereo runs the native multichannel engine with shared
//! decisions and image-preserving synthesis).
//!
//!   opq in.wav out.wav --notes C4,E4,G4 [--feel 0.35] [--glide 0.06]
//!       [--grit 0] [--voices 6] [--unowned dry|map] [--gate 2.5]
//!       [--gate-mode fresh|bypass] [--mode repeat|custom]
//!       [--rounding nearest|intelligent] [--fmax 5000] [--no-transient]
//!       [--coherence 1.0]
//!
//! Output is latency-compensated (N_FFT samples trimmed).

use opq_engine::{Engine, EngineParams, Mode, Rounding, TonalityMode, Unowned, N_FFT};

fn die(msg: &str) -> ! {
    eprintln!("error: {msg}");
    std::process::exit(1)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() < 2 {
        die("usage: opq in.wav out.wav --notes C4,E4,G4 [options]");
    }
    let in_path = &args[0];
    let out_path = &args[1];
    let mut p = EngineParams {
        feel: 0.0,
        glide: 0.0,
        rounding: Rounding::Nearest,
        ..EngineParams::default()
    };
    let mut held = [false; 128];
    let mut i = 2;
    while i < args.len() {
        let key = args[i].as_str();
        let mut val = || {
            i += 1;
            args.get(i).unwrap_or_else(|| die("missing value")).clone()
        };
        match key {
            "--notes" => {
                for n in val().split(',') {
                    match opq_engine::parse_note(n) {
                        Some(nn) => held[nn as usize] = true,
                        None => die("bad note name"),
                    }
                }
            }
            "--feel" => p.feel = val().parse().unwrap_or_else(|_| die("bad --feel")),
            "--glide" => p.glide = val().parse().unwrap_or_else(|_| die("bad --glide")),
            "--grit" => p.grit = val().parse().unwrap_or_else(|_| die("bad --grit")),
            "--voices" => p.voices = val().parse().unwrap_or_else(|_| die("bad --voices")),
            "--gate" => p.tonality_gate = val().parse().unwrap_or_else(|_| die("bad --gate")),
            "--fmax" => p.fmax_map = val().parse().unwrap_or_else(|_| die("bad --fmax")),
            "--coherence" => {
                p.coherence = val().parse().unwrap_or_else(|_| die("bad --coherence"))
            }
            "--unowned" => {
                p.unowned = match val().as_str() {
                    "dry" => Unowned::Dry,
                    "map" => Unowned::Map,
                    _ => die("bad --unowned"),
                }
            }
            "--gate-mode" => {
                p.tonality_mode = match val().as_str() {
                    "fresh" => TonalityMode::Fresh,
                    "bypass" => TonalityMode::Bypass,
                    _ => die("bad --gate-mode"),
                }
            }
            "--mode" => {
                p.mode = match val().as_str() {
                    "repeat" => Mode::Repeat,
                    "custom" => Mode::Custom,
                    _ => die("bad --mode"),
                }
            }
            "--rounding" => {
                p.rounding = match val().as_str() {
                    "nearest" => Rounding::Nearest,
                    "intelligent" => Rounding::Intelligent,
                    _ => die("bad --rounding"),
                }
            }
            "--no-transient" => p.transient_bypass = false,
            _ => die(&format!("unknown arg {key}")),
        }
        i += 1;
    }

    let mut reader = hound::WavReader::open(in_path).unwrap_or_else(|e| die(&e.to_string()));
    let spec = reader.spec();
    let ch = (spec.channels as usize).min(2);
    let interleaved: Vec<f32> = match spec.sample_format {
        hound::SampleFormat::Float => reader.samples::<f32>().map(|s| s.unwrap()).collect(),
        hound::SampleFormat::Int => {
            let scale = 1.0 / (1i64 << (spec.bits_per_sample - 1)) as f32;
            reader
                .samples::<i32>()
                .map(|s| s.unwrap() as f32 * scale)
                .collect()
        }
    };
    let n_frames = interleaved.len() / spec.channels as usize;
    // deinterleave (first `ch` channels), plus N_FFT zero tail to flush
    let mut chans: Vec<Vec<f32>> = (0..ch)
        .map(|c| {
            let mut v: Vec<f32> = (0..n_frames)
                .map(|f| interleaved[f * spec.channels as usize + c])
                .collect();
            v.extend(std::iter::repeat(0.0).take(N_FFT));
            v
        })
        .collect();

    let mut engine = Engine::new(spec.sample_rate as f64, ch);
    {
        let mut slices: Vec<&mut [f32]> = chans.iter_mut().map(|v| v.as_mut_slice()).collect();
        engine.process_block(&mut slices, &held, &p);
    }

    let wspec = hound::WavSpec {
        channels: ch as u16,
        sample_rate: spec.sample_rate,
        bits_per_sample: 24,
        sample_format: hound::SampleFormat::Int,
    };
    let mut peak = 0.0f32;
    for c in &chans {
        for &s in &c[N_FFT..N_FFT + n_frames] {
            peak = peak.max(s.abs());
        }
    }
    let g = if peak > 0.99 { 0.99 / peak } else { 1.0 };
    let mut writer =
        hound::WavWriter::create(out_path, wspec).unwrap_or_else(|e| die(&e.to_string()));
    for f in 0..n_frames {
        for c in 0..ch {
            let v = (chans[c][N_FFT + f] * g * 8_388_607.0) as i32;
            writer.write_sample(v).unwrap();
        }
    }
    writer.finalize().unwrap();
    println!(
        "wrote {out_path} ({:.2}s @ {} Hz, {}ch)",
        n_frames as f64 / spec.sample_rate as f64,
        spec.sample_rate,
        ch
    );
}
