#!/usr/bin/env python3
"""Render our engine's side of every A/B job from the identical job files.

For each pack job (except j00, the plugin-bypassed control) the stem's
PITCHMAP settings are translated to opq flags and the job WAV+MID —
the same bytes PITCHMAP rendered on the Windows machine — go through
rt/target/release/opq into out/ab-ours/<stem>.wav.

The translation (calibrated against PITCHMAP's own renders, see
docs/research/04-pitchmap-measured.md):

  Edit Mode repeat/custom  -> --mode repeat|custom
  Xclude Round. near/intel -> --rounding nearest|intelligent
  th50   -> --threshold 45   (th50 spared -40c and +20c, corrected +35c;
                              45c reproduces the spared pair, C diverges)
  fe100  -> --feel 1.0       (their FEEL 100 ~= leave source detune)
  gl100  -> --glide 0.25     (their glide is ONSET-ONLY portamento,
                              ~160c early offset settling in ~1/4 s;
                              ours also glides retargets — known fork)
  el0    -> --voices 12      el100 -> --voices 1   (ELECTRIFY = tracked
                              sound count; their el50 default ~ our 6)
  pu*, alg*, strict, NONOTES -> no analog; base flags (NONOTES jobs
                              carry their empty MID — we pass unowned
                              dry where PITCHMAP mutes; that divergence
                              is the finding, not an error)

Base flags for every render pin the engine to the job's declared state
(the CLI default carries the champ's feel 0.35, so --feel is always
explicit). Everything else stays at CLI defaults = champ base.

Run:  nix develop --command python3 tools/render_ab_ours.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from make_ab_pack import build_jobs, stem  # noqa: E402

BIN = ROOT / "rt" / "target" / "release" / "opq"
JOBS = ROOT / "testdata" / "reference" / "jobs"
OUT = ROOT / "out" / "ab-ours"

RND = dict(near="nearest", intel="intelligent")


def flags(j):
    k = j["knobs"]
    f = ["--mode", j["mode"], "--rounding", RND[j["rnd"]]]
    f += ["--threshold", "45" if k["th"] == 50 else "0"]
    f += ["--feel", "1.0" if k["fe"] == 100 else "0"]
    f += ["--glide", "0.25" if k["gl"] == 100 else "0"]
    if k["el"] == 0:
        f += ["--voices", "12"]
    elif k["el"] == 100:
        f += ["--voices", "1"]
    return f


def main():
    if not BIN.exists():
        sys.exit(f"{BIN} missing — cd rt && cargo build --release -p opq-cli")
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [j for j in build_jobs() if j["flag"] != "NULL"]
    for j in jobs:
        s = stem(j)
        cmd = [str(BIN), str(JOBS / f"{s}.wav"), str(OUT / f"{s}.wav"),
               "--midi", str(JOBS / f"{s}.mid"), *flags(j)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"{s}: {r.stderr.strip()}")
        print(f"j{j['num']:02d} {' '.join(flags(j))}")
    (OUT / "_ENGINE.txt").write_text(f"opq @ {commit}\n")
    print(f"{len(jobs)} renders -> {OUT.relative_to(ROOT)} (engine {commit})")


if __name__ == "__main__":
    main()
