"""Bake OpenPitchQuant's Blender-made parts through the template's rack composer.

**Blender goes through DESIGN's farm, never from this session** (Sam,
2026-10-10, via DESIGN: "everything blender should go through you [the
template design-lab session] or one of your limbs exclusively"). This script
plans the bakes for the farm and packs the frames it returns; it never runs
Blender.

Plan (from the repo root, in `nix develop`):
    python3 -I rt/panel/assets/bake_rack.py --plan rack-plan [--template PATH]
        [--only OUT_STEM ...] [--samples 128]
Pack the farm's frames (DIR/<stem>/NNN.png or frame.png):
    python3 -I rt/panel/assets/bake_rack.py --pack rack-plan [--only ...]

The family's one pipeline (Sam, 2026-10-17: "EVERY plugin has the SAME
lighting and scene idioms and rendering pipelines"). The driver is the
template's shared one (rack_bake.py, retained in source/rack/components/
_studio): this file only names the product. The board's rack layout
(`panel-render --rack-layout`, from src/rack_layout.rs, kept at
assets/rack-layout.json) is the one source of every part's place, flags,
region and states, and its scene is the window's (template 229a80c).

--template refreshes source/rack/components from the template's working tree
first (retain.py); without it the retained tree is baked as it stands.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'source/rack/components/_studio'))
from retain import check_large, retain  # noqa: E402
import rack_bake  # noqa: E402

if __name__ == '__main__':
    rack_bake.main(rack_bake.Product(
        name='open-pitch-quant', assets=ROOT, retain=retain, check=check_large,
        export=['cargo', 'run', '--release', '-q', '-p', 'opq-panel', '--bin',
                'panel-render', '--', '--rack-layout', '{out}'],
        cwd=ROOT.parents[1]))
