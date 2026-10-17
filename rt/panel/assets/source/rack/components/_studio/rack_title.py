"""The rack composer as a title-bake/1 `--scene`: one region of a rack
layout, called the way the title driver calls a panel scene.

  blender -b -P rack_title.py -- OUT --layout LAYOUT.json --region x,y,w,h
      [--samples N] [--denoise on|off] [--adaptive on|off] [--dark]
      [element flags, e.g. --title MUTATION --title-lit 2 ...]

Only argument translation: rack.py takes LAYOUT and OUT first, and the title
flags (and --dark, which the plate also reads) are appended to the layout's
last element, the bake's own plate (rack_bake puts its mattes first). A
layer's --title-lit replaces the layout's. rack.py renders an OUT ending in
.exr raw, and --dark with no rig.
"""
import json
import runpy
import sys
import tempfile
from pathlib import Path

COMPOSER = Path(__file__).resolve().parent / 'rack.py'
OPTIONS = ('--layout', '--region', '--samples', '--denoise', '--adaptive')

argv = sys.argv[sys.argv.index('--') + 1:]
out, rest = argv[0], argv[1:]
options, element_flags, dark = {}, [], False
args = iter(rest)
for arg in args:
    if arg in OPTIONS:
        options[arg] = next(args)
    else:
        dark = dark or arg == '--dark'
        element_flags.append(arg)
layout = json.loads(Path(options.pop('--layout')).read_text())
plate = layout['elements'][-1]
flags = [str(flag) for flag in plate.get('flags', [])]
if '--title-lit' in element_flags and '--title-lit' in flags:
    index = flags.index('--title-lit')
    del flags[index:index + 2]
plate['flags'] = flags + element_flags
with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as handle:
    json.dump(layout, handle)
sys.argv = [str(COMPOSER), '--', handle.name, out, '--density', '2',
            *[str(part) for option in options.items() for part in option],
            *(['--dark'] if dark else [])]
runpy.run_path(str(COMPOSER), run_name='__main__')
