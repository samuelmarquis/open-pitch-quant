//! The audio-thread processor: drives `opq_engine::Engine`.
//!
//! Events (MIDI notes + parameter changes) are applied at block granularity —
//! the engine's internal frame is 1024 samples, so sub-block precision would
//! be lost anyway. Note events maintain the held-note set that defines the
//! target pitch grid (PITCHMAP "MIDI MAP" semantics; empty set = silence).

use std::any::Any;
use std::sync::Arc;

use opq_engine::Engine;
use wrac_clap_adapter::{
    AudioPortChannels, InputEvent, PluginResult, ProcessContext, ProcessStatus, Processor,
};

use crate::state::SharedState;

const MAX_CHANNELS: usize = 2;

pub(crate) struct OpqAudioProcessor {
    shared: Arc<SharedState>,
    engine: Engine,
    held: [bool; 128],
    channels: usize,
    max_frames: usize,
    /// Flat scratch: `channels * max_frames`, split per channel each block.
    scratch: Vec<f32>,
}

impl OpqAudioProcessor {
    pub(crate) fn new(
        shared: Arc<SharedState>,
        channels: u32,
        sample_rate: f64,
        max_frames: u32,
    ) -> Self {
        let channels = (channels as usize).clamp(1, MAX_CHANNELS);
        let max_frames = max_frames as usize;
        Self {
            shared,
            engine: Engine::new(sample_rate, channels),
            held: [false; 128],
            channels,
            max_frames,
            scratch: vec![0.0; channels * max_frames],
        }
    }

    fn note_on(&mut self, key: i16) {
        if (0..128).contains(&key) {
            self.held[key as usize] = true;
        }
    }

    fn note_off(&mut self, key: i16) {
        if (0..128).contains(&key) {
            self.held[key as usize] = false;
        } else if key < 0 {
            // CLAP wildcard: -1 addresses all keys
            self.held = [false; 128];
        }
    }
}

impl Processor for OpqAudioProcessor {
    fn into_any(self: Box<Self>) -> Box<dyn Any + Send> {
        self
    }

    fn process(&mut self, mut context: ProcessContext<'_>) -> PluginResult<ProcessStatus> {
        // 1) Drain this block's events into held-note set + shared params.
        for event in context.events.input.iter() {
            match event {
                InputEvent::NoteOn(e) => self.note_on(e.key),
                InputEvent::NoteOff(e) | InputEvent::NoteChoke(e) => self.note_off(e.key),
                InputEvent::Midi(e) => {
                    let status = e.data[0] & 0xF0;
                    let key = e.data[1] as i16;
                    if status == 0x90 && e.data[2] > 0 {
                        self.note_on(key);
                    } else if status == 0x80 || (status == 0x90 && e.data[2] == 0) {
                        self.note_off(key);
                    }
                }
                InputEvent::ParamValue(e) => {
                    let _ = self.shared.set_parameter_value(e.param_id, e.value);
                }
                _ => {}
            }
        }
        let params = self.shared.engine_params();

        let frames = (context.frames_count as usize).min(self.max_frames);

        // 2) Copy input into per-channel scratch.
        {
            let Some(mut port) = context.audio.port_pair(0) else {
                return Ok(ProcessStatus::Continue);
            };
            match port.channels()? {
                AudioPortChannels::F32(mut chans) => {
                    for ci in 0..self.channels {
                        let dst = &mut self.scratch[ci * self.max_frames..][..frames];
                        if let Some(mut pair) = chans.channel_pair(ci) {
                            if let Some(input) = pair.input() {
                                dst.copy_from_slice(&input[..frames]);
                            }
                        }
                    }
                }
                AudioPortChannels::F64(mut chans) => {
                    for ci in 0..self.channels {
                        let dst = &mut self.scratch[ci * self.max_frames..][..frames];
                        if let Some(mut pair) = chans.channel_pair(ci) {
                            if let Some(input) = pair.input() {
                                for (d, s) in dst.iter_mut().zip(input[..frames].iter()) {
                                    *d = *s as f32;
                                }
                            }
                        }
                    }
                }
            }
        }

        // 3) Run the engine in place on the scratch channels.
        {
            let (a, b) = self.scratch.split_at_mut(self.max_frames);
            if self.channels == 1 {
                let mut io: [&mut [f32]; 1] = [&mut a[..frames]];
                self.engine.process_block(&mut io, &self.held, &params);
            } else {
                let mut io: [&mut [f32]; 2] = [&mut a[..frames], &mut b[..frames]];
                self.engine.process_block(&mut io, &self.held, &params);
            }
        }

        // 4) Copy scratch to the output channels.
        {
            let Some(mut port) = context.audio.port_pair(0) else {
                return Ok(ProcessStatus::Continue);
            };
            match port.channels()? {
                AudioPortChannels::F32(mut chans) => {
                    for ci in 0..chans.channel_pair_count() {
                        let src = &self.scratch[(ci.min(self.channels - 1)) * self.max_frames..]
                            [..frames];
                        if let Some(mut pair) = chans.channel_pair(ci) {
                            if let Some(output) = pair.output_mut() {
                                output[..frames].copy_from_slice(src);
                            }
                        }
                    }
                }
                AudioPortChannels::F64(mut chans) => {
                    for ci in 0..chans.channel_pair_count() {
                        let src = &self.scratch[(ci.min(self.channels - 1)) * self.max_frames..]
                            [..frames];
                        if let Some(mut pair) = chans.channel_pair(ci) {
                            if let Some(output) = pair.output_mut() {
                                for (d, s) in output[..frames].iter_mut().zip(src.iter()) {
                                    *d = *s as f64;
                                }
                            }
                        }
                    }
                }
            }
        }

        // The engine has a 4096-sample tail (its latency buffer); keep running.
        Ok(ProcessStatus::Continue)
    }
}
