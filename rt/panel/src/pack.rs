//! The board's mounted inventory: offline and native boards use the same
//! bytes. Every file is written by assets/bake.py, which records where it
//! came from in assets/vendor/provenance.json.
panelkit::pack! {
    FONT = "assets/vendor/SourceSansPro-Regular.otf";
    FONT_LICENSE = "assets/vendor/SourceSans-LICENSE.txt";
    /// The monitor housing, our own composer bake at this board's monitor
    /// (2x, drawn whole at layout::HOUSING).
    BEZEL = "assets/vendor/monitor-housing.png";
    /// The rack plates: each plate's rack scene (its switches and LAW's
    /// chickenhead in their first state) at exactly 2x.
    PLATE_CAPTURE = "assets/vendor/plate-capture.png";
    PLATE_LAW = "assets/vendor/plate-law.png";
    PLATE_FINISH = "assets/vendor/plate-finish.png";
    /// The parts baked with the plates (bake.py RACK_PLATES): each one's
    /// cell, cropped from its plate's frames, one cell per state, side by
    /// side (down then up; HOUSE then ORACLE).
    RACK_GATE_MODE = "assets/vendor/rack-gate-mode.png";
    RACK_UNOWNED = "assets/vendor/rack-unowned.png";
    RACK_TRANSIENTS = "assets/vendor/rack-transients.png";
    RACK_SOURCE = "assets/vendor/rack-source.png";
    RACK_SCOPE = "assets/vendor/rack-scope.png";
    RACK_ROUNDING = "assets/vendor/rack-rounding.png";
    RACK_TRANSITIONS = "assets/vendor/rack-transitions.png";
    RACK_ALGORITHM = "assets/vendor/rack-algorithm.png";
    /// Voices' boss over its lens ring, one cell per step.
    RACK_VOICES = "assets/vendor/rack-voices.png";
    /// The continuous knobs, 101 positions each (bake.py KNOB_PARTS).
    RACK_TONALITY = "assets/vendor/rack-tonality.png";
    RACK_CEILING = "assets/vendor/rack-ceiling.png";
    RACK_FEEL = "assets/vendor/rack-feel.png";
    RACK_GLIDE = "assets/vendor/rack-glide.png";
    RACK_THRESHOLD = "assets/vendor/rack-threshold.png";
    RACK_PURIFY = "assets/vendor/rack-purify.png";
    RACK_GRIT = "assets/vendor/rack-grit.png";
    RACK_FORMANT = "assets/vendor/rack-formant.png";
    RACK_CARRY = "assets/vendor/rack-carry.png";
    RACK_COHERENCE = "assets/vendor/rack-coherence.png";
    /// The viewer keys, one straight-alpha row in layout::Viewer::ALL order,
    /// each key's inactive then active 128x32 cell (bake.py VIEWER_KEYS).
    VIEWER_KEYS = "assets/vendor/viewer-keys.png";
    /// The family's screen glass (screen-monitor's _vig and _refl, bake.py
    /// GLASS_SID), cropped to the screen and recast for the canvas's blend:
    /// the vignette as black with alpha 1 - vig, the reflection with alpha 0.
    GLASS_VIG = "assets/vendor/glass-vig.png";
    GLASS_REFL = "assets/vendor/glass-refl.png";
}


/// The rack-baked parts in layout::RACK_PARTS order.
pub const RACK_PARTS: [&str; 19] = [
    RACK_GATE_MODE, RACK_UNOWNED, RACK_TRANSIENTS, RACK_SOURCE, RACK_SCOPE, RACK_ROUNDING,
    RACK_TRANSITIONS, RACK_ALGORITHM, RACK_VOICES, RACK_TONALITY, RACK_CEILING, RACK_FEEL, RACK_GLIDE,
    RACK_THRESHOLD, RACK_PURIFY, RACK_GRIT, RACK_FORMANT, RACK_CARRY, RACK_COHERENCE,
];
