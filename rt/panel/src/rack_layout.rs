//! The board as one layout for open-plugin-template's rack composer
//! (`components/_studio/rack.py`), the family's shared pipeline (Sam,
//! 2026-10-17: "EVERY plugin has the SAME lighting and scene idioms and
//! rendering pipelines"). Every Blender-made part the board mounts sits at
//! the place the board draws it, as the canonical component and flags that
//! build it, with the bakes the template's driver (`rack_bake.py`, through
//! assets/bake_rack.py) renders of it. The shape is open-spectrum's and
//! open-comp's.
//!
//! The scene is the whole window's (template 229a80c): one light, one
//! camera, its cards over the whole board. Each bake renders its region of
//! that scene: a plate alone, and a part over its plate held out as a matte
//! (so the part comes with its own shadow on the plate, nothing else).
//!
//! Rects are logical board px `[x, y, w, h]`, y down, from [`crate::layout`];
//! the composer puts an element's origin at its rect's centre. The screen's
//! content, the infotext, the strip and all type are drawn at runtime.
use crate::layout::{self as L, Kind, Plate, Skin, Viewer, Widget};
use panelkit::canvas::Rect;
use serde_json::{json, Value};

pub const SCHEMA: &str = "opq-rack-layout/1";

/// Logical px per world unit: the family's 1 unit = 100 px = 25 mm.
pub const PX_PER_UNIT: f32 = 100.0;
/// The composer's camera height over the rack centre, world units.
const VIEW: f32 = 12.0;

/// The monitor housing (Sam on p179: "beige plastic is best"), an lcd
/// screen-monitor at 2x whose aperture is the screen.
const HOUSING_FLAGS: [&str; 16] = [
    "--style", "lcd", "--bezel", "beige-plastic", "--fasteners", "none", "--aperture", "48,48,2040,820",
    "--margin", "0", "--corner-r", "0", "--overscan", "0", "--res", "2136x916",
];

/// The plates' faces: CAPTURE anodized blue (Sam, 2026-10-10), LAW the
/// mirror brass (Sam, p217: "I actually kind of prefer the as-shipped/mirror
/// to satin"), FINISH the polished catalin jade (Sam, p181).
fn plate_face(plate: Plate) -> [&'static str; 4] {
    match plate {
        Plate::Capture => ["--face", "anodized-blue", "--fasteners", "screws"],
        Plate::Law => ["--face", "brass", "--fasteners", "screws"],
        Plate::Finish => ["--face", "catalin-jade-polished", "--fasteners", "rivets"],
        Plate::Bottom => unreachable!("the bottom row is not a plate"),
    }
}
const PLATE_EDGE: [&str; 8] = ["--edge", "flat", "--corner", ".015", "--bevel", ".04", "--bevel-segments", "4"];

/// A knob skin's component and preset (open-cepstrum's knob previews').
fn skin(skin: Skin) -> (&'static str, &'static str) {
    match skin {
        Skin::Hifi => ("knob-hifi", "black"),
        Skin::Heady => ("knob-heady", "implosion"),
        Skin::Catalin => ("knob-catalin", "butterscotch"),
        Skin::Leather => ("knob-leather", "oxblood"),
        Skin::Ebony => ("knob-wood", "ebony"),
        Skin::HeatTint => ("knob-chrome", "heat-tint"),
    }
}

/// The viewer keys' faces: label and LED hue (DESIGN's p200 B: the
/// housing's own plastic under a dark legend).
fn key_face(viewer: Viewer) -> (&'static str, &'static str) {
    match viewer {
        Viewer::Transect => ("TRANSECT", "1f388c"),
        Viewer::Ladders => ("LADDERS", "cc341a"),
        Viewer::Scope => ("SCOPE", "2a7f62"),
    }
}

fn rect(r: Rect) -> Value {
    json!([tidy(r.x), tidy(r.y), tidy(r.w), tidy(r.h)])
}

/// A logical px value to 2 decimals, without f32's widening noise.
fn tidy(v: f32) -> f64 {
    (v as f64 * 100.0).round() / 100.0
}

fn units(px: f32) -> String {
    format!("{}", tidy(px / PX_PER_UNIT))
}

/// One bake of an element: its output under rt/panel, its grid of states.
fn bake(out: &str, grid: (usize, usize), straight: bool) -> Value {
    json!({
        "out": format!("assets/vendor/{out}"),
        "flags": [],
        "grid": [grid.0, grid.1],
        "alpha": if straight { "straight" } else { "premultiplied" },
    })
}

/// A plate's element id.
pub fn plate_id(plate: Plate) -> &'static str {
    match plate {
        Plate::Capture => "plate-capture",
        Plate::Law => "plate-law",
        Plate::Finish => "plate-finish",
        Plate::Bottom => unreachable!("the bottom row is not a plate"),
    }
}

/// A part's element id: its caption, lower-case and hyphenated
/// ("GATE MODE" is gate-mode).
pub fn part_id(widget: &Widget) -> String {
    widget.caption.to_ascii_lowercase().replace(' ', "-")
}

/// A viewer key's element id.
pub fn key_id(viewer: Viewer) -> String {
    format!("key-{}", viewer.label().to_ascii_lowercase())
}

/// The layout for the board, as pretty JSON.
pub fn rack_layout() -> String {
    let mut els: Vec<Value> = Vec::new();

    // The monitor housing, drawn orthographically so its bezel registers
    // with the runtime screen.
    els.push(json!({
        "id": "monitor",
        "component": "screen-monitor",
        "flags": HOUSING_FLAGS,
        "rect": rect(L::MONITOR),
        "fit": "width",
        "orthographic": true,
        "region": rect(L::HOUSING),
        "mattes": [],
        // The housing, then its screen glass (the template's glass bake
        // kind: screen-glass.json with its raw _refl and _vig layers, which
        // panelkit's glass::Glass loads and draws over SCREEN).
        "bakes": [
            bake("rack-monitor.png", (1, 1), true),
            json!({"kind": "glass", "out": "assets/vendor/screen-glass.json"}),
        ],
    }));

    // The viewer keys, named by their place in the monitor's right key row
    // (p197): rack.py writes their rect, fit and seat, and layout::viewer_key
    // matches it. The whole row comes along, held out, so it runs unbroken.
    for viewer in Viewer::ALL {
        let id = key_id(viewer);
        let (text, hue) = key_face(viewer);
        els.push(json!({
            "id": id,
            "component": "button-bezel",
            "flags": [
                "--variant", "wide", "--body", "beige-plastic", "--text-color", "1b1b1b",
                "--text", text, "--led-end", "left", "--hue", hue, "--bloom", "off",
                "--font", "mono", "--font-weight", "bold", "--width", "56", "--height", "14",
                "--cap-height", "5.75", "--travel", "0.65", "--state", "inactive",
            ],
            "key": ["monitor", -(viewer.index() as i64) - 1, L::VIEWER_KEY.0],
            "region": rect(L::viewer_key_region(viewer)),
            "states": format!("{id}:--state=inactive,active"),
            "mattes": std::iter::once("monitor".to_string())
                .chain(Viewer::ALL.into_iter().filter(|v| *v != viewer).map(key_id))
                .collect::<Vec<_>>(),
            "feather": L::BAKE_FEATHER,
            // Straight alpha: panelkit's widgets::Keys draws keys as art.
            "bakes": [bake(&format!("rack-{id}.png"), (2, 1), true)],
        }));
    }

    // The plates.
    for plate in [Plate::Capture, Plate::Law, Plate::Finish] {
        let r = L::plate_rect(plate);
        let mut flags: Vec<String> = vec!["--w".into(), units(r.w), "--h".into(), units(r.h)];
        flags.extend(plate_face(plate).iter().chain(PLATE_EDGE.iter()).map(|s| s.to_string()));
        els.push(json!({
            "id": plate_id(plate),
            "component": "panel-board",
            "flags": flags,
            "rect": rect(r),
            "region": rect(L::bake_region(r, L::PLATE_PAD)),
            "mattes": [],
            "bakes": [bake(&format!("rack-{}.png", plate_id(plate)), (1, 1), false)],
        }));
    }

    // Every plate control, standing on its plate's face, over the plate
    // held out.
    for widget in L::WIDGETS.iter().filter(|w| w.plate != Plate::Bottom) {
        let id = part_id(widget);
        let plate = plate_id(widget.plate);
        let (cx, cy) = widget.at;
        let square = |d: f32| Rect::new(cx - d * 0.5, cy - d * 0.5, d, d);
        let region = rect(L::part_region(widget));
        match widget.kind {
            Kind::Knob(s) => {
                let (component, preset) = skin(s);
                els.push(json!({
                    "id": id,
                    "component": component,
                    "flags": ["--preset", preset, "--start-deg", "-135", "--end-deg", "-45", "--value", "0"],
                    "rect": rect(L::rack_rect(widget)),
                    "fit": "diameter",
                    "z": "seat",
                    "region": region,
                    "states": format!("{id}:--value=0..1/{}", L::KNOB_FRAMES),
                    "mattes": [plate],
                    "feather": L::BAKE_FEATHER,
                    "bakes": [bake(&format!("rack-{id}.png"), L::KNOB_GRID, false)],
                }));
            }
            Kind::Stepped => {
                // Voices: DESIGN's boss over its lens ring (Sam on p180),
                // stepping together through the 12 detents (rack.py drives
                // both from one state list, template e82dedd). Fits are
                // DESIGN's: boss 55 px, ring 70, both seated.
                let ring = format!("{id}-ring");
                els.push(json!({
                    "id": ring,
                    "component": "knob-ring",
                    "flags": ["--segments", "12", "--from", "0", "--start-deg", "-135", "--end-deg", "-45",
                              "--hue", "amber", "--value", "0"],
                    "rect": rect(square(L::VOICES_RING)),
                    "fit": "diameter",
                    "z": "seat",
                }));
                els.push(json!({
                    "id": id,
                    "component": "knob-boss",
                    "flags": ["--body", "pom-white", "--cap", "aluminium-spun", "--detents", "12",
                              "--start-deg", "-135", "--end-deg", "-45", "--value", "0"],
                    "rect": rect(L::rack_rect(widget)),
                    "fit": "diameter",
                    "z": "seat",
                    "region": region,
                    "states": format!("{id},{ring}:--value=0..1/{}", L::VOICES_STEPS),
                    "with": [ring],
                    "mattes": [plate],
                    "feather": L::BAKE_FEATHER,
                    "bakes": [bake(&format!("rack-{id}.png"), (L::VOICES_STEPS, 1), false)],
                }));
            }
            Kind::Toggle(..) => {
                // DESIGN's toggle-tab (Sam, p214 D), fitted 30 px wide.
                els.push(json!({
                    "id": id,
                    "component": "toggle-tab",
                    "flags": ["--state", "down"],
                    "rect": rect(L::rack_rect(widget)),
                    "fit": "width",
                    "z": "seat",
                    "region": region,
                    "states": format!("{id}:--state=down,up"),
                    "mattes": [plate],
                    "feather": L::BAKE_FEATHER,
                    "bakes": [bake(&format!("rack-{id}.png"), (2, 1), false)],
                }));
            }
            Kind::Selector => {
                // The chickenhead, fitted at 102 px so its drum is 43 px
                // (DESIGN's refit, pass 54); its 5-detent throw puts HOUSE at
                // 0.25 and ORACLE at 0.75.
                els.push(json!({
                    "id": id,
                    "component": "knob-chickenhead",
                    "flags": ["--color", "black", "--value", "0.25"],
                    "rect": rect(L::rack_rect(widget)),
                    "fit": "diameter",
                    "region": region,
                    "states": format!("{id}:--value=0.25,0.75"),
                    "mattes": [plate],
                    "feather": L::BAKE_FEATHER,
                    "bakes": [bake(&format!("rack-{id}.png"), (2, 1), false)],
                }));
            }
            Kind::Text => {}
        }
    }

    let doc = json!({
        "schema": SCHEMA,
        "px_per_unit": PX_PER_UNIT,
        // The rig is the window's (template 229a80c).
        "window": [0.0, 0.0, L::WIDTH as f32, L::HEIGHT as f32],
        "light": "rack",
        "view": VIEW,
        "notes": NOTES,
        "elements": els,
    });
    let mut out = serde_json::to_string_pretty(&doc).expect("a JSON value serializes");
    out.push('\n');
    out
}

const NOTES: &[&str] = &[
    "rect: logical board px [x, y, w, h], y down; the element's origin is the rect centre. Board 1100x768 at 100 px per world unit.",
    "key: [monitor, index, width] places a viewer key in the monitor's right key row (rack.py, p197); the composer writes its rect, fit and seat.",
    "z: seat rests each part on its plate's face. fit: diameter sizes a knob to its rect's circle; fit: width builds a part to its rect's width.",
    "region: where the board draws the element's bakes, rendered at 2x through the composer over its mattes, every state packed row-major into grid; out is the path under rt/panel.",
    "The housing is drawn orthographically so its bezel registers with the runtime screen.",
    "The monitor also bakes the screen glass (drawn by panelkit::glass over the screen's content).",
    "Not included: the screen's content, the infotext, the bottom row, and all type.",
];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_bake_fits_its_grid_and_names_real_mattes() {
        let doc: Value = serde_json::from_str(&rack_layout()).unwrap();
        let els = doc["elements"].as_array().unwrap();
        let ids: Vec<&str> = els.iter().map(|e| e["id"].as_str().unwrap()).collect();
        for el in els {
            for m in el["mattes"].as_array().into_iter().flatten().chain(el["with"].as_array().into_iter().flatten()) {
                assert!(ids.contains(&m.as_str().unwrap()), "{} names {m}", el["id"]);
            }
            for b in el["bakes"].as_array().into_iter().flatten() {
                // The glass kind is one still, no grid.
                if b["kind"] == "glass" {
                    continue;
                }
                let states = el["states"].as_str().map_or(1, |s| {
                    let spec = s.split_once('=').unwrap().1;
                    spec.rsplit_once('/').map_or_else(|| spec.split(',').count(), |(_, n)| n.parse().unwrap())
                });
                let grid = b["grid"].as_array().unwrap();
                assert!(states <= (grid[0].as_u64().unwrap() * grid[1].as_u64().unwrap()) as usize, "{}", el["id"]);
            }
        }
        // Every plate control and every viewer key has a bake; the monitor
        // bakes its glass too.
        assert_eq!(els.iter().filter(|e| e.get("bakes").is_some()).count(), 1 + 3 + 3 + 19);
        let glass = els.iter().flat_map(|e| e["bakes"].as_array().into_iter().flatten()).filter(|b| b["kind"] == "glass");
        assert_eq!(glass.count(), 1);
    }
}
