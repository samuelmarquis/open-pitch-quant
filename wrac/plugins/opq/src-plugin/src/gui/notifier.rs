//! Outbound notification channels pushing GUI state to the WebView.
//!
//! Two streams: parameter values (host automation → GUI) and the analysis
//! feed (engine viz frames → the pitch-object display). Subscriptions are
//! routed by kind so each can be torn down independently.

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};

use novonotes_run_loop::RunLoop;
use parking_lot::Mutex;
use serde_json::json;
use wxp::Channel;

use opq_engine::VizFrame;

use crate::plugin::parameter_value_text;

pub(crate) struct GuiStateNotifier {
    next_subscription_id: AtomicU64,
    subscriptions: Mutex<HashMap<GuiSubscriptionId, GuiSubscription>>,
}

#[derive(Clone)]
struct GuiSubscription {
    kind: GuiSubscriptionKind,
    channel: Channel,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub(crate) struct GuiSubscriptionId(u64);

impl GuiSubscriptionId {
    pub(crate) fn get(self) -> u64 {
        self.0
    }

    pub(crate) fn from_raw(value: u64) -> Self {
        Self(value)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum GuiSubscriptionKind {
    Parameters,
    Viz,
}

impl GuiStateNotifier {
    pub(super) fn new() -> Self {
        Self {
            next_subscription_id: AtomicU64::new(1),
            subscriptions: Mutex::new(HashMap::new()),
        }
    }

    pub(crate) fn subscribe_parameters(&self, channel: Channel) -> GuiSubscriptionId {
        self.subscribe(GuiSubscriptionKind::Parameters, channel)
    }

    pub(crate) fn subscribe_viz(&self, channel: Channel) -> GuiSubscriptionId {
        self.subscribe(GuiSubscriptionKind::Viz, channel)
    }

    fn subscribe(&self, kind: GuiSubscriptionKind, channel: Channel) -> GuiSubscriptionId {
        let id = GuiSubscriptionId(self.next_subscription_id.fetch_add(1, Ordering::Relaxed));
        self.subscriptions
            .lock()
            .insert(id, GuiSubscription { kind, channel });
        id
    }

    pub(crate) fn unsubscribe(&self, id: GuiSubscriptionId) {
        self.subscriptions.lock().remove(&id);
    }

    pub(crate) fn clear_subscriptions(&self) {
        self.subscriptions.lock().clear();
    }

    pub(crate) fn has_viz_subscribers(&self) -> bool {
        self.subscriptions
            .lock()
            .values()
            .any(|s| s.kind == GuiSubscriptionKind::Viz)
    }

    pub(crate) fn notify_parameter(&self, parameter_id: u32, value: f32) {
        self.notify(
            GuiSubscriptionKind::Parameters,
            parameter_payload(parameter_id, value),
        );
    }

    pub(crate) fn notify_viz(&self, frames: &[VizFrame], sample_rate: f32, hop: u32) {
        if frames.is_empty() {
            return;
        }
        self.notify(
            GuiSubscriptionKind::Viz,
            viz_payload(frames, sample_rate, hop),
        );
    }

    fn notify(&self, kind: GuiSubscriptionKind, payload: serde_json::Value) {
        // Clone the delivery targets before releasing the lock so a re-entrant
        // call from a recipient cannot deadlock.
        let subscriptions: Vec<_> = self
            .subscriptions
            .lock()
            .values()
            .filter(|subscription| subscription.kind == kind)
            .cloned()
            .collect();
        if subscriptions.is_empty() {
            return;
        }

        for subscription in subscriptions {
            let payload = payload.clone();
            // WebView channels may only be touched on the GUI's UI thread;
            // always dispatch back through the run loop.
            let _ = RunLoop::post(move |_| {
                let _ = subscription.channel.send(payload);
            });
        }
    }
}

/// JSON payload for one parameter. The TypeScript side expects this shape.
pub(crate) fn parameter_payload(parameter_id: u32, value: f32) -> serde_json::Value {
    json!({
        "type": "parameter-value",
        "parameterId": parameter_id,
        "value": value,
        "text": parameter_value_text(parameter_id, f64::from(value))
            .unwrap_or_else(|_| value.to_string()),
    })
}

/// JSON payload for a batch of analysis frames. Field names match the CLI's
/// `--viz-dump` JSON-lines format so the GUI shares one parser between the
/// live feed and baked demo traces.
fn viz_payload(frames: &[VizFrame], sample_rate: f32, hop: u32) -> serde_json::Value {
    let frames: Vec<serde_json::Value> = frames
        .iter()
        .map(|fr| {
            let grid: Vec<u32> = (0..127u32)
                .filter(|n| fr.grid_mask & (1u128 << n) != 0)
                .collect();
            let tracks: Vec<serde_json::Value> = fr.tracks[..fr.n as usize]
                .iter()
                .map(|tr| {
                    json!({
                        "id": tr.id,
                        "f0": tr.f0,
                        "tgt": tr.tgt,
                        "amp": tr.amp,
                        "nh": tr.nh,
                        "nb": tr.newborn,
                    })
                })
                .collect();
            json!({
                "t": fr.t,
                "time": if sample_rate > 0.0 {
                    fr.t as f64 * f64::from(hop) / f64::from(sample_rate)
                } else {
                    0.0
                },
                "flux": fr.flux.min(99.0),
                "transient": fr.transient,
                "in": fr.in_energy,
                "res": fr.res_energy,
                "repeat": fr.grid_mask & (1u128 << 127) != 0,
                "grid": grid,
                "bands": fr.res_bands.to_vec(),
                "tracks": tracks,
            })
        })
        .collect();
    json!({
        "type": "viz-frames",
        "sampleRate": sample_rate,
        "hop": hop,
        "frames": frames,
    })
}
