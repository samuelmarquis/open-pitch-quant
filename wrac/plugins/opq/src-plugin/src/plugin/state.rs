//! Project state: pluginkit's document (`{"version":2,"params":{"values":
//! [...]}}`) through wrac_shell. Only the exact version loads; anything else
//! (including the pre-pluginkit version 1) is refused and leaves the
//! plugin's state alone.

use std::sync::Arc;

use opq_engine::params::{PARAM_COUNT, ParamSchema, Params, STATE_VERSION};
use wrac_clap_adapter::{PluginResult, PluginStateExtension, State};
use wrac_shell::{load_document, save_document};

use crate::state::SharedState;

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
        Ok(save_document(STATE_VERSION, &self.shared.values()))
    }

    fn restore_state(&self, state: State) -> PluginResult<()> {
        let values = load_document::<ParamSchema, PARAM_COUNT>(&state, STATE_VERSION)?;
        self.shared.sync.restore(Params { values });
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use opq_engine::params::{ALGORITHM, FEEL, PURIFY};

    #[test]
    fn state_round_trips_and_refuses_bad_documents() {
        let shared = Arc::new(SharedState::new());
        let ext = OpqStateExtension::new(shared.clone());
        let mut p = Params::default();
        p.set(ALGORITHM, 1.0);
        p.set(PURIFY, 0.4);
        p.set(FEEL, 0.8);
        let doc = State { bytes: pluginkit::state::save(STATE_VERSION, &p.values) };
        ext.restore_state(doc).unwrap();
        let saved = ext.save_state().unwrap();
        assert_eq!(
            std::str::from_utf8(&saved.bytes).unwrap(),
            std::str::from_utf8(&pluginkit::state::save(STATE_VERSION, &p.values)).unwrap()
        );
        let other = OpqStateExtension::new(Arc::new(SharedState::new()));
        other.restore_state(saved).unwrap();
        assert_eq!(other.shared.values(), p.values);

        let before = other.shared.values();
        let mut bad = p.values;
        bad[ALGORITHM] = 0.5;
        for bytes in [
            pluginkit::state::save(STATE_VERSION, &bad),
            pluginkit::state::save(STATE_VERSION + 1, &p.values),
            pluginkit::state::save(STATE_VERSION, &p.values[..PARAM_COUNT - 1]),
            // a 0.1.0 project: the id-keyed version 1 no longer loads
            br#"{"version":1,"params":[{"id":2,"value":0.5}]}"#.to_vec(),
            b"{".to_vec(),
        ] {
            assert!(other.restore_state(State { bytes }).is_err());
            assert_eq!(other.shared.values(), before);
        }
    }
}
