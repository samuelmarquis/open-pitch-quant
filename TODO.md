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
     - Round 1 of Sam's notes (2026-10-10, verbatim in LISTENING-LOG
       "Panel round 1"). Done in 0.5.0 (catalogue/v11): the paper screen
       and its palette; the always-shown scroll bar; natural scrolling
       over the screen (panelkit `scroll_content_notches`, 71b01e3); the
       infotext line (panelkit `hover`); values only while in use (the
       guide); SOURCE beside SCOPE (a switch since 0.5.1: "just use a
       switch" for two-point controls); no Bypass control; no witchhat or
       handwheel (their files deleted in 0.5.1); anodized-blue CAPTURE; no
       display header; Tonality Gate read as continuous.
       - The lighter monitor housing (0.5.2, done): DESIGN's beige-plastic
         screen-monitor through the composer (rack.py), our own bake,
         drawn whole.
       - Voices' stepped knob (0.6.0, done): boss-ivory with the
         knob-ring (Sam, p180), from DESIGN's farm renders composited by
         `bake.py --only stepped --renders DIR`, with a wider crop than
         the footprint contract so the ring shows whole.
       - FINISH's new face (0.5.2, done): catalin-jade-polished, light
         captions.
       - MIX as bottom-row text, the OUTPUT plate gone (0.6.0, done): on
         panelkit `strip` (c2c5514); the LCD module and lamps went with
         the plate; the three plates rebaked wider on DESIGN's farm.
       - MIX typed entry (0.6.1, done): panelkit `keys` (5518dfa) policy
         in both mounts, `entry::TextEdit` opened by a right-click or
         Enter over MIX.
         - [ ] Open question to terrible-cepstra/Sam: pluginkit reads a
           bare typed number for a `%` parameter as 0..1, so "75" sets
           100% (clamped). Proposed: a bare number means percent.
       - [ ] Display-mode keys stacked left from the screen's top-right
         edge: panelkit's key row (extraction E, in progress) plus
         DESIGN's key bake (after the template's seat-on-surface and key
         fixes, p183/p184). Candidate viewers are in
         docs/design/04-panel-ideas.md. The key sheet must be packed
         straight alpha (Keys draws with paint::ART; panelkit 1cc10e0).
     - [ ] Still known: plate titles are drawn text, not the
       panel-board's backlit cut titles (title-bake/1).
     - [ ] Ideas for later rounds: `docs/design/04-panel-ideas.md`
       (25 of them, with effort marks; Claude's first picks are basins,
       residual octaves, harmonic ladders and LCD alarms).
     - [ ] Live check of the new editor on the Mac (open, drag, pointer
       lock, resize, close while playing). sam-pc passed on 0.4.1
       (E1–E7, 2026-10-10); Ctrl-drag fine and cursor hiding couldn't be
       observed by the tester.
  5. The WRAC template's own docs (done, 2026-10-10): `wrac/README.md`
     describes this workspace and points at `../open-wrac`, with the
     lineage in `wrac/PROVENANCE.txt`; Sam removed `README_JA.md` and
     `wrac/docs/`.
  6. The pitch analysis in `open-audiokit` (0.4.5, done; Sam: "I'd
     support separating pitch tracking out now"): `audiokit::pitch` holds
     the instantaneous frequency, peaks and regions, and the greedy
     multi-F0, now allocation-free per hop (asserted with pluginkit's
     counting allocator); HOUSE byte-identical. Track continuity stays
     in the engine.
     - The shared STFT frame (0.4.6, done; Sam: "If you want to hit
       the shared STFT stage for your sisters then that's fine by me"):
       `audiokit::stft` (92a61a7), built to OpenEQ's, OpenSpectrum's and
       our requirements; the engine runs on it, HOUSE byte-identical.
       `tests/realtime_alloc.rs` now asserts that `process_block` never
       allocates (every FFT used to: realfft's `process` allocates its
       scratch per call). OpenEQ and OpenSpectrum adopt it when they
       choose.

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
- **No local Blender (Sam via DESIGN, 2026-10-10):** after a bake thrashed
  the workstation, every Blender render goes through the template's
  design-lab session and its farm, one process per machine. bake.py's
  Blender steps refuse to run unless OPQ_BLENDER_FARM=1 (farm hosts only);
  `--only stepped --renders DIR` composites the farm's renders locally.
- **Reference data stays out of git (Sam, 2026-10-09):** refpacks and
  PITCHMAP renders are gitignored, to keep the repo small.
- **The current sound survives (Sam, 2026-07-20):** HOUSE is a
  permanent algorithm choice; matching work adds, never replaces.
