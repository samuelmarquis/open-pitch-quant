#!/usr/bin/env python3
"""Pack v3: the GUI-purify sweep (small; completes what v2 proved).

v2 established that the 2017 VST3 binary's Purify parameter is FOLDED
around its center: normalized 0.0 and 1.0 both land on the same
"reduce noise" state (hat noise-share 7.5% at both extremes, ~94% across
the whole middle), so the manual's below-50 noise-INCREASE side is
unreachable through the parameter API. v3 renders the sweep with the
knob set BY MOUSE in the plugin GUI — 5 points on the three most
purify-responsive materials — plus one cross-check pair asking whether
GUI 100% equals param 1.0 (same folded state or not).

Self-test for this pack (replaces v2's waveform diff, which false-passes
on synthesis-phase randomness): render catsum_hat at GUI purify 0 and
100; the band-energy ratio E(6-14 kHz)/E(total) must differ by >2x
between them. If the GUI knob also behaves symmetrically (0 sounds like
100), record that verbatim — it means the fold is in the DSP, not the
parameter wrapper, and that itself is the answer.

Job numbers j200+. Stems carry __GUI: the pu value was set by mouse.

Run:  nix develop --command python3 tools/make_ab_pack_p3.py
"""

import shutil
import sys
import zipfile
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from make_ab_pack import SR, knobs  # noqa: E402

P2JOBS = ROOT / "testdata" / "reference-p2" / "jobs"
PACK = ROOT / "testdata" / "reference-p3"
ZIP = ROOT / "out" / "opq-pm-refpack-p3.zip"

MATS = ["catsum_hat", "amen02_165", "murky_sustain"]


def build_jobs_p3():
    jobs, n = [], [200]
    for mat in MATS:
        for pu in (0, 25, 50, 75, 100):
            jobs.append(dict(num=n[0], src=mat, pu=pu, flag="GUI",
                             note="PURIFY set by mouse in the plugin GUI"))
            n[0] += 1
    # cross-check: param API at 1.0 on the hat — same state as GUI 100?
    jobs.append(dict(num=n[0], src="catsum_hat", pu=100, flag="PARAM",
                     note="Purify via param API index 3 at 1.0 — fold cross-check"))
    return jobs


def stem_p3(j):
    return (f"j{j['num']}__{j['src']}__repeat-intel"
            f"__th0_fe0_gl0_pu{j['pu']}_el50__{j['flag']}")


OPERATOR = """\
# Pack v3 — GUI-purify sweep (small, surgical)

v2 proved the VST3 Purify parameter is folded: normalized 0.0 == 1.0 in
effect, and the manual's below-50 noise-increase side is unreachable by
param API. These jobs re-run the sweep with Purify set BY MOUSE in the
plugin GUI. Everything else exactly as before (constants, one pair one
bounce, renders/<stem>.wav, PDC, no normalize).

- __GUI jobs: set the Purify knob by mouse to the stem's pu value (0 =
  hard left, 50 = center detent, 100 = hard right). Read the GUI's own
  displayed value if it shows one; log it. Set every OTHER control via
  the param API as usual (they are not folded).
- The __PARAM job: set Purify through the parameter API (index 3) at
  normalized 1.0 instead. This pairs against j204 (GUI 100) to test
  whether the GUI drives the same folded parameter or its own path.

SELF-TEST before the batch (mandatory): render j200 (GUI 0) and j204
(GUI 100) first. Compute band-energy ratio E(6-14 kHz)/E(60 Hz-16 kHz)
for both — they must differ by more than 2x (do NOT use waveform diffs;
synthesis phases are re-randomized every render and false-pass them).
If they do NOT differ, the fold lives in the DSP itself, not the
wrapper: record that verbatim, render the batch anyway, and say so
loudly in the log.

Return: renders/ + filled _RENDER-LOG.md (+ anything the GUI displayed).
"""


def render_log(jobs):
    lines = ["# Render log — pack v3 (GUI purify)", "",
             "- self-test (j200 vs j204 band ratio): `___` vs `___` (>2x? `___`)",
             "- GUI displayed values, if any: `___`   date/DAW: `___`",
             "",
             "| done | job | input | purify | via | notes |", "|---|---|---|---|---|---|"]
    for j in jobs:
        lines.append(f"| [ ] | `j{j['num']}` | {j['src']} | {j['pu']} |"
                     f" {j['flag']} | {j['note']} |")
    return "\n".join(lines) + "\n"


def main():
    jobs = build_jobs_p3()
    if PACK.exists():
        shutil.rmtree(PACK)
    (PACK / "jobs").mkdir(parents=True)
    (PACK / "renders").mkdir()
    # reuse v2's baked job audio+mid verbatim (same materials, same chords)
    for j in jobs:
        s = stem_p3(j)
        src_pair = sorted(P2JOBS.glob(f"*__{j['src']}__*_pu50_*"))
        wav = next(p for p in src_pair if p.suffix == ".wav")
        mid = next(p for p in src_pair if p.suffix == ".mid")
        shutil.copy(wav, PACK / "jobs" / f"{s}.wav")
        shutil.copy(mid, PACK / "jobs" / f"{s}.mid")
    (PACK / "_OPERATOR.md").write_text(OPERATOR)
    (PACK / "_RENDER-LOG.md").write_text(render_log(jobs))
    (PACK / "renders" / "README.txt").write_text(
        "v3 bounces land here, same stem as jobs/.\n")
    ZIP.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(PACK.rglob("*")):
            if p.is_file():
                z.write(p, Path("opq-pm-refpack-p3") / p.relative_to(PACK))
    print(f"{len(jobs)} job pairs -> {PACK.relative_to(ROOT)};"
          f" zip {ZIP.relative_to(ROOT)} ({ZIP.stat().st_size/1e6:.0f} MB)")


if __name__ == "__main__":
    main()
