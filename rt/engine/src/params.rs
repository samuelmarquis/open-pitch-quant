//! The parameter schema: one pluginkit `ParamSpec` row per host parameter,
//! shared by the plugin shell, the panel and (eventually) the CLI. Each
//! parameter's id is its index in [`SPECS`]; values are plain (the unit
//! the user reads). [`Params::engine`] turns a set into the engine's
//! [`EngineParams`].
//!
//! The saved document is pluginkit's at exactly [`STATE_VERSION`]: bump it
//! whenever an id, range or meaning changes. Before 1.0 there are no
//! migrations (Sam, 2026-10-09).

use pluginkit::param::{ParamSpec, Text};

use crate::{Algorithm, EngineParams, Mode, Newborn, Rounding, TonalityMode, Unowned};

/// Version 1 was the pre-pluginkit id-keyed document (18 parameters);
/// version 2 is pluginkit's, with ALGORITHM and PURIFY; version 3 adds
/// SOURCE and the key states as the document's product section.
pub const STATE_VERSION: u32 = 3;
pub const PARAM_COUNT: usize = 21;

pub const BYPASS: usize = 0;
pub const MIX: usize = 1;
pub const FEEL: usize = 2;
pub const GLIDE: usize = 3;
pub const GRIT: usize = 4;
pub const VOICES: usize = 5;
pub const UNOWNED: usize = 6;
pub const GATE: usize = 7;
pub const GATE_MODE: usize = 8;
pub const FMAX: usize = 9;
pub const TRANSIENT: usize = 10;
pub const SCOPE: usize = 11;
pub const ROUNDING: usize = 12;
pub const COHERENCE: usize = 13;
pub const THRESHOLD: usize = 14;
pub const FORMANT: usize = 15;
pub const CARRY: usize = 16;
pub const TRANSITIONS: usize = 17;
pub const ALGORITHM: usize = 18;
pub const PURIFY: usize = 19;
pub const SOURCE: usize = 20;

const OFF_ON: Text = Text::Labels(&["Off", "On"]);

/// A whole number: the voice count, the tonality gate's peakiness.
const WHOLE: Text = Text::Custom {
    format: |_, v| format!("{v:.0}"),
    parse: |spec, text| spec.parse_number(text).map(|v| spec.clamp(v)),
};

/// Glide is stored in seconds and reads in milliseconds; typed text is
/// milliseconds unless it ends in a bare `s`.
const MILLISECONDS: Text = Text::Custom {
    format: |_, v| format!("{:.0} ms", v * 1000.0),
    parse: |spec, text| {
        let (number, per_second) = if let Some(ms) = text.strip_suffix("ms") {
            (ms, 1000.0)
        } else if let Some(s) = text.strip_suffix('s') {
            (s, 1.0)
        } else {
            (text, 1000.0)
        };
        let v = number.trim().parse::<f32>().ok()?;
        v.is_finite().then(|| spec.clamp(v / per_second))
    },
};

const fn row(
    id: usize,
    name: &'static str,
    min: f32,
    max: f32,
    default: f32,
    unit: &'static str,
    stepped: bool,
) -> ParamSpec {
    ParamSpec::new(id, name, "", min, max, default, unit, stepped, false, "")
}

const fn labels(id: usize, name: &'static str, names: &'static [&'static str], default: f32) -> ParamSpec {
    row(id, name, 0.0, (names.len() - 1) as f32, default, "", true).with_text(Text::Labels(names))
}

pub static SPECS: [ParamSpec; PARAM_COUNT] = [
    row(BYPASS, "Bypass", 0.0, 1.0, 0.0, "", true).with_text(OFF_ON),
    row(MIX, "Mix", 0.0, 1.0, 1.0, "%", false),
    row(FEEL, "Feel", 0.0, 1.0, 0.35, "%", false),
    row(GLIDE, "Glide", 0.0, 0.5, 0.0, "s", false).with_text(MILLISECONDS),
    row(GRIT, "Grit", 0.0, 1.0, 0.0, "%", false),
    row(VOICES, "Voices", 1.0, 12.0, 6.0, "", true).with_text(WHOLE),
    row(UNOWNED, "Map Unowned", 0.0, 1.0, 0.0, "", true).with_text(OFF_ON),
    row(GATE, "Tonality Gate", 0.0, 6.0, 0.0, "", false).with_text(WHOLE),
    labels(GATE_MODE, "Gate Mode", &["Fresh", "Bypass"], 0.0),
    row(FMAX, "Map Ceiling", 1000.0, 20000.0, 5000.0, "Hz", false),
    row(TRANSIENT, "Transient Bypass", 0.0, 1.0, 1.0, "", true).with_text(OFF_ON),
    labels(SCOPE, "MIDI Scope", &["Repeat", "Custom"], 0.0),
    labels(ROUNDING, "Rounding", &["Intelligent", "Nearest"], 0.0),
    row(COHERENCE, "Stereo Coherence", 0.0, 1.0, 1.0, "%", false),
    row(THRESHOLD, "Threshold", 0.0, 100.0, 0.0, "cents", false),
    row(FORMANT, "Formant Preserve", 0.0, 1.0, 0.0, "%", false),
    row(CARRY, "Residual Carry", 0.0, 1.0, 1.0, "%", false),
    labels(TRANSITIONS, "Transitions", &["Map", "Dry"], 0.0),
    // HOUSE is the current sound (the default, so a fresh instance sounds
    // as the plugin always has); ORACLE is the PITCHMAP-faithful policy.
    labels(ALGORITHM, "Algorithm", &["House", "Oracle"], 0.0),
    row(PURIFY, "Purify", 0.0, 1.0, 0.0, "%", false),
    // Where the target grid comes from: the notes held on the MIDI side
    // chain (PITCHMAP's MIDI MAP), or the keys set on the panel (its
    // Lower Keyboard, with per-key Bypass).
    labels(SOURCE, "Map Source", &["MIDI", "Keys"], 0.0),
];

/// The keys set on the panel, for the Keys source: bit n of `target` is MIDI
/// note n as an allowed target (PITCHMAP's Lower Keyboard, un-Xcluded); bit
/// n of `bypass` lets an object sitting on note n pass unbent. Not host
/// parameters: saved as the document's product section.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Keys {
    pub target: u128,
    pub bypass: u128,
}

impl Default for Keys {
    /// Every note a target, none bypassed: chromatic, as PITCHMAP starts.
    fn default() -> Self {
        Self { target: u128::MAX, bypass: 0 }
    }
}

/// Which of a key's two states an edit touches.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum KeyState {
    Target,
    Bypass,
}

impl Keys {
    pub fn get(&self, state: KeyState, note: u32) -> bool {
        let mask = match state {
            KeyState::Target => self.target,
            KeyState::Bypass => self.bypass,
        };
        note < 128 && mask >> note & 1 == 1
    }

    /// Set `note`'s state to `on`: every octave of it when `repeat`
    /// (PITCHMAP's Repeat), else that note alone (Custom).
    pub fn set(&mut self, state: KeyState, note: u32, on: bool, repeat: bool) {
        let mask = match state {
            KeyState::Target => &mut self.target,
            KeyState::Bypass => &mut self.bypass,
        };
        let notes = (0..128u32).filter(|&n| if repeat { n % 12 == note % 12 } else { n == note });
        for n in notes {
            if on {
                *mask |= 1 << n;
            } else {
                *mask &= !(1 << n);
            }
        }
    }

    /// The target grid as the engine's held-note array.
    pub fn held(&self) -> [bool; 128] {
        std::array::from_fn(|n| self.target >> n & 1 == 1)
    }
}

/// The whole parameter set, plain values indexed by id.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Params {
    pub values: [f32; PARAM_COUNT],
}

impl Default for Params {
    fn default() -> Self {
        Self {
            values: std::array::from_fn(|id| SPECS[id].default),
        }
    }
}

impl Params {
    pub fn get(&self, id: usize) -> f32 {
        self.values[id]
    }

    /// pluginkit's write rule: finite, clamped, unknown ids ignored.
    pub fn set(&mut self, id: usize, value: f32) {
        pluginkit::param::write(&mut self.values, &SPECS, None, id, value, &mut |_, _, _| {});
    }

    fn on(&self, id: usize) -> bool {
        self.values[id] >= 0.5
    }

    /// The grid comes from the panel's keys, not the MIDI side chain.
    pub fn keys_source(&self) -> bool {
        self.on(SOURCE)
    }

    /// The engine's view of this set. Bypass is realized as mix = 0: the
    /// engine's dry path is latency-aligned, so bypass is click-free and
    /// delay-compensated.
    pub fn engine(&self) -> EngineParams {
        let v = |id: usize| self.values[id] as f64;
        EngineParams {
            algorithm: if self.on(ALGORITHM) {
                Algorithm::Oracle
            } else {
                Algorithm::House
            },
            purify: v(PURIFY),
            voices: self.values[VOICES].round().clamp(1.0, 12.0) as usize,
            unowned: if self.on(UNOWNED) { Unowned::Map } else { Unowned::Dry },
            tonality_gate: v(GATE),
            tonality_mode: if self.on(GATE_MODE) {
                TonalityMode::Bypass
            } else {
                TonalityMode::Fresh
            },
            fmax_map: v(FMAX),
            transient_bypass: self.on(TRANSIENT),
            feel: v(FEEL),
            glide: v(GLIDE),
            grit: v(GRIT),
            mode: if self.on(SCOPE) { Mode::Custom } else { Mode::Repeat },
            rounding: if self.on(ROUNDING) {
                Rounding::Nearest
            } else {
                Rounding::Intelligent
            },
            mix: if self.on(BYPASS) { 0.0 } else { v(MIX) },
            coherence: v(COHERENCE),
            threshold_cents: v(THRESHOLD),
            formant: v(FORMANT),
            carry: v(CARRY),
            newborn: if self.on(TRANSITIONS) { Newborn::Dry } else { Newborn::Map },
            // not host parameters: the engine's tuned constants
            ..EngineParams::default()
        }
    }
}

/// The parameter set as pluginkit's sync sees it.
pub struct ParamSchema;
/// One editor operation or host timestamp of edits.
pub type ParameterBatch = pluginkit::sync::Batch<ParamSchema, PARAM_COUNT>;

impl pluginkit::sync::Schema<PARAM_COUNT> for ParamSchema {
    type Params = Params;
    fn spec(id: usize) -> Option<&'static ParamSpec> {
        SPECS.get(id)
    }
    fn value(params: &Params, id: usize) -> f32 {
        params.values[id]
    }
    fn store(params: &mut Params, id: usize, value: f32) {
        params.values[id] = value;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ids_match_rows() {
        for (i, s) in SPECS.iter().enumerate() {
            assert_eq!(s.id, i, "{}", s.name);
        }
    }

    #[test]
    fn defaults_are_accepted_and_ranges_normalize() {
        for s in SPECS.iter() {
            assert!(s.max > s.min, "{}", s.name);
            assert!(s.accepts(s.default), "{}", s.name);
            assert!(s.normalized(s.default).is_finite(), "{}", s.name);
        }
    }

    /// The defaults are the engine's own: a fresh instance plays HOUSE as
    /// the plugin always has.
    #[test]
    fn the_default_set_is_the_engines_default() {
        let p = Params::default().engine();
        let e = EngineParams::default();
        assert!(p.algorithm == Algorithm::House);
        assert_eq!(p.purify, e.purify);
        assert_eq!(p.voices, e.voices);
        assert!(p.unowned == e.unowned && p.mode == e.mode && p.rounding == e.rounding);
        assert!(p.tonality_mode == e.tonality_mode && p.newborn == e.newborn);
        assert_eq!(p.transient_bypass, e.transient_bypass);
        assert_eq!(
            [p.tonality_gate, p.fmax_map, p.glide, p.grit, p.mix, p.coherence],
            [e.tonality_gate, e.fmax_map, e.glide, e.grit, e.mix, e.coherence]
        );
        assert_eq!([p.threshold_cents, p.formant, p.carry], [e.threshold_cents, e.formant, e.carry]);
        assert!((p.feel - e.feel).abs() < 1e-6, "{}", p.feel);
    }

    #[test]
    fn the_new_two_reach_the_engine() {
        let mut p = Params::default();
        p.set(ALGORITHM, 1.0);
        p.set(PURIFY, 0.4);
        let e = p.engine();
        assert!(e.algorithm == Algorithm::Oracle);
        assert!((e.purify - 0.4).abs() < 1e-6);
        p.set(BYPASS, 1.0);
        assert_eq!(p.engine().mix, 0.0);
    }

    #[test]
    fn text_round_trips() {
        let glide = &SPECS[GLIDE];
        assert_eq!(glide.format(0.12), "120 ms");
        assert_eq!(glide.parse("120 ms"), Some(0.12));
        assert_eq!(glide.parse("120"), Some(0.12));
        assert_eq!(glide.parse("0.2 s"), Some(0.2));
        assert_eq!(SPECS[VOICES].format(6.0), "6");
        assert_eq!(SPECS[VOICES].parse("7"), Some(7.0));
        assert_eq!(SPECS[ALGORITHM].format(1.0), "Oracle");
        assert_eq!(SPECS[ALGORITHM].parse("house"), Some(0.0));
        assert_eq!(SPECS[PURIFY].format(0.25), "25%");
        assert_eq!(SPECS[BYPASS].format(1.0), "On");
        assert_eq!(SPECS[SOURCE].format(1.0), "Keys");
    }

    #[test]
    fn keys_set_one_note_or_every_octave() {
        let mut k = Keys { target: 0, bypass: 0 };
        k.set(KeyState::Target, 60, true, false);
        assert!(k.get(KeyState::Target, 60) && !k.get(KeyState::Target, 72));
        k.set(KeyState::Target, 64, true, true);
        assert!((0..128).filter(|n| n % 12 == 4).all(|n| k.get(KeyState::Target, n)));
        k.set(KeyState::Target, 76, false, true);
        assert!(!k.get(KeyState::Target, 64));
        k.set(KeyState::Bypass, 67, true, false);
        assert!(k.get(KeyState::Bypass, 67) && !k.get(KeyState::Target, 67));
        assert_eq!(k.held().iter().filter(|&&h| h).count(), 1);
        assert_eq!(Keys::default().held(), [true; 128]);
    }
}
