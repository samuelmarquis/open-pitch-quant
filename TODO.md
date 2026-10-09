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
     - [ ] Sam: a Live 12 check of 0.2.0 (both new parameters automate,
       a saved set reopens with them, the panel still drives the other
       18).
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
     - [ ] Ideas parked for later rounds: harmonic ladders (hmask) on the
       transect; a residual-band strip (res_bands); the LCD's crawl as
       the old mutter; the parked organs (monitor stations, session
       plates).
     - [ ] Live check of the new editor on sam-pc and the Mac (open,
       drag, pointer lock, resize, close while playing).
  5. [ ] `wrac/README.md`, `README_JA.md` and `wrac/docs/` are the
     WRAC template's own docs (they still describe `wrac-gain`);
     drop them or point at `../open-wrac`.
  6. [ ] A generic pitch tracker, if one falls out of the engine, moves
     into `open-audiokit`.

- [ ] **Live: edits made with Live's own device controls while the device
  is off never reach the saved state** (sam-pc, 0.2.1 check F: Live's
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

## Rulings

- **Compatibility (Sam, 2026-10-09):** "we do not care about backwards
  compatibility anywhere — break things freely to keep everyone on a
  clean common ground." A plugin stays backward compatible only once it
  has had a public release *and* reached 1.0. OpenPitchQuant (public
  v0.1.0, pre-1.0) may break saved projects.
- **Reference data stays out of git (Sam, 2026-10-09):** refpacks and
  PITCHMAP renders are gitignored, to keep the repo small.
- **The current sound survives (Sam, 2026-07-20):** HOUSE is a
  permanent algorithm choice; matching work adds, never replaces.
