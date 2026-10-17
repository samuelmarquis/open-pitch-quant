"""knob-chickenhead selector states: chickenhead_COLOUR_posI.png per colour and position.

  design-lab/.venv/bin/python render_states.py [--output DIR] [--color all|black|cream|red]
      [--angles -60,-30,0,30,60] [--scale 1] [--res 640] [--samples 220] [--bleed 8]
      [--blender PATH] [-- scene flags]

Position I renders the I-th angle (deg clockwise from 12 o'clock) of --angles:
a detent angle as `--preset COLOUR --value (angle + 60) / 120`, any other as
`--preset COLOUR --angle ANGLE`. Scene flags after `--` pass through (`--indicator
KEY`). Blender runs as an argument list; a state passes only if its PNG exists
and its receipt carries every requested flag (`_studio/strip.py` verify_receipt,
strict); edge RGB is then bled under zero alpha with alpha and visible pixels
asserted unchanged.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
from strip import (bleed_transparent_rgb, find_receipt, parse_passthrough,  # noqa: E402
                   verify_receipt)

SCENE = HERE / "knob_scene.py"
DEFAULT_OUT = HERE.parent / "renders"
DEFAULT_BLENDER = Path.home() / "Applications/Blender.app/Contents/MacOS/Blender"
CANON_ANGLES = (-60.0, -30.0, 0.0, 30.0, 60.0)
CANON_COLORS = ("black", "cream", "red")


def parse_args(argv):
    cut = argv.index("--") if "--" in argv else len(argv)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--blender", type=Path,
                        default=Path(os.environ.get("BLENDER", DEFAULT_BLENDER)))
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--res", type=int, default=640)
    parser.add_argument("--samples", type=int, default=220)
    parser.add_argument("--color", choices=("all", *CANON_COLORS), default="all")
    parser.add_argument("--angles", default=",".join(f"{v:g}" for v in CANON_ANGLES),
                        help="comma-separated selector angles in degrees")
    parser.add_argument("--bleed", type=int, default=8)
    args = parser.parse_args(argv[:cut])
    args.passthrough = argv[cut + 1:]
    try:
        args.angles = tuple(float(token) for token in args.angles.split(","))
    except ValueError as exc:
        parser.error(f"invalid --angles: {exc}")
    if args.scale <= 0:
        parser.error("--scale must be positive")
    if args.res < 64 or args.samples < 1:
        parser.error("--res must be >= 64 and --samples must be positive")
    if args.bleed < 0:
        parser.error("--bleed must be non-negative")
    reserved = {"value", "angle", "preset", "scale", "res", "samples"} & set(
        parse_passthrough(args.passthrough))
    if reserved:
        parser.error(f"pass-through may not set {sorted(reserved)}; use the driver flags")
    return args


def position_flags(angle):
    if angle in CANON_ANGLES:
        return {"value": f"{(angle + 60.0) / 120.0:g}"}
    return {"angle": f"{angle:g}"}


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    blender = args.blender.expanduser().resolve()
    if not blender.is_file():
        raise SystemExit(f"Blender executable not found: {blender}")
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    extra = parse_passthrough(args.passthrough)
    colors = CANON_COLORS if args.color == "all" else (args.color,)
    for color in colors:
        for position, angle in enumerate(args.angles):
            path = output / f"chickenhead_{color}_pos{position}.png"
            path.unlink(missing_ok=True)
            requested = {"preset": color, **position_flags(angle), "scale": f"{args.scale:g}",
                         "res": str(args.res), "samples": str(args.samples)}
            command = [str(blender), "-b", "-P", str(SCENE), "--", str(path),
                       *[t for k, v in requested.items() for t in (f"--{k}", v)],
                       *args.passthrough]
            result = subprocess.run(command, capture_output=True, text=True)
            tail = "\n".join((result.stdout + result.stderr).splitlines()[-25:])
            if result.returncode != 0 or not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"Blender did not produce {path}:\n{tail}")
            line, values = find_receipt(result.stdout, path)
            if line is None:
                raise RuntimeError(f"no receipt naming {path}:\n{tail}")
            problems = verify_receipt(values, {**requested, **extra}, "strict")
            if problems:
                raise RuntimeError(f"receipt mismatch for {path}: {'; '.join(problems)}\n"
                                   f"  receipt: {line}")
            bleed_transparent_rgb(path, args.bleed)
            print(f"[{color} pos{position} angle={angle:g}] {path}")


if __name__ == "__main__":
    main()
