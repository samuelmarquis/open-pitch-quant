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

then:

    python3 -I rt/panel/assets/bake_rack.py --plan DIR [--template PATH] [--only STEM ...]
    python3 -I rt/panel/assets/bake_rack.py --pack DIR [--only STEM ...]

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


def write_plan(product, plan, found, chosen, samples, revision):
    if not plan.resolve().is_relative_to(product.repo):
        raise SystemExit(f'--plan {plan}: the farm syncs the product repo, so the plan goes inside it')
    rack = product.assets / 'source/rack/components/_studio/rack.py'
    rel_rack = os.path.relpath(rack, plan.resolve())
    jobs, farm = [], []
    for stem, out in chosen:
        doc, el, bake = found[out]
        _, command = plan_one(doc, el, bake, plan / stem, samples, repo=product.repo)
        jobs.append({'stem': stem, 'out': out, 'frames': frame_count(el), 'command': command})
        farm.append({'cwd': str(plan.resolve().relative_to(product.repo)),
                     'argv': ['BLENDER' if c == 'blender' else rel_rack if c == '{RACK}' else c
                              for c in command],
                     'outputs': [f'{stem}/{n}' for n in frame_names(el)]})
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
        if args.template:
            # the retained revision, on record for the pack that follows
            manifest_path.write_text(json.dumps(manifest, indent=1) + '\n')
        return
    vendor.mkdir(parents=True, exist_ok=True)
    products = manifest.setdefault('products', {})
    for stale in [out for out in products if out not in stems.values()]:
        products.pop(stale)
    for stem, out in chosen:
        doc, el, bake = found[out]
        work = args.pack / stem
        layout, command = plan_one(doc, el, bake, work / '_check', args.samples, repo=product.repo)
        record = pack_one(product, out, el, bake, [work / n for n in frame_names(el)], layout, command)
        products[out] = record
        print(f"PACKED {stem} {record['bytes']} bytes", flush=True)
    manifest.update({'contract': 'rack bake/1', 'product': product.name, 'density': DENSITY,
                     'samples': args.samples, 'driver': 'components/_studio/rack_bake.py',
                     'products': dict(sorted(products.items()))})
    manifest_path.write_text(json.dumps(manifest, indent=1) + '\n')
