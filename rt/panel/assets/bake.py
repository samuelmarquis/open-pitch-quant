#!/usr/bin/env python3
"""The panel's asset bake: vendors accepted family artwork and bakes the
rack plates, writing everything the board embeds to assets/vendor/ with a
provenance record (assets/vendor/provenance.json).

Sources, all read-only:
  - ../open-plugin-template/components (accepted component renders and the
    panel-board generator), the family's design system;
  - ../open-cepstrum/rt/panel/assets/vendor (the monitor housing bake, the
    knob-preview atlases and Source Sans), the reference consumer's bakes.

Run from anywhere:
  python3 -I rt/panel/assets/bake.py            # everything
  python3 -I rt/panel/assets/bake.py --only plates

Needs Blender 5.2 (BLENDER, default ~/Applications/Blender.app) for the
plates and ffmpeg for resampling component renders to their 2x draw size.
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
    "plate-capture": (258, 250, ["--face", "black-paint", "--fasteners", "screws"]),
    "plate-law": (300, 250, ["--face", "brass", "--fasteners", "screws"]),
    "plate-finish": (258, 250, ["--face", "verdigris", "--fasteners", "rivets"]),
    "plate-module": (228, 250, ["--face", "worn-steel", "--fasteners", "screws"]),
}
PLATE_COMMON = ["--edge", "flat", "--corner", ".015", "--bevel", ".04",
                "--bevel-segments", "4", "--ortho-px", "200", "--samples", "160"]

# Knob atlases (cepstrum-knob-preview/1: 11x10 cells of 120 px, frames
# 0..100 row-major, sRGB-encoded linear-premultiplied), copied as baked.
KNOBS = ["handwheel", "hifi-black-turned", "witchhat-black", "heady", "catalin",
         "leather-oxblood", "wood-ebony", "chrome-heat-tint", "davies-black",
         "ceramic-cobalt"]

# Component renders resampled to their 2x draw size: name -> (source, w, h).
SPRITES = {
    "selector-house": ("knob-chickenhead/renders/chickenhead_black_pos1.png", 192, 192),
    "selector-oracle": ("knob-chickenhead/renders/chickenhead_black_pos3.png", 192, 192),
    "toggle-up": ("toggle-bat/renders/toggle_up.png", 60, 80),
    "toggle-down": ("toggle-bat/renders/toggle_down.png", 60, 80),
    "led-green-off": ("led-indicator/renders/led_green_b00.png", 80, 80),
    "led-green-on": ("led-indicator/renders/led_green_b15.png", 80, 80),
    "led-amber-off": ("led-indicator/renders/led_amber_b00.png", 80, 80),
    "led-amber-on": ("led-indicator/renders/led_amber_b15.png", 80, 80),
    "led-red-off": ("led-indicator/renders/led_red_b00.png", 80, 80),
    "led-red-on": ("led-indicator/renders/led_red_b15.png", 80, 80),
}

COPIES = {
    "monitor-housing.png": CEP_VENDOR / "monitor-housing.png",
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


def bake_plates(record):
    with tempfile.TemporaryDirectory() as temp:
        for name, (w, h, flags) in PLATES.items():
            out = Path(temp) / f"{name}.png"
            args = [str(BLENDER), "-b", "-P",
                    str(COMPONENTS / "panel-board/generator/panel_scene.py"), "--",
                    str(out), "--w", str(w / 100), "--h", str(h / 100), *flags, *PLATE_COMMON]
            run = subprocess.run(args, capture_output=True, text=True)
            receipt = [line for line in run.stdout.splitlines() if line.startswith("panel-board ")]
            # Blender exits 0 after a script exception: the file and the
            # receipt are the proof.
            if not out.exists() or not receipt:
                sys.exit(f"{name}: bake failed\n{run.stdout[-2000:]}\n{run.stderr[-2000:]}")
            shutil.copyfile(out, VENDOR / out.name)
            record[out.name] = {
                "kind": "plate",
                "logical": [w, h],
                "generator": "open-plugin-template/components/panel-board/generator/panel_scene.py",
                "args": args[5:],
                "receipt": receipt[-1],
            }
            print("plate", name, flush=True)


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
    for name, (source, w, h) in SPRITES.items():
        target = VENDOR / f"{name}.png"
        # Straight alpha, lanczos: a component render down to its 2x size.
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(COMPONENTS / source),
                        "-vf", f"scale={w}:{h}:flags=lanczos", "-pix_fmt", "rgba", str(target)],
                       check=True)
        record[target.name] = {
            "kind": "component render, resampled",
            "source": f"open-plugin-template/components/{source}",
            "size": [w, h],
            "resample": "ffmpeg lanczos, straight alpha",
        }


def copy_files(record):
    for name, source in COPIES.items():
        shutil.copyfile(source, VENDOR / name)
        record[name] = {"kind": "copied", "source": str(source.relative_to(DEV))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=["plates", "knobs", "sprites", "copies"])
    args = parser.parse_args()
    VENDOR.mkdir(exist_ok=True)
    manifest_path = VENDOR / "provenance.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    record = manifest.setdefault("files", {})
    steps = {"plates": bake_plates, "knobs": vendor_knobs,
             "sprites": resample_sprites, "copies": copy_files}
    for step in args.only:
        steps[step](record)
    for name, entry in record.items():
        path = VENDOR / name
        if path.exists():
            entry["sha256"] = digest(path)
    manifest["sources"] = {
        "open-plugin-template": git_head(TEMPLATE),
        "open-cepstrum": git_head(CEPSTRUM),
    }
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
