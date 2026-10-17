"""Retain the template's canonical components in source/rack/components.

bake_rack.py runs over this one retained tree, so OpenPitchQuant's art
reproduces from this repository alone (DESIGN's path; open-conv's and
open-cepstrum's retain.py are the model). It copies the template's working
tree, not its last commit, and marks the revision `-dirty` when a retained
path has uncommitted changes.

Run: python3 -I rt/panel/assets/retain.py [TEMPLATE]
"""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPONENTS = ROOT / 'source/rack/components'
# The components rack-layout.json builds parts from.
RETAINED = ('panel-board', 'screen-monitor', 'button-bezel', 'toggle-tab', 'knob-hifi', 'knob-heady',
            'knob-catalin', 'knob-leather', 'knob-wood', 'knob-chrome', 'knob-chickenhead', 'knob-boss',
            'knob-ring')
IGNORE = shutil.ignore_patterns('__pycache__', '_scratch', 'selftest.py')


def mirror(source, target):
    """`target` becomes a copy of `source`, deletions included."""
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=IGNORE)


def retain(template):
    """Copies the retained components and the composer's studio; returns the
    template's short revision, `-dirty` when retained paths have changes."""
    template = Path(template).resolve()
    corpus = template / 'components'
    paths = [f'components/{name}' for name in (*RETAINED, '_studio')]
    dirty = subprocess.check_output(['git', '-C', str(template), 'status', '--short', '--', *paths], text=True)
    revision = subprocess.check_output(['git', '-C', str(template), 'rev-parse', '--short', 'HEAD'],
                                       text=True).strip()
    if dirty.strip():
        print(f'Retaining uncommitted template changes:\n{dirty}', flush=True)
        revision += '-dirty'
    COMPONENTS.mkdir(parents=True, exist_ok=True)
    for stale in COMPONENTS.iterdir():
        if stale.is_dir() and stale.name not in (*RETAINED, '_studio'):
            shutil.rmtree(stale)
    for name in RETAINED:
        origin, dest = corpus / name, COMPONENTS / name
        mirror(origin / 'generator', dest / 'generator')
        for meta in ('provenance.json', 'recipes.json'):
            if (origin / meta).is_file():
                shutil.copyfile(origin / meta, dest / meta)
    # The studio: its modules, rigs' HDRIs and provenance (no self-tests),
    # and its families, material library and fonts.
    studio = COMPONENTS / '_studio'
    studio.mkdir(exist_ok=True)

    def kept(path):
        return path.is_file() and path.suffix in ('.py', '.hdr', '.json') and not path.name.startswith('selftest')
    for path in [p for p in studio.iterdir() if kept(p)]:
        if not (corpus / '_studio' / path.name).is_file():
            path.unlink()
    for path in sorted((corpus / '_studio').iterdir()):
        if kept(path):
            shutil.copyfile(path, studio / path.name)
    for name in ('families', 'matlib', 'fonts'):
        mirror(corpus / '_studio' / name, studio / name)
    pin_large()
    return revision


# Retained files this size or larger stay out of git (open-conv's rule,
# relayed by DESIGN): `.gitignore` lists them and large.json pins their
# digests, so a bake can refuse copies that differ.
LARGE_BYTES = 1 << 20
LARGE = ROOT / 'source/rack/large.json'


def digest(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin_large():
    """Lists the retained tree's large files in its .gitignore and pins
    their digests in large.json."""
    tree = ROOT / 'source/rack'
    large = sorted(p for p in tree.rglob('*') if p.is_file() and p.stat().st_size >= LARGE_BYTES
                   and p.name not in ('.gitignore', 'large.json'))
    pins = {str(p.relative_to(tree)): {'sha256': digest(p), 'bytes': p.stat().st_size} for p in large}
    import json
    LARGE.write_text(json.dumps(pins, indent=1, sort_keys=True) + '\n')
    (tree / '.gitignore').write_text(
        '# Retained files of 1 MiB or more: pinned in large.json, kept out of git.\n'
        + ''.join(f'/{path}\n' for path in pins))


def check_large():
    """Raises unless every pinned large file is present with its digest."""
    import json
    if not LARGE.exists():
        return
    tree = ROOT / 'source/rack'
    for path, pin in json.loads(LARGE.read_text()).items():
        file = tree / path
        if not file.is_file() or digest(file) != pin['sha256']:
            raise SystemExit(f'Retained large file {path} is missing or differs from large.json: '
                             're-run with --template to retain it')


if __name__ == '__main__':
    import sys
    print(retain(sys.argv[1] if len(sys.argv) > 1 else ROOT.parents[3] / 'open-plugin-template'))
