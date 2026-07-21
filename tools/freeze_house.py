#!/usr/bin/env python3
"""Freeze the HOUSE baseline: the permanent regression fence.

Standing law: the current sound ships as its own algorithm choice and is
never silently retuned. This renders a coverage matrix through opq —
every material, and variants exercising every parameter code path — and
commits a manifest of sha256/rms/duration per render (the WAVs stay in
out/house-freeze/, gitignored). Any future refactor re-runs this script:
with --algorithm house (or default) every hash must match the manifest,
byte for byte, or the change does not merge.

Run:    nix develop --command python3 tools/freeze_house.py
Check:  nix develop --command python3 tools/freeze_house.py --check
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from render_batch import CHAMP, SOURCES  # noqa: E402

BIN = ROOT / "rt" / "target" / "release" / "opq"
OUT = ROOT / "out" / "house-freeze"
MANIFEST = ROOT / "testdata" / "HOUSE-BASELINE.json"

# every param code path gets exercised on a focused subset
VARIANT_SOURCES = ["p03", "p05", "amen", "phylovox"]
VARIANTS = {
    "champ": CHAMP,
    "flat": "",
    "glide60": CHAMP + " --glide 0.06",
    "thresh25": CHAMP + " --threshold 25",
    "custom": CHAMP + " --mode custom",
    "voices1": CHAMP + " --voices 1",
    "formant100": CHAMP + " --formant 1.0",
    "grit35": CHAMP + " --grit 0.35",
    "map": CHAMP + " --unowned map --gate 2.5",
    "feel100": "--rounding intelligent --feel 1.0",
    "carry0": CHAMP + " --carry 0.0",
    "notransient": CHAMP + " --no-transient",
}


def jobs():
    for slug in SOURCES:
        yield slug, "champ"
    for slug in VARIANT_SOURCES:
        for v in VARIANTS:
            if v != "champ":
                yield slug, v


def targs(slug):
    path, targets = SOURCES[slug]
    if isinstance(targets, tuple):
        return path, ["--midi", str(targets[0]), "--midi-stretch", str(targets[1])]
    if isinstance(targets, Path):
        return path, ["--midi", str(targets)]
    return path, ["--notes", targets]


def render_all():
    OUT.mkdir(parents=True, exist_ok=True)
    entries = {}
    for slug, v in jobs():
        path, ta = targs(slug)
        name = f"{slug}__{v}.wav"
        f = OUT / name
        cmd = [str(BIN), str(path), str(f), "--stereo-out", *ta, *VARIANTS[v].split()]
        subprocess.run(cmd, check=True, capture_output=True)
        data = f.read_bytes()
        x, sr = sf.read(str(f), always_2d=True)
        entries[name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "rms": float(np.sqrt(np.mean(x.mean(axis=1) ** 2))),
            "samples": len(x),
            "flags": VARIANTS[v],
        }
    return entries


def main():
    if not BIN.exists():
        sys.exit(f"{BIN} missing — cd rt && cargo build --release -p opq-cli")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    entries = render_all()

    if "--check" in sys.argv:
        ref = json.loads(MANIFEST.read_text())
        bad = [n for n, e in entries.items()
               if ref["renders"].get(n, {}).get("sha256") != e["sha256"]]
        missing = [n for n in ref["renders"] if n not in entries]
        if bad or missing:
            for n in bad:
                print(f"HASH MISMATCH: {n}")
            for n in missing:
                print(f"MISSING: {n}")
            sys.exit(f"HOUSE FENCE BREACHED: {len(bad)} changed, "
                     f"{len(missing)} missing (frozen @ {ref['engine_commit'][:8]})")
        print(f"HOUSE intact: {len(entries)} renders byte-identical to the "
              f"manifest (frozen @ {ref['engine_commit'][:8]})")
        return

    MANIFEST.write_text(json.dumps(
        {"engine_commit": commit, "frozen": "2026-07-21",
         "law": "algorithm=house must reproduce these bytes forever",
         "renders": entries}, indent=1) + "\n")
    print(f"froze {len(entries)} renders @ {commit[:8]} -> "
          f"{MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
