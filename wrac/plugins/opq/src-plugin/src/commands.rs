//! Registration of commands callable from the WebView frontend.
//!
//! From Rust's perspective this module is the contract with the TypeScript UI.
//! When renaming commands or changing payload shapes, update the `invoke(...)`
//! calls and subscriptions in `src-gui` at the same time.
//!
//! opq-specific additions over the wrac-gain template:
//! - `get_parameter_manifest`: the full spec table (ranges, defaults, choice
//!   labels) so the GUI renders generically from Rust's single source of truth
//! - `subscribe_viz`: the live analysis feed (pitch objects, grid, flux)
//!   pushed by the GUI runtime timer

use std::rc::Rc;
use std::sync::Arc;

use serde::Deserialize;
use serde_json::json;
use wrac_clap_adapter::{
    HostContext, HostFamily, HostGuiResizeRequester, HostParamsEditNotifier, PluginDescriptor,
};
use wrac_wxp_gui::{
    WxpGuiResizeHandle, register_native_cursor_bridge_commands, register_resize_commands,
};
use wxp::{Channel, WxpCommandHandler};

use crate::gui::{GuiStateNotifier, GuiSubscriptionId, parameter_payload};
use crate::plugin::{
    parameter_default_value, parameter_host_value, parameter_manifest_json, parameter_text_value,
};
use crate::state::SharedState;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "kebab-case")]
enum FrontendLogLevel {
    Debug,
    Info,
    Warn,
    Error,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct FrontendLogEntry {
    level: FrontendLogLevel,
    message: String,
    #[serde(default)]
    data: Option<serde_json::Value>,
}

pub(crate) struct CommandRegistrationDependencies {
    pub(crate) shared: Arc<SharedState>,
    pub(crate) gui_notifier: Arc<GuiStateNotifier>,
    pub(crate) descriptor: PluginDescriptor,
    pub(crate) host_parameter_edit_notifier: Arc<dyn HostParamsEditNotifier>,
    pub(crate) host_gui_resize_requester: Arc<dyn HostGuiResizeRequester>,
    pub(crate) gui_resize_handle: WxpGuiResizeHandle,
    pub(crate) host_context: HostContext,
}

pub(crate) fn register_commands(
    command_handler: Rc<WxpCommandHandler>,
    dependencies: CommandRegistrationDependencies,
) {
    let CommandRegistrationDependencies {
        shared,
        gui_notifier,
        descriptor,
        host_parameter_edit_notifier,
        host_gui_resize_requester,
        gui_resize_handle,
        host_context,
    } = dependencies;

    command_handler.register_sync("get_plugin_metadata", move |_| {
        Ok::<_, String>(json!({
            "pluginId": descriptor.id,
            "pluginName": descriptor.name,
            "companyName": descriptor.vendor,
            "version": descriptor.version,
        }))
    });

    // The WebView console is often invisible inside a DAW. Bridge frontend logs
    // to the plugin's logger so GUI initialisation progress is visible natively.
    command_handler.register_sync("write_to_log", move |ctx| {
        let entry = ctx
            .arg::<FrontendLogEntry>("entry")
            .map_err(|e| e.to_string())?;
        write_frontend_log(entry);
        Ok::<_, String>(json!({ "ok": true }))
    });

    let frontend_runtime_context = frontend_runtime_context(&host_context);
    command_handler.register_sync("get_frontend_runtime_context", move |_| {
        Ok::<_, String>(frontend_runtime_context.clone())
    });

    command_handler.register_sync("get_parameter_manifest", move |_| {
        Ok::<_, String>(parameter_manifest_json())
    });

    // Engine constants the display needs for its time axis. Zero until the
    // host activates the processor.
    {
        let shared = shared.clone();
        command_handler.register_sync("get_engine_info", move |_| {
            let (sample_rate, hop) = shared.engine_info();
            Ok::<_, String>(json!({
                "sampleRate": sample_rate,
                "hop": hop,
                "latency": opq_engine::N_FFT,
            }))
        });
    }

    {
        let shared = shared.clone();
        command_handler.register_sync("get_parameter_state", move |ctx| {
            let parameter_id = ctx.arg::<u32>("parameterId").map_err(|e| e.to_string())?;
            let value = shared
                .parameter_value(parameter_id)
                .ok_or_else(|| "invalid parameter id".to_string())?;
            Ok::<_, String>(parameter_payload(parameter_id, value))
        });
    }

    // Converts a display string back to a plain value via the Rust parser.
    {
        let shared = shared.clone();
        let gui_notifier = gui_notifier.clone();
        let host_parameter_edit_notifier = host_parameter_edit_notifier.clone();
        command_handler.register_sync("set_parameter_text", move |ctx| {
            let parameter_id = ctx.arg::<u32>("parameterId").map_err(|e| e.to_string())?;
            let text = ctx.arg::<String>("text").map_err(|e| e.to_string())?;
            let value = parameter_text_value(parameter_id, &text).map_err(|e| e.to_string())?;
            host_parameter_edit_notifier.begin_edit(parameter_id);
            let applied = shared
                .set_parameter_value(parameter_id, value)
                .ok_or_else(|| "invalid parameter id".to_string())?;
            gui_notifier.notify_parameter(parameter_id, applied);
            host_parameter_edit_notifier.update_edit(
                parameter_id,
                parameter_host_value(parameter_id, applied)
                    .map_err(|_| "invalid parameter id".to_string())?,
            );
            host_parameter_edit_notifier.end_edit(parameter_id);
            Ok::<_, String>(parameter_payload(parameter_id, applied))
        });
    }

    {
        let shared = shared.clone();
        let gui_notifier = gui_notifier.clone();
        let host_parameter_edit_notifier = host_parameter_edit_notifier.clone();
        command_handler.register_sync("reset_parameter_to_default", move |ctx| {
            let parameter_id = ctx.arg::<u32>("parameterId").map_err(|e| e.to_string())?;
            let value = parameter_default_value(parameter_id).map_err(|e| e.to_string())?;
            host_parameter_edit_notifier.begin_edit(parameter_id);
            let applied = shared
                .set_parameter_value(parameter_id, value)
                .ok_or_else(|| "invalid parameter id".to_string())?;
            gui_notifier.notify_parameter(parameter_id, applied);
            host_parameter_edit_notifier.update_edit(
                parameter_id,
                parameter_host_value(parameter_id, applied)
                    .map_err(|_| "invalid parameter id".to_string())?,
            );
            host_parameter_edit_notifier.end_edit(parameter_id);
            Ok::<_, String>(parameter_payload(parameter_id, applied))
        });
    }

    // Gesture begin/end bracket drags so the host records one undo unit.
    {
        let host_parameter_edit_notifier = host_parameter_edit_notifier.clone();
        command_handler.register_sync("begin_parameter_gesture", move |ctx| {
            let parameter_id = ctx.arg::<u32>("parameterId").map_err(|e| e.to_string())?;
            host_parameter_edit_notifier.begin_edit(parameter_id);
            Ok::<_, String>(json!({ "ok": true }))
        });
    }

    {
        let shared = shared.clone();
        let gui_notifier = gui_notifier.clone();
        let host_parameter_edit_notifier = host_parameter_edit_notifier.clone();
        command_handler.register_sync("set_parameter_value", move |ctx| {
            let parameter_id = ctx.arg::<u32>("parameterId").map_err(|e| e.to_string())?;
            let value = ctx.arg::<f64>("value").map_err(|e| e.to_string())?;
            let applied = shared
                .set_parameter_value(parameter_id, value)
                .ok_or_else(|| "invalid parameter id".to_string())?;
            gui_notifier.notify_parameter(parameter_id, applied);
            host_parameter_edit_notifier.update_edit(
                parameter_id,
                parameter_host_value(parameter_id, applied)
                    .map_err(|_| "invalid parameter id".to_string())?,
            );
            Ok::<_, String>(parameter_payload(parameter_id, applied))
        });
    }

    {
        let host_parameter_edit_notifier = host_parameter_edit_notifier.clone();
        command_handler.register_sync("end_parameter_gesture", move |ctx| {
            let parameter_id = ctx.arg::<u32>("parameterId").map_err(|e| e.to_string())?;
            host_parameter_edit_notifier.end_edit(parameter_id);
            Ok::<_, String>(json!({ "ok": true }))
        });
    }

    {
        let gui_notifier = gui_notifier.clone();
        command_handler.register_sync("subscribe_parameters", move |ctx| {
            let channel = ctx.arg::<Channel>("channel").map_err(|e| e.to_string())?;
            let subscription_id = gui_notifier.subscribe_parameters(channel);
            Ok::<_, String>(json!({
                "ok": true,
                "subscriptionId": subscription_id.get(),
            }))
        });
    }

    // The analysis feed: batches of engine frames pushed at GUI timer rate.
    {
        let gui_notifier = gui_notifier.clone();
        command_handler.register_sync("subscribe_viz", move |ctx| {
            let channel = ctx.arg::<Channel>("channel").map_err(|e| e.to_string())?;
            let subscription_id = gui_notifier.subscribe_viz(channel);
            Ok::<_, String>(json!({
                "ok": true,
                "subscriptionId": subscription_id.get(),
            }))
        });
    }

    {
        let gui_notifier = gui_notifier.clone();
        command_handler.register_sync("unsubscribe_gui_subscription", move |ctx| {
            let subscription_id = ctx
                .arg::<u64>("subscriptionId")
                .map_err(|e| e.to_string())?;
            gui_notifier.unsubscribe(GuiSubscriptionId::from_raw(subscription_id));
            Ok::<_, String>(json!({ "ok": true }))
        });
    }

    command_handler.register_sync("focus_host_window", move |ctx| {
        ctx.webview()
            .post_focus_parent()
            .map_err(|e| format!("focus_parent failed: {e}"))?;
        Ok::<_, String>(json!({ "ok": true }))
    });

    register_resize_commands(
        &command_handler,
        host_gui_resize_requester,
        gui_resize_handle,
    );
    register_native_cursor_bridge_commands(&command_handler);
}

fn write_frontend_log(entry: FrontendLogEntry) {
    let message = match entry.data {
        Some(data) => format!("{} data={data}", entry.message),
        None => entry.message,
    };

    match entry.level {
        FrontendLogLevel::Debug => log::debug!(target: "frontend", "{message}"),
        FrontendLogLevel::Info => log::info!(target: "frontend", "{message}"),
        FrontendLogLevel::Warn => log::warn!(target: "frontend", "{message}"),
        FrontendLogLevel::Error => log::error!(target: "frontend", "{message}"),
    }
}

fn frontend_runtime_context(host_context: &HostContext) -> serde_json::Value {
    json!({
        "os": std::env::consts::OS,
        "pluginFormat": host_context.plugin_format.as_str(),
        "hostFamily": host_family_id(host_context.host.family),
        "hostName": host_context.host.display_name,
        "processName": host_context.host.process_name,
    })
}

fn host_family_id(family: HostFamily) -> &'static str {
    match family {
        HostFamily::AbletonLive => "ableton-live",
        HostFamily::AdobeAudition => "adobe-audition",
        HostFamily::AdobePremiere => "adobe-premiere",
        HostFamily::AppleAuLab => "apple-au-lab",
        HostFamily::AppleAuval => "apple-auval",
        HostFamily::AppleFinalCut => "apple-final-cut",
        HostFamily::AppleGarageBand => "apple-garage-band",
        HostFamily::AppleInfoHelper => "apple-info-helper",
        HostFamily::AppleLogic => "apple-logic",
        HostFamily::AppleMainStage => "apple-mainstage",
        HostFamily::Ardour => "ardour",
        HostFamily::BitwigStudio => "bitwig-studio",
        HostFamily::CakewalkByBandlab => "cakewalk-by-bandlab",
        HostFamily::CakewalkSonar => "cakewalk-sonar",
        HostFamily::DaVinciResolve => "davinci-resolve",
        HostFamily::DigitalPerformer => "digital-performer",
        HostFamily::FlStudio => "fl-studio",
        HostFamily::JuceAudioPluginHost => "juce-audio-plugin-host",
        HostFamily::Luna => "luna",
        HostFamily::MagixSamplitude => "magix-samplitude",
        HostFamily::MagixSequoia => "magix-sequoia",
        HostFamily::MuseReceptor => "muse-receptor",
        HostFamily::NiMaschine => "ni-maschine",
        HostFamily::Pluginval => "pluginval",
        HostFamily::ProTools => "pro-tools",
        HostFamily::Pyramix => "pyramix",
        HostFamily::Reason => "reason",
        HostFamily::Renoise => "renoise",
        HostFamily::Reaper => "reaper",
        HostFamily::Sadie => "sadie",
        HostFamily::SteinbergCubase => "steinberg-cubase",
        HostFamily::SteinbergCubaseBridged => "steinberg-cubase-bridged",
        HostFamily::SteinbergNuendo => "steinberg-nuendo",
        HostFamily::SteinbergTestHost => "steinberg-test-host",
        HostFamily::SteinbergWavelab => "steinberg-wavelab",
        HostFamily::StudioOne => "studio-one",
        HostFamily::Tracktion => "tracktion",
        HostFamily::TracktionWaveform => "tracktion-waveform",
        HostFamily::VbVstScanner => "vb-vst-scanner",
        HostFamily::ViennaEnsemblePro => "vienna-ensemble-pro",
        HostFamily::WaveBurner => "waveburner",
        HostFamily::Unknown => "unknown",
    }
}
