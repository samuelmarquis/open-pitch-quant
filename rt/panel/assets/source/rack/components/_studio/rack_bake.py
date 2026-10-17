"""rack_bake: the products' one plan/pack driver for rack-composed parts.

A product's board exports its rack layout (every plate and part: place,
flags, region, states, mattes, bakes); this driver turns each bake into one
run of the composer (rack.py, retained beside this file) and packs the
returned frames into the product's atlases. Blender never runs here: --plan
writes a job list for DESIGN's farm, --pack assembles the frames it returns.

A product calls it from a short script of its own (rt/panel/assets/bake_rack.py):

    import sys
    from pathlib import Path
    ROOT = Path(__file__).resolve().parent
    sys.path.insert(0, str(ROOT / 'source/rack/components/_studio'))
    import rack_bake
    from retain import retain
    rack_bake.main(rack_bake.Product(
        name='open-comp', assets=ROOT, retain=retain,
        export=['cargo', 'run', '--release', '-q', '-p', 'open-comp-panel', '--bin',
                'panel-render', '--', '--rack-layout', '{out}']))

then, with any python3 that has numpy and Pillow (the design-lab venv):

    python3 rt/panel/assets/bake_rack.py --plan DIR [--template PATH] [--only STEM ...]
    python3 rt/panel/assets/bake_rack.py --pack DIR [--only STEM ...]

Export: Product.export is the board's command; '{view}' is replaced by each
of Product.views (one export per board state whose layout differs, e.g. a
reference page or a dial position), '{out}' by a file it writes (else it
prints the layout). The first view's layout is kept at assets/rack-layout.json.
A bake found in several views comes from the first; an element of a later
view is taken only if it carries "page" (Product.paged) or always (not paged).

Bake: the element, with the elements it names in "with", over the elements
it names in "mattes" (matte), in the export's scene (px_per_unit, window,
light, view: the rig is the window's, see rack.py), rendering its region at DENSITY through its
"states", the bake's flags over the element's own. Bakes marked "layered"
are not the composer's. A "script" element's path, and any flag value
starting '{repo}/' (a repo-relative file the job reads, e.g. a font; list it
in Product.files so the farm syncs it), is made relative to the job's
directory.

Plan: DIR/<stem>/layout.json per bake, DIR/jobs.json (each job's command with
{RACK}) and DIR/farm.json, the same jobs in the farm's own format (farm.py
run DIR/farm.json), so a plan goes to the farm as written.

Glass: a screen-monitor bake {"kind": "glass", "out": ".../<id>.json"} is
the screen's glass (p211/p212 C: reflection at 1/3 added, vignette
multiplied), a standalone screen_scene.py run with the element's flags (the
bake's over them) so its layers register with the housing. Pack ships it as
panelkit's housing treatment loads it, the one runtime path for screen glass:
the manifest at <id>.json and the full-size raw <id>_refl.png (sRGB RGB,
adds) and <id>_vig.png (one grey data channel, multiplies) beside it, refusing a vignette that does
not reach 1 on clear glass.

Title: a panel-board bake {"kind": "title", "out": ".../<name>.json"} on a
plate whose flags carry --title is its backlit cut title (title-bake/1: the
unlit face and one light layer per letter), rendered by title_bake.py through
rack_title.py in the same rack scene as the plate, over the plate's rect.
Pack writes the plate-title/1 package: <name>-linear.png (half-float bits,
face then the letters) and <name>.json.

Pack: the frames (DIR/<stem>/NNN.png, or frame.png) feathered over the
region's outer "feather" px, packed row-major into the bake's grid,
premultiplied in linear light (or kept straight, "alpha": "straight") at the
bake's "out" path under the panel; vendor/rack-bake.json records the
template revision, layouts, commands and each output's digest.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image

DENSITY = 2
SCENE_KEYS = ('px_per_unit', 'window', 'light', 'view')
BAKE_KEYS = ('region', 'states', 'mattes', 'with', 'feather', 'bakes')


@dataclass
class Product:
    name: str                      # 'open-comp'
    assets: Path                   # rt/panel/assets
    export: list                   # the board's layout command ('{view}', '{out}' tokens)
    retain: Callable               # retain(template) -> revision
    views: list = field(default_factory=lambda: [None])
    paged: bool = False            # later views add only "page" elements
    check: Optional[Callable] = None   # run before every plan/pack (e.g. retain.check_large)
    cwd: Optional[Path] = None     # where the export runs (default: the repo)
    manifest: str = 'rack-bake.json'   # under assets/vendor
    files: list = field(default_factory=list)  # repo-relative paths the jobs read ('{repo}/' flags)

    @property
    def panel(self):
        return self.assets.parent

    @property
    def repo(self):
        return self.assets.parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export(product, view):
    """The board's rack layout at `view`."""
    out = product.assets / '.rack-layout-export.json'
    command = [str(view) if c == '{view}' else str(out) if c == '{out}' else c
               for c in product.export if not (c == '{view}' and view is None)]
    result = subprocess.run(command, capture_output=True, text=True, cwd=product.cwd or product.repo)
    if result.returncode:
        raise RuntimeError(f'Rack layout export failed ({view}):\n{result.stderr[-4000:]}')
    text = out.read_text() if '{out}' in product.export else result.stdout
    out.unlink(missing_ok=True)
    if view == product.views[0]:
        (product.assets / 'rack-layout.json').write_text(text)
    return json.loads(text)


def bakes(product):
    """Every composer bake over the views: out -> (layout, element, bake)."""
    found = {}
    for i, view in enumerate(product.views):
        doc = export(product, view)
        for el in doc['elements']:
            if i and product.paged and not el.get('page'):
                continue
            for bake in el.get('bakes', []):
                if not bake.get('layered'):
                    found.setdefault(bake['out'], (doc, el, bake))
    return found


def with_flags(flags, sets):
    """`flags` with each NAME VALUE pair of `sets` replacing or joining it."""
    flags = [str(f) for f in flags]
    for name, value in zip(sets[::2], sets[1::2]):
        if name in flags:
            flags[flags.index(name) + 1] = str(value)
        else:
            flags += [name, str(value)]
    return flags


def bake_layout(doc, el, bake, work, repo=None):
    """The composer layout for one bake: the element over its mattes."""
    by_id = {e['id']: e for e in doc['elements']}
    cwd = work.resolve().parent

    def element(e, **extra):
        e = {**{k: v for k, v in e.items() if k not in BAKE_KEYS}, **extra}
        if 'script' in e:
            e['script'] = os.path.relpath(Path(e['script']).resolve(), cwd)
        if 'flags' in e:
            e['flags'] = [os.path.relpath(Path(repo) / f[len('{repo}/'):], cwd)
                          if isinstance(f, str) and f.startswith('{repo}/') else f
                          for f in e['flags']]
        return e
    elements = [element(by_id[m], matte=True) for m in el['mattes']]
    elements += [element(by_id[w]) for w in el.get('with', [])]
    elements.append(element(el, flags=with_flags(el['flags'], bake['flags'])))
    return {**{k: doc[k] for k in SCENE_KEYS}, 'elements': elements}


def frame_count(el):
    """How many frames --states ID:FLAG=SPEC renders (a,b,c or a..b/n)."""
    if not el.get('states'):
        return 1
    spec = el['states'].partition('=')[2]
    return int(spec.rpartition('/')[2]) if '..' in spec else len(spec.split(','))


def frame_names(el):
    return [f'{i:03}.png' for i in range(frame_count(el))] if el.get('states') else ['frame.png']


def plan_one(doc, el, bake, work, samples, rack='{RACK}', repo=None):
    """Writes one bake's layout under `work`; returns (layout, command)."""
    work.mkdir(parents=True, exist_ok=True)
    layout = bake_layout(doc, el, bake, work, repo)
    (work / 'layout.json').write_text(json.dumps(layout, indent=1))
    if frame_count(el) > bake['grid'][0] * bake['grid'][1]:
        raise RuntimeError(f'{work.name}: {frame_count(el)} states do not fit its grid {bake["grid"]}')
    x, y, w, h = el['region']
    target = f'{work.name}/' + ('{i:03}.png' if el.get('states') else 'frame.png')
    command = ['blender', '-b', '-P', rack, '--', f'{work.name}/layout.json', target,
               '--density', str(DENSITY), '--samples', str(samples), '--region', f'{x},{y},{w},{h}']
    if el.get('states'):
        command += ['--states', el['states']]
    return layout, command


def glass_one(el, bake, work, repo):
    """One glass bake's command (screen_scene.py's {SCREEN} token) and outputs."""
    flags = bake_layout({'elements': [el], **{k: None for k in SCENE_KEYS}},
                        el, {'flags': bake.get('flags', [])}, work, repo)['elements'][-1]['flags']
    stem = work.name
    command = ['blender', '-b', '-P', '{SCREEN}', '--', *[str(f) for f in flags],
               '--outdir', stem, '--sid', stem]
    return command, [f'{stem}/{stem}{s}' for s in ('_refl.png', '_vig.png', '.json')]


def pack_glass(product, out, el, src, command):
    """Ships one glass bake from `src` for panelkit's treatment; returns its record."""
    sid = src.name
    manifest = json.loads((src / f'{sid}.json').read_text())
    a = manifest['aperture']
    box = (a['x'], a['y'], a['x'] + a['w'], a['y'] + a['h'])
    vig = np.asarray(Image.open(src / f'{sid}_vig.png').convert('RGB').crop(box))[..., 0] / 255.0
    peak = float(vig.max())
    if peak < 254 / 255:
        raise SystemExit(f'{sid}: vig peaks at {peak:.3f}, not 1 on clear glass')
    dest = product.panel / out
    dest.parent.mkdir(parents=True, exist_ok=True)
    names = {'_refl.png': f'{dest.stem}_refl.png', '_vig.png': f'{dest.stem}_vig.png'}
    # refl as RGB, vig as one grey channel (data): the same pixels, small
    # enough to vendor (the full-size RGBA layers pass 1 MiB)
    Image.open(src / f'{sid}_refl.png').convert('RGB').save(dest.parent / names['_refl.png'], optimize=True)
    grey = np.asarray(Image.open(src / f'{sid}_vig.png').convert('RGB'))[..., 0]
    Image.fromarray(grey).save(dest.parent / names['_vig.png'], optimize=True)
    dest.write_text(json.dumps(manifest, indent=1) + '\n')
    return {'contract': 'screen glass/1 (p211/p212 C), panelkit housing treatment',
            'element': el['id'], 'command': command, 'vig_peak': round(peak, 4),
            'outputs': {n: digest(dest.parent / n) for n in [dest.name, *names.values()]}}


TITLE_FLAGS = ('--title', '--title-cap', '--title-top', '--title-lit')


def flag(flags, name):
    flags = [str(f) for f in flags]
    return flags[flags.index(name) + 1] if name in flags else None


def title_one(doc, el, bake, work, repo):
    """One title bake: writes its layout (the plate's title flags left to the
    driver) under `work`; returns (command, outputs)."""
    work.mkdir(parents=True, exist_ok=True)
    layout = bake_layout(doc, el, bake, work, repo)
    plate = layout['elements'][-1]
    kept, pairs = [], iter(str(f) for f in plate['flags'])
    for f in pairs:
        if f in TITLE_FLAGS:
            next(pairs, None)
        else:
            kept.append(f)
    plate['flags'] = kept
    (work / 'layout.json').write_text(json.dumps(layout, indent=1))
    stem, title = work.name, flag(el['flags'], '--title')
    x, y, w, h = el['rect']
    command = ['python3', '{TITLE}', stem, '--blender', 'blender', '--scene', '{TITLE_SCENE}',
               '--px-per-unit', str(100 * DENSITY), '--', '--layout', f'{stem}/layout.json',
               '--region', f'{x},{y},{w},{h}', '--title', title]
    for name in ('--title-cap', '--title-top'):
        if flag(el['flags'], name) is not None:
            command += [name, flag(el['flags'], name)]
    outputs = [f'{stem}/{n}' for n in ('title.json', 'face.exr',
                                       *[f'letter_{i}.exr' for i in range(1, len(title) + 1)])]
    return command, outputs


def pack_title(product, out, el, src, command):
    """The plate-title/1 package from the driver's output `src`; returns its record."""
    import bakelib
    from halfpng import half_png
    title = flag(el['flags'], '--title')
    made = json.loads((src / 'title.json').read_text())
    crop = made['crop']
    letters = [bakelib.read_exr(src / f) for f in made['layers']['letters']]
    face = bakelib.read_exr(src / made['layers']['face'])
    h, w = crop['h'], crop['w']
    if len(letters) != len(title) or face.shape[:2] != (h, w):
        raise RuntimeError(f'{src.name}: layers do not match the {w}x{h} crop')
    atlas = np.zeros((2 * h, len(letters) * w, 4), dtype=np.float32)
    atlas[:h, :w, :3] = face[..., :3]
    atlas[:h, :w, 3] = face[..., 3] if face.shape[-1] == 4 else 1.0
    for i, letter in enumerate(letters):
        atlas[h:, i * w:(i + 1) * w, :3] = letter[..., :3]
        atlas[h:, i * w:(i + 1) * w, 3] = 1.0
    dest = product.panel / out
    dest.parent.mkdir(parents=True, exist_ok=True)
    linear = dest.parent / f'{dest.stem}-linear.png'
    half_png(linear, atlas)
    x, y = el['rect'][:2]
    package = {
        'contract': 'plate-title/1 over title-bake/1', 'title': title, 'letters': len(letters),
        'crop_pixels': crop,
        'logical_rect': [x + crop['x'] / DENSITY, y + crop['y'] / DENSITY, w / DENSITY, h / DENSITY],
        'atlas': {'path': os.path.relpath(linear, product.assets), 'sha256': digest(linear),
                  'layout': 'face (unlit band, RGBA) at the origin; letters left to right in one row below, RGB',
                  'encoding': 'PNG16 RGBA stores IEEE float16 bit patterns, NOT image values'},
        **{k: made[k] for k in ('unit', 'composite', 'glow', 'view_transform', 'residual', 'samples')},
    }
    dest.write_text(json.dumps(package, indent=2) + '\n')
    return {'contract': package['contract'], 'element': el['id'], 'command': command,
            'sha256': digest(dest), 'bytes': dest.stat().st_size}


def write_plan(product, plan, found, chosen, samples, revision):
    if not plan.resolve().is_relative_to(product.repo):
        raise SystemExit(f'--plan {plan}: the farm syncs the product repo, so the plan goes inside it')
    rack = product.assets / 'source/rack/components/_studio/rack.py'
    rel_rack = os.path.relpath(rack, plan.resolve())
    screen = product.assets / 'source/rack/components/screen-monitor/generator/screen_scene.py'
    studio = product.assets / 'source/rack/components'
    tokens = {'blender': 'BLENDER', 'python3': 'PYTHON', '{RACK}': rel_rack,
              '{SCREEN}': os.path.relpath(screen, plan.resolve()),
              '{TITLE}': os.path.relpath(studio / 'panel-board/generator/title_bake.py', plan.resolve()),
              '{TITLE_SCENE}': os.path.relpath(studio / '_studio/rack_title.py', plan.resolve())}
    jobs, farm = [], []
    for stem, out in chosen:
        doc, el, bake = found[out]
        if bake.get('kind') == 'glass':
            command, outputs = glass_one(el, bake, plan / stem, product.repo)
            frames = 1
        elif bake.get('kind') == 'title':
            command, outputs = title_one(doc, el, bake, plan / stem, product.repo)
            frames = 1
        else:
            _, command = plan_one(doc, el, bake, plan / stem, samples, repo=product.repo)
            outputs, frames = [f'{stem}/{n}' for n in frame_names(el)], frame_count(el)
        jobs.append({'stem': stem, 'out': out, 'frames': frames, 'command': command})
        farm.append({'cwd': str(plan.resolve().relative_to(product.repo)),
                     'argv': [tokens.get(c, c) for c in command], 'outputs': outputs})
    (plan / 'jobs.json').write_text(json.dumps({
        'product': product.name, 'template_revision': revision, 'samples': samples,
        'density': DENSITY, 'jobs': jobs}, indent=1) + '\n')
    (plan / 'farm.json').write_text(json.dumps({
        'root': str(product.repo),
        'sync': [str(plan.resolve().relative_to(product.repo)),
                 str((product.assets / 'source/rack').relative_to(product.repo)),
                 *product.files],
        'jobs': farm}, indent=1) + '\n')
    print(f'{len(jobs)} jobs, {sum(j["frames"] for j in jobs)} frames -> {plan / "farm.json"}')


def premultiply(rgba):
    """Straight sRGB RGBA bytes to sRGB-encoded linear-premultiplied RGB with
    linear alpha, as panelkit's compositor blends."""
    v = rgba.astype(np.float32) / 255
    rgb = v[..., :3]
    rgb = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4) * v[..., 3:4]
    v[..., :3] = np.where(rgb <= .0031308, rgb * 12.92, 1.055 * np.maximum(rgb, 0) ** (1 / 2.4) - .055)
    return (np.clip(v, 0, 1) * 255 + .5).astype(np.uint8)


def feathered(frame, band):
    """`frame` (straight RGBA) with alpha faded to nothing over the region's
    outer `band` px (smoothstep), so a cut shadow has no edge."""
    v = np.asarray(frame).copy()
    h, w = v.shape[:2]
    y, x = np.mgrid[0:h, 0:w].astype(np.float32) + .5
    t = np.clip(np.minimum(np.minimum(x, w - x), np.minimum(y, h - y)) / band, 0, 1)
    v[..., 3] = (v[..., 3] * (t * t * (3 - 2 * t)) + .5).astype(np.uint8)
    return Image.fromarray(v)


def body_edges(frame, band):
    """The region edges the part's opaque body reaches: its region is too small."""
    body = np.asarray(frame)[..., 3] > 250
    band = max(int(band), 1)
    return [side for side, edge in (('left', body[:, :band]), ('right', body[:, -band:]),
                                    ('top', body[:band]), ('bottom', body[-band:])) if edge.any()]


def pack_one(product, out, el, bake, frames, layout, command):
    """Packs one bake's frames into its atlas at `out`; returns its record."""
    x, y, w, h = el['region']
    cell = (round(w * DENSITY), round(h * DENSITY))
    cols, rows = bake['grid']
    atlas = Image.new('RGBA', (cell[0] * cols, cell[1] * rows))
    band = el.get('feather', 0) * DENSITY
    edges = {}
    for i, path in enumerate(frames):
        with Image.open(path) as im:
            im = im.convert('RGBA')
            if im.size != cell:
                raise RuntimeError(f'{Path(out).stem} frame {i} is {im.size}, not {cell}')
            if body_edges(im, band):
                edges[i] = body_edges(im, band)
            atlas.paste(feathered(im, band) if band else im, ((i % cols) * cell[0], (i // cols) * cell[1]))
    straight = bake['alpha'] == 'straight'
    pixels = np.asarray(atlas)
    dest = product.panel / out
    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels if straight else premultiply(pixels)).save(dest, optimize=True)
    return {
        'element': el['id'], 'component': el['component'], 'region': el['region'],
        'page': el.get('page'), 'states': el.get('states'), 'grid': bake['grid'],
        'cell_pixels': list(cell),
        'encoding': ('straight sRGB RGBA, drawn as art' if straight
                     else 'sRGB-encoded linear-premultiplied RGB; linear alpha'),
        'mattes': el['mattes'], 'layout': layout, 'feather_pixels': band, 'command': command,
        'body_touches_region_edge': edges, 'sha256': digest(dest), 'bytes': dest.stat().st_size,
    }


def main(product, argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--template', type=Path, help='retain the template working tree first')
    ap.add_argument('--samples', type=int, default=128)
    ap.add_argument('--only', nargs='+', metavar='STEM', help='these outputs only (file stems)')
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', type=Path, metavar='DIR', help="write every bake's job for the farm")
    mode.add_argument('--pack', type=Path, metavar='DIR', help="pack the farm's frames from DIR/<stem>/")
    args = ap.parse_args(argv)

    vendor = product.assets / 'vendor'
    manifest_path = vendor / product.manifest
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if args.template:
        manifest['template_revision'] = product.retain(args.template)
        vendor.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=1) + '\n')
        # this process runs the driver retained before the refresh: run the
        # new one, the same arguments without --template
        rest, skip = [], False
        for a in (sys.argv[1:] if argv is None else argv):
            if skip:
                skip = False
            elif a == '--template':
                skip = True
            elif not a.startswith('--template='):
                rest.append(a)
        os.execv(sys.executable, [sys.executable, sys.argv[0], *rest])
    if 'template_revision' not in manifest:
        raise SystemExit('No template revision on record: run with --template')
    if product.check:
        product.check()
    found = bakes(product)
    stems = {Path(out).stem: out for out in found}
    unknown = sorted(set(args.only or []) - set(stems))
    if unknown:
        raise SystemExit(f'Not a bake: {unknown}; bakes are {sorted(stems)}')
    chosen = [(s, stems[s]) for s in (args.only or sorted(stems))]
    if args.plan:
        args.plan.mkdir(parents=True, exist_ok=True)
        write_plan(product, args.plan, found, chosen, args.samples, manifest['template_revision'])
        return
    vendor.mkdir(parents=True, exist_ok=True)
    products = manifest.setdefault('products', {})
    for stale in [out for out in products if out not in stems.values()]:
        products.pop(stale)
    for stem, out in chosen:
        doc, el, bake = found[out]
        work = args.pack / stem
        if bake.get('kind') == 'glass':
            products[out] = pack_glass(product, out, el, work, glass_one(el, bake, work, product.repo)[0])
            print(f"PACKED {stem} glass", flush=True)
            continue
        if bake.get('kind') == 'title':
            command = title_one(doc, el, bake, work / '_check', product.repo)[0]
            products[out] = pack_title(product, out, el, work, command)
            print(f"PACKED {stem} title", flush=True)
            continue
        layout, command = plan_one(doc, el, bake, work / '_check', args.samples, repo=product.repo)
        record = pack_one(product, out, el, bake, [work / n for n in frame_names(el)], layout, command)
        products[out] = record
        print(f"PACKED {stem} {record['bytes']} bytes", flush=True)
    manifest.update({'contract': 'rack bake/1', 'product': product.name, 'density': DENSITY,
                     'samples': args.samples, 'driver': 'components/_studio/rack_bake.py',
                     'products': dict(sorted(products.items()))})
    manifest_path.write_text(json.dumps(manifest, indent=1) + '\n')
