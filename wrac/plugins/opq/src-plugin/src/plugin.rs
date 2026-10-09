//! The plugin contract as seen by the host: the 20 parameters, the saved
//! state, a main audio pair (mono or stereo), the MIDI note side chain, a
//! constant latency, and the panel where the platform has one. The entry,
//! factory and audio ports are wrac_shell's.

use std::sync::Arc;

mod params;
mod state;

use params::OpqParams;
use state::OpqStateExtension;
use wrac_clap_adapter::{
    AaxDescriptor, AaxStemConfig, ActivateContext, Auv2Descriptor, NoteDialects, NotePortInfo,
    PluginAudioPortsExtension, PluginConfigurableAudioPortsExtension, PluginCore,
    PluginCoreContext, PluginDescriptor, PluginFeature, PluginLatencyExtension,
    PluginNotePortsExtension, PluginParamsExtension, PluginResult, PluginStateExtension,
    Processor, Vst3Descriptor,
};
use wrac_shell::MonoStereoPorts;

use crate::audio::OpqAudioProcessor;
#[cfg(target_os = "macos")]
use crate::gui::PanelGui;
#[cfg(target_os = "windows")]
use crate::gui_win32::PanelGui;
#[cfg(any(target_os = "macos", target_os = "windows"))]
use wrac_clap_adapter::PluginGuiExtension;

use crate::state::SharedState;

// Generated from [package.metadata.wrac] in src-plugin/Cargo.toml.
include!(concat!(env!("OUT_DIR"), "/wrac_plugin_products.rs"));
wrac_shell::plugin_entry!(OpqPlugin, log = "OpenPitchQuant");

/// MIDI note sidechain: one input note port, CLAP + MIDI dialects.
struct OpqNotePorts;

impl PluginNotePortsExtension for OpqNotePorts {
    fn note_port_count(&self, is_input: bool) -> u32 {
        if is_input { 1 } else { 0 }
    }

    fn note_port_info(&self, index: u32, is_input: bool) -> Option<NotePortInfo> {
        (is_input && index == 0).then(|| NotePortInfo {
            id: 0,
            supported_dialects: NoteDialects::from_bits(
                NoteDialects::CLAP.bits() | NoteDialects::MIDI.bits(),
            ),
            preferred_dialect: NoteDialects::CLAP,
            name: "MIDI Sidechain",
        })
    }
}

/// Constant algorithmic latency: the engine's STFT window (4096 samples).
struct OpqLatency;

impl PluginLatencyExtension for OpqLatency {
    fn latency_frames(&self) -> u32 {
        opq_engine::N_FFT as u32
    }
}

pub(crate) struct OpqPlugin {
    shared: Arc<SharedState>,
    /// The main pair only: the side chain is MIDI, a note port.
    ports: Arc<MonoStereoPorts>,
    params: Arc<OpqParams>,
    state_extension: Arc<OpqStateExtension>,
    note_ports: Arc<OpqNotePorts>,
    latency: Arc<OpqLatency>,
    #[cfg(any(target_os = "macos", target_os = "windows"))]
    gui: Arc<PanelGui>,
}

impl OpqPlugin {
    pub(crate) fn new(context: PluginCoreContext) -> Self {
        #[cfg(not(any(target_os = "macos", target_os = "windows")))]
        let _ = &context;
        let shared = Arc::new(SharedState::new());
        Self {
            #[cfg(any(target_os = "macos", target_os = "windows"))]
            gui: Arc::new(PanelGui::new(
                shared.clone(),
                context.host_parameter_edit_notifier.clone(),
            )),
            ports: Arc::new(MonoStereoPorts::main_only()),
            params: Arc::new(OpqParams::new(shared.clone())),
            state_extension: Arc::new(OpqStateExtension::new(shared.clone())),
            note_ports: Arc::new(OpqNotePorts),
            latency: Arc::new(OpqLatency),
            shared,
        }
    }
}

impl PluginCore for OpqPlugin {
    fn activate(&mut self, context: ActivateContext) -> PluginResult<Box<dyn Processor>> {
        let channels = self.ports.channels();
        log::debug!(
            "activating: sample_rate={}, max_frames={}, channels={}",
            context.sample_rate,
            context.max_frames_count,
            channels
        );
        Ok(Box::new(OpqAudioProcessor::new(
            self.shared.clone(),
            channels,
            context.sample_rate,
            context.max_frames_count,
        )))
    }

    fn deactivate(&mut self, processor: Box<dyn Processor>) -> PluginResult<()> {
        // The processor's drop reports its final values and deactivates the
        // sync, which cancels gestures in flight; the editor ends its own.
        drop(processor);
        #[cfg(any(target_os = "macos", target_os = "windows"))]
        self.gui.cancel_gestures();
        Ok(())
    }

    fn audio_ports(&self) -> Option<Arc<dyn PluginAudioPortsExtension>> {
        Some(self.ports.clone())
    }

    fn configurable_audio_ports(&self) -> Option<Arc<dyn PluginConfigurableAudioPortsExtension>> {
        Some(self.ports.clone())
    }

    fn note_ports(&self) -> Option<Arc<dyn PluginNotePortsExtension>> {
        Some(self.note_ports.clone())
    }

    fn params(&self) -> Option<Arc<dyn PluginParamsExtension>> {
        Some(self.params.clone())
    }

    fn state(&self) -> Option<Arc<dyn PluginStateExtension>> {
        Some(self.state_extension.clone())
    }

    fn latency(&self) -> Option<Arc<dyn PluginLatencyExtension>> {
        Some(self.latency.clone())
    }

    #[cfg(any(target_os = "macos", target_os = "windows"))]
    fn gui(&self) -> Option<Arc<dyn PluginGuiExtension>> {
        Some(self.gui.clone())
    }
}
