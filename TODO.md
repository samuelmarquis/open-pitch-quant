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
  3. [ ] **wrac_shell's mechanical steps,** each behaviour-identical
     and validated: `plugin_entry!`, `MonoStereoPorts` (if the ports
     fit), `audio_io`. Decide `vst3_midi_channels` (the sidechain chord
     is read on which channels?). Model: open-cepstrum 0.26.15–0.26.22.
  4. [ ] **The panel, rebuilt from scratch in the family idiom (Sam,
     2026-10-09)** on panelkit: canvas, mount with `PointerLock`,
     widgets, `GestureDelivery`; our own `canvas.rs`, `font.rs`,
     `assets.rs`, `board.rs` and the drum's mounts go. Models:
     open-cepstrum (the furthest along) and open-conv (the same idioms
     in an older form, being updated now). Coordinate with open-eq and
     DESIGN. It carries ALGORITHM and PURIFY controls.
  5. [ ] `wrac/README.md`, `README_JA.md` and `wrac/docs/` are the
     WRAC template's own docs (they still describe `wrac-gain`);
     drop them or point at `../open-wrac`.
  6. [ ] A generic pitch tracker, if one falls out of the engine, moves
     into `open-audiokit`.

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
