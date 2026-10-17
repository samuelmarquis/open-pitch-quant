#!/usr/bin/env python3
"""recipes: every committed render and bake file is reproducible by command.

  python3 components/_studio/recipes.py check [COMPONENT ...]
  python3 components/_studio/recipes.py render COMPONENT [--only GLOB] [--dry]

Each component with committed files under renders/ or bake/ carries
components/<c>/recipes.json:

  {"recipes": [
    {"outputs": ["renders/variants/finish-blue.png"],
     "blender": "generator/knob_scene.py",
     "args": ["{out}", "--value", "0.5", "--finish", "blue"]},
    {"outputs": ["renders/rail-*.png"],
     "python": "{studio}/render_rails.py", "args": ["--only", "rail-cross"]}
  ]}

An asset made outside this repo (a hosted image model) is recorded as
  {"outputs": [...], "external": "<the pipeline and its exact inputs>"}
and points at provenance.json; `check` accepts it, `render` skips it.

`outputs` are paths or globs relative to the component; `blender` runs
`Blender -b -P SCRIPT -- ARGS`, `python` runs `SCRIPT ARGS` under
design-lab/.venv's python (else this interpreter), both from the repo root. Script paths are relative to the component, or start with
{studio} / {repo}. In args, {out} is the absolute path of a recipe's single
output, {dir} the component's absolute path, {repo} / {studio} as above.

`check` fails when a component has committed renders/bake files and no
recipes.json, or any committed file matches no recipe's outputs. `render`
runs the recipes (those with an output matching --only) and fails when
the command fails or leaves any output it names unwritten — Blender exits 0
after a script error, so an unwritten output is the failure signal.
"""
import fnmatch
import json
import os
import subprocess
import sys
import time
from pathlib import Path

STUDIO = Path(__file__).resolve().parent
COMPONENTS = STUDIO.parent
REPO = COMPONENTS.parent
BLENDER = os.environ.get("BLENDER",
                         str(Path.home() / "Applications/Blender.app/Contents/MacOS/Blender"))
# `python` recipes run in the design-lab venv (wgpu, scipy) when it exists
VENV = REPO / "design-lab/.venv/bin/python"
PYTHON = str(VENV) if VENV.is_file() else sys.executable


def committed(c):
    out = subprocess.run(["git", "ls-files", f"components/{c}/renders", f"components/{c}/bake"],
                         cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    return [str(Path(p).relative_to(f"components/{c}")) for p in out]


def load(c):
    path = COMPONENTS / c / "recipes.json"
    return json.loads(path.read_text())["recipes"] if path.is_file() else None


def covers(recipe, rel):
    return any(fnmatch.fnmatch(rel, pat) for pat in recipe["outputs"])


def check(names):
    names = names or sorted(p.name for p in COMPONENTS.iterdir()
                            if p.is_dir() and not p.name.startswith("_"))
    bad = 0
    for c in names:
        files = committed(c)
        if not files:
            continue
        recipes = load(c)
        if recipes is None:
            print(f"MISSING {c}: {len(files)} committed render/bake files, no recipes.json")
            bad += 1
            continue
        orphans = [f for f in files if not any(covers(r, f) for r in recipes)]
        for f in orphans:
            print(f"NO-RECIPE {c}/{f}")
        bad += bool(orphans)
    print(f"recipes: {len(names)} components checked, {bad} incomplete")
    return 1 if bad else 0


def expand(s, c, out):
    return (s.replace("{studio}", str(STUDIO)).replace("{repo}", str(REPO))
            .replace("{dir}", str(COMPONENTS / c)).replace("{out}", out or ""))


def render(c, only, dry):
    recipes = load(c)
    if recipes is None:
        raise SystemExit(f"recipes: {c} has no recipes.json")
    base = COMPONENTS / c
    failed = 0
    for r in recipes:
        if only and not any(fnmatch.fnmatch(o, only) or fnmatch.fnmatch(only, o)
                            for o in r["outputs"]):
            continue
        if "external" in r:
            print(f"EXTERNAL {c} {r['outputs']}: {r['external']}")
            continue
        single = r["outputs"][0] if len(r["outputs"]) == 1 and not any(
            ch in r["outputs"][0] for ch in "*?[") else None
        out = str(base / single) if single else None
        key = "blender" if "blender" in r else "python"
        script = expand(r[key], c, out)
        script = script if Path(script).is_absolute() else str(base / script)
        args = [expand(str(a), c, out) for a in r.get("args", [])]
        cmd = ([BLENDER, "-b", "-P", script, "--", *args] if key == "blender"
               else [PYTHON, script, *args])
        print("RUN", " ".join(cmd), flush=True)
        if dry:
            continue
        start = time.time()
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        written = [p for pat in r["outputs"] for p in base.glob(pat)]
        stale = [str(p.relative_to(base)) for p in written if p.stat().st_mtime < start]
        if proc.returncode or not written or stale:
            failed += 1
            print(f"FAILED {c} {r['outputs']} (exit {proc.returncode}, unwritten {stale or 'all'})")
            print(proc.stdout[-1500:], proc.stderr[-1500:])
    print(f"recipes: {c} rendered, {failed} failed")
    return 1 if failed else 0


def main(argv):
    if not argv or argv[0] not in ("check", "render"):
        raise SystemExit(__doc__)
    if argv[0] == "check":
        return check(argv[1:])
    c, rest = argv[1], argv[2:]
    only = rest[rest.index("--only") + 1] if "--only" in rest else None
    return render(c, only, "--dry" in rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
