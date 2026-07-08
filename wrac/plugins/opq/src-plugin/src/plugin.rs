//! The plugin contract as seen by the host. Headless: `PluginCore::gui()`
//! stays at its default `None`, so hosts present their generic editor.

use std::sync::Arc;

mod audio_ports;
mod params;
mod state;

pub(crate) use params::{
    PARAM_BYPASS_ID, PARAM_CARRY_ID, PARAM_COHERENCE_ID, PARAM_FEEL_ID, PARAM_FMAX_ID,
    PARAM_FORMANT_ID, PARAM_GATE_ID, PARAM_GATE_MODE_ID, PARAM_GLIDE_ID, PARAM_GRIT_ID,
    PARAM_MIX_ID, PARAM_ROUNDING_ID, PARAM_SCOPE_ID, PARAM_THRESHOLD_ID, PARAM_TRANSIENT_ID,
    PARAM_TRANSITIONS_ID, PARAM_UNOWNED_ID, PARAM_VOICES_ID, param_clamp, param_default,
    param_exists, parameter_infos,
};

use audio_ports::{AudioLayoutStore, OpqAudioPorts, OpqConfigurableAudioPorts};
use params::OpqParamsExtension;
use state::OpqStateExtension;
use wrac_clap_adapter::{
    AaxDescriptor, AaxStemConfig, ActivateContext, Auv2Descriptor, NoteDialects, NotePortInfo,
    PluginAudioPortsExtension, PluginConfigurableAudioPortsExtension, PluginCore,
    PluginCoreContext, PluginDescriptor, PluginEntry, PluginFactory, PluginFeature,
    PluginLatencyExtension, PluginNotePortsExtension, PluginParamsExtension, PluginResult,
    PluginStateExtension, Processor, Vst3Descriptor,
};

use crate::audio::OpqAudioProcessor;
use crate::state::SharedState;

// Generated from [package.metadata.wrac] in src-plugin/Cargo.toml.
include!(concat!(env!("OUT_DIR"), "/wrac_plugin_products.rs"));

pub(crate) static PLUGIN_ENTRY: OpqEntry = OpqEntry;

pub(crate) struct OpqEntry;

impl PluginEntry for OpqEntry {
    fn plugin_factory(&self) -> Option<&dyn PluginFactory> {
        Some(&OPQ_FACTORY)
    }
}

static OPQ_FACTORY: OpqFactory = OpqFactory;

struct OpqFactory;

impl PluginFactory for OpqFactory {
    fn plugin_count(&self) -> u32 {
        PLUGIN_DESCRIPTORS.len() as u32
    }

    fn plugin_descriptor(&self, index: u32) -> Option<PluginDescriptor> {
        PLUGIN_DESCRIPTORS.get(index as usize).copied()
    }

    fn create_plugin(
        &self,
        plugin_id: &str,
        context: PluginCoreContext,
    ) -> Option<Box<dyn PluginCore>> {
        PLUGIN_DESCRIPTORS
            .iter()
            .find(|descriptor| descriptor.id == plugin_id)
            .map(|descriptor| create_plugin_core(context, *descriptor))
    }
}

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
    descriptor: PluginDescriptor,
    shared: Arc<SharedState>,
    audio_layout: Arc<AudioLayoutStore>,
    audio_ports: Arc<OpqAudioPorts>,
    configurable_audio_ports: Arc<OpqConfigurableAudioPorts>,
    params: Arc<OpqParamsExtension>,
    state_extension: Arc<OpqStateExtension>,
    note_ports: Arc<OpqNotePorts>,
    latency: Arc<OpqLatency>,
}

impl OpqPlugin {
    pub(crate) fn new(_context: PluginCoreContext, descriptor: PluginDescriptor) -> Self {
        let shared = Arc::new(SharedState::new());
        let audio_layout = Arc::new(AudioLayoutStore::new(2));
        let audio_ports = Arc::new(OpqAudioPorts::new(audio_layout.clone()));
        let configurable_audio_ports =
            Arc::new(OpqConfigurableAudioPorts::new(audio_layout.clone()));
        let params = Arc::new(OpqParamsExtension::new(shared.clone()));
        let state_extension = Arc::new(OpqStateExtension::new(shared.clone()));

        Self {
            descriptor,
            shared,
            audio_layout,
            audio_ports,
            configurable_audio_ports,
            params,
            state_extension,
            note_ports: Arc::new(OpqNotePorts),
            latency: Arc::new(OpqLatency),
        }
    }
}

pub(crate) fn create_plugin_core(
    context: PluginCoreContext,
    descriptor: PluginDescriptor,
) -> Box<dyn PluginCore> {
    wrac_log::init!(descriptor.name);
    log::debug!(
        "creating plugin core: id={}, name={}",
        descriptor.id,
        descriptor.name
    );
    Box::new(OpqPlugin::new(context, descriptor))
}

impl PluginCore for OpqPlugin {
    fn activate(&mut self, context: ActivateContext) -> PluginResult<Box<dyn Processor>> {
        let audio_channel_count = self.audio_layout.channel_count();
        log::debug!(
            "activating: plugin_id={}, sample_rate={}, max_frames={}, channels={}",
            self.descriptor.id,
            context.sample_rate,
            context.max_frames_count,
            audio_channel_count
        );
        Ok(Box::new(OpqAudioProcessor::new(
            self.shared.clone(),
            audio_channel_count,
            context.sample_rate,
            context.max_frames_count,
        )))
    }

    fn deactivate(&mut self, _processor: Box<dyn Processor>) -> PluginResult<()> {
        Ok(())
    }

    fn audio_ports(&self) -> Option<Arc<dyn PluginAudioPortsExtension>> {
        Some(self.audio_ports.clone())
    }

    fn configurable_audio_ports(&self) -> Option<Arc<dyn PluginConfigurableAudioPortsExtension>> {
        Some(self.configurable_audio_ports.clone())
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
}
