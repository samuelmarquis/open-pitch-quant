//! The board's mounted inventory: offline and native boards use the same
//! bytes. Every file is written by assets/bake.py, which records where it
//! came from in assets/vendor/provenance.json.
panelkit::pack! {
    FONT = "assets/vendor/SourceSansPro-Regular.otf";
    FONT_LICENSE = "assets/vendor/SourceSans-LICENSE.txt";
    /// The monitor housing, our own composer bake at this board's monitor
    /// (2x, drawn whole at layout::HOUSING).
    BEZEL = "assets/vendor/monitor-housing.png";
    /// Voices' stepped knob, the boss over its lens ring: one cell per
    /// step (bake.py STEPPED).
    KNOB_VOICES = "assets/vendor/knobs/knob-voices.png";
    /// The rack plates: each plate's rack scene (its switches and LAW's
    /// chickenhead in their first state) at exactly 2x.
    PLATE_CAPTURE = "assets/vendor/plate-capture.png";
    PLATE_LAW = "assets/vendor/plate-law.png";
    PLATE_FINISH = "assets/vendor/plate-finish.png";
    /// Knob atlases (cepstrum-knob-preview/1), in layout::Skin order.
    KNOB_HIFI = "assets/vendor/knobs/knob-hifi-black-turned.png";
    KNOB_HEADY = "assets/vendor/knobs/knob-heady.png";
    KNOB_CATALIN = "assets/vendor/knobs/knob-catalin.png";
    KNOB_LEATHER = "assets/vendor/knobs/knob-leather-oxblood.png";
    KNOB_EBONY = "assets/vendor/knobs/knob-wood-ebony.png";
    KNOB_HEAT_TINT = "assets/vendor/knobs/knob-chrome-heat-tint.png";
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
    /// The viewer keys, one straight-alpha row in layout::Viewer::ALL order,
    /// each key's inactive then active 128x32 cell (bake.py VIEWER_KEYS).
    VIEWER_KEYS = "assets/vendor/viewer-keys.png";
    /// The family's screen glass (screen-monitor's _vig and _refl, bake.py
    /// GLASS_SID), cropped to the screen and recast for the canvas's blend:
    /// the vignette as black with alpha 1 - vig, the reflection with alpha 0.
    GLASS_VIG = "assets/vendor/glass-vig.png";
    GLASS_REFL = "assets/vendor/glass-refl.png";
}

/// The knob atlases in layout::Skin order.
pub const KNOBS: [&str; 6] = [KNOB_HIFI, KNOB_HEADY, KNOB_CATALIN, KNOB_LEATHER, KNOB_EBONY, KNOB_HEAT_TINT];

/// The rack-baked parts in layout::RACK_PARTS order.
pub const RACK_PARTS: [&str; 8] = [
    RACK_GATE_MODE, RACK_UNOWNED, RACK_TRANSIENTS, RACK_SOURCE, RACK_SCOPE, RACK_ROUNDING,
    RACK_TRANSITIONS, RACK_ALGORITHM,
];
