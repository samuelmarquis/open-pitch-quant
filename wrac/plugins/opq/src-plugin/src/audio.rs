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
        grid: &[bool; 128],
        params: &opq_engine::EngineParams,
    ) {
        let mut channels = channels.into_iter();
        let mut pairs = [channels.next(), channels.next()];
        let (a, b) = self.scratch.split_at_mut(self.max_frames);
        let (a, b) = (&mut a[..frames], &mut b[..frames]);
        read_block(&pairs[0], 0, a);
        if self.channels == 1 {
            self.engine.process_block(&mut [&mut *a], grid, params);
            for pair in &mut pairs {
                write_block(pair, 0, a);
            }
        } else {
            read_block(&pairs[1], 0, b);
            self.engine.process_block(&mut [&mut *a, &mut *b], grid, params);
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

    /// Reset may consume an idle host flush (`receive`) with no block after
    /// it before the host saves: report what audio now holds at once
    /// (OpenCepstrum's rule).
    fn reset(&mut self) {
        self.sync.receive(&self.shared.sync, || {});
        self.sync.report(&self.shared.sync);
    }

    fn process(&mut self, mut context: ProcessContext<'_>) -> PluginResult<ProcessStatus> {
        // 1) Queued edits and restores, then this block's events: the
        // held-note set, and the parameter events as one batch.
        self.sync.receive(&self.shared.sync, || {});
        let mut batch: Option<ParameterBatch> = None;
        for event in context.events.input.iter() {
            self.event(event, &mut batch);
        }
        if let Some(batch) = batch {
            batch.apply(&mut self.sync.params, |_, _, _| {});
        }
        let mut params = self.sync.params.engine();
        params.house_feel = self.shared.house_feel();
        // The grid: the panel's keys (and their Bypass) under the Keys
        // source, else the notes held on the MIDI side chain.
        let grid = if self.sync.params.keys_source() {
            let keys = self.shared.keys();
            params.bypass_keys = keys.bypass;
            // The Key Transform's map, when it asks for more than the
            // nearest target (no allocation: a few loops over 12 and 128).
            params.remap = keys.remap();
            keys.held()
        } else {
            self.held
        };

        let frames = (context.frames_count as usize).min(self.max_frames);

        // 2) Read the main pair, run the engine, write the main pair. The
        // block's parameters are reported whatever the buffers did.
        let ran = match context.audio.port_pair(0) {
            Some(mut port) => port.channels().map(|channels| match channels {
                AudioPortChannels::F32(chans) => self.run(chans, frames, &grid, &params),
                AudioPortChannels::F64(chans) => self.run(chans, frames, &grid, &params),
            }),
            None => Ok(()),
        };

        // 3) Hand this block's analysis frames to the drum (never blocks).
        self.shared
            .publish_viz(std::iter::from_fn(|| self.engine.viz_pop()));

        self.sync.report(&self.shared.sync);
        ran?;
        // The engine has a 4096-sample tail (its latency buffer); keep running.
        Ok(ProcessStatus::Continue)
    }
}

impl OpqAudioProcessor {
    /// One input event: a note into the held set, a global parameter value
    /// into this block's batch.
    fn event(&mut self, event: InputEvent, batch: &mut Option<ParameterBatch>) {
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
}

impl Drop for OpqAudioProcessor {
    fn drop(&mut self) {
        self.sync.report(&self.shared.sync);
        self.shared.sync.deactivate();
    }
}

/// Every way a host's value reaches the plugin must reach the saved state
/// (Live on sam-pc, 0.2.1 check F: edits made while the device was off
/// were missing from the saved state).
#[cfg(test)]
mod tests {
    use super::*;
    use opq_engine::params::{ALGORITHM, FEEL, PURIFY, Params};
    use wrac_clap_adapter::ParamValueEvent;

    fn automation(id: usize, value: f64) -> InputEvent {
        InputEvent::ParamValue(ParamValueEvent {
            time: 0,
            param_id: id as u32,
            value,
            note_id: -1,
            port_index: -1,
            channel: -1,
            key: -1,
        })
    }

    fn batch(values: &[(usize, f32)]) -> ParameterBatch {
        let mut batch = ParameterBatch::new();
        for &(id, value) in values {
            batch.insert(id, value);
        }
        batch
    }

    /// A process call with no ports (a supported silent host path).
    fn silent_block(audio: &mut OpqAudioProcessor) {
        let context = unsafe { wrac_clap_adapter::__private::process_context_from_raw(&[], &mut [], 256) }.unwrap();
        audio.process(context).unwrap();
    }

    fn running(shared: &Arc<SharedState>) -> OpqAudioProcessor {
        let mut audio = OpqAudioProcessor::new(shared.clone(), 2, 48_000.0, 512);
        silent_block(&mut audio);
        audio
    }

    fn saved(shared: &SharedState) -> [f32; opq_engine::params::PARAM_COUNT] {
        shared.values()
    }

    #[test]
    fn automation_in_a_block_reaches_the_saved_state() {
        let shared = Arc::new(SharedState::new());
        let mut audio = running(&shared);
        let mut b = None;
        audio.event(automation(ALGORITHM, 1.0), &mut b);
        audio.event(automation(PURIFY, 0.75), &mut b);
        b.unwrap().apply(&mut audio.sync.params, |_, _, _| {});
        audio.sync.report(&shared.sync);
        let s = saved(&shared);
        assert_eq!((s[ALGORITHM], s[PURIFY]), (1.0, 0.75));
    }

    #[test]
    fn a_flush_while_the_host_has_stopped_processing_is_saved() {
        let shared = Arc::new(SharedState::new());
        let _audio = running(&shared);
        // The device is off: active, no more process calls.
        shared.sync.flush_batch(batch(&[(ALGORITHM, 1.0), (PURIFY, 0.78)])).unwrap();
        let s = saved(&shared);
        assert_eq!((s[ALGORITHM], s[PURIFY]), (1.0, 0.78));
    }

    #[test]
    fn a_flush_that_reset_consumes_is_saved_without_another_block() {
        let shared = Arc::new(SharedState::new());
        let mut audio = running(&shared);
        shared.sync.flush_batch(batch(&[(PURIFY, 0.5)])).unwrap();
        audio.reset();
        assert_eq!(saved(&shared)[PURIFY], 0.5);
    }

    #[test]
    fn a_flush_audio_consumes_in_a_block_is_saved() {
        let shared = Arc::new(SharedState::new());
        let mut audio = running(&shared);
        shared.sync.flush_batch(batch(&[(PURIFY, 0.6)])).unwrap();
        silent_block(&mut audio);
        assert_eq!(saved(&shared)[PURIFY], 0.6);
    }

    /// An editor edit queued while the host stopped processing, then a host
    /// value for another lane once it resumes: both are saved.
    #[test]
    fn an_editor_edit_and_resumed_automation_are_both_saved() {
        let shared = Arc::new(SharedState::new());
        let mut audio = running(&shared);
        shared.set_batch(&batch(&[(FEEL, 0.9)]));
        shared.sync.flush_batch(batch(&[(ALGORITHM, 1.0)])).unwrap();
        let mut b = None;
        silent_block(&mut audio);
        audio.event(automation(PURIFY, 0.25), &mut b);
        b.unwrap().apply(&mut audio.sync.params, |_, _, _| {});
        audio.sync.report(&shared.sync);
        let s = saved(&shared);
        assert_eq!((s[FEEL], s[ALGORITHM], s[PURIFY]), (0.9, 1.0, 0.25));
    }

    /// A state loaded before activation, then values edited with the device
    /// off and the editor closed, then the device back on: the save holds
    /// the edits, not the load.
    #[test]
    fn edits_after_a_load_outlive_the_load() {
        let shared = Arc::new(SharedState::new());
        let mut loaded = Params::default();
        loaded.set(ALGORITHM, 1.0);
        loaded.set(PURIFY, 0.38);
        shared.sync.restore(loaded);
        let mut audio = running(&shared);
        shared.sync.flush_batch(batch(&[(ALGORITHM, 0.0), (PURIFY, 0.78)])).unwrap();
        silent_block(&mut audio);
        silent_block(&mut audio);
        let s = saved(&shared);
        assert_eq!((s[ALGORITHM], s[PURIFY]), (0.0, 0.78));
        drop(audio);
        let s = saved(&shared);
        assert_eq!((s[ALGORITHM], s[PURIFY]), (0.0, 0.78));
    }
}
