# OpenPitchQuant — session conventions

Standing instructions for assistant sessions in this repo, instantiated
from `../open-plugin-template/CLAUDE.template.md`. Family lifecycle and
laws: `../open-plugin-template/AN-OPEN-PLUGIN-IS-MADE.md`; the shell
source map: `../open-plugin-template/WRAC-SHELL-MAP.md`.

OpenPitchQuant is the first of the line. It predates the kits and the
template's conventions, so parts of it still carry their own copies of
what the kits now hold; `TODO.md` tracks bringing it onto the common
ground.

Project records: `README.md` (the manual *and* the per-release
changelog; a contract, nothing user-facing may lie), `TODO.md` (open
items, deferrals and Sam's standing rulings), `docs/DSP.md` (the
engine walkthrough), `docs/design/` (architecture, the drum, the
panel, asset provenance), `docs/research/` (the PITCHMAP evidence
corpus, 01–04), `LISTENING-LOG.md` and `PATHS-NOT-TAKEN.md`. Unlike the
template, `LISTENING-LOG.md` is tracked here; it was public before the
convention existed.

## Working rules

- **File edits use the Edit/Write tools, never shell scripts or python
  heredocs**: Sam reads the diffs in chat.
- **Only touch this repo and the kits.** The kits (`../open-audiokit`,
  `../open-pluginkit`, `../open-panelkit`, and `../open-wrac`, the
  plugin shell) may be edited: move reusable code into them and update
  every consumer in the same pass. Tell DESIGN about template changes.
  Other `open-*` repos are read-only unless Sam says otherwise.
- **Several sessions may share this checkout.** Re-check `git status`
  before editing and before staging; stage only your own paths.
- **LISTENING-LOG.md is the primary decision record**: every render
  batch/build round gets an entry (config, the question asked, Sam's
  VERBATIM verdict, interpretation + action). Taste is data.
- **Commit after every turn with a patch version bump**; make a feature
  (minor) bump instead when the turn adds a major system. The product
  version is `wrac/plugins/opq/src-plugin/Cargo.toml`'s; each release
  gets a README changelog entry. Attribution per the session's policy.
  Remote: `git@github.com:samuelmarquis/open-pitch-quant.git`, branch
  `devel`.
- **Reference data stays out of git.** PITCHMAP renders, refpacks
  (`testdata/reference*/`, `opq-pm-refpack-*.zip`) and source material
  are gitignored to keep the repo small; only the bench tools, the
  protocol (`testdata/REFERENCE-RENDERS.md`) and the fences
  (`testdata/HOUSE-BASELINE.json`) are tracked.
- **Keep `target/` from piling up.** Every few weeks, or when a target
  passes about 10 GB, run `cargo sweep --time 7` in each workspace
  (`rt/`, `wrac/`). Only when nothing is building, deleting `target/`
  outright is also safe, apart from the wrapper's CMake cache under
  `wrac/target/wrac-plugins/opq/wrac`. Without that cache, the next
  configure must be pointed at Apple's compilers
  (`PATH=/usr/bin:$PATH CC=/usr/bin/cc CXX=/usr/bin/c++ SDKROOT=`), or
  it picks Nix clang and the vendored C headers fail.

## Architecture and boundaries

- **Two workspaces:** `rt/{engine,cli}` and `wrac/` (the plugin crate
  `opq_plugin_wrac` plus `xtask`). The wrapper framework and the
  clap-wrapper build are `../open-wrac`, consumed by path. There is no
  `rt/panel` crate yet: the panel (board, drum, canvas, font, assets)
  lives inside the plugin crate, and has no offline harness.
- **Host-free product logic:** the engine owns DSP and its parameters
  (`EngineParams`, `Algorithm::{House, Oracle}`); the panel owns layout,
  drawing and fittings; the shell owns host translation, native
  view/timer lifetime and gesture delivery.
- **Share mechanisms, vendor artwork.** Take every reusable mechanism
  from the kits:
  - `audiokit`: real-time-safe numeric DSP. A generic pitch tracker
    belongs there eventually.
  - `pluginkit`: `ParamSpec` schemas and their text, `ParamSync`, the
    saved state document, the telemetry exchange, the allocation test.
  - `panelkit`: canvas, LCD, asset packs, the Cocoa/Win32 mount with
    `PointerLock`, `GestureDelivery`, widgets, the graph viewer.
  - `open-wrac`'s `wrac_shell`: `plugin_entry!`, `MonoStereoPorts`,
    `audio_io`, `LatencyGate`, and with feature `sync`, `HostParams` and
    `save_document`/`load_document`.

  The reference consumers are open-cepstrum (0.26.15–0.26.22, one shell
  step each) and open-eq.
- **One plain-domain schema:** engine, panel, host adapter and CLI use
  the same IDs, ranges, defaults and units, and a parameter's ID equals
  its list index (`luna-vst3-param-id-must-match-index`).
- **Real-time boundary:** allocate and prepare off the callback; use
  bounded nonblocking handoffs; no allocation on the audio thread.
- **Honest platform claims:** the editor is a native Cocoa view on
  macOS and a raw Win32 child window on Windows; CPU pixels, no
  webview. Verify native input and teardown in a host, not only stills.

## Engineering law

- **Identity is ABI:** plugin ID `org.open-pitch-quant.opq`, VST3 cid
  `816CCE6ABF2353C48D06EDEC34C7E518`, AU `aumf`/`Opq1`/`Opqt`. The AU
  must stay `aumf`, or hosts hide it from MIDI routing.
- **Compatibility (Sam, 2026-10-09):** a plugin stays backward
  compatible only once it has had a public release *and* reached 1.0.
  OpenPitchQuant has a public release (v0.1.0, 2026-07-04) but is
  pre-1.0: saved projects may break, and only the exact saved-state
  version loads. Never reuse a parameter ID for a different meaning.
- **Batch param additions:** Ableton caches the param interface per
  project file; every param-list change costs a patch rebuild.
- **Install release builds:** `cargo xtask install -p opq_plugin_wrac
  --release`. A debug engine underruns in Ableton.
- **QC exercises the installed host path:** `cargo xtask validate
  --release` (clap-validator, the VST3 validator, auval), then actual
  host audio, MIDI, automation, restore and editor lifecycle checks.

## Doctrine

- **The current sound survives (Sam, 2026-07-20):** "I absolutely want
  to keep the current sound of this thing as a choice in the algorithm
  switcher." HOUSE is that sound, frozen by
  `testdata/HOUSE-BASELINE.json` (`tools/freeze_house.py --check` gates
  every engine refactor). PITCHMAP-matching work adds ORACLE; it never
  retunes HOUSE.
- **Clean-room only:** claims about PITCHMAP come from public docs and
  probe-pack I/O characterization, never disassembly.
- **The panel's design law** is `docs/design/03-the-panel.md`: an
  operable maximalist board; every fitting is wired to a real
  parameter; alarms are honest.

## Method

- The Python lab (`opq/`) is frozen; the Rust engine is canonical.
- Every batch entry states its QUESTION before rendering; every
  mechanism ships with an honest imposter for A/B when possible.
- Deferrals go to `PATHS-NOT-TAKEN.md` with what/why/what-hides/re-entry.
- Panel iterations are proposed as catalogue stills (`catalogue/vNN.png`)
  before they ship.

## Current state

- Installed: v0.1.0-era build (Jul 20) as CLAP, VST3 and AU; 18 host
  parameters, ids 0–17; HOUSE pinned, PURIFY pinned at 0.
- Engine: HOUSE and ORACLE algorithms plus PURIFY, done (397de9f).
- Next: the 18→20 parameter change (ALGORITHM, PURIFY) on a pluginkit
  schema with the SEL-2200 selector; then the wrac_shell steps; then
  the panel onto panelkit. See `TODO.md`.
