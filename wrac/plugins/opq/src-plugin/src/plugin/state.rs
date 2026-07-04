//! Project state persistence: all parameters serialized as JSON by stable id.

use std::sync::Arc;

use serde::{Deserialize, Serialize};
use wrac_clap_adapter::{PluginError, PluginResult, PluginStateExtension, State};

use crate::plugin::parameter_infos;
use crate::state::SharedState;

#[derive(Debug, Serialize, Deserialize)]
struct SavedParam {
    id: u32,
    value: f32,
}

#[derive(Debug, Serialize, Deserialize)]
struct SavedState {
    /// Bump only with a migration plan; unknown ids are ignored on restore.
    version: u32,
    params: Vec<SavedParam>,
}

pub(super) struct OpqStateExtension {
    shared: Arc<SharedState>,
}

impl OpqStateExtension {
    pub(super) fn new(shared: Arc<SharedState>) -> Self {
        Self { shared }
    }
}

impl PluginStateExtension for OpqStateExtension {
    fn save_state(&self) -> PluginResult<State> {
        let params = parameter_infos()
            .filter_map(|info| {
                self.shared
                    .parameter_value(info.id)
                    .map(|value| SavedParam { id: info.id, value })
            })
            .collect();
        let bytes = serde_json::to_vec(&SavedState { version: 1, params })
            .map_err(|_| PluginError::InvalidState)?;
        Ok(State { bytes })
    }

    fn restore_state(&self, state: State) -> PluginResult<()> {
        let saved: SavedState =
            serde_json::from_slice(&state.bytes).map_err(|_| PluginError::InvalidState)?;
        // Reset to defaults first so params missing from old saves stay sane.
        for info in parameter_infos() {
            let _ = self
                .shared
                .set_parameter_value(info.id, info.default_value);
        }
        for param in saved.params {
            let _ = self.shared.set_parameter_value(param.id, param.value as f64);
        }
        Ok(())
    }
}
