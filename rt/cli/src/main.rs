//! Offline parity harness: WAV in → engine → WAV out (channel count
//! preserved; stereo runs the native multichannel engine with shared
//! decisions and image-preserving synthesis).
//!
//!   opq in.wav out.wav (--notes C4,E4,G4 | --midi part.mid) [--feel 0.35]
//!       [--midi-stretch 1.0] [--glide 0.06] [--grit 0] [--voices 6]
//!       [--unowned dry|map] [--gate 2.5] [--gate-mode fresh|bypass]
//!       [--mode repeat|custom] [--rounding nearest|intelligent]
//!       [--fmax 5000] [--no-transient] [--coherence 1.0]
//!       [--threshold 0] [--formant 0]
//!
//! Output is latency-compensated (N_FFT samples trimmed).

use opq_engine::{
    Algorithm, Engine, EngineParams, Mode, Newborn, Rounding, TonalityMode, Unowned, N_FFT,
};

fn die(msg: &str) -> ! {
    eprintln!("error: {msg}");
    std::process::exit(1)
}

/// MIDI file → [(t_seconds, held[128])] breakpoints, honoring tempo map.
fn midi_breakpoints(path: &str, stretch: f64) -> Vec<(f64, [bool; 128])> {
    let data = std::fs::read(path).unwrap_or_else(|e| die(&e.to_string()));
    let smf = midly::Smf::parse(&data).unwrap_or_else(|e| die(&e.to_string()));
    let ppq = match smf.header.timing {
        midly::Timing::Metrical(n) => n.as_int() as f64,
        _ => die("SMPTE-timed MIDI unsupported"),
    };
    enum Ev {
        Tempo(u32),
        On(u8),
        Off(u8),
    }
    let mut evs: Vec<(u64, Ev)> = Vec::new();
    for track in &smf.tracks {
        let mut tick = 0u64;
        for e in track {
            tick += e.delta.as_int() as u64;
            match e.kind {
                midly::TrackEventKind::Meta(midly::MetaMessage::Tempo(t)) => {
                    evs.push((tick, Ev::Tempo(t.as_int())))
                }
                midly::TrackEventKind::Midi { message, .. } => match message {
                    midly::MidiMessage::NoteOn { key, vel } => {
                        if vel.as_int() > 0 {
                            evs.push((tick, Ev::On(key.as_int())))
                        } else {
                            evs.push((tick, Ev::Off(key.as_int())))
                        }
                    }
                    midly::MidiMessage::NoteOff { key, .. } => {
                        evs.push((tick, Ev::Off(key.as_int())))
                    }
                    _ => {}
                },
                _ => {}
            }
        }
    }
    evs.sort_by_key(|e| e.0);
    let mut out: Vec<(f64, [bool; 128])> = vec![(0.0, [false; 128])];
    let mut held = [false; 128];
    let mut tempo = 500_000f64; // µs per quarter
    let mut last_tick = 0u64;
    let mut t = 0.0f64;
    for (tick, ev) in evs {
        t += (tick - last_tick) as f64 * tempo / (ppq * 1e6);
        last_tick = tick;
        match ev {
            Ev::Tempo(us) => tempo = us as f64,
            Ev::On(n) => {
                held[n as usize] = true;
                out.push((t * stretch, held));
            }
            Ev::Off(n) => {
                held[n as usize] = false;
                out.push((t * stretch, held));
            }
        }
    }
    out
}

type VizDump = Option<(std::io::BufWriter<std::fs::File>, f64, f64)>;

/// Runs a segment through the engine. With a viz dump active, processing is
/// chunked by hop so the 16-frame viz ring never overflows between drains.
fn process_seg(
    engine: &mut Engine,
    slices: &mut [&mut [f32]],
    held: &[bool; 128],
    p: &EngineParams,
    dump: &mut VizDump,
) {
    let Some((file, sr, hop)) = dump else {
        engine.process_block(slices, held, p);
        return;
    };
    use std::io::Write;
    let total = slices[0].len();
    let step = *hop as usize;
    let mut c = 0usize;
    while c < total {
        let end = (c + step).min(total);
        let mut seg: Vec<&mut [f32]> = slices.iter_mut().map(|s| &mut s[c..end]).collect();
        engine.process_block(&mut seg, held, p);
        while let Some(fr) = engine.viz_pop() {
            let mut grid = String::new();
            for n in 0..127usize {
                if fr.grid_mask & (1u128 << n) != 0 {
                    if !grid.is_empty() {
                        grid.push(',');
                    }
                    grid.push_str(&n.to_string());
                }
            }
            let mut tracks = String::new();
            for k in 0..fr.n as usize {
                let tr = &fr.tracks[k];
                if k > 0 {
                    tracks.push(',');
                }
                tracks.push_str(&format!(
                    "{{\"id\":{},\"f0\":{:.2},\"tgt\":{:.2},\"out\":{:.2},\"amp\":{:.4},\"nh\":{},\"hmask\":{},\"spared\":{},\"nb\":{}}}",
                    tr.id, tr.f0, tr.tgt, tr.out, tr.amp, tr.nh, tr.hmask, tr.spared, tr.newborn
                ));
            }
            let bands = fr
                .res_bands
                .iter()
                .map(|b| format!("{b:.2}"))
                .collect::<Vec<_>>()
                .join(",");
            writeln!(
                file,
                "{{\"t\":{},\"time\":{:.4},\"flux\":{:.3},\"transient\":{:.3},\"in\":{:.4},\"res\":{:.4},\"repeat\":{},\"grid\":[{}],\"bands\":[{}],\"tracks\":[{}]}}",
                fr.t,
                fr.t as f64 * *hop / *sr,
                fr.flux.min(99.0),
                fr.transient,
                fr.in_energy,
                fr.res_energy,
                fr.grid_mask & (1u128 << 127) != 0,
                grid,
                bands,
                tracks
            )
            .unwrap_or_else(|e| die(&e.to_string()));
        }
        c = end;
    }
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
    let mut midi_path: Option<String> = None;
    let mut midi_stretch = 1.0f64;
    let mut stereo_out = false; // duplicate mono output to dual-mono stereo
    let mut blocksize = N_FFT; // STFT window; hop = blocksize/4
    let mut viz_dump_path: Option<String> = None; // JSON-lines analysis trace
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
            "--midi" => midi_path = Some(val()),
            "--midi-stretch" => {
                midi_stretch = val().parse().unwrap_or_else(|_| die("bad --midi-stretch"))
            }
            "--threshold" => {
                p.threshold_cents = val().parse().unwrap_or_else(|_| die("bad --threshold"))
            }
            "--formant" => {
                p.formant = val().parse().unwrap_or_else(|_| die("bad --formant"))
            }
            "--carry" => {
                p.carry = val().parse().unwrap_or_else(|_| die("bad --carry"))
            }
            "--newborn" => {
                p.newborn = match val().as_str() {
                    "map" => Newborn::Map,
                    "dry" => Newborn::Dry,
                    _ => die("bad --newborn"),
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
            "--algorithm" => {
                p.algorithm = match val().as_str() {
                    "house" => Algorithm::House,
                    "oracle" => Algorithm::Oracle,
                    _ => die("bad --algorithm (house|oracle)"),
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
            "--stereo-out" => stereo_out = true,
            "--viz-dump" => viz_dump_path = Some(val()),
            "--blocksize" => {
                blocksize = val().parse().unwrap_or_else(|_| die("bad --blocksize"));
                if !blocksize.is_power_of_two() || !(1024..=16384).contains(&blocksize) {
                    die("--blocksize must be a power of two in 1024..=16384");
                }
            }
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
            v.extend(std::iter::repeat(0.0).take(blocksize));
            v
        })
        .collect();

    let mut engine = Engine::new_sized(spec.sample_rate as f64, ch, blocksize, blocksize / 4);
    let mut viz_dump = viz_dump_path.map(|path| {
        (
            std::io::BufWriter::new(
                std::fs::File::create(&path).unwrap_or_else(|e| die(&e.to_string())),
            ),
            spec.sample_rate as f64,
            (blocksize / 4) as f64,
        )
    });
    {
        let mut slices: Vec<&mut [f32]> = chans.iter_mut().map(|v| v.as_mut_slice()).collect();
        match midi_path {
            None => process_seg(&mut engine, &mut slices, &held, &p, &mut viz_dump),
            Some(mp) => {
                // segment the stream at held-set breakpoints
                let bps = midi_breakpoints(&mp, midi_stretch);
                let sr = spec.sample_rate as f64;
                let total = slices[0].len();
                let mut cursor = 0usize;
                for (bi, &(bt, bheld)) in bps.iter().enumerate() {
                    let start = ((bt * sr).round() as usize).min(total).max(cursor);
                    let end = if bi + 1 < bps.len() {
                        (((bps[bi + 1].0) * sr).round() as usize).min(total)
                    } else {
                        total
                    };
                    // fill any gap before this breakpoint with previous state
                    let _ = start;
                    if end > cursor {
                        let mut seg: Vec<&mut [f32]> = slices
                            .iter_mut()
                            .map(|s| &mut s[cursor..end])
                            .collect();
                        process_seg(&mut engine, &mut seg, &bheld, &p, &mut viz_dump);
                        cursor = end;
                    }
                }
                if cursor < total {
                    let last = bps.last().map(|b| b.1).unwrap_or([false; 128]);
                    let mut seg: Vec<&mut [f32]> =
                        slices.iter_mut().map(|s| &mut s[cursor..total]).collect();
                    process_seg(&mut engine, &mut seg, &last, &p, &mut viz_dump);
                }
            }
        }
    }

    let out_ch = if stereo_out && ch == 1 { 2 } else { ch };
    let wspec = hound::WavSpec {
        channels: out_ch as u16,
        sample_rate: spec.sample_rate,
        bits_per_sample: 24,
        sample_format: hound::SampleFormat::Int,
    };
    let mut peak = 0.0f32;
    for c in &chans {
        for &s in &c[blocksize..blocksize + n_frames] {
            peak = peak.max(s.abs());
        }
    }
    let g = if peak > 0.99 { 0.99 / peak } else { 1.0 };
    let mut writer =
        hound::WavWriter::create(out_path, wspec).unwrap_or_else(|e| die(&e.to_string()));
    for f in 0..n_frames {
        for c in 0..out_ch {
            let v = (chans[c.min(ch - 1)][blocksize + f] * g * 8_388_607.0) as i32;
            writer.write_sample(v).unwrap();
        }
    }
    writer.finalize().unwrap();
    println!(
        "wrote {out_path} ({:.2}s @ {} Hz, {}ch)",
        n_frames as f64 / spec.sample_rate as f64,
        spec.sample_rate,
        out_ch
    );
}
