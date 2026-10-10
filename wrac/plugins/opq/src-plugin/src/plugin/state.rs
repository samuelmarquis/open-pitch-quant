//! Project state: pluginkit's document through wrac_shell, with the key
//! states as its product section:
//!
//!   {"version":3,"params":{"values":[...]},"product":{"keys":{"target":[lo,hi],"bypass":[lo,hi]}}}
//!
//! Only the exact version loads; anything else (an earlier version, the
//! pre-pluginkit version 1) is refused and leaves the plugin's state alone.

use std::sync::Arc;

use opq_engine::params::{Keys, PARAM_COUNT, ParamSchema, Params, STATE_VERSION};
use serde::{Deserialize, Serialize};
use wrac_clap_adapter::{PluginResult, PluginStateExtension, State};
use wrac_shell::{load_document_with, save_document_with};

use crate::state::SharedState;

/// The product section's size bound: two pairs of u64 and their keys.
const PRODUCT_BYTES: usize = 256;

#[derive(Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Product {
    keys: KeyMasks,
}

/// The key masks as low/high 64-bit halves (JSON numbers stay exact).
#[derive(Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct KeyMasks {
    target: [u64; 2],
    bypass: [u64; 2],
}

impl From<Keys> for KeyMasks {
    fn from(k: Keys) -> Self {
        let halves = |m: u128| [m as u64, (m >> 64) as u64];
        Self { target: halves(k.target), bypass: halves(k.bypass) }
    }
}

impl From<KeyMasks> for Keys {
    fn from(m: KeyMasks) -> Self {
        let join = |h: [u64; 2]| h[0] as u128 | (h[1] as u128) << 64;
        Self { target: join(m.target), bypass: join(m.bypass) }
    }
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
        let product = Product { keys: self.shared.keys().into() };
        Ok(save_document_with(STATE_VERSION, &self.shared.values(), Some(&product)))
    }

    fn restore_state(&self, state: State) -> PluginResult<()> {
        let (values, product) =
            load_document_with::<ParamSchema, Product, PARAM_COUNT>(&state, STATE_VERSION, PRODUCT_BYTES)?;
        self.shared.sync.restore(Params { values });
        self.shared.set_keys(product.map_or_else(Keys::default, |p| p.keys.into()), false);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use opq_engine::params::{ALGORITHM, FEEL, KeyState, PURIFY, SOURCE};

    #[test]
    fn state_round_trips_and_refuses_bad_documents() {
        let shared = Arc::new(SharedState::new());
        let ext = OpqStateExtension::new(shared.clone());
        let mut p = Params::default();
        p.set(ALGORITHM, 1.0);
        p.set(PURIFY, 0.4);
        p.set(FEEL, 0.8);
        p.set(SOURCE, 1.0);
        let mut keys = Keys { target: 0, bypass: 0 };
        keys.set(KeyState::Target, 60, true, true);
        keys.set(KeyState::Bypass, 127, true, false);
        let product = Product { keys: keys.into() };
        let doc = State { bytes: pluginkit::state::save_with(STATE_VERSION, &p.values, Some(&product)) };
        ext.restore_state(doc).unwrap();
        assert_eq!(shared.keys(), keys);
        let saved = ext.save_state().unwrap();
        assert_eq!(
            std::str::from_utf8(&saved.bytes).unwrap(),
            std::str::from_utf8(&pluginkit::state::save_with(STATE_VERSION, &p.values, Some(&product))).unwrap()
        );
        let other = OpqStateExtension::new(Arc::new(SharedState::new()));
        other.restore_state(saved).unwrap();
        assert_eq!(other.shared.values(), p.values);
        assert_eq!(other.shared.keys(), keys);

        // A document without the section loads with the default keys.
        other.restore_state(State { bytes: pluginkit::state::save(STATE_VERSION, &p.values) }).unwrap();
        assert_eq!(other.shared.keys(), Keys::default());

        let before = other.shared.values();
        let mut bad = p.values;
        bad[ALGORITHM] = 0.5;
        for bytes in [
            pluginkit::state::save(STATE_VERSION, &bad),
            pluginkit::state::save(STATE_VERSION + 1, &p.values),
            pluginkit::state::save(STATE_VERSION, &p.values[..PARAM_COUNT - 1]),
            // a 0.3.x project (version 2, 20 values) no longer loads
            pluginkit::state::save(2, &p.values[..PARAM_COUNT - 1]),
            // a 0.1.0 project: the id-keyed version 1 no longer loads
            br#"{"version":1,"params":[{"id":2,"value":0.5}]}"#.to_vec(),
            b"{".to_vec(),
        ] {
            assert!(other.restore_state(State { bytes }).is_err());
            assert_eq!(other.shared.values(), before);
        }
    }
}
