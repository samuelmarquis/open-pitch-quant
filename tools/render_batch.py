#!/usr/bin/env python3
"""Render the full material suite through the CANONICAL Rust engine.

As of 2026-07-03 this drives rt/target/release/opq (build with
`cargo build --release -p opq-cli` in rt/). The Python engine in opq/ is a
frozen prototyping lab and is no longer used for listening batches.

Usage:
  python3 tools/render_batch.py listen-010
  python3 tools/render_batch.py listen-011 --variants champ,formant100
  python3 tools/render_batch.py scratch --sources amen,audio178
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "rt" / "target" / "release" / "opq"
M = ROOT / "testdata" / "material"
P = ROOT / "testdata" / "probes"

# source slug → (audio path, targets) where targets is "notes" or
# (midi path, stretch) or midi Path
SOURCES = {
    "resoguitar": (M / "resoguitar13.wav", "A3,C#4,E4"),
    "audio178": (M / "audio178.wav", "D4,F#4,A4"),
    "audio116": (M / "audio116.wav", "C4,E4,G4"),
    "amen": (M / "amen02_165.wav", "C3,E3,G3"),
    "memories": (M / "memories.wav", "A#3,D4,F#4"),
    "when": (M / "when.wav", "D4,F#4,A#4"),
    "falter": (M / "falter.wav", "A2,C3,E3"),
    "prism": (M / "prism_scrambler_10s.wav", "F#2,C#3,G#3"),
    "phylovox": (M / "phylovox.wav", (M / "phylovox.mid", 0.75)),
    "p01": (P / "01_noise_vs_Cmaj.wav", P / "01_noise_vs_Cmaj.mid"),
    "p03": (P / "03_detuned_triad_vs_Cmaj.wav", P / "03_detuned_triad_vs_Cmaj.mid"),
    "p05": (P / "05_sustain_vs_chordchange.wav", P / "05_sustain_vs_chordchange.mid"),
}
DEFAULT_SOURCES = (
    "resoguitar,audio178,audio116,amen,memories,when,falter,prism,phylovox"
)

# CLI defaults already carry the champion base: unowned=dry, fmax=5000,
# transient bypass on, gate off, coherence 1. Variants add the rest.
CHAMP = "--rounding intelligent --feel 0.35"  # glide 0 per user default
VARIANTS = {
    "champ": CHAMP,
    "formant60": CHAMP + " --formant 0.6",
    "glide60": CHAMP + " --glide 0.06",
    "formant100": CHAMP + " --formant 1.0",
    "thresh25": CHAMP + " --threshold 25",
    "grit35": CHAMP + " --grit 0.35",
    "map": CHAMP + " --unowned map --gate 2.5",
    "flat": "",  # everything at zero, nearest rounding — the 007 reference
}
DEFAULT_VARIANTS = "champ,formant60,formant100"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("batch")
    ap.add_argument("--sources", default=DEFAULT_SOURCES)
    ap.add_argument("--variants", default=DEFAULT_VARIANTS)
    args = ap.parse_args()

    if not BIN.exists():
        sys.exit(f"{BIN} missing — run: cd rt && cargo build --release -p opq-cli")

    out = ROOT / "out" / args.batch
    out.mkdir(parents=True, exist_ok=True)
    for s in [s.strip() for s in args.sources.split(",")]:
        path, targets = SOURCES[s]
        if isinstance(targets, tuple):
            targs = ["--midi", str(targets[0]), "--midi-stretch", str(targets[1])]
        elif isinstance(targets, Path):
            targs = ["--midi", str(targets)]
        else:
            targs = ["--notes", targets]
        for v in [v.strip() for v in args.variants.split(",")]:
            f = out / f"{s}__{v}.wav"
            cmd = [str(BIN), str(path), str(f), "--stereo-out",
                   *targs, *VARIANTS[v].split()]
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"wrote {f.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
