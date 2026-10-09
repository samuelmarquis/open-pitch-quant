//! The audio-thread processor: drives `opq_engine::Engine`.
//!
//! Events (MIDI notes + parameter changes) are applied at block granularity —
//! the engine's internal frame is 1024 samples, so sub-block precision would
//! be lost anyway. Note events maintain the held-note set that defines the
//! target pitch grid (PITCHMAP "MIDI MAP" semantics; empty set = silence).
//!
//! Parameters are pluginkit's audio-side copy: queued edits and restores
//! land at the block boundary, the block's host events as one batch, and the
//! set audio plays is reported back after the block.

use std::any::Any;
use std::sync::Arc;

use opq_engine::Engine;
use opq_engine::params::ParameterBatch;
use wrac_clap_adapter::{
    AudioPairedChannels, AudioPortChannels, InputEvent, PluginResult, ProcessContext,
    ProcessStatus, Processor,
};
use wrac_shell::audio_io::{Sample, read_block, write_block};

use crate::state::{AudioSync, SharedState};

const MAX_CHANNELS: usize = 2;

pub(crate) struct OpqAudioProcessor {
    shared: Arc<SharedState>,
    sync: AudioSync,
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
        shared.set_engine_info(sample_rate as f32, (opq_engine::N_FFT / 4) as u32);
        Self {
            sync: shared.sync.activate(),
            shared,
            engine: Engine::new(sample_rate, channels),
            held: [false; 128],
            channels,
            max_frames,
            scratch: vec![0.0; channels * max_frames],
        }
    }

    /// The block through the engine, in place on the scratch channels: input
    /// read (silence where the host gives none), processed, written back. A
    /// mono engine feeds every output channel.
    fn run<T: Sample>(
        &mut self,
        channels: AudioPairedChannels<'_, T>,
        frames: usize,
        params: &opq_engine::EngineParams,
    ) {
        let mut channels = channels.into_iter();
        let mut pairs = [channels.next(), channels.next()];
        let (a, b) = self.scratch.split_at_mut(self.max_frames);
        let (a, b) = (&mut a[..frames], &mut b[..frames]);
        read_block(&pairs[0], 0, a);
        if self.channels == 1 {
            self.engine.process_block(&mut [&mut *a], &self.held, params);
            for pair in &mut pairs {
                write_block(pair, 0, a);
            }
        } else {
            read_block(&pairs[1], 0, b);
            self.engine.process_block(&mut [&mut *a, &mut *b], &self.held, params);
            write_block(&mut pairs[0], 0, a);
            write_block(&mut pairs[1], 0, b);
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
        // 1) Queued edits and restores, then this block's events: the
        // held-note set, and the parameter events as one batch.
        self.sync.receive(&self.shared.sync, || {});
        let mut batch: Option<ParameterBatch> = None;
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
                InputEvent::ParamValue(e)
                    if e.note_id == -1 && e.key == -1 && e.channel == -1 && e.port_index == -1 =>
                {
                    batch
                        .get_or_insert_with(ParameterBatch::new)
                        .insert(e.param_id as usize, e.value as f32);
                }
                _ => {}
            }
        }
        if let Some(batch) = batch {
            batch.apply(&mut self.sync.params, |_, _, _| {});
        }
        let params = self.sync.params.engine();

        let frames = (context.frames_count as usize).min(self.max_frames);

        // 2) Read the main pair, run the engine, write the main pair.
        if let Some(mut port) = context.audio.port_pair(0) {
            match port.channels()? {
                AudioPortChannels::F32(chans) => self.run(chans, frames, &params),
                AudioPortChannels::F64(chans) => self.run(chans, frames, &params),
            }
        }

        // 3) Hand this block's analysis frames to the drum (never blocks).
        self.shared
            .publish_viz(std::iter::from_fn(|| self.engine.viz_pop()));

        self.sync.report(&self.shared.sync);
        // The engine has a 4096-sample tail (its latency buffer); keep running.
        Ok(ProcessStatus::Continue)
    }
}

impl Drop for OpqAudioProcessor {
    fn drop(&mut self) {
        self.sync.report(&self.shared.sync);
        self.shared.sync.deactivate();
    }
}
