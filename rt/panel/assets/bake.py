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
  python3 -I rt/panel/assets/bake.py --only plates

Needs Blender 5.2 (BLENDER, default ~/Applications/Blender.app) for the
plates, components and housing, ffmpeg for resampling component renders to
their 2x draw size, and PIL (the dev shell's) for the stepped knob's strip.
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
    "plate-law": (380, 250, ["--face", "brass", "--fasteners", "screws"]),
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

# Controls rendered here under the family's footprint contract (the knobs'
# own, extended to the button family by DESIGN, template 6796dcc): render
# `--footprint 0.5` square, crop the centre [68, 68, 252, 252] of a 320 px
# frame (here [136, 136, 504, 504] of 640, for density), scale the crop to
# the slot. One framing for every state, so states swap in register.
# name -> (generator, flags, 2x slot px). Slots must match layout.rs.
CONTRACT_RES = 640
CONTRACT_CROP = (136, 136, 368, 368)  # x, y, w, h
COMPONENT_RENDERS = {
    "toggle-up": ("toggle-bat/generator/toggle_scene.py", ["--state", "up"], 88),
    "toggle-down": ("toggle-bat/generator/toggle_scene.py", ["--state", "down"], 88),
    # The chickenhead's 5-detent throw: 0.25 points the nose -30 deg
    # (HOUSE), 0.75 +30 deg (ORACLE).
    "selector-house": ("knob-chickenhead/generator/knob_scene.py", ["--color", "black", "--value", "0.25"], 176),
    "selector-oracle": ("knob-chickenhead/generator/knob_scene.py", ["--color", "black", "--value", "0.75"], 176),
}

# Component renders resampled to their 2x draw size: name -> (source, w, h,
# crop).
SPRITES = {}

# Stepped knobs: one footprint-contract render per detent, the knob over
# its lens ring, cropped and scaled into one cell each of a strip (cell i
# is step i). Straight alpha. name -> (steps, 2x cell px, crop, knob,
# ring). The ring straddles the knob beyond its footprint (alpha bounds
# 105..535 of 640 against the footprint's 136..504), so the crop is wider
# than the contract's: 440 px, scaled so the knob body keeps the
# contract's scale (368 px -> 120 px cell), 144 px, 72 logical.
# Voices: Sam on DESIGN's p180, "Maybe boss-ivory with the knob-ring";
# DESIGN's recipe (2026-10-10); the ring registers pixel-for-pixel with
# the boss at its default geometry. Amber lenses against CAPTURE's blue.
STEPPED = {
    "knob-voices": (12, 144, (100, 100, 440, 440),
                    ("knob-boss/generator/knob_scene.py",
                     ["--body", "pom-white", "--cap", "aluminium-spun", "--detents", "12",
                      "--start-deg", "-135", "--end-deg", "-45", "--footprint", "0.5"]),
                    ("knob-ring/generator/knob_scene.py",
                     ["--segments", "12", "--from", "0", "--start-deg", "-135", "--end-deg", "-45",
                      "--hue", "amber"])),
}

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


def bake_plates(record, renders=None):
    """With `renders` (the farm's NAME.png and receipts.txt), only takes the
    farm's plates in, checking each receipt names the plate; no Blender."""
    if renders is None:
        no_local_blender()
    farm_receipts = (Path(renders) / "receipts.txt").read_text().splitlines() if renders else []
    with tempfile.TemporaryDirectory() as temp:
        for name, (w, h, flags) in PLATES.items():
            out = Path(temp) / f"{name}.png"
            args = [str(BLENDER), "-b", "-P",
                    str(COMPONENTS / "panel-board/generator/panel_scene.py"), "--",
                    str(out), "--w", str(w / 100), "--h", str(h / 100), *flags, *PLATE_COMMON]
            if renders:
                out = Path(renders) / f"{name}.png"
                receipt = [r for r in farm_receipts if r.startswith("panel-board ") and r.endswith(out.name)]
            else:
                run = subprocess.run(args, capture_output=True, text=True)
                receipt = [line for line in run.stdout.splitlines() if line.startswith("panel-board ")]
            # Blender exits 0 after a script exception: the file and the
            # receipt are the proof.
            if not out.exists() or not receipt:
                sys.exit(f"{name}: bake failed or the farm's plate/receipt is missing")
            shutil.copyfile(out, VENDOR / out.name)
            record[out.name] = {
                "kind": "plate",
                "logical": [w, h],
                "generator": "open-plugin-template/components/panel-board/generator/panel_scene.py",
                "args": args[5:],
                "receipt": receipt[-1],
            }
            print("plate", name, flush=True)


def render_components(record):
    no_local_blender()
    cx, cy, cw, ch = CONTRACT_CROP
    with tempfile.TemporaryDirectory() as temp:
        for name, (generator, flags, size) in COMPONENT_RENDERS.items():
            raw = Path(temp) / f"{name}.png"
            args = [str(BLENDER), "-b", "-P", str(COMPONENTS / generator), "--", str(raw),
                    *flags, "--footprint", "0.5", "--res", str(CONTRACT_RES)]
            run = subprocess.run(args, capture_output=True, text=True)
            receipt = [line for line in run.stdout.splitlines() if "->" in line and str(raw) in line]
            # Blender exits 0 after a script exception: the file and the
            # receipt are the proof.
            if not raw.exists() or not receipt:
                sys.exit(f"{name}: render failed\n{run.stdout[-2000:]}\n{run.stderr[-2000:]}")
            target = VENDOR / f"{name}.png"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(raw), "-vf",
                            f"crop={cw}:{ch}:{cx}:{cy},scale={size}:{size}:flags=lanczos",
                            "-pix_fmt", "rgba", str(target)], check=True)
            record[target.name] = {
                "kind": "component render, footprint contract",
                "generator": f"open-plugin-template/components/{generator}",
                "args": args[5:],
                "receipt": receipt[-1],
                "crop": list(CONTRACT_CROP),
                "size": [size, size],
                "resample": "ffmpeg lanczos, straight alpha",
            }
            print("component", name, flush=True)


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


def bake_stepped(record, renders=None):
    """With `renders` (a directory of the farm's NAME-knob-K.png and
    NAME-ring-K.png and their receipts, receipts.txt), only composites; no
    Blender. Without it, renders here, which only a farm host may."""
    from PIL import Image  # the dev shell's; only this step needs it

    if renders is None:
        no_local_blender()
    (VENDOR / "knobs").mkdir(exist_ok=True)
    farm_receipts = (Path(renders) / "receipts.txt").read_text().splitlines() if renders else []
    with tempfile.TemporaryDirectory() as temp:
        for name, (steps, cell, crop, (knob_gen, knob_flags), (ring_gen, ring_flags)) in STEPPED.items():
            cx, cy, cw, ch = crop
            strip = Image.new("RGBA", (cell * steps, cell))
            receipts = []
            for k in range(steps):
                value = f"{k / (steps - 1):.6f}"
                knob_flags_k = [*knob_flags, "--value", value, "--res", str(CONTRACT_RES)]
                ring_flags_k = [*ring_flags, "--value", value, "--res", str(CONTRACT_RES)]
                if renders:
                    knob = Path(renders) / f"{name}-knob-{k}.png"
                    ring = Path(renders) / f"{name}-ring-{k}.png"
                    knob_args, ring_args = knob_flags_k, ring_flags_k
                    knob_receipt = next((r for r in farm_receipts if knob.name in r), None)
                    ring_receipt = next((r for r in farm_receipts if ring.name in r), None)
                    if not (knob.exists() and ring.exists() and knob_receipt and ring_receipt):
                        sys.exit(f"{name} step {k}: the farm's renders or receipts are missing")
                else:
                    knob = Path(temp) / f"{name}-knob-{k}.png"
                    ring = Path(temp) / f"{name}-ring-{k}.png"
                    knob_args, knob_receipt = blender_render(knob_gen, knob, knob_flags_k)
                    ring_args, ring_receipt = blender_render(ring_gen, ring, ring_flags_k)
                # The knob over its ring, then the contract's crop.
                frame = Image.alpha_composite(Image.open(ring).convert("RGBA"),
                                              Image.open(knob).convert("RGBA"))
                frame = frame.crop((cx, cy, cx + cw, cy + ch)).resize((cell, cell), Image.LANCZOS)
                strip.paste(frame, (k * cell, 0))
                receipts.append([knob_receipt, ring_receipt])
                print("stepped", name, k, flush=True)
            target = VENDOR / "knobs" / f"{name}.png"
            strip.save(target)
            record[f"knobs/{target.name}"] = {
                "kind": "stepped knob strip: knob over ring, one cell per step",
                "knob": {"generator": f"open-plugin-template/components/{knob_gen}", "args": knob_args},
                "ring": {"generator": f"open-plugin-template/components/{ring_gen}", "args": ring_args},
                "values": "k / (steps - 1), k = 0..steps-1 (the receipts' --value)",
                "crop": list(crop),
                "cell": [cell, cell],
                "steps": steps,
                "resample": "PIL lanczos, straight alpha",
                "receipts": receipts,
            }


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


def pack_viewer_keys(record, renders=None):
    """Packs the farm's keys/<key>-<state>.png into one straight-alpha row:
    each key's inactive then active cell (panelkit widgets::Keys, 2 states).
    Farm renders only: a key bake is Blender's."""
    from PIL import Image

    if not renders:
        sys.exit("keys: pass --renders (the farm's directory); keys are baked on the farm")
    farm = Path(renders)
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
        "layout": json.loads((farm / "keys.json").read_text()),
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
    parser.add_argument("--only", nargs="*", default=["plates", "components", "stepped", "housing",
                                                      "keys", "knobs", "sprites", "copies"])
    parser.add_argument("--renders",
                        help="the farm's renders (plates, stepped knob, housing): take them in, no Blender")
    args = parser.parse_args()
    VENDOR.mkdir(exist_ok=True)
    manifest_path = VENDOR / "provenance.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    record = manifest.setdefault("files", {})
    steps = {"plates": lambda record: bake_plates(record, args.renders),
             "components": render_components,
             "stepped": lambda record: bake_stepped(record, args.renders),
             "housing": lambda record: bake_housing(record, args.renders),
             "keys": lambda record: pack_viewer_keys(record, args.renders),
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
    if {"plates", "components", "stepped", "housing", "keys", "sprites"} & set(args.only):
        sources["open-plugin-template"] = git_head(TEMPLATE)
    if {"knobs", "copies"} & set(args.only):
        sources["open-cepstrum"] = git_head(CEPSTRUM)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
