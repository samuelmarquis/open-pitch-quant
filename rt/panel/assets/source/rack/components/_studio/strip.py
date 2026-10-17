"""Generic value-strip driver: render frames of a scene script, verify each
receipt, and bleed RGB under transparent pixels.

Runs under a Python with numpy + Pillow (not Blender's):

  python strip.py SCENE.py --output DIR [--start 0] [--end 100] [--bleed 8]
      [--scale 1] [--res 640] [--samples 220] [--blender PATH]
      [--verify strict|present|off] [-- <scene flags passed through>]

Contract:
- Frame f renders `SCENE -- DIR/fNNN.png --value f/100 --scale S --res R
  --samples N <pass-through flags>`; 0 <= start <= end <= 100. Blender is run as
  an argument list, never through a shell.
- Blender exits 0 after a script exception, so a frame passes only if its PNG
  exists and is non-empty AND its stdout carries a receipt: the last line of the
  form `<component> k=v ... -> OUT` whose OUT is this frame's path.
- `--verify strict` (default): every requested flag (value, scale, res, samples
  and each pass-through `--flag value` / switch) must appear in the receipt with
  an equal value (numbers compare numerically, switches as on). `present`: flags
  the receipt carries must match and at least `value` must be carried — for
  scenes whose receipt predates the scaffold. `off`: existence only.
  A requested flag the receipt names in an alias note `[alias --old as --new]`
  is satisfied when the receipt carries `new` (the scene maps the value).
- Edge bleed (`--bleed` px, 8-neighbour average, repeated): RGB under alpha 0 is
  filled from visible neighbours; alpha and every visible pixel are asserted
  unchanged, else the frame fails.
"""

import argparse
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

DEFAULT_BLENDER = Path.home() / "Applications/Blender.app/Contents/MacOS/Blender"


def bleed_transparent_rgb(path, radius):
    """Extend edge RGB under zero alpha without changing any visible pixel."""
    image = Image.open(path).convert("RGBA")
    pixels = np.asarray(image, dtype=np.uint8).copy()
    alpha_before = pixels[:, :, 3].copy()
    visible_before = pixels[alpha_before > 0].copy()
    rgb = pixels[:, :, :3].astype(np.float32)
    known = alpha_before > 0

    for _ in range(radius):
        count = np.zeros(known.shape, dtype=np.uint8)
        total = np.zeros(rgb.shape, dtype=np.float32)
        for dy, dx in ((-1, -1), (-1, 0), (-1, 1), (0, -1),
                       (0, 1), (1, -1), (1, 0), (1, 1)):
            source_y = slice(max(0, -dy), known.shape[0] - max(0, dy))
            source_x = slice(max(0, -dx), known.shape[1] - max(0, dx))
            target_y = slice(max(0, dy), known.shape[0] - max(0, -dy))
            target_x = slice(max(0, dx), known.shape[1] - max(0, -dx))
            neighbours = known[source_y, source_x]
            count[target_y, target_x] += neighbours
            total[target_y, target_x] += rgb[source_y, source_x] * neighbours[:, :, None]
        fill = (~known) & (count > 0)
        if not fill.any():
            break
        rgb[fill] = total[fill] / count[fill][:, None]
        known[fill] = True

    pixels[:, :, :3] = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
    if not np.array_equal(pixels[:, :, 3], alpha_before):
        raise RuntimeError(f"alpha changed during edge bleed: {path}")
    if not np.array_equal(pixels[alpha_before > 0], visible_before):
        raise RuntimeError(f"visible pixels changed during edge bleed: {path}")
    Image.fromarray(pixels).save(path, optimize=True)
    return int(np.count_nonzero(known & (alpha_before == 0)))


def parse_passthrough(tokens):
    """[`--flag`, `value`, `--switch`, ...] -> {key: value or "on"}."""
    out, i = {}, 0
    while i < len(tokens):
        tok = tokens[i]
        if not tok.startswith("--"):
            raise SystemExit(f"pass-through argument {tok!r} is not a --flag")
        name, eq, inline = tok.partition("=")
        if eq:
            out[name[2:]] = inline
            i += 1
        elif i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
            out[name[2:]] = tokens[i + 1]
            i += 2
        else:
            out[name[2:]] = "on"
            i += 1
    return out


def find_receipt(stdout, path):
    """(line, {key: raw}) of the last receipt naming `path`, or (None, None).
    Alias notes are returned under the key `[alias]` as {old key: new key}."""
    target = Path(path).resolve()
    for line in reversed(stdout.splitlines()):
        head, sep, tail = line.rpartition(" -> ")
        if not sep or not tail.strip():
            continue
        try:
            if Path(tail.strip()).expanduser().resolve() != target:
                continue
        except (OSError, ValueError):
            continue
        try:
            tokens = shlex.split(head)
        except ValueError:
            tokens = head.split()
        values = {}
        for tok in tokens[1:]:
            k, eq, v = tok.partition("=")
            if eq and not k.startswith("["):
                values[k] = v
        values["[alias]"] = {old[2:]: new[2:] for old, new in
                             re.findall(r"\[alias (--\S+) as (--\S+)\]", head)}
        return line, values
    return None, None


def same_value(want, got):
    if want == got:
        return True
    try:
        a, b = float(want), float(got)
    except (TypeError, ValueError):
        return False
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def verify_receipt(values, requested, mode):
    """List of problems (empty = pass)."""
    if mode == "off":
        return []
    problems = []
    aliased = values.get("[alias]", {})
    for key, want in requested.items():
        if key in aliased:
            if aliased[key] not in values:
                problems.append(f"{key} arrived as {aliased[key]}, which the receipt lacks")
            continue
        if key not in values:
            if mode == "strict":
                problems.append(f"{key} missing (wanted {want})")
            continue
        if not same_value(want, values[key]):
            problems.append(f"{key}={values[key]} (wanted {want})")
    if mode == "present" and "value" not in values:
        problems.append("value missing")
    return problems


def parse_args(argv):
    if "--" in argv:
        cut = argv.index("--")
        own, passthrough = argv[:cut], argv[cut + 1:]
    else:
        own, passthrough = argv, []
    parser = argparse.ArgumentParser(description="Render a value strip of a scene script.")
    parser.add_argument("scene", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--blender", type=Path,
                        default=Path(os.environ.get("BLENDER", DEFAULT_BLENDER)))
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--res", type=int, default=640)
    parser.add_argument("--samples", type=int, default=220)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=100)
    parser.add_argument("--bleed", type=int, default=8,
                        help="invisible RGB edge extension in pixels")
    parser.add_argument("--verify", choices=("strict", "present", "off"), default="strict")
    args = parser.parse_args(own)
    if args.scale <= 0:
        parser.error("--scale must be positive")
    if args.res < 64 or args.samples < 1:
        parser.error("--res must be >= 64 and --samples must be positive")
    if not 0 <= args.start <= args.end <= 100:
        parser.error("require 0 <= --start <= --end <= 100")
    if args.bleed < 0:
        parser.error("--bleed must be non-negative")
    reserved = {"value", "scale", "res", "samples"} & set(parse_passthrough(passthrough))
    if reserved:
        parser.error(f"pass-through may not set {sorted(reserved)}; use the strip flags")
    args.passthrough = passthrough
    return args


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    blender = args.blender.expanduser().resolve()
    if not blender.is_file():
        raise SystemExit(f"Blender executable not found: {blender}")
    scene = args.scene.expanduser().resolve()
    if not scene.is_file():
        raise SystemExit(f"scene script not found: {scene}")
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    extra = parse_passthrough(args.passthrough)

    for frame in range(args.start, args.end + 1):
        path = output / f"f{frame:03d}.png"
        path.unlink(missing_ok=True)
        value = f"{frame / 100:.2f}"
        command = [
            str(blender), "-b", "-P", str(scene), "--", str(path),
            "--value", value, "--scale", f"{args.scale:g}",
            "--res", str(args.res), "--samples", str(args.samples),
            *args.passthrough,
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-25:])
        if result.returncode != 0:
            raise RuntimeError(f"Blender exited {result.returncode} for {path}:\n{tail}")
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Blender did not produce {path}:\n{tail}")
        line, values = find_receipt(result.stdout, path)
        if args.verify != "off":
            if line is None:
                raise RuntimeError(f"no receipt naming {path}:\n{tail}")
            requested = {"value": value, "scale": f"{args.scale:g}",
                         "res": str(args.res), "samples": str(args.samples), **extra}
            problems = verify_receipt(values, requested, args.verify)
            if problems:
                raise RuntimeError(f"receipt mismatch for {path}: {'; '.join(problems)}\n"
                                   f"  receipt: {line}")
        filled = bleed_transparent_rgb(path, args.bleed)
        print(f"[{frame:03d}/100] {path} bleed={filled}px receipt={'ok' if line else 'none'}"
              f" ({args.verify})")


if __name__ == "__main__":
    main()
