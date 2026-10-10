//! The board's mounted inventory: offline and native boards use the same
//! bytes. Every file is written by assets/bake.py, which records where it
//! came from in assets/vendor/provenance.json.
panelkit::pack! {
    FONT = "assets/vendor/SourceSansPro-Regular.otf";
    FONT_LICENSE = "assets/vendor/SourceSans-LICENSE.txt";
    /// The monitor housing, OpenCepstrum's bake (2x, 1068x489 logical,
    /// 24 px bezel), nine-sliced to this board's monitor.
    BEZEL = "assets/vendor/monitor-housing.png";
    /// The rack plates, panel-board bakes at exactly their 2x size.
    PLATE_CAPTURE = "assets/vendor/plate-capture.png";
    PLATE_LAW = "assets/vendor/plate-law.png";
    PLATE_FINISH = "assets/vendor/plate-finish.png";
    PLATE_MODULE = "assets/vendor/plate-module.png";
    /// Knob atlases (cepstrum-knob-preview/1), in layout::Skin order.
    KNOB_HIFI = "assets/vendor/knobs/knob-hifi-black-turned.png";
    KNOB_HEADY = "assets/vendor/knobs/knob-heady.png";
    KNOB_CATALIN = "assets/vendor/knobs/knob-catalin.png";
    KNOB_LEATHER = "assets/vendor/knobs/knob-leather-oxblood.png";
    KNOB_EBONY = "assets/vendor/knobs/knob-wood-ebony.png";
    KNOB_HEAT_TINT = "assets/vendor/knobs/knob-chrome-heat-tint.png";
    KNOB_DAVIES = "assets/vendor/knobs/knob-davies-black.png";
    KNOB_COBALT = "assets/vendor/knobs/knob-ceramic-cobalt.png";
    /// The algorithm's chickenhead at its two positions.
    SELECTOR_HOUSE = "assets/vendor/selector-house.png";
    SELECTOR_ORACLE = "assets/vendor/selector-oracle.png";
    TOGGLE_UP = "assets/vendor/toggle-up.png";
    TOGGLE_DOWN = "assets/vendor/toggle-down.png";
    LED_GREEN_OFF = "assets/vendor/led-green-off.png";
    LED_GREEN_ON = "assets/vendor/led-green-on.png";
    LED_AMBER_OFF = "assets/vendor/led-amber-off.png";
    LED_AMBER_ON = "assets/vendor/led-amber-on.png";
}

/// The knob atlases in layout::Skin order.
pub const KNOBS: [&str; 8] = [
    KNOB_HIFI,
    KNOB_HEADY,
    KNOB_CATALIN,
    KNOB_LEATHER,
    KNOB_EBONY,
    KNOB_HEAT_TINT,
    KNOB_DAVIES,
    KNOB_COBALT,
];
