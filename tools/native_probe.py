#!/usr/bin/env python3
"""Run the family native probe's generic checks on OpenPitchQuant.

The probe is ../open-wrac/tools/native-probe. OpenPitchQuant has no product
layer, so it needs no signed app of its own: the family checks run through
OpenCepstrum's signed app (its names below; build it once from
open-cepstrum), with this product's installed VST3 and the geometry
`panel-render --geometry` prints. Always pass --family-only.

    python3 tools/native_probe.py --run --family-only --remote servo-critter@solidgoldmagikarp

A run takes the machine's pointer and keyboard for about a minute: the
headless Mini needs no asking, a local run asks Sam first.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / "open-wrac/tools/native-probe"))
import native_probe  # noqa: E402


def geometry():
    renderer = ROOT / "rt/target/release/panel-render"
    if not renderer.is_file():
        raise RuntimeError("Build panel-render (release) first, or pass --geometry PATH.")
    return subprocess.check_output([str(renderer), "--geometry"], text=True)


PRODUCT = native_probe.Product(
    executable="OpenCepstrumNativeProbe",
    identifier="org.open-cepstrum.native-probe",
    bundle_name="OpenCepstrum Native Probe",
    identity="OpenCepstrum Native Probe",
    plugin=Path.home() / "Library/Audio/Plug-Ins/VST3/OpenPitchQuant.vst3",
    out=ROOT / "out",
    geometry=geometry,
    remote_stage=".open-cepstrum-probe",
)

if __name__ == "__main__":
    sys.exit(native_probe.main(PRODUCT, __doc__))
