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
  2. [ ] **The 18→20 parameter change on a pluginkit schema.**
     ALGORITHM (HOUSE/ORACLE) and PURIFY become host parameters 18 and
     19 on an `open-pluginkit` `ParamSpec` schema with id == index,
     served by `wrac_shell::HostParams`, saved with
     `save_document`/`load_document` (exact version only; old projects
     need not load, see Rulings). Together with the panel's SEL-2200
     selector (HOUSE/ORACLE positions), the NO BIJECTION plate
     re-lettered per position (CARRIED/DISCARDED; its bake key gains
     the algorithm) and a PURIFY fitting, proposed first as
     `catalogue/v07.png`. Then a release install, validate, and a Live
     check.
  3. [ ] **wrac_shell's mechanical steps,** each behaviour-identical
     and validated: `plugin_entry!`, `MonoStereoPorts` (if the ports
     fit), `audio_io`. Decide `vst3_midi_channels` (the sidechain chord
     is read on which channels?). Model: open-cepstrum 0.26.15–0.26.22.
  4. [ ] **The panel onto panelkit:** canvas, mount with
     `PointerLock`, widgets, `GestureDelivery`; our own `canvas.rs`,
     `font.rs`, `assets.rs` and `SharedState` go. Coordinate with
     open-eq (doing the same port now) and DESIGN.
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
