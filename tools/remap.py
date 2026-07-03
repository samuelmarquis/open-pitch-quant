#!/usr/bin/env python3
"""CLI for the offline remap engine.

Examples:
  python3 tools/remap.py testdata/probes/03_detuned_triad_vs_Cmaj.wav \\
      --midi testdata/probes/03_detuned_triad_vs_Cmaj.mid -o out/x.wav
  python3 tools/remap.py testdata/material/amen02_165.wav \\
      --notes C4,E4,G4 --mode repeat -o out/amen_Cmaj.wav
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opq import engine, io  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("--midi", help="MIDI file defining the held-note sidechain")
    ap.add_argument("--notes", help="static held notes, e.g. C4,E4,G4")
    ap.add_argument("--mode", default="repeat", choices=["repeat", "custom"])
    ap.add_argument("--assign", default="peak", choices=["peak", "group"],
                    help="peak = M0 independent snapping; group = M1 "
                         "harmonic objects")
    ap.add_argument("--voices", type=int, default=6,
                    help="max harmonic objects per frame (group mode)")
    ap.add_argument("--unowned", default="map", choices=["map", "dry"],
                    help="group mode: unclaimed peaks are mapped M0-style "
                         "or left dry (residual layer)")
    ap.add_argument("--fmax-map", type=float, default=None,
                    help="peaks above this Hz pass through unmapped")
    ap.add_argument("--transient-bypass", action="store_true",
                    help="onset frames pass dry + re-anchor phases")
    ap.add_argument("--flux-thresh", type=float, default=0.6)
    ap.add_argument("--tonality-gate", type=float, default=None,
                    help="peak/mean ratio below which a region is 'noise'")
    ap.add_argument("--tonality-mode", default="fresh",
                    choices=["fresh", "bypass"],
                    help="noise regions: map with fresh phases, or pass dry")
    ap.add_argument("--no-phase-lock", action="store_true",
                    help="legacy free-running phases (watery; for A/B)")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    if bool(args.midi) == bool(args.notes):
        ap.error("exactly one of --midi / --notes required")

    x = io.load_audio(args.input)
    if args.midi:
        held_fn = io.held_fn_from_breakpoints(io.midi_breakpoints(args.midi))
    else:
        held_fn = io.held_fn_static(io.parse_note(n) for n in args.notes.split(","))

    y = engine.process(
        x, io.SR, held_fn, mode=args.mode,
        fmax_map=args.fmax_map,
        transient_bypass=args.transient_bypass,
        flux_thresh=args.flux_thresh,
        tonality_gate=args.tonality_gate,
        tonality_mode=args.tonality_mode,
        phase_lock=not args.no_phase_lock,
        assign=args.assign,
        voices=args.voices,
        unowned=args.unowned,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    io.save_audio(out, y)
    print(f"wrote {out} ({len(y)/io.SR:.2f}s)")


if __name__ == "__main__":
    main()
