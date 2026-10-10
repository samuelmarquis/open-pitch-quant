//! The host's view of the engine's schema (`rt/engine/src/params.rs`).
//! Every id is listed at its own index; the listing, values, events and
//! text are wrac_shell's `HostParams` over SharedState, and this is
//! OpenPitchQuant's flag policy: every parameter automatable, Bypass the
//! host's bypass, labelled choices enums.

use opq_engine::params::{self, PARAM_COUNT, ParamSchema, ParameterBatch};
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use wrac_clap_adapter::PluginParamsExtension;

    #[test]
    fn every_id_is_listed_at_its_index_and_automatable() {
        let ext = OpqParams::new(Arc::new(SharedState::new()));
        assert_eq!(ext.param_count(), 21);
        for i in 0..ext.param_count() {
            let info = ext.param_info(i).unwrap();
            assert_eq!(info.id, i);
            assert!(info.flags.is_automatable && !info.flags.is_hidden, "{}", info.name);
        }
        assert!(ext.param_info(21).is_none());
        assert!(ext.param_value(21).is_err());
        let bypass = ext.param_info(params::BYPASS as u32).unwrap().flags;
        assert!(bypass.is_bypass && bypass.is_enum);
        let voices = ext.param_info(params::VOICES as u32).unwrap().flags;
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
        assert_eq!(ext.value_to_text(params::GLIDE as u32, 0.12).unwrap(), "120 ms");
        let purify = params::PURIFY as u32;
        assert!((ext.text_to_value(purify, "40%").unwrap() - 0.4).abs() < 1e-6);
    }
}
