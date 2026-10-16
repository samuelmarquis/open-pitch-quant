#!/usr/bin/env python3
"""The panel's asset bake: vendors accepted family artwork and bakes the
rack plates, writing everything the board embeds to assets/vendor/ with a
provenance record (assets/vendor/provenance.json).

Sources, all read-only:
  - ../open-plugin-template/components (accepted component renders, the
    panel-board, knob and screen-monitor generators and the composer,
    _studio/rack.py), the family's design system;
  - ../open-cepstrum/rt/panel/assets/vendor (the knob-preview atlases and
    Source Sans), the reference consumer's bakes.

Run from anywhere:
  python3 -I rt/panel/assets/bake.py            # everything
  python3 -I rt/panel/assets/bake.py --only rack --renders DIR

Needs Blender 5.2 (BLENDER, default ~/Applications/Blender.app) for the
plates, components and housing, ffmpeg for resampling component renders to
their 2x draw size, and PIL (the dev shell's) for the rack and key imports.
Paths: TEMPLATE and CEPSTRUM override the sibling checkouts.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor"
ROOT = HERE.parents[2]  # the open-pitch-quant checkout
DEV = ROOT.parent
TEMPLATE = Path(os.environ.get("TEMPLATE", DEV / "open-plugin-template"))
CEPSTRUM = Path(os.environ.get("CEPSTRUM", DEV / "open-cepstrum"))
BLENDER = Path(os.environ.get(
    "BLENDER", Path.home() / "Applications/Blender.app/Contents/MacOS/Blender"))
COMPONENTS = TEMPLATE / "components"
CEP_VENDOR = CEPSTRUM / "rt/panel/assets/vendor"

# Rack plates: name -> (logical w, h, panel-board flags). Logical px; the
# plate renders orthographic at 200 px per world unit, so 1 world unit is
# 100 logical px and the bake is exactly 2x. Must match layout.rs.
PLATES = {
    # Sam, 2026-10-10: "switch the capture panel to anodized-blue".
    # Three plates fill the rack (Sam: "nix the output panel").
    "plate-capture": (336, 250, ["--face", "anodized-blue", "--fasteners", "screws"]),
    # Under the rack light the mirror "brass" read cream with a room band;
    # DESIGN's house call (p217, 27ce85b): brass-bare, an even gold.
    "plate-law": (380, 250, ["--face", "brass-bare", "--fasteners", "screws"]),
    # Sam on DESIGN's p181: "let's go catalin jade" (the polished plate key).
    "plate-finish": (336, 250, ["--face", "catalin-jade-polished", "--fasteners", "rivets"]),
}
PLATE_COMMON = ["--edge", "flat", "--corner", ".015", "--bevel", ".04",
                "--bevel-segments", "4", "--ortho-px", "200", "--samples", "160"]

# Knob atlases (cepstrum-knob-preview/1: 11x10 cells of 120 px, frames
# 0..100 row-major, sRGB-encoded linear-premultiplied), copied as baked.
# No witchhat (Sam, 2026-10-10: "hate the witchhat knob. nix it") and no
# handwheel (it is for a One Knob situation, which this board isn't).
KNOBS = ["hifi-black-turned", "heady", "catalin", "leather-oxblood", "wood-ebony",
         "chrome-heat-tint"]

# Component renders resampled to their 2x draw size: name -> (source, w, h,
# crop).
SPRITES = {}

# The toggles and the chickenhead (until 0.9.0) and Voices' stepped knob
# (until 0.9.1) were footprint-contract renders here; they are rack-baked
# with their plates now (RACK_PLATES).

# The monitor housing, baked through the template's composer (rack.py) at
# this board's monitor (layout.rs MONITOR, SCREEN), DESIGN's recipe for
# Sam's p179 pick: "beige plastic is best". Rendered at density 2 over the
# housing padded by HOUSING_PAD logical px; the board draws the whole
# image at that padded rect.
HOUSING_RECT = (16, 10, 1068, 458)
HOUSING_PAD = 8
HOUSING_FLAGS = ["--style", "lcd", "--bezel", "beige-plastic", "--fasteners", "none",
                 "--aperture", "48,48,2040,820", "--margin", "0", "--corner-r", "0",
                 "--overscan", "0", "--res", "2136x916"]

COPIES = {
    "SourceSansPro-Regular.otf": CEP_VENDOR / "SourceSansPro-Regular.otf",
    "SourceSans-LICENSE.txt": CEP_VENDOR / "SourceSans-LICENSE.txt",
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_head(repo):
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def no_local_blender():
    """Sam, 2026-10-10 (via DESIGN): no local Blender on the workstation;
    every Blender render goes through the template's design-lab session and
    its farm, one process per machine. A farm runner sets OPQ_BLENDER_FARM=1."""
    if os.environ.get("OPQ_BLENDER_FARM") != "1":
        sys.exit("bake.py: this step runs Blender; send it to DESIGN's farm "
                 "(set OPQ_BLENDER_FARM=1 only on a farm host)")


def blender_render(generator, out, flags):
    """One component render; the file and its receipt line are the proof
    (Blender exits 0 after a script exception)."""
    args = [str(BLENDER), "-b", "-P", str(COMPONENTS / generator), "--", str(out), *flags]
    # One retry: a long run of renders has seen Blender die without a word.
    for _ in range(2):
        run = subprocess.run(args, capture_output=True, text=True)
        receipt = [line for line in run.stdout.splitlines() if "->" in line and str(out) in line]
        if Path(out).exists() and receipt:
            return args[5:], receipt[-1]
    sys.exit(f"{generator}: render failed (exit {run.returncode})\n{run.stdout[-2000:]}\n{run.stderr[-2000:]}")


def bake_housing(record, renders=None):
    """With `renders` (the farm's monitor-housing.png, housing.json and
    receipts.txt), only takes the farm's housing in, checking its layout is
    this one and its receipt names the file; no Blender."""
    x, y, w, h = HOUSING_RECT
    pad = HOUSING_PAD
    frame = [x - pad, y - pad, w + 2 * pad, h + 2 * pad]
    layout = {
        "px_per_unit": 100,
        "frame": frame,
        "elements": [{"id": "monitor", "component": "screen-monitor", "rect": [x, y, w, h],
                      "fit": "width", "orthographic": True, "flags": HOUSING_FLAGS}],
    }
    if renders:
        farm = Path(renders)
        out = farm / "monitor-housing.png"
        lines = (farm / "receipts.txt").read_text().splitlines()
        receipt = [r for r in lines if r.startswith("rack ") and r.endswith(out.name)]
        template = [r.split()[1] for r in lines if r.startswith("template ")]
        if not out.exists() or not receipt:
            sys.exit("housing: the farm's housing or its receipt is missing")
        if json.loads((farm / "housing.json").read_text()) != layout:
            sys.exit("housing: the farm baked a different layout from this one")
        shutil.copyfile(out, VENDOR / out.name)
        record[out.name] = {
            "kind": "monitor housing, composer bake (rack.py), on DESIGN's farm",
            "generator": "open-plugin-template/components/_studio/rack.py",
            "template": template[-1] if template else None,
            "layout": layout,
            "args": ["LAYOUT.json", "OUT.png", "--density", "2"],
            "drawn_at": frame,
            "receipt": receipt[-1:],
        }
        print("housing (farm)", flush=True)
        return
    no_local_blender()
    with tempfile.TemporaryDirectory() as temp:
        layout_path = Path(temp) / "housing.json"
        layout_path.write_text(json.dumps(layout, indent=1))
        out = Path(temp) / "monitor-housing.png"
        args = [str(BLENDER), "-b", "-P", str(COMPONENTS / "_studio/rack.py"), "--",
                str(layout_path), str(out), "--density", "2"]
        run = subprocess.run(args, capture_output=True, text=True)
        if not out.exists():
            sys.exit(f"housing: bake failed\n{run.stdout[-2000:]}\n{run.stderr[-2000:]}")
        shutil.copyfile(out, VENDOR / out.name)
        record[out.name] = {
            "kind": "monitor housing, composer bake (rack.py)",
            "generator": "open-plugin-template/components/_studio/rack.py",
            "layout": layout,
            "args": args[5:6] + args[7:],
            "drawn_at": frame,
            "receipt": [line for line in run.stdout.splitlines() if line.startswith("rack")][-1:],
        }
        print("housing", flush=True)


# The viewer keys (layout.rs Viewer::ALL order, rightmost first): button-bezel
# keys baked on DESIGN's farm through rack.py with the housing as their
# matte, one 128x32 cell per state (each key's 64x16 rect at 2x).
VIEWER_KEYS = ["transect", "ladders", "scope"]
VIEWER_KEY_STATES = ["inactive", "active"]
VIEWER_KEY_CELL = (128, 32)
# Each key's label and LED hue, rightmost first.
VIEWER_KEY_FACES = {"transect": ("TRANSECT", "1f388c"), "ladders": ("LADDERS", "cc341a"),
                    "scope": ("SCOPE", "2a7f62")}
VIEWER_KEY_W = 64


def viewer_keys_layout():
    """The farm's keys job (rack.py), on the family's panel key row (DESIGN
    p197, Sam): each key named by its place on the monitor's right inner
    edge, "key": ["monitor", -1|-2|-3, 64], never a rect. rack.py writes
    the rects, which are layout.rs's viewer_key rects (right inner edge
    1060, 4 px apart, y 14); the housing is the keys' matte. A bake's
    --state flag is the farm's per cell."""
    x, y, w, h = HOUSING_RECT
    frame = [x - HOUSING_PAD, y - HOUSING_PAD, w + 2 * HOUSING_PAD, h + 2 * HOUSING_PAD]
    keys = [{"id": key, "component": "button-bezel", "key": ["monitor", -(i + 1), VIEWER_KEY_W],
             # The housing's own plastic, key and escutcheon, under a dark
             # legend (Sam, 2026-10-11: "baked keys are black, they should
             # be white/match the panel's material"; DESIGN's p200 B).
             "flags": ["--variant", "wide", "--body", "beige-plastic", "--text-color", "1b1b1b",
                       "--text", VIEWER_KEY_FACES[key][0], "--led-end", "left",
                       "--hue", VIEWER_KEY_FACES[key][1], "--bloom", "off", "--font", "mono",
                       "--font-weight", "bold", "--width", "56", "--height", "14",
                       "--cap-height", "5.75", "--travel", "0.65", "--state", "inactive"]}
            for i, key in enumerate(VIEWER_KEYS)]
    monitor = {"id": "monitor", "component": "screen-monitor", "rect": [x, y, w, h],
               "fit": "width", "orthographic": True, "flags": HOUSING_FLAGS, "matte": True}
    return {"px_per_unit": 100, "frame": frame, "lit": frame, "elements": [monitor] + keys}


# The family's screen glass (Sam, p211 C, 2026-10-16): screen-monitor's
# _vig and _refl, a standalone screen_scene.py bake at HOUSING_FLAGS so its
# layers cover MONITOR at density 2 and its aperture is SCREEN. Farm only.
GLASS_SID = "opq-screen"
GLASS_APERTURE = {"x": 48, "y": 48, "w": 2040, "h": 820}


def bake_glass(record, renders=None):
    """Takes the farm's <sid>_vig.png, <sid>_refl.png and <sid>.json in,
    cropped to the aperture (the board draws them over SCREEN) and recast
    for the canvas's premultiplied blend: glass-vig.png is black with alpha
    1 - vig (so drawing it multiplies by vig), glass-refl.png is the
    reflection with alpha 0 (so drawing it adds). No Blender."""
    from PIL import Image

    if renders is None:
        no_local_blender()
    farm = Path(renders)
    manifest = json.loads((farm / f"{GLASS_SID}.json").read_text())
    names = [f"{GLASS_SID}_vig.png", f"{GLASS_SID}_refl.png", f"{GLASS_SID}.json"]
    receipts = [r for r in (farm / "receipts.txt").read_text().splitlines()
                if all(n in r for n in names)]
    if not receipts:
        sys.exit("glass: no receipt names the farm's layers")
    if manifest["res"] != [2136, 916] or manifest["aperture"] != GLASS_APERTURE:
        sys.exit(f"glass: the farm baked another geometry: {manifest['res']} {manifest['aperture']}")
    if manifest["glare"]["strength"] != 1.0:
        sys.exit("glass: glare.strength is not the identity")
    a = GLASS_APERTURE
    box = (a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"])
    vig = Image.open(farm / names[0]).convert("RGB").getchannel("R").crop(box)
    refl = Image.open(farm / names[1]).convert("RGB").crop(box)
    black = Image.new("L", vig.size, 0)
    Image.merge("RGBA", (black, black, black, vig.point(lambda v: 255 - v))).save(VENDOR / "glass-vig.png")
    r, g, b = refl.split()
    Image.merge("RGBA", (r, g, b, black)).save(VENDOR / "glass-refl.png")
    for out, source in (("glass-vig.png", names[0]), ("glass-refl.png", names[1])):
        record[out] = {
            "kind": "screen glass layer, screen_scene.py bake on DESIGN's farm, "
                    "cropped to the aperture and recast for the canvas blend",
            "generator": "open-plugin-template/components/screen-monitor/generator/screen_scene.py",
            "source": source,
            "args": ["--sid", GLASS_SID] + HOUSING_FLAGS,
            "manifest": manifest,
            "receipt": receipts[-1:],
        }
    print("glass (farm)", flush=True)


# The plates as rack scenes (Sam, p210 B and p213 B: the open-comp style;
# p214 D: every two-way switch is toggle-tab). Each plate is its own rack
# scene, as the FINISH pilot Sam passed: the plate, its switches and LAW's
# chickenhead, dead-on under the rack light. The knobs stay per-part sprites
# for now (steps b and c). Each stateful part renders the whole plate through
# its states (--states), so every frame shares the plate's noise; the import
# keeps one frame as the plate and crops each part's window (layout.rs
# TAB_WINDOW, SELECTOR_WINDOW) from its frames. Centres are layout.rs's widgets.
RACK_PLATES = {"capture": (16, 494, 336, 250), "law": (360, 494, 380, 250),
               "finish": (748, 494, 336, 250)}
TAB = 30          # the tab's fitted width, logical px (pass 51 D)
TABS = {          # id -> (plate, centre)
    "gate-mode": ("capture", (78, 672)), "unowned": ("capture", (184, 672)),
    "transients": ("capture", (290, 672)),
    "source": ("law", (412, 676)), "scope": ("law", (492, 676)),
    "rounding": ("law", (672, 672)),
    "transitions": ("finish", (1022, 672)),
}
TAB_STATES = ["down", "up"]
# The ALGORITHM chickenhead at (436, 576) since the tabs (0.8.23), fitted by
# diameter at 102 px so its drum is the 43 px the sprite board drew
# (DESIGN's refit, pass 54: 88 gave 37); its 5-detent throw puts HOUSE at
# 0.25 and ORACLE at 0.75.
SELECTOR = ("law", (436, 576), 102)
SELECTOR_VALUES = ["0.25", "0.75"]
# The windows the import crops round each part (layout.rs TAB_WINDOW,
# SELECTOR_WINDOW): dx, dy, w, h from its centre, logical px. Under the rack
# light a part's change between states runs well past it: a long shadow
# streak down and right, soft shade to the left (pass 51 D). Inside its
# window, a part keeps only what its states change (alpha, feathered), so
# neighbours' windows may overlap.
TAB_WINDOW = (-64, -56, 144, 136)
SELECTOR_WINDOW = (-70, -70, 160, 160)


RACK_BASE = "design-lab/passes/54-opq-rack"


# Voices (step b): knob-boss over knob-ring, stepping together through its
# 12 detents (rack drives both from one state list, template e82dedd). Fits
# are DESIGN's, measured against v25: boss 55 px, ring 70, both seated.
VOICES = ("capture", (78, 560))
VOICES_STEPS = 12
VOICES_ELEMENTS = [
    {"id": "voices-ring", "component": "knob-ring", "rect": [43, 525, 70, 70], "fit": "diameter",
     "z": "seat", "flags": ["--segments", "12", "--from", "0", "--start-deg", "-135",
                            "--end-deg", "-45", "--hue", "amber", "--value", "0"]},
    {"id": "voices", "component": "knob-boss", "rect": [50.5, 532.5, 55, 55], "fit": "diameter",
     "z": "seat", "flags": ["--body", "pom-white", "--cap", "aluminium-spun", "--detents", "12",
                            "--start-deg", "-135", "--end-deg", "-45", "--value", "0"]},
]
VOICES_WINDOW = (-72, -68, 160, 150)


def rack_plate_layout(plate):
    x, y, w, h = RACK_PLATES[plate]
    face = PLATES[f"plate-{plate}"][2]
    common = list(PLATE_COMMON)
    for flag in ("--ortho-px", "--samples"):  # the rack's camera and samples own these
        i = common.index(flag)
        del common[i:i + 2]
    elements = [{"id": f"plate-{plate}", "component": "panel-board", "rect": [x, y, w, h],
                 "flags": ["--w", w / 100, "--h", h / 100, *face, *common]}]
    for key, (home, (cx, cy)) in TABS.items():
        if home == plate:
            elements.append({"id": key, "component": "toggle-tab",
                             "rect": [cx - TAB / 2, cy - TAB / 2, TAB, TAB],
                             "fit": "width", "z": "seat", "flags": ["--state", TAB_STATES[0]]})
    if VOICES[0] == plate:
        elements.extend(json.loads(json.dumps(VOICES_ELEMENTS)))
    home, (cx, cy), d = SELECTOR
    if home == plate:
        elements.append({"id": "algorithm", "component": "knob-chickenhead",
                         "rect": [cx - d / 2, cy - d / 2, d, d], "fit": "diameter",
                         "flags": ["--color", "black", "--value", SELECTOR_VALUES[0]]})
    return {"px_per_unit": 100, "frame": [x, y, w, h], "elements": elements}


def rack_parts(plate):
    """A plate's stateful parts: (id, flag, values, the --states argument)."""
    parts = [(key, "--state", TAB_STATES, f"{key}:--state={','.join(TAB_STATES)}")
             for key, (home, _) in TABS.items() if home == plate]
    if VOICES[0] == plate:
        n = VOICES_STEPS
        parts.append(("voices", "--value", [f"{k / (n - 1):.6f}" for k in range(n)],
                      f"voices,voices-ring:--value=0..1/{n}"))
    if SELECTOR[0] == plate:
        parts.append(("algorithm", "--value", SELECTOR_VALUES,
                      f"algorithm:--value={','.join(SELECTOR_VALUES)}"))
    return parts


def rack_jobs(base):
    """The farm's jobs for every plate, in the farm's jobs format, paths
    under `base` (relative to the template root)."""
    jobs = []
    for plate in RACK_PLATES:
        for key, flag, values, states in rack_parts(plate):
            outs = [f"{base}/out/{plate}/{key}-{i}.png" for i in range(len(values))]
            jobs.append({"argv": ["BLENDER", "-b", "-P", "components/_studio/rack.py", "--",
                                  f"{base}/layouts/{plate}.json",
                                  f"{base}/out/{plate}/{key}-{{i}}.png", "--density", "2",
                                  "--states", states],
                         "outputs": outs})
    return {"root": str(TEMPLATE), "sync": ["components", f"{base}/layouts"], "jobs": jobs}


def bake_rack(record, renders=None):
    """Takes the farm's plate frames in (RACK_BASE's out/<plate>/<part>-<i>.png
    and receipts.txt). Each plate's first frame becomes plate-<plate>.png.
    Each part's window is cropped from its frames into rack-<part>.png, one
    cell per state side by side, its alpha the feathered region its states
    change. Refuses a plate whose first-state frames disagree, or a part
    whose change outside its window is more than a few stray pixels (a far
    rivet catching the part's reflection). No Blender."""
    import numpy as np
    from PIL import Image, ImageFilter

    if renders is None:
        no_local_blender()
    farm = Path(renders)
    receipts = (farm / "receipts.txt").read_text().splitlines()
    noise = 3     # frames of one plate share the seed: max difference far off
    stray = 40    # changed pixels allowed outside a window (2x px)

    for plate, (px, py, pw, ph) in RACK_PLATES.items():
        parts = rack_parts(plate)
        frames = {}
        for key, _, values, _ in parts:
            frames[key] = []
            for i in range(len(values)):
                path = farm / "out" / plate / f"{key}-{i}.png"
                if not path.exists() or not any(r.endswith(f"{plate}/{key}-{i}.png") for r in receipts):
                    sys.exit(f"rack: {plate}/{key}-{i}.png or its receipt is missing")
                frames[key].append(np.asarray(Image.open(path).convert("RGBA"), dtype=np.int16))
        base = frames[parts[0][0]][0]
        if base.shape[:2] != (ph * 2, pw * 2):
            sys.exit(f"rack: {plate} frames are {base.shape[1::-1]}, not {(pw * 2, ph * 2)}")
        for key, *_ in parts:
            # A few speckled pixels may differ between runs (sampling at an
            # edge: 4 px by 9 in CAPTURE's pass-54 re-run); a scene does not.
            off = int((np.abs(frames[key][0] - base).max(axis=2) > noise).sum())
            if off > stray:
                sys.exit(f"rack: {plate}'s first-state frames disagree ({key}, {off} px)")
        Image.fromarray(base.astype(np.uint8)).save(VENDOR / f"plate-{plate}.png")
        record[f"plate-{plate}.png"] = {
            "kind": "rack plate, rack.py on DESIGN's farm, its parts in their first state",
            "generator": "open-plugin-template/components/_studio/rack.py",
            "layout": rack_plate_layout(plate),
            "logical": [pw, ph],
            "receipt": [r for r in receipts if f"{plate}/{parts[0][0]}-0.png" in r][-1:],
        }
        # Each changed pixel belongs to the part that changes it most: a
        # glossy neighbour mirrors a part's state (the chickenhead shows the
        # tabs), and a part must never repaint its neighbour.
        change = np.stack([np.max([np.abs(f - base).max(axis=2) for f in frames[key][1:]], axis=0)
                           for key, *_ in parts])
        owner = np.where(change.max(axis=0) > noise, change.argmax(axis=0), -1)
        for n, (key, flag, values, _) in enumerate(parts):
            (cx, cy), (dx, dy, w, h) = {"algorithm": (SELECTOR[1], SELECTOR_WINDOW),
                                        "voices": (VOICES[1], VOICES_WINDOW)}.get(
                                            key, (TABS.get(key, (None, None))[1], TAB_WINDOW))
            x0, y0 = round((cx + dx - px) * 2), round((cy + dy - py) * 2)
            x1, y1 = x0 + w * 2, y0 + h * 2
            changed = owner == n
            outside = changed.copy()
            outside[max(y0, 0):y1, max(x0, 0):x1] = False
            if outside.sum() > stray:
                sys.exit(f"rack: {key} changes {outside.sum()} px outside its window")
            # The window, padded where it runs off the plate (transparent).
            pad = ((max(-y0, 0), max(y1 - base.shape[0], 0)), (max(-x0, 0), max(x1 - base.shape[1], 0)))
            window = (slice(max(y0, 0), y1), slice(max(x0, 0), x1))
            theirs = ((owner >= 0) & ~changed)[window]
            grown = Image.fromarray(np.pad(changed[window], pad).astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(9))
            grown = np.asarray(grown) * ~np.pad(theirs, pad)
            alpha = np.asarray(Image.fromarray(grown.astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)),
                               dtype=np.int16)
            strip = np.zeros((h * 2, w * 2 * len(values), 4), np.uint8)
            for i, frame in enumerate(frames[key]):
                cell = np.pad(frame[window], pad + ((0, 0),))
                cell[..., 3] = cell[..., 3] * alpha // 255
                strip[:, i * w * 2:(i + 1) * w * 2] = cell.astype(np.uint8)
            Image.fromarray(strip).save(VENDOR / f"rack-{key}.png")
            record[f"rack-{key}.png"] = {
                "kind": "rack part's window per state, cropped from its plate's frames, "
                        "alpha the feathered region its states change most",
                "plate": plate, "states": [f"{flag}={v}" for v in values],
                "window_2x": [x0, y0, x1, y1], "stray_px": int(outside.sum()),
                "receipt": [r for r in receipts if f"{plate}/{key}-" in r],
            }
        print("rack", plate, flush=True)


def write_jobs(out):
    """Writes the farm's job files into `out`: keys.json, and the plates'
    rack layouts (layouts/<plate>.json) with their jobs.json (paths under
    RACK_BASE in the template), which the import steps check the farm baked."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "keys.json").write_text(json.dumps(viewer_keys_layout(), indent=1) + "\n")
    print(out / "keys.json", flush=True)
    (out / "layouts").mkdir(exist_ok=True)
    for plate in RACK_PLATES:
        path = out / "layouts" / f"{plate}.json"
        path.write_text(json.dumps(rack_plate_layout(plate), indent=1) + "\n")
        print(path, flush=True)
    (out / "jobs.json").write_text(json.dumps(rack_jobs(RACK_BASE), indent=1) + "\n")
    print(out / "jobs.json", flush=True)


def pack_viewer_keys(record, renders=None):
    """Packs the farm's keys/<key>-<state>.png into one straight-alpha row:
    each key's inactive then active cell (panelkit widgets::Keys, 2 states).
    Farm renders only: a key bake is Blender's."""
    from PIL import Image

    if not renders:
        sys.exit("keys: pass --renders (the farm's directory); keys are baked on the farm")
    farm = Path(renders)
    layout = json.loads((farm / "keys.json").read_text())
    if layout != viewer_keys_layout():
        sys.exit("keys: the farm baked a different layout from this one (bake.py --jobs DIR writes it)")
    lines = (farm / "receipts.txt").read_text().splitlines()
    template = [r.split()[2] for r in lines if r.startswith("keys: template ")]
    w, h = VIEWER_KEY_CELL
    atlas = Image.new("RGBA", (w * len(VIEWER_KEYS) * len(VIEWER_KEY_STATES), h))
    receipts = []
    for k, key in enumerate(VIEWER_KEYS):
        for s, state in enumerate(VIEWER_KEY_STATES):
            name = f"{key}-{state}.png"
            receipt = [r for r in lines if r.startswith("rack ") and r.endswith(f"keys/{name}")]
            path = farm / "keys" / name
            if not path.exists() or not receipt:
                sys.exit(f"keys: the farm's {name} or its receipt is missing")
            with Image.open(path) as cell:
                if cell.size != VIEWER_KEY_CELL or cell.mode != "RGBA":
                    sys.exit(f"keys: {name} is {cell.size} {cell.mode}, not {VIEWER_KEY_CELL} RGBA")
                atlas.paste(cell, ((k * len(VIEWER_KEY_STATES) + s) * w, 0))
            receipts += receipt
    out = VENDOR / "viewer-keys.png"
    atlas.save(out)
    record[out.name] = {
        "kind": "viewer key row, button-bezel composer bakes (rack.py) on DESIGN's farm, housing as matte",
        "generator": "open-plugin-template/components/_studio/rack.py",
        "template": template[-1] if template else None,
        "layout": layout,
        "cells": [f"{key} {state}" for key in VIEWER_KEYS for state in VIEWER_KEY_STATES],
        "cell": list(VIEWER_KEY_CELL),
        "packing": "PIL paste, straight alpha (panelkit Keys draws with paint::ART)",
        "receipts": receipts,
    }
    print("viewer keys (farm)", flush=True)


def vendor_knobs(record):
    (VENDOR / "knobs").mkdir(exist_ok=True)
    for knob in KNOBS:
        source = CEP_VENDOR / "knob-preview" / f"knob-{knob}.png"
        target = VENDOR / "knobs" / source.name
        shutil.copyfile(source, target)
        bake = source.with_name(f"knob-{knob}-bake.json")
        record[f"knobs/{source.name}"] = {
            "kind": "knob atlas (cepstrum-knob-preview/1)",
            "source": f"open-cepstrum/rt/panel/assets/vendor/knob-preview/{source.name}",
            "bake": json.loads(bake.read_text()) .get("canonical_flags") if bake.exists() else None,
        }


def resample_sprites(record):
    for name, (source, w, h, crop) in SPRITES.items():
        target = VENDOR / f"{name}.png"
        # Straight alpha, lanczos: a component render (cropped round its
        # pivot) down to its 2x size.
        filters = f"scale={w}:{h}:flags=lanczos"
        if crop:
            cx, cy, cw, ch = crop
            filters = f"crop={cw}:{ch}:{cx}:{cy}," + filters
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(COMPONENTS / source),
                        "-vf", filters, "-pix_fmt", "rgba", str(target)],
                       check=True)
        record[target.name] = {
            "kind": "component render, resampled",
            "source": f"open-plugin-template/components/{source}",
            "crop": list(crop) if crop else None,
            "size": [w, h],
            "resample": "ffmpeg lanczos, straight alpha",
        }


def copy_files(record):
    for name, source in COPIES.items():
        shutil.copyfile(source, VENDOR / name)
        record[name] = {"kind": "copied", "source": str(source.relative_to(DEV))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=["rack", "housing",
                                                      "keys", "glass", "knobs", "sprites", "copies"])
    parser.add_argument("--renders",
                        help="the farm's renders (rack plates, housing, keys, glass): take them in, no Blender")
    parser.add_argument("--jobs", metavar="DIR",
                        help="write the farm's job files (keys.json) into DIR and stop")
    args = parser.parse_args()
    if args.jobs:
        write_jobs(args.jobs)
        return
    VENDOR.mkdir(exist_ok=True)
    manifest_path = VENDOR / "provenance.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    record = manifest.setdefault("files", {})
    steps = {"rack": lambda record: bake_rack(record, args.renders),
             "housing": lambda record: bake_housing(record, args.renders),
             "keys": lambda record: pack_viewer_keys(record, args.renders),
             "glass": lambda record: bake_glass(record, args.renders),
             "knobs": vendor_knobs, "sprites": resample_sprites,
             "copies": copy_files}
    for step in args.only:
        steps[step](record)
    # A vendored file that is gone (dropped from the board) leaves no record.
    for name in [name for name in record if not (VENDOR / name).exists()]:
        del record[name]
    for name, entry in record.items():
        path = VENDOR / name
        if path.exists():
            entry["sha256"] = digest(path)
    # A source's commit is the one this run drew from: only a step that took
    # files from it moves it (a housing import leaves cep's knobs dated).
    sources = manifest.setdefault("sources", {})
    if {"rack", "housing", "keys", "glass", "sprites"} & set(args.only):
        sources["open-plugin-template"] = git_head(TEMPLATE)
    if {"knobs", "copies"} & set(args.only):
        sources["open-cepstrum"] = git_head(CEPSTRUM)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
