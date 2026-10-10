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
    /// The rack plates, panel-board bakes at exactly their 2x size.
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
    /// The algorithm's chickenhead at its two positions.
    SELECTOR_HOUSE = "assets/vendor/selector-house.png";
    SELECTOR_ORACLE = "assets/vendor/selector-oracle.png";
    TOGGLE_UP = "assets/vendor/toggle-up.png";
    TOGGLE_DOWN = "assets/vendor/toggle-down.png";
    /// The viewer keys, one straight-alpha row in layout::Viewer::ALL order,
    /// each key's inactive then active 128x32 cell (bake.py VIEWER_KEYS).
    VIEWER_KEYS = "assets/vendor/viewer-keys.png";
}

/// The knob atlases in layout::Skin order.
pub const KNOBS: [&str; 6] = [KNOB_HIFI, KNOB_HEADY, KNOB_CATALIN, KNOB_LEATHER, KNOB_EBONY, KNOB_HEAT_TINT];
