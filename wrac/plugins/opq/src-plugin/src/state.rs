//! Parameter state shared by the audio thread and host, plus the analysis
//! feed for the drum.
//!
//! One atomic per parameter, indexed by the spec table in `plugin/params.rs`.
//! The audio thread reads a full [`opq_engine::EngineParams`] snapshot per
//! block without taking any lock.
//!
//! The viz queue hands [`VizFrame`]s from the audio thread to the GUI timer.
//! The audio side only ever `try_lock`s — under contention it drops that
//! block's frames (a skipped drum column, never a glitch).

use atomic_float::AtomicF32;
use std::collections::VecDeque;
use std::sync::Mutex;
use std::sync::atomic::Ordering;

use opq_engine::{EngineParams, Mode, Newborn, Rounding, TonalityMode, Unowned, VizFrame};

/// Frames buffered between GUI drains (~1.5 s at typical hop rates).
const VIZ_QUEUE: usize = 64;

use crate::plugin::{
    PARAM_BYPASS_ID, PARAM_CARRY_ID, PARAM_COHERENCE_ID, PARAM_FEEL_ID, PARAM_FMAX_ID,
    PARAM_FORMANT_ID, PARAM_GATE_ID, PARAM_GATE_MODE_ID, PARAM_GLIDE_ID, PARAM_GRIT_ID,
    PARAM_MIX_ID, PARAM_ROUNDING_ID, PARAM_SCOPE_ID, PARAM_THRESHOLD_ID, PARAM_TRANSIENT_ID,
    PARAM_TRANSITIONS_ID, PARAM_UNOWNED_ID, PARAM_VOICES_ID, param_clamp, param_default,
    param_exists,
};

pub(crate) const PARAM_SLOTS: usize = 18;

pub(crate) struct SharedState {
    values: [AtomicF32; PARAM_SLOTS],
    viz: Mutex<VecDeque<VizFrame>>,
}

impl SharedState {
    pub(crate) fn new() -> Self {
        let values = std::array::from_fn(|i| AtomicF32::new(param_default(i as u32)));
        Self {
            values,
            viz: Mutex::new(VecDeque::with_capacity(VIZ_QUEUE)),
        }
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
    pub(crate) fn drain_viz(&self, into: &mut Vec<VizFrame>) {
        if let Ok(mut q) = self.viz.lock() {
            into.extend(q.drain(..));
        }
    }

    /// Clamp + store. Returns the applied value, or None for unknown ids.
    pub(crate) fn set_parameter_value(&self, id: u32, plain: f64) -> Option<f32> {
        if !param_exists(id) {
            return None;
        }
        let v = param_clamp(id, plain as f32);
        self.values[id as usize].store(v, Ordering::Relaxed);
        Some(v)
    }

    pub(crate) fn parameter_value(&self, id: u32) -> Option<f32> {
        param_exists(id).then(|| self.values[id as usize].load(Ordering::Relaxed))
    }

    fn v(&self, id: u32) -> f32 {
        self.values[id as usize].load(Ordering::Relaxed)
    }

    pub(crate) fn bypass(&self) -> bool {
        self.v(PARAM_BYPASS_ID) >= 0.5
    }

    /// Snapshot for the audio thread. Bypass is realized as mix=0 because the
    /// engine's dry path is latency-aligned — a click-free, PDC-correct bypass.
    pub(crate) fn engine_params(&self) -> EngineParams {
        let mut p = EngineParams {
            voices: self.v(PARAM_VOICES_ID).round().clamp(1.0, 12.0) as usize,
            unowned: if self.v(PARAM_UNOWNED_ID) >= 0.5 {
                Unowned::Map
            } else {
                Unowned::Dry
            },
            tonality_gate: self.v(PARAM_GATE_ID) as f64,
            tonality_mode: if self.v(PARAM_GATE_MODE_ID) >= 0.5 {
                TonalityMode::Bypass
            } else {
                TonalityMode::Fresh
            },
            fmax_map: self.v(PARAM_FMAX_ID) as f64,
            transient_bypass: self.v(PARAM_TRANSIENT_ID) >= 0.5,
            flux_thresh: 0.6,
            feel: self.v(PARAM_FEEL_ID) as f64,
            glide: self.v(PARAM_GLIDE_ID) as f64,
            grit: self.v(PARAM_GRIT_ID) as f64,
            mode: if self.v(PARAM_SCOPE_ID) >= 0.5 {
                Mode::Custom
            } else {
                Mode::Repeat
            },
            rounding: if self.v(PARAM_ROUNDING_ID) >= 0.5 {
                Rounding::Nearest
            } else {
                Rounding::Intelligent
            },
            hyst_cents: 40.0,
            mix: self.v(PARAM_MIX_ID) as f64,
            coherence: self.v(PARAM_COHERENCE_ID) as f64,
            threshold_cents: self.v(PARAM_THRESHOLD_ID) as f64,
            formant: self.v(PARAM_FORMANT_ID) as f64,
            carry: self.v(PARAM_CARRY_ID) as f64,
            newborn: if self.v(PARAM_TRANSITIONS_ID) >= 0.5 {
                Newborn::Dry
            } else {
                Newborn::Map
            },
        };
        if self.bypass() {
            p.mix = 0.0;
        }
        p
    }
}
