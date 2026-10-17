#!/usr/bin/env python3
"""The panel's remaining asset step: the screen glass, taken in from DESIGN's
farm, with a provenance record (assets/vendor/provenance.json, which also
keeps Source Sans's record).

Everything Blender-made on the board is the family's one rack pipeline now
(assets/bake_rack.py over src/rack_layout.rs, recorded in
assets/vendor/rack-bake.json; Sam, 2026-10-17: "EVERY plugin has the SAME
lighting and scene idioms and rendering pipelines"). The glass moves onto it
next (the template's glass bake kind, drawn by panelkit::glass), and this
file goes with it.

Run from the repo root, in `nix develop`:
  python3 -I rt/panel/assets/bake.py --renders DIR   # the farm's glass layers
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor"
ROOT = HERE.parents[2]  # the open-pitch-quant checkout
TEMPLATE = Path(os.environ.get("TEMPLATE", ROOT.parent / "open-plugin-template"))

# The monitor's screen-monitor flags (rack_layout.rs HOUSING_FLAGS), which
# the glass layers were baked at.
HOUSING_FLAGS = ["--style", "lcd", "--bezel", "beige-plastic", "--fasteners", "none",
                 "--aperture", "48,48,2040,820", "--margin", "0", "--corner-r", "0",
                 "--overscan", "0", "--res", "2136x916"]

# Source Sans was copied from open-cepstrum's vendor until 0.9.9; it is
# vendored here as it stands (DESIGN: nothing is read from another product).


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_head(repo):
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--renders", required=True,
                        help="the farm's glass layers: take them in, no Blender")
    args = parser.parse_args()
    manifest_path = VENDOR / "provenance.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    record = manifest.setdefault("files", {})
    bake_glass(record, args.renders)
    # A vendored file that is gone (dropped from the board) leaves no record.
    for name in [name for name in record if not (VENDOR / name).exists()]:
        del record[name]
    for name, entry in record.items():
        entry["sha256"] = digest(VENDOR / name)
    manifest.setdefault("sources", {})["open-plugin-template"] = git_head(TEMPLATE)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
