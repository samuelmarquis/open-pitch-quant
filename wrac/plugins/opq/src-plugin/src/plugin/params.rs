//! The host's view of the engine's schema (`rt/engine/src/params.rs`).
//! Every id is listed at its own index; the listing, values, events and
//! text are wrac_shell's `HostParams` over SharedState, and this is
//! OpenPitchQuant's flag policy: every parameter automatable, Bypass the
//! host's bypass, labelled choices enums.

use opq_engine::params::{self, PARAM_COUNT, ParamSchema, ParameterBatch, SPECS};
use pluginkit::param::{ParamSpec, Text};
use wrac_clap_adapter::{ParamFlags, PluginError, PluginResult};
use wrac_shell::{HostParams, ParamsTarget, stepped_flags};

use crate::state::SharedState;

pub(crate) type OpqParams = HostParams<SharedState, ParamSchema, PARAM_COUNT>;

impl ParamsTarget<ParamSchema, PARAM_COUNT> for SharedState {
    fn value(&self, id: usize) -> f32 {
        SharedState::value(self, id)
    }

    fn flush_batch(&self, batch: ParameterBatch) -> PluginResult<()> {
        self.sync
            .flush_batch(batch)
            .map_err(|_| PluginError::InvalidState)
    }

    fn flags(&self, spec: &ParamSpec) -> ParamFlags {
        ParamFlags {
            is_bypass: spec.id == params::BYPASS,
            is_automatable: true,
            // Voices is stepped but a count, not a list of names.
            is_enum: matches!(spec.text, Text::Labels(_)),
            ..stepped_flags(spec)
        }
    }
}

// The panel's names for the ids it draws (the board predates the schema).
pub(crate) const PARAM_BYPASS_ID: u32 = params::BYPASS as u32;
pub(crate) const PARAM_MIX_ID: u32 = params::MIX as u32;
pub(crate) const PARAM_FEEL_ID: u32 = params::FEEL as u32;
pub(crate) const PARAM_GLIDE_ID: u32 = params::GLIDE as u32;
pub(crate) const PARAM_GRIT_ID: u32 = params::GRIT as u32;
pub(crate) const PARAM_VOICES_ID: u32 = params::VOICES as u32;
pub(crate) const PARAM_UNOWNED_ID: u32 = params::UNOWNED as u32;
pub(crate) const PARAM_GATE_ID: u32 = params::GATE as u32;
pub(crate) const PARAM_GATE_MODE_ID: u32 = params::GATE_MODE as u32;
pub(crate) const PARAM_FMAX_ID: u32 = params::FMAX as u32;
pub(crate) const PARAM_TRANSIENT_ID: u32 = params::TRANSIENT as u32;
pub(crate) const PARAM_SCOPE_ID: u32 = params::SCOPE as u32;
pub(crate) const PARAM_ROUNDING_ID: u32 = params::ROUNDING as u32;
pub(crate) const PARAM_COHERENCE_ID: u32 = params::COHERENCE as u32;
pub(crate) const PARAM_THRESHOLD_ID: u32 = params::THRESHOLD as u32;
pub(crate) const PARAM_FORMANT_ID: u32 = params::FORMANT as u32;
pub(crate) const PARAM_CARRY_ID: u32 = params::CARRY as u32;
pub(crate) const PARAM_TRANSITIONS_ID: u32 = params::TRANSITIONS as u32;

/// Panel helpers: the board draws fittings from the same rows the host sees.
#[cfg(any(target_os = "macos", target_os = "windows"))]
pub(crate) fn param_value_text(id: u32, value: f64) -> String {
    SPECS.get(id as usize).map(|s| s.format(value as f32)).unwrap_or_default()
}

#[cfg(any(target_os = "macos", target_os = "windows"))]
pub(crate) fn param_minmax(id: u32) -> (f32, f32) {
    SPECS.get(id as usize).map(|s| (s.min, s.max)).unwrap_or((0.0, 1.0))
}

#[cfg(test)]
pub(crate) fn param_default(id: u32) -> f32 {
    SPECS.get(id as usize).map(|s| s.default).unwrap_or(0.0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use wrac_clap_adapter::PluginParamsExtension;

    #[test]
    fn every_id_is_listed_at_its_index_and_automatable() {
        let ext = OpqParams::new(Arc::new(SharedState::new()));
        assert_eq!(ext.param_count(), 20);
        for i in 0..ext.param_count() {
            let info = ext.param_info(i).unwrap();
            assert_eq!(info.id, i);
            assert!(info.flags.is_automatable && !info.flags.is_hidden, "{}", info.name);
        }
        assert!(ext.param_info(20).is_none());
        assert!(ext.param_value(20).is_err());
        let bypass = ext.param_info(PARAM_BYPASS_ID).unwrap().flags;
        assert!(bypass.is_bypass && bypass.is_enum);
        let voices = ext.param_info(PARAM_VOICES_ID).unwrap().flags;
        assert!(voices.is_stepped && !voices.is_enum);
        let algorithm = ext.param_info(params::ALGORITHM as u32).unwrap();
        assert_eq!(algorithm.name, "Algorithm");
        assert!(algorithm.flags.is_enum);
    }

    #[test]
    fn text_round_trips() {
        let ext = OpqParams::new(Arc::new(SharedState::new()));
        let algorithm = params::ALGORITHM as u32;
        assert_eq!(ext.value_to_text(algorithm, 1.0).unwrap(), "Oracle");
        assert_eq!(ext.text_to_value(algorithm, "House").unwrap(), 0.0);
        assert_eq!(ext.value_to_text(PARAM_GLIDE_ID, 0.12).unwrap(), "120 ms");
        let purify = params::PURIFY as u32;
        assert!((ext.text_to_value(purify, "40%").unwrap() - 0.4).abs() < 1e-6);
    }
}
