#!/usr/bin/env python3
"""Render the canon stills for the rail family.

Every tile is at the family's scale contract (42 px per world unit), so a canon
render IS an actual-size render — there is no separate "product scale" pass to
disagree with.

    design-lab/.venv/bin/python components/_studio/render_rails.py [--samples N]
                                                                  [--only comp]
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

STUDIO = Path(__file__).resolve().parent
REPO = STUDIO.parents[1]
BLENDER = Path(os.environ.get("BLENDER",
                              Path.home() / "Applications/Blender.app/Contents/MacOS/Blender"))
DEMO_PANEL = "gunmetal-brushed"

SCENES = {
    "rail-cross": "components/rail-cross/generator/cross_scene.py",
    "rail-position": "components/rail-position/generator/position_scene.py",
    "rail-range": "components/rail-range/generator/range_scene.py",
}

# name -> flags. `--panel` given = the standalone demo look; omitted = cut-in,
# the transparent part a consumer actually composites.
JOBS = {
    "rail-cross": {
        "v000": ["--value", "0.0"], "v025": ["--value", "0.25"],
        "v050": ["--value", "0.5"], "v075": ["--value", "0.75"],
        "v100": ["--value", "1.0"],
        "wells-none": ["--wells", "none"], "cap-plain": ["--cap-texture", "plain"],
        "witness-short": ["--witness", "short"],
        "cut-in": ["--panel", "none", "--tick-fill", "white"],
    },
    "rail-position": {
        "v000": ["--value", "0.0"], "v025": ["--value", "0.25"],
        "v050": ["--value", "0.5"], "v075": ["--value", "0.75"],
        "v100": ["--value", "1.0"],
        "bipolar": ["--ticks", "bipolar"],
        "landmark": ["--ticks", "landmark", "--major", "4", "--minor", "1"],
        "coarse": ["--major", "3", "--minor", "2"],
        "cut-in": ["--panel", "none", "--tick-fill", "white"],
    },
    "rail-range": {
        "wide": ["--low", "0.08", "--high", "0.92"],
        "mid": ["--low", "0.25", "--high", "0.75"],
        "narrow": ["--low", "0.46", "--high", "0.56"],
        "adjacent": ["--low", "0.48", "--high", "0.52"],
        "crossed": ["--low", "0.62", "--high", "0.38"],
        "edge-low": ["--low", "0.0", "--high", "0.30"],
        "cut-in": ["--panel", "none", "--tick-fill", "white"],
    },
}
# the fill following the board, one per component, on a pale panel
for comp in JOBS:
    JOBS[comp]["on-catalin"] = ["--panel", "catalin"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=220)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()

    comps = a.only.split(",") if a.only else list(JOBS)
    manifest = {}
    total = sum(len(JOBS[c]) for c in comps)
    i = 0
    for comp in comps:
        out_dir = REPO / "components" / comp / "renders"
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, flags in JOBS[comp].items():
            i += 1
            dest = out_dir / f"{name}.png"
            argv = [str(BLENDER), "-b", "-P", str(REPO / SCENES[comp]), "--", str(dest)]
            if "--panel" not in flags:
                argv += ["--panel", DEMO_PANEL]
            argv += flags + ["--samples", str(a.samples)]
            print(f"[{i}/{total}] {comp}/{name}", flush=True)
            p = subprocess.run(argv, capture_output=True, text=True)
            # Blender exits 0 after a script exception: the receipt is the proof
            rec = [ln for ln in p.stdout.splitlines() if ln.startswith(comp + " ")]
            if not rec or not dest.is_file() or dest.stat().st_size == 0:
                sys.stderr.write(p.stdout[-2500:] + p.stderr[-1500:])
                raise SystemExit(f"FAILED: {comp}/{name}")
            manifest[f"{comp}/{name}"] = {
                "path": str(dest.relative_to(REPO)), "flags": flags, "receipt": rec[-1]}
    out = STUDIO / "rails_manifest.json"
    prev = json.loads(out.read_text()) if out.is_file() else {}
    prev.update(manifest)
    out.write_text(json.dumps(prev, indent=1))
    print(f"ok: {len(manifest)} rendered, {len(prev)} in manifest")


if __name__ == "__main__":
    main()
