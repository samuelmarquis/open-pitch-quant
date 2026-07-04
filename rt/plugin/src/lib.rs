//! OpenPitchQuant — real-time polyphonic pitch mapping (VST3/CLAP).
//!
//! MIDI sidechain semantics: held notes define the allowed target grid
//! (PITCHMAP "MIDI MAP + Xclude"); no held notes = silence.

use nih_plug::prelude::*;
use opq_engine::{Engine, EngineParams, Mode, Rounding, TonalityMode, Unowned, N_FFT};
use std::sync::Arc;

#[derive(Enum, PartialEq, Clone, Copy)]
enum OctaveMode {
    #[name = "Repeat (pitch classes)"]
    Repeat,
    #[name = "Custom (exact notes)"]
    Custom,
}

#[derive(Enum, PartialEq, Clone, Copy)]
enum RoundMode {
    #[name = "Intelligent (sticky)"]
    Intelligent,
    #[name = "Nearest"]
    Nearest,
}

#[derive(Enum, PartialEq, Clone, Copy)]
enum GateMode {
    #[name = "Fresh (tonalize noise)"]
    Fresh,
    #[name = "Bypass (dry noise)"]
    Bypass,
}

struct OpqPlugin {
    params: Arc<OpqParams>,
    engine: Option<Engine>,
    held: [bool; 128],
}

#[derive(Params)]
struct OpqParams {
    #[id = "feel"]
    feel: FloatParam,
    #[id = "glide"]
    glide: FloatParam,
    #[id = "grit"]
    grit: FloatParam,
    #[id = "voices"]
    voices: IntParam,
    #[id = "unowned"]
    map_unowned: BoolParam,
    #[id = "tgate"]
    tonality_gate: FloatParam,
    #[id = "gmode"]
    gate_mode: EnumParam<GateMode>,
    #[id = "fmax"]
    fmax: FloatParam,
    #[id = "tbyp"]
    transient_bypass: BoolParam,
    #[id = "omode"]
    octave_mode: EnumParam<OctaveMode>,
    #[id = "round"]
    rounding: EnumParam<RoundMode>,
    #[id = "mix"]
    mix: FloatParam,
    #[id = "stcoh"]
    coherence: FloatParam,
    #[id = "thresh"]
    threshold: FloatParam,
    #[id = "formant"]
    formant: FloatParam,
    #[id = "carry"]
    carry: FloatParam,
}

impl Default for OpqPlugin {
    fn default() -> Self {
        Self {
            params: Arc::new(OpqParams::default()),
            engine: None,
            held: [false; 128],
        }
    }
}

impl Default for OpqParams {
    fn default() -> Self {
        Self {
            feel: FloatParam::new("Feel", 0.35, FloatRange::Linear { min: 0.0, max: 1.0 })
                .with_unit(" %")
                .with_value_to_string(formatters::v2s_f32_percentage(0))
                .with_string_to_value(formatters::s2v_f32_percentage()),
            glide: FloatParam::new(
                "Glide",
                0.0,
                FloatRange::Linear { min: 0.0, max: 0.5 },
            )
            .with_unit(" s"),
            grit: FloatParam::new("Grit", 0.0, FloatRange::Linear { min: 0.0, max: 1.0 })
                .with_unit(" %")
                .with_value_to_string(formatters::v2s_f32_percentage(0))
                .with_string_to_value(formatters::s2v_f32_percentage()),
            voices: IntParam::new("Voices", 6, IntRange::Linear { min: 1, max: 12 }),
            map_unowned: BoolParam::new("Map Unowned", false),
            tonality_gate: FloatParam::new(
                "Tonality Gate",
                0.0,
                FloatRange::Linear { min: 0.0, max: 6.0 },
            ),
            gate_mode: EnumParam::new("Gate Mode", GateMode::Fresh),
            fmax: FloatParam::new(
                "Map Ceiling",
                5000.0,
                FloatRange::Skewed {
                    min: 1000.0,
                    max: 20000.0,
                    factor: FloatRange::skew_factor(-1.0),
                },
            )
            .with_unit(" Hz"),
            transient_bypass: BoolParam::new("Transient Bypass", true),
            octave_mode: EnumParam::new("MIDI Scope", OctaveMode::Repeat),
            rounding: EnumParam::new("Rounding", RoundMode::Intelligent),
            mix: FloatParam::new("Mix", 1.0, FloatRange::Linear { min: 0.0, max: 1.0 })
                .with_unit(" %")
                .with_value_to_string(formatters::v2s_f32_percentage(0))
                .with_string_to_value(formatters::s2v_f32_percentage()),
            coherence: FloatParam::new(
                "Stereo Coherence",
                1.0,
                FloatRange::Linear { min: 0.0, max: 1.0 },
            )
            .with_unit(" %")
            .with_value_to_string(formatters::v2s_f32_percentage(0))
            .with_string_to_value(formatters::s2v_f32_percentage()),
            threshold: FloatParam::new(
                "Threshold",
                0.0,
                FloatRange::Linear { min: 0.0, max: 100.0 },
            )
            .with_unit(" ct"),
            formant: FloatParam::new(
                "Formant Preserve",
                0.0,
                FloatRange::Linear { min: 0.0, max: 1.0 },
            )
            .with_unit(" %")
            .with_value_to_string(formatters::v2s_f32_percentage(0))
            .with_string_to_value(formatters::s2v_f32_percentage()),
            carry: FloatParam::new(
                "Residual Carry",
                1.0,
                FloatRange::Linear { min: 0.0, max: 1.0 },
            )
            .with_unit(" %")
            .with_value_to_string(formatters::v2s_f32_percentage(0))
            .with_string_to_value(formatters::s2v_f32_percentage()),
        }
    }
}

impl OpqPlugin {
    fn engine_params(&self) -> EngineParams {
        EngineParams {
            voices: self.params.voices.value() as usize,
            unowned: if self.params.map_unowned.value() {
                Unowned::Map
            } else {
                Unowned::Dry
            },
            tonality_gate: self.params.tonality_gate.value() as f64,
            tonality_mode: match self.params.gate_mode.value() {
                GateMode::Fresh => TonalityMode::Fresh,
                GateMode::Bypass => TonalityMode::Bypass,
            },
            fmax_map: self.params.fmax.value() as f64,
            transient_bypass: self.params.transient_bypass.value(),
            flux_thresh: 0.6,
            feel: self.params.feel.value() as f64,
            glide: self.params.glide.value() as f64,
            grit: self.params.grit.value() as f64,
            mode: match self.params.octave_mode.value() {
                OctaveMode::Repeat => Mode::Repeat,
                OctaveMode::Custom => Mode::Custom,
            },
            rounding: match self.params.rounding.value() {
                RoundMode::Nearest => Rounding::Nearest,
                RoundMode::Intelligent => Rounding::Intelligent,
            },
            hyst_cents: 40.0,
            mix: self.params.mix.value() as f64,
            coherence: self.params.coherence.value() as f64,
            threshold_cents: self.params.threshold.value() as f64,
            formant: self.params.formant.value() as f64,
            carry: self.params.carry.value() as f64,
        }
    }
}

impl Plugin for OpqPlugin {
    const NAME: &'static str = "OpenPitchQuant";
    const VENDOR: &'static str = "open-pitch-quant";
    const URL: &'static str = "https://github.com/open-pitch-quant";
    const EMAIL: &'static str = "info@localhost";
    const VERSION: &'static str = env!("CARGO_PKG_VERSION");

    const AUDIO_IO_LAYOUTS: &'static [AudioIOLayout] = &[
        AudioIOLayout {
            main_input_channels: NonZeroU32::new(2),
            main_output_channels: NonZeroU32::new(2),
            aux_input_ports: &[],
            aux_output_ports: &[],
            names: PortNames::const_default(),
        },
        AudioIOLayout {
            main_input_channels: NonZeroU32::new(1),
            main_output_channels: NonZeroU32::new(1),
            aux_input_ports: &[],
            aux_output_ports: &[],
            names: PortNames::const_default(),
        },
    ];

    const MIDI_INPUT: MidiConfig = MidiConfig::Basic;
    const MIDI_OUTPUT: MidiConfig = MidiConfig::None;
    const SAMPLE_ACCURATE_AUTOMATION: bool = false;

    type SysExMessage = ();
    type BackgroundTask = ();

    fn params(&self) -> Arc<dyn Params> {
        self.params.clone()
    }

    fn initialize(
        &mut self,
        audio_io_layout: &AudioIOLayout,
        buffer_config: &BufferConfig,
        context: &mut impl InitContext<Self>,
    ) -> bool {
        let ch = audio_io_layout
            .main_input_channels
            .map(|n| n.get())
            .unwrap_or(2) as usize;
        self.engine = Some(Engine::new(buffer_config.sample_rate as f64, ch));
        context.set_latency_samples(N_FFT as u32);
        true
    }

    fn reset(&mut self) {
        if let Some(e) = &mut self.engine {
            e.reset();
        }
        self.held = [false; 128];
    }

    fn process(
        &mut self,
        buffer: &mut Buffer,
        _aux: &mut AuxiliaryBuffers,
        context: &mut impl ProcessContext<Self>,
    ) -> ProcessStatus {
        // frame granularity is 1024 samples; block-start event drain is fine
        while let Some(event) = context.next_event() {
            match event {
                NoteEvent::NoteOn { note, .. } => self.held[note as usize] = true,
                NoteEvent::NoteOff { note, .. } => self.held[note as usize] = false,
                _ => (),
            }
        }
        let p = self.engine_params();
        if let Some(engine) = &mut self.engine {
            engine.process_block(buffer.as_slice(), &self.held, &p);
        }
        ProcessStatus::Normal
    }
}

impl ClapPlugin for OpqPlugin {
    const CLAP_ID: &'static str = "org.open-pitch-quant.opq";
    const CLAP_DESCRIPTION: Option<&'static str> =
        Some("Real-time polyphonic pitch mapping (open PITCHMAP exploration)");
    const CLAP_MANUAL_URL: Option<&'static str> = None;
    const CLAP_SUPPORT_URL: Option<&'static str> = None;
    const CLAP_FEATURES: &'static [ClapFeature] = &[
        ClapFeature::AudioEffect,
        ClapFeature::PitchShifter,
        ClapFeature::Stereo,
        ClapFeature::Mono,
    ];
}

impl Vst3Plugin for OpqPlugin {
    const VST3_CLASS_ID: [u8; 16] = *b"OpenPitchQuant01";
    const VST3_SUBCATEGORIES: &'static [Vst3SubCategory] =
        &[Vst3SubCategory::Fx, Vst3SubCategory::PitchShift];
}

nih_export_clap!(OpqPlugin);
nih_export_vst3!(OpqPlugin);
