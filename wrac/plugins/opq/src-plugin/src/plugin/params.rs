//! The host-facing parameter table. Adding a parameter starts here; count,
//! info, conversions, defaults, and persistence all derive from this table.
//!
//! Parameter IDs are host/project ABI. Never renumber an existing id after
//! publishing; add new ids instead.

use std::sync::Arc;

use wrac_clap_adapter::{
    ParamFlags, ParamInfo, ParamInputEvents, PluginError, PluginParamsExtension, PluginResult,
};

use crate::state::SharedState;

pub(crate) const PARAM_BYPASS_ID: u32 = 0;
pub(crate) const PARAM_MIX_ID: u32 = 1;
pub(crate) const PARAM_FEEL_ID: u32 = 2;
pub(crate) const PARAM_GLIDE_ID: u32 = 3;
pub(crate) const PARAM_GRIT_ID: u32 = 4;
pub(crate) const PARAM_VOICES_ID: u32 = 5;
pub(crate) const PARAM_UNOWNED_ID: u32 = 6;
pub(crate) const PARAM_GATE_ID: u32 = 7;
pub(crate) const PARAM_GATE_MODE_ID: u32 = 8;
pub(crate) const PARAM_FMAX_ID: u32 = 9;
pub(crate) const PARAM_TRANSIENT_ID: u32 = 10;
pub(crate) const PARAM_SCOPE_ID: u32 = 11;
pub(crate) const PARAM_ROUNDING_ID: u32 = 12;
pub(crate) const PARAM_COHERENCE_ID: u32 = 13;
pub(crate) const PARAM_THRESHOLD_ID: u32 = 14;
pub(crate) const PARAM_FORMANT_ID: u32 = 15;
pub(crate) const PARAM_CARRY_ID: u32 = 16;
pub(crate) const PARAM_TRANSITIONS_ID: u32 = 17;

/// How a parameter formats/parses its value text.
#[derive(Debug, Clone, Copy)]
enum Format {
    Percent,
    Seconds,
    Hertz,
    Cents,
    Integer,
    Choice(&'static [&'static str]),
}

#[derive(Debug, Clone, Copy)]
struct ParameterSpec {
    info: ParamInfo,
    format: Format,
}

const fn flags(stepped: bool, is_enum: bool, is_bypass: bool) -> ParamFlags {
    ParamFlags {
        is_stepped: stepped,
        is_periodic: false,
        is_hidden: false,
        is_readonly: false,
        is_bypass,
        is_automatable: true,
        is_automatable_per_note_id: false,
        is_automatable_per_key: false,
        is_automatable_per_channel: false,
        is_automatable_per_port: false,
        is_modulatable: false,
        is_modulatable_per_note_id: false,
        is_modulatable_per_key: false,
        is_modulatable_per_channel: false,
        is_modulatable_per_port: false,
        requires_process: false,
        is_enum,
    }
}

const fn continuous(
    id: u32,
    name: &'static str,
    min: f64,
    max: f64,
    default: f64,
    format: Format,
) -> ParameterSpec {
    ParameterSpec {
        info: ParamInfo {
            id,
            name,
            module: "",
            min_value: min,
            max_value: max,
            default_value: default,
            flags: flags(false, false, false),
        },
        format,
    }
}

const fn choice(
    id: u32,
    name: &'static str,
    names: &'static [&'static str],
    default: f64,
    is_bypass: bool,
) -> ParameterSpec {
    ParameterSpec {
        info: ParamInfo {
            id,
            name,
            module: "",
            min_value: 0.0,
            max_value: (names.len() - 1) as f64,
            default_value: default,
            flags: flags(true, true, is_bypass),
        },
        format: Format::Choice(names),
    }
}

const OFF_ON: &[&str] = &["Off", "On"];

// Host domain == plain domain for every parameter (CLAP allows arbitrary
// ranges; wrappers normalize internally). Conversions are clamp-identity.
const PARAM_SPECS: &[ParameterSpec] = &[
    choice(PARAM_BYPASS_ID, "Bypass", OFF_ON, 0.0, true),
    continuous(PARAM_MIX_ID, "Mix", 0.0, 1.0, 1.0, Format::Percent),
    continuous(PARAM_FEEL_ID, "Feel", 0.0, 1.0, 0.35, Format::Percent),
    continuous(PARAM_GLIDE_ID, "Glide", 0.0, 0.5, 0.0, Format::Seconds),
    continuous(PARAM_GRIT_ID, "Grit", 0.0, 1.0, 0.0, Format::Percent),
    ParameterSpec {
        info: ParamInfo {
            id: PARAM_VOICES_ID,
            name: "Voices",
            module: "",
            min_value: 1.0,
            max_value: 12.0,
            default_value: 6.0,
            flags: flags(true, false, false),
        },
        format: Format::Integer,
    },
    choice(PARAM_UNOWNED_ID, "Map Unowned", OFF_ON, 0.0, false),
    continuous(PARAM_GATE_ID, "Tonality Gate", 0.0, 6.0, 0.0, Format::Integer),
    choice(
        PARAM_GATE_MODE_ID,
        "Gate Mode",
        &["Fresh", "Bypass"],
        0.0,
        false,
    ),
    continuous(PARAM_FMAX_ID, "Map Ceiling", 1000.0, 20000.0, 5000.0, Format::Hertz),
    choice(PARAM_TRANSIENT_ID, "Transient Bypass", OFF_ON, 1.0, false),
    choice(
        PARAM_SCOPE_ID,
        "MIDI Scope",
        &["Repeat", "Custom"],
        0.0,
        false,
    ),
    choice(
        PARAM_ROUNDING_ID,
        "Rounding",
        &["Intelligent", "Nearest"],
        0.0,
        false,
    ),
    continuous(PARAM_COHERENCE_ID, "Stereo Coherence", 0.0, 1.0, 1.0, Format::Percent),
    continuous(PARAM_THRESHOLD_ID, "Threshold", 0.0, 100.0, 0.0, Format::Cents),
    continuous(PARAM_FORMANT_ID, "Formant Preserve", 0.0, 1.0, 0.0, Format::Percent),
    continuous(PARAM_CARRY_ID, "Residual Carry", 0.0, 1.0, 1.0, Format::Percent),
    choice(
        PARAM_TRANSITIONS_ID,
        "Transitions",
        &["Map", "Dry"],
        0.0,
        false,
    ),
];

fn param_spec(id: u32) -> PluginResult<&'static ParameterSpec> {
    PARAM_SPECS
        .iter()
        .find(|spec| spec.info.id == id)
        .ok_or(PluginError::InvalidParameter)
}

pub(crate) fn param_exists(id: u32) -> bool {
    PARAM_SPECS.iter().any(|spec| spec.info.id == id)
}

pub(crate) fn param_clamp(id: u32, value: f32) -> f32 {
    match param_spec(id) {
        Ok(spec) => value.clamp(spec.info.min_value as f32, spec.info.max_value as f32),
        Err(_) => value,
    }
}

pub(crate) fn param_default(id: u32) -> f32 {
    param_spec(id).map(|s| s.info.default_value as f32).unwrap_or(0.0)
}

pub(crate) fn parameter_infos() -> impl Iterator<Item = ParamInfo> {
    PARAM_SPECS.iter().map(|spec| spec.info)
}

fn value_to_text(spec: &ParameterSpec, value: f64) -> String {
    match spec.format {
        Format::Percent => format!("{:.0} %", value * 100.0),
        Format::Seconds => format!("{:.0} ms", value * 1000.0),
        Format::Hertz => format!("{:.0} Hz", value),
        Format::Cents => format!("{:.0} ct", value),
        Format::Integer => format!("{:.0}", value),
        Format::Choice(names) => {
            let idx = (value.round() as usize).min(names.len() - 1);
            names[idx].to_string()
        }
    }
}

fn text_to_plain(spec: &ParameterSpec, text: &str) -> PluginResult<f64> {
    let text = text.trim();
    if let Format::Choice(names) = spec.format {
        if let Some(idx) = names
            .iter()
            .position(|n| n.eq_ignore_ascii_case(text))
        {
            return Ok(idx as f64);
        }
    }
    let numeric: String = text
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.' || *c == '-' || *c == '+')
        .collect();
    let mut v: f64 = numeric.parse().map_err(|_| PluginError::InvalidParameter)?;
    match spec.format {
        Format::Percent => v /= 100.0,
        Format::Seconds => {
            if text.contains("ms") {
                v /= 1000.0;
            }
        }
        _ => {}
    }
    Ok(v.clamp(spec.info.min_value, spec.info.max_value))
}

pub(crate) struct OpqParamsExtension {
    shared: Arc<SharedState>,
}

impl OpqParamsExtension {
    pub(crate) fn new(shared: Arc<SharedState>) -> Self {
        Self { shared }
    }
}

impl PluginParamsExtension for OpqParamsExtension {
    fn param_count(&self) -> u32 {
        PARAM_SPECS.len() as u32
    }

    fn param_info(&self, index: u32) -> Option<ParamInfo> {
        PARAM_SPECS.get(index as usize).map(|spec| spec.info)
    }

    fn param_value(&self, param_id: u32) -> PluginResult<f64> {
        param_spec(param_id)?;
        self.shared
            .parameter_value(param_id)
            .map(f64::from)
            .ok_or(PluginError::InvalidParameter)
    }

    fn apply_param_events(&self, events: ParamInputEvents<'_>) -> PluginResult<()> {
        for event in events.values() {
            if self
                .shared
                .set_parameter_value(event.param_id, event.value)
                .is_none()
            {
                wrac_log::rtwarn!(
                    "params.flush: ignoring unknown parameter id={} value={}",
                    event.param_id,
                    event.value
                );
            }
        }
        Ok(())
    }

    fn value_to_text(&self, param_id: u32, value: f64) -> PluginResult<String> {
        Ok(value_to_text(param_spec(param_id)?, value))
    }

    fn text_to_value(&self, param_id: u32, text: &str) -> PluginResult<f64> {
        text_to_plain(param_spec(param_id)?, text)
    }
}
