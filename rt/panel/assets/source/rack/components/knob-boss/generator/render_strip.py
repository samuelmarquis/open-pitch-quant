"""knob-boss value strip: `_studio/strip.py` over knob_scene.py (contract there).

  design-lab/.venv/bin/python render_strip.py [--output DIR] [strip flags] [scene flags]

Frames land in ../renders by default; any flag strip.py does not own passes
through to the scene (`--cap KEY`, `--footprint 0.5`).
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
from families import run_strip  # noqa: E402

if __name__ == "__main__":
    run_strip(HERE / "knob_scene.py", default_output=HERE.parent / "renders")
