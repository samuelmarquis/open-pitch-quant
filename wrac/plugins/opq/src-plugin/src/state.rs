//! State shared by the host callbacks, the audio thread and the editor:
//! the parameter set, plus the analysis feed for the drum.
//!
//! Parameters are pluginkit's sync over the engine's schema
//! (`opq_engine::params`): the control side owns the coherent set, edits
//! reach audio as bounded fixed-size commands, and audio reports back what
//! it plays. Nothing on the audio side allocates, locks or waits.
//!
//! The viz queue hands [`VizFrame`]s from the audio thread to the GUI timer.
//! The audio side only ever `try_lock`s — under contention it drops that
//! block's frames (a skipped drum column, never a glitch).

use std::collections::VecDeque;
use std::sync::atomic::{AtomicU8, AtomicU32, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use opq_engine::{HouseFeel, VizFrame};
use opq_engine::params::{Keys, PARAM_COUNT, ParamSchema, ParameterBatch, Params};
use opq_engine::scales::KeyTransform;
use pluginkit::sync::{AudioParams, ParamSync};
use wrac_clap_adapter::HostStateDirtyNotifier;

pub(crate) type Sync = ParamSync<ParamSchema, PARAM_COUNT>;
pub(crate) type AudioSync = AudioParams<ParamSchema, PARAM_COUNT>;

/// Frames buffered between GUI drains (~1.5 s at typical hop rates).
const VIZ_QUEUE: usize = 64;

pub(crate) struct SharedState {
    pub(crate) sync: Sync,
    viz: Mutex<VecDeque<VizFrame>>,
    /// Sample rate bits + hop, published by the processor for panel captions.
    sr_bits: AtomicU32,
    hop: AtomicU32,
    /// The Keys source's key states (product state, not parameters): the
    /// target and bypass masks as low/high halves. The editor writes them,
    /// audio reads them each block; a torn read between halves lasts one
    /// block at most. The fifth word is the Key Transform, a byte each for
    /// its source key, source scale and destination key.
    keys: [AtomicU64; 5],
    /// HOUSE's Feel law on audition (product state): its index.
    house_feel: AtomicU8,
    /// Tells the host its saved state changed when the keys do.
    dirty: Option<Arc<dyn HostStateDirtyNotifier>>,
}

impl SharedState {
    #[cfg(test)]
    pub(crate) fn new() -> Self {
        Self::with_host(None)
    }

    pub(crate) fn with_host(dirty: Option<Arc<dyn HostStateDirtyNotifier>>) -> Self {
        let keys = Keys::default();
        let words = split(keys);
        Self {
            sync: Sync::new(Params::default()),
            viz: Mutex::new(VecDeque::with_capacity(VIZ_QUEUE)),
            sr_bits: AtomicU32::new(0),
            hop: AtomicU32::new(0),
            keys: words.map(AtomicU64::new),
            house_feel: AtomicU8::new(0),
            dirty,
        }
    }

    /// The key states.
    pub(crate) fn keys(&self) -> Keys {
        let w = |i: usize| self.keys[i].load(Ordering::Relaxed) as u128;
        let t = w(4);
        let transform =
            KeyTransform { src_key: t as u8, src_scale: (t >> 8) as u8, dst_key: (t >> 16) as u8 }.sanitised();
        Keys { target: w(0) | w(1) << 64, bypass: w(2) | w(3) << 64, transform }
    }

    /// Replace the key states. An editor edit (`edited`) tells the host
    /// its state changed (main thread); a load does not.
    pub(crate) fn set_keys(&self, keys: Keys, edited: bool) {
        for (slot, word) in self.keys.iter().zip(split(keys)) {
            slot.store(word, Ordering::Relaxed);
        }
        if edited && let Some(dirty) = &self.dirty {
            dirty.mark_dirty();
        }
    }

    /// HOUSE's Feel law on audition.
    pub(crate) fn house_feel(&self) -> HouseFeel {
        HouseFeel::from_index(self.house_feel.load(Ordering::Relaxed))
    }

    /// Replace it; an editor edit (`edited`) tells the host, as for keys.
    pub(crate) fn set_house_feel(&self, feel: HouseFeel, edited: bool) {
        self.house_feel.store(feel.index(), Ordering::Relaxed);
        if edited && let Some(dirty) = &self.dirty {
            dirty.mark_dirty();
        }
    }

    pub(crate) fn set_engine_info(&self, sr: f32, hop: u32) {
        self.sr_bits.store(sr.to_bits(), Ordering::Relaxed);
        self.hop.store(hop, Ordering::Relaxed);
    }

    /// (sample rate, hop); defaults before the first processor exists.
    #[cfg_attr(not(any(target_os = "macos", target_os = "windows")), allow(dead_code))]
    pub(crate) fn engine_info(&self) -> (f32, u32) {
        let sr = f32::from_bits(self.sr_bits.load(Ordering::Relaxed));
        let hop = self.hop.load(Ordering::Relaxed);
        if sr > 0.0 && hop > 0 { (sr, hop) } else { (44100.0, 1024) }
    }

    /// Audio thread: append this block's analysis frames. Never blocks;
    /// frames are dropped wholesale if the GUI holds the lock right now.
    pub(crate) fn publish_viz(&self, frames: impl Iterator<Item = VizFrame>) {
        if let Ok(mut q) = self.viz.try_lock() {
            for fr in frames {
                if q.len() == VIZ_QUEUE {
                    q.pop_front();
                }
                q.push_back(fr);
            }
        }
    }

    /// GUI timer: take everything published since the last drain.
    #[cfg_attr(not(any(target_os = "macos", target_os = "windows")), allow(dead_code))]
    pub(crate) fn drain_viz(&self, into: &mut Vec<VizFrame>) {
        if let Ok(mut q) = self.viz.lock() {
            into.extend(q.drain(..));
        }
    }

    /// The control side's value for `id`.
    pub(crate) fn value(&self, id: usize) -> f32 {
        self.sync.value(id)
    }

    /// The whole set.
    pub(crate) fn values(&self) -> [f32; PARAM_COUNT] {
        self.sync.snapshot().0.values
    }

    /// The coherent set and its restore revision, for the editor: a new
    /// revision means a state load, which ends any gesture in progress.
    #[cfg_attr(not(any(target_os = "macos", target_os = "windows")), allow(dead_code))]
    pub(crate) fn snapshot(&self) -> (Params, u64) {
        self.sync.snapshot()
    }

    /// Commit an editor batch. It always lands, even while the host keeps
    /// the plugin active but stops processing it.
    #[cfg_attr(not(any(target_os = "macos", target_os = "windows")), allow(dead_code))]
    pub(crate) fn set_batch(&self, batch: &ParameterBatch) {
        self.sync.set_batch(batch);
    }
}

/// Key masks and the transform as the five 64-bit words SharedState stores.
fn split(keys: Keys) -> [u64; 5] {
    let t = keys.transform;
    [
        keys.target as u64,
        (keys.target >> 64) as u64,
        keys.bypass as u64,
        (keys.bypass >> 64) as u64,
        t.src_key as u64 | (t.src_scale as u64) << 8 | (t.dst_key as u64) << 16,
    ]
}
