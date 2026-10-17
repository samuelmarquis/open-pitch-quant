//! The board's mounted inventory: offline and native boards use the same
//! bytes. The rack-* and screen-glass* files are packed by
//! assets/bake_rack.py (recorded in assets/vendor/rack-bake.json); the font
//! is vendored as it stands (assets/vendor/provenance.json).
panelkit::pack! {
    FONT = "assets/vendor/SourceSansPro-Regular.otf";
    FONT_LICENSE = "assets/vendor/SourceSans-LICENSE.txt";
    /// The rack bakes (assets/bake_rack.py, the template's rack_bake.py over
    /// src/rack_layout.rs; manifest assets/vendor/rack-bake.json), all at 2x
    /// over their bake regions. The monitor housing, straight alpha, drawn
    /// whole at layout::HOUSING.
    RACK_MONITOR = "assets/vendor/rack-monitor.png";
    /// The plates, premultiplied, each over bake_region(plate, PLATE_PAD).
    RACK_PLATE_CAPTURE = "assets/vendor/rack-plate-capture.png";
    RACK_PLATE_LAW = "assets/vendor/rack-plate-law.png";
    RACK_PLATE_FINISH = "assets/vendor/rack-plate-finish.png";
    /// The viewer keys, straight alpha, inactive then active, each over its
    /// layout::viewer_key_region.
    RACK_KEY_TRANSECT = "assets/vendor/rack-key-transect.png";
    RACK_KEY_LADDERS = "assets/vendor/rack-key-ladders.png";
    RACK_KEY_SCOPE = "assets/vendor/rack-key-scope.png";
    /// The plate controls, premultiplied, over layout::part_region: the
    /// switches down then up, ALGORITHM HOUSE then ORACLE, Voices' 12 steps
    /// in a row, the knobs' 101 positions 11 to a row.
    RACK_GATE_MODE = "assets/vendor/rack-gate-mode.png";
    RACK_UNOWNED = "assets/vendor/rack-unowned.png";
    RACK_TRANSIENTS = "assets/vendor/rack-transients.png";
    RACK_SOURCE = "assets/vendor/rack-source.png";
    RACK_SCOPE = "assets/vendor/rack-scope.png";
    RACK_ROUNDING = "assets/vendor/rack-rounding.png";
    RACK_TRANSITIONS = "assets/vendor/rack-transitions.png";
    RACK_ALGORITHM = "assets/vendor/rack-algorithm.png";
    RACK_VOICES = "assets/vendor/rack-voices.png";
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
    /// The screen glass (p211 C): the monitor's glass bake, screen-monitor's
    /// reflection and vignette (recorded in rack-bake.json with the rack),
    /// the layers named from the manifest's id (panelkit::pack::
    /// housing_layer) and drawn by panelkit::glass.
    GLASS = "assets/vendor/screen-glass.json";
    GLASS_REFL = "assets/vendor/screen-glass_refl.png";
    GLASS_VIG = "assets/vendor/screen-glass_vig.png";
}


/// The plate controls' bakes, in layout::RACK_PARTS order.
pub const RACK_PARTS: [&str; 19] = [
    RACK_GATE_MODE, RACK_UNOWNED, RACK_TRANSIENTS, RACK_SOURCE, RACK_SCOPE, RACK_ROUNDING,
    RACK_TRANSITIONS, RACK_ALGORITHM, RACK_VOICES, RACK_TONALITY, RACK_CEILING, RACK_FEEL, RACK_GLIDE,
    RACK_THRESHOLD, RACK_PURIFY, RACK_GRIT, RACK_FORMANT, RACK_CARRY, RACK_COHERENCE,
];

/// The viewer keys' bakes, in layout::Viewer::ALL order.
pub const RACK_KEYS: [&str; 3] = [RACK_KEY_TRANSECT, RACK_KEY_LADDERS, RACK_KEY_SCOPE];
