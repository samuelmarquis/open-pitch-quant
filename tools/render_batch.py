#!/usr/bin/env python3
"""Render the full material suite through named engine-variant presets.

Usage:
  python3 tools/render_batch.py listen-006
  python3 tools/render_batch.py listen-007 --variants group-dry,peak
  python3 tools/render_batch.py scratch --sources amen,audio178

Writes out/<batch>/<source>__<variant>.wav for every (source, variant).
Target-note sets are chroma-informed (see git history / MATERIAL.md) and
deliberately near each clip's own tonal center — retuning material toward
itself is the fair test; creative remaps are a per-experiment override.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opq import engine, io  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
M = ROOT / "testdata" / "material"
P = ROOT / "testdata" / "probes"

# source slug → (audio path, targets: "note,note,.." or .mid Path)
SOURCES = {
    "resoguitar": (M / "resoguitar13.wav", "A3,C#4,E4"),   # A-major territory
    "audio178": (M / "audio178.wav", "D4,F#4,A4"),         # D-majorish vocal
    "audio116": (M / "audio116.wav", "C4,E4,G4"),          # C/E dominant
    "amen": (M / "amen02_165.wav", "C3,E3,G3"),            # drums vs C major
    "memories": (M / "memories.wav", "A#3,D4,F#4"),        # CIRCLES: D-F#-A# aug
    "when": (M / "when.wav", "D4,F#4,A#4"),                # same aug family
    "falter": (M / "falter.wav", "A2,C3,E3"),              # big A2 bass → Am
    "prism": (M / "prism_scrambler_10s.wav", "F#2,C#3,G#3"),  # sound design
    # paired MIDI part; stretch 0.75 = exact 4:3 tempo-export mismatch
    # (midi span 29.99s vs audio 22.50s — 120 vs 160 BPM)
    "phylovox": (M / "phylovox.wav", (M / "phylovox.mid", 0.75)),
    # probes, rendered on demand via --sources:
    "p01": (P / "01_noise_vs_Cmaj.wav", P / "01_noise_vs_Cmaj.mid"),
    "p03": (P / "03_detuned_triad_vs_Cmaj.wav", P / "03_detuned_triad_vs_Cmaj.mid"),
    "p05": (P / "05_sustain_vs_chordchange.wav", P / "05_sustain_vs_chordchange.mid"),
}
DEFAULT_SOURCES = (
    "resoguitar,audio178,audio116,amen,memories,when,falter,prism,phylovox"
)

_BASE = dict(fmax_map=5000.0, transient_bypass=True)
VARIANTS = {
    # current champions
    "group-dry": dict(_BASE, assign="group", voices=6, unowned="dry"),
    "group-map": dict(_BASE, assign="group", voices=6, unowned="map",
                      tonality_gate=2.5),
    # octave-semantics variant (exact held notes, no pitch-class repeat)
    "group-dry-custom": dict(_BASE, assign="group", voices=6, unowned="dry",
                             mode="custom"),
    # references
    "peak": dict(_BASE, tonality_gate=2.5),   # M0.5, per-peak snapping
    "peak-raw": {},                           # naked M0 (batch-001 sound)
}
DEFAULT_VARIANTS = "group-dry,group-map"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("batch", help="output folder name under out/")
    ap.add_argument("--sources", default=DEFAULT_SOURCES)
    ap.add_argument("--variants", default=DEFAULT_VARIANTS)
    args = ap.parse_args()

    out = ROOT / "out" / args.batch
    out.mkdir(parents=True, exist_ok=True)
    for s in [s.strip() for s in args.sources.split(",")]:
        path, targets = SOURCES[s]
        x = io.load_audio(path)
        if isinstance(targets, tuple):  # (midi path, time stretch)
            held = io.held_fn_from_breakpoints(
                io.midi_breakpoints(targets[0], stretch=targets[1])
            )
        elif isinstance(targets, Path):
            held = io.held_fn_from_breakpoints(io.midi_breakpoints(targets))
        else:
            held = io.held_fn_static(
                io.parse_note(n) for n in targets.split(",")
            )
        for v in [v.strip() for v in args.variants.split(",")]:
            y = engine.process(x, io.SR, held, **VARIANTS[v])
            f = out / f"{s}__{v}.wav"
            io.save_audio(f, y)
            print(f"wrote {f.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
