"""knob-heady value strips: `_studio/strip.py` over knob_scene.py (contract there).

  design-lab/.venv/bin/python render_strip.py --style NAME [--output DIR] [strip flags] [scene flags]

A style (`--style NAME` or `--preset NAME`) is required. Frames land in
../renders/strip-<style> at `--samples 256` unless it is given;
every flag strip.py does not own passes through to the scene.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
from families import run_strip  # noqa: E402

STYLES = ("implosion", "fumed", "linework", "crushed")
CANON = (("--samples", "256"),)


def main(argv):
    tokens = list(argv)
    style = None
    for i, tok in enumerate(tokens):
        name, eq, value = tok.partition("=")
        if name in ("--style", "--preset"):
            style = value if eq else (tokens[i + 1] if i + 1 < len(tokens) else None)
    if style not in STYLES:
        raise SystemExit(f"render_strip: --style must be one of {', '.join(STYLES)}")
    given = {tok.partition("=")[0] for tok in tokens}
    canon = [part for flag, value in CANON if flag not in given for part in (flag, value)]
    return run_strip(HERE / "knob_scene.py", HERE.parent / f"renders/strip-{style}",
                     canon + tokens)


if __name__ == "__main__":
    main(sys.argv[1:])
