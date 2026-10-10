# TODO

Open work, deferrals and standing rulings. Verification belongs in commit
messages, and behavior belongs in the README; neither is kept here.

## Open

- [ ] **Onto the family's common ground (2026-10-09).** OpenPitchQuant
  predates the kits; bring it up to the template's standards. Order
  agreed with open-cepstrum's session:
  1. Records and dead code (0.1.1, done): `CLAUDE.md`, this file; the
     nih-plug shell (`rt/plugin`, `rt/xtask`) and the template's demo
     `wrac-gain` removed; refpacks gitignored.
  2. The 18→20 parameter change on a pluginkit schema (0.2.0, done):
     the engine's `params.rs` holds the `ParamSpec` rows, id == index,
     with ALGORITHM (18) and PURIFY (19); `wrac_shell::HostParams` is
     the host's view, pluginkit's `ParamSync` carries edits to audio,
     and state is `save_document`/`load_document` at version 2.
     - Live 12 check of the new parameters: covered by sam-pc's 0.4.1
       run (E7: Algorithm and Purify move from Live's panel and from
       automation; F5/F6: they save and reopen).
     - Not built, by Sam's word (2026-10-09: the panel is redone from
       scratch in the family idiom soon): the old board's SEL-2200
       selector, the NO BIJECTION plate re-lettered per algorithm
       (CARRIED/DISCARDED) and a PURIFY fitting. They are design input
       for the new panel.
  3. wrac_shell's mechanical steps (0.2.1, done): `plugin_entry!`,
     `MonoStereoPorts::main_only` (added to open-wrac for a product whose
     side chain is MIDI), `audio_io`'s `read_block`/`write_block`.
     `vst3_midi_channels` stays at the default 1, as every build so far
     has had (daily-driven in Live over VST3). `LatencyGate` is not
     taken: the latency is a constant 4096.
  4. The panel, rebuilt from scratch in the family idiom (Sam,
     2026-10-09: "an LCD screen showing the display and dynamic
     elements, and skeuomorphic solid panels with fixed controls
     beneath"; first pass is Claude's to explore, then many nit rounds).
     - First pass (0.3.0, done, catalogue/v07): `rt/panel` on panelkit
       (canvas, LCD module, widgets, mount with `PointerLock`,
       `GestureDelivery`), open-eq's mounts; plates baked with
       panel-board at their exact size, knobs from OpenCepstrum's
       knob-preview atlases, switches/LEDs from template components.
     - Nits (0.3.1, done, catalogue/v08): toggle and selector size
       (Sam: the bat switch read too small); the time axis; octave and
       lane names; the bypass lamp; the strip's version.
     - The switches' size contract (0.3.2, done): DESIGN's template
       6796dcc (plate p174); bake.py renders toggle-bat and the
       chickenhead itself under it, and the stopgap crops are gone.
     - [ ] Sam's fuller notes on v07/v08, then more nit rounds. Still
       known: plate titles are drawn text, not the panel-board's backlit
       cut titles (title-bake/1).
     - [ ] Ideas for later rounds: `docs/design/04-panel-ideas.md`
       (25 of them, with effort marks; Claude's first picks are basins,
       residual octaves, harmonic ladders and LCD alarms).
     - [ ] Live check of the new editor on the Mac (open, drag, pointer
       lock, resize, close while playing). sam-pc passed on 0.4.1
       (E1–E7, 2026-10-10); Ctrl-drag fine and cursor hiding couldn't be
       observed by the tester.
  5. [ ] The WRAC template's own docs. `wrac/README.md` now describes
     this workspace and points at `../open-wrac`, with the lineage in
     `wrac/PROVENANCE.txt`. Still to remove: `wrac/README_JA.md` and
     `wrac/docs/`, which describe the template's demo plugin. Claude's
     `git rm` was refused by the session's permissions; it waits for
     Sam.
  6. [ ] A generic pitch tracker, if one falls out of the engine, moves
     into `open-audiokit`.

- [x] **Live: edits made with Live's own device controls while the device
  is off never reach the saved state** (closed 2026-10-10: on 0.4.1,
  sam-pc passed F5, F6 (i) and F6 (ii), saving while still off, and A1:
  an automated Mix lane over 8 bars ran with no backward or repeated
  steps. Live's Device On is its own switch, not our Bypass parameter;
  that's expected.) (sam-pc, 0.2.1 check F: Live's
  parameter list new, our saved document old). Every plugin-side path is
  tested and saves (audio.rs tests). terrible-cepstra's hypothesis: a
  family-wide wrapper gap, as open-wrac's clap-wrapper never overrides
  VST3 `IEditController::setParamNormalized`, so a host edit reaches the
  plugin only through process(). Confirming on sam-pc: (a) does process()
  run while off, (b) the same edit from our own editor, (c) the same on
  open-cepstrum. Confirmed (F6: an edit from our own editor persists;
  Live-panel edits never reach the plugin) plus a second symptom (F5:
  Algorithm, a list param, lost from Live's panel even while
  processing). Fix: open-wrac 668bc84 (P27, terrible-cepstra): the
  wrapper forwards setParamNormalized to the plugin. Reviewed; open
  question: Live's automation echoes to the controller may now step
  automated continuous lanes backwards. 0.3.1 is built on it; awaiting
  WIN's rerun of F5/F6 (and save-while-still-off) and an automation
  smoothness check.

- PITCHMAP without MIDI (0.4.0, done; Sam: "full pitchmap
  non-midi-input compat with vertical scrolling in the main window and
  clicking on the keys on the left bar"): Map Source MIDI/Keys, the ruler
  as the Lower Keyboard (target / exclude / bypass, Repeat or Custom
  scope, drag to paint), the wheel scrolling all 128 notes, key states in
  the document's product section (v3), the host told its state is dirty.
  - [ ] Not yet PITCHMAP's: the per-source Pitch Mapping Sliders (127
    slots, this-goes-there, -12..+23), Xclude Round mode (up/down/
    nearest for excluded pitches), Regular mode's note-ons latch-toggling
    the keys, Global Threshold, shift-click sine reference, Key Transform
    (root + scale presets), snapshots.
  - Live check of Keys on sam-pc (0.4.1, K1–K4 passed 2026-10-10). K4's
    bottom label "D4294967295" (octave −1 unsigned) is fixed in 0.4.2
    (unit-tested; no Windows recheck queued, per the ruling below).
- panelkit's `Grabbed` anchor (0.4.0, done) replaces fittings.rs's own.

## Rulings

- **Family input rulings (Sam via terrible-cepstra, 2026-10-09):** the
  wheel is "fingers up = value up" regardless of natural scrolling
  (panelkit's `mount::scroll_notches` returns that; our fittings take a
  positive notch as more); after a relative drag the cursor returns where
  it was grabbed (our anchor: the knob's centre plus the press offset).

- **Windows checks are sequenced late (Sam via terrible-cepstra,
  2026-10-10):** sam-pc's priority is real audio work. Don't queue
  WIN-COMPUTER-USE runs for patch bumps or knob checks; running things
  on Windows comes far later. A cross-compile (`cargo check --target
  x86_64-pc-windows-gnu`) is still fine.

- **Compatibility (Sam, 2026-10-09):** "we do not care about backwards
  compatibility anywhere — break things freely to keep everyone on a
  clean common ground." A plugin stays backward compatible only once it
  has had a public release *and* reached 1.0. OpenPitchQuant (public
  v0.1.0, pre-1.0) may break saved projects.
- **Reference data stays out of git (Sam, 2026-10-09):** refpacks and
  PITCHMAP renders are gitignored, to keep the repo small.
- **The current sound survives (Sam, 2026-07-20):** HOUSE is a
  permanent algorithm choice; matching work adds, never replaces.
