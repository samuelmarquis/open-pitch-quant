# TODO

Open work, deferrals and standing rulings. Verification belongs in commit
messages, and behavior belongs in the README; neither is kept here.

## Open

- [ ] **HOUSE's Feel reaches too far (Sam, 2026-10-11), waiting on
  Sam's go to re-freeze HOUSE.** Sam, 2026-10-16: "HOUSE's feel still
  has the same problem (on phylovox, you can hear--literally, the second
  note--that it warbles up and down on HOUSE with feel at 40% but does
  not on oracle)". Measured (LISTENING-LOG "HOUSE's Feel, second
  round"): on that note HOUSE overshoots ~90 c sharp and comes back;
  capping the deviation at ±50 c (ORACLE's bound) lands it within
  ~10-30 c of ORACLE; restarting the average on a note change barely
  helps. The cap is recommended; it changes 30 of the 56 frozen renders,
  so it needs Sam's go to re-record the baseline. Sam is auditioning
  A/B/C/D on his own material through the strip's HOUSE FEEL dropdown
  (0.8.13). When he picks: make the pick HOUSE's only law, remove the
  dropdown, `EngineParams.house_feel`, `--house-feel` and the saved
  field, and re-record the baseline if it isn't A. The original note: "One thing that I think HOUSE should get from ORACLE;
  FEEL for ORACLE seems to track small deviations but not large ones,
  but FEEL on HOUSE allows deviations of a semitone or more." The
  cause: ORACLE's deviation is from the voice's own nearest semitone,
  so it is within 50 cents by construction; HOUSE's is from a 250 ms
  average of the voice's pitch, with no limit. Capping HOUSE's at 50
  cents is a five-line change (kept as a patch, not shipped), but it
  is no edge case: 30 of the 56 frozen renders change, most across
  nearly every sample (the difference is 2 to 18 dB under the signal),
  because real material's tracked pitch passes 50 cents constantly.
  That retunes HOUSE, which is frozen by Sam's doctrine, so it is his
  call. Before/after renders: `out/feel-cap-ab/` (A is HOUSE now, B is
  capped). Options: re-record HOUSE with the cap; a wider cap (say 100
  cents) that only catches leaps; or leave HOUSE and fix it elsewhere.
- **The HOUSE fence builds its own renderer (0.8.2).** `freeze_house.py`
  used whatever `opq` binary was lying in `rt/target/release`, so a
  check could pass without testing the change in front of it. It did
  once, for 0.8.0; rechecked with a fresh build, 0.8.0 and 0.8.1 are
  byte-identical to the manifest.
- [x] **ORACLE's phase smear, closed by Sam's ear (2026-10-16):** "The
  phasing issue with HOUSE has been solved imo", corrected the same
  day: "I meant ORACLE's phase smear". Nothing was changed for it
  directly; it went sometime between 0.7.14 and 0.8.10. The original
  note, Sam, 2026-10-11: "I think 'ORACLE'
  needs a little more work; the phase sounds much smearier than HOUSE,
  and much smearier than I remember pitchmap sounding." Not started.
  First step: an A/B of ORACLE against HOUSE and the PITCHMAP refpack on
  the same material, looking at what ORACLE does to stamp phase that
  HOUSE doesn't. HOUSE stays frozen.
- [x] **Scales into audiokit (open-harmonizer, 2026-10-15); done in
  0.8.9 on open-audiokit 673a980, HOUSE byte-identical; the note-hold
  primitive (`audiokit::glide::Retune`, 1476c56) in 0.8.11, HOUSE and
  ORACLE byte-identical on the fence's 56 renders.** The harmonizer will move `Scale`, `SCALES` (append-only: saved
  state stores the index), `CHROMATIC` and `absolute`/`relative`/
  `recognise` from `rt/engine/src/scales.rs` into audiokit and send the
  module path; we switch OPQ over ourselves (HOUSE fence, renders
  identical). `KeyTransform`, `Remap`, `ANY_KEY` and the "*" stay here
  until Sam has reviewed the transform's choices. They will also offer an
  audiokit note-hold primitive (hysteresis, 3-frame debounce, log-ratio
  glide with a 1.5-frame floor) written to drop into `map_frame` in the
  same float order; adopt it only if HOUSE stays byte-identical.
- [x] **The viewer keys in the housing's material (Sam, 2026-10-11):**
  "baked keys are black, they should be white/match the panel's
  material". DESIGN's p200 B: `--body beige-plastic --text-color
  1b1b1b` on each key (also Sam's p195 rule: keys take the material of
  the panel under them). Baked at template a202a23 (farm log
  20261011-010947-20412; p198's flat-shaded faces come with it),
  imported in 0.7.15 (catalogue/v19*). Sam on p200, via DESIGN: "B is
  the one I would've picked, so all good there". The keys stand.
- [x] **The transect runs left to right (Sam, 2026-10-11):** "the
  TRANSCET display should move in the opposite direction, starting at
  the left and scrolling out to the right, so that we can see what
  notes things clip to (it's non-obvious with the current controls)."
  0.7.15: now is at the left edge, against the key ruler, and the past
  runs right (catalogue/v19).
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
         - A bare typed number for a `%` parameter used to read as
           0..1 ("75" set 100%); terrible-cepstra ruled it a bug and
           fixed it in pluginkit 6752fb6 (0.6.2): "75" is 75%.
       - Display-mode keys stacked left from the screen's top-right edge
         (0.7.0, catalogue/v14*): Sam picked the viewers ("let's do
         ladders and scope as the viewers"): TRANSECT, LADDERS and SCOPE.
         The engine reports a 288-bin scope spectrum per frame (in and
         wet out, a third of a semitone per bin); HOUSE byte-identical.
         - The keys' baked art (0.7.3, catalogue/v15*): DESIGN's farm
           baked the row on current canon (Sam: "why are we waiting on
           bakes? ... Go, go, go!"), button-bezel through rack.py with the
           housing as matte. It was packed by `bake.py --only keys
           --renders DIR` into `viewer-keys.png` (straight alpha) and is
           drawn through panelkit `widgets::Keys`. The housing was
           rebaked at template bd863d6 (e1ea7a3's rack light: no band)
           and imported by `bake.py --only housing --renders DIR`.
           - The post-p189 rebake (0.7.5, catalogue/v16*; Sam: "189 B,
             ship it", template 3c07a68): through-mounted keys (0.5 mm
             escutcheon, 1.4 mm proud), z seat, sRGB hex, a shared
             --cap-height 5.75, the active key pressed (--travel 0.65).
             Our rects were right ("too far to the right" came from
             DESIGN's scratch layout). The housing needed no rebake:
             each key's cut lies inside its own cell.
           - [x] The panel key row standard (DESIGN p197, Sam; template
             27feb8e): a key is placed by `"key": ["monitor", -1|-2|-3,
             64]`, never a rect. The 0.7.5 bake's seated keys were not
             drawn orthographic, so they sit 1.6–2.7 px right and 1.1 px
             low of their rects (TRANSECT overhangs the bezel's inner
             edge). bake.py owns the job since 0.7.11 (`--jobs DIR`
             writes keys.json; the import refuses any other layout).
             DESIGN's farm re-baked it at 27feb8e (log
             20261010-233347-54679); imported in 0.7.12 (catalogue/v18*).
             Each key fills its cell. layout.rs's rects are unchanged,
             and the housing needed no re-bake (it holds no key cut).
     - [ ] Still known: plate titles are drawn text, not the
       panel-board's backlit cut titles (title-bake/1).
     - [ ] Ideas for later rounds: `docs/design/04-panel-ideas.md`
       (25 of them, with effort marks; Claude's first picks are basins,
       residual octaves, harmonic ladders and LCD alarms).
     - [ ] Live check of the new editor on the Mac (open, drag, pointer
       lock, resize, close while playing). sam-pc passed on 0.4.1
       (E1–E7, 2026-10-10); Ctrl-drag fine and cursor hiding couldn't be
       observed by the tester. The family's native probe (a minimal
       VST3 host, on the headless Mini) passed 0.7.13 on 2026-10-11, 93
       checks and 0 failures: all 12 value controls (double-click reset,
       drag as one gesture, the cursor back at the grab, wheel), which
       keys reach the host, and typed entry both ways (MIX from its
       menu, Feel by hover and Enter). Sam, 2026-10-11, on the Mac:
       "Ableton live passes the sniff test". Not separately confirmed:
       resize, and close while playing.
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
    the keys, Global Threshold, shift-click sine reference, snapshots.
  - [x] The Key Transform, our way (0.8.0, catalogue/v20-transform*).
    Sam, 2026-10-11: "I want to handle this differently than PM.
    PitchMap's way of handling this, frankly, kind of sucks; their
    preset for e.g. 'F Major' will move a C to an F, which in most
    cases is not what I want because I have no fucking clue if my
    input audio is in C Major. So, what I'd like to do instead is, on
    the panel (not a panel button, like, inside the panel) have four
    dropdowns like DROP1 DROP2 -> DROP3 DROP4 where each dropdown can
    select a key and a scale DROP1 and DROP3 select from C, C# ... B,
    and DROP2 DROP4 major/minor, all the modes, and a variety of Funky
    Scales if you feel inclined to do some digging here (neapolitan
    minor, blues, whole-tone, whatever); by default they'll be *
    CHROMATIC each, and with these we can choose the src-dst key
    mapping; note that * here means 'adopt the other one'. So I can
    map * CHROMATIC -> F MAJOR and it'll keep F locked at F, but F#
    will drop to F, or raise to G (pick one rounding scheme and be
    consistent, I haven't mentally weighed the pros/cons of
    round-up/round-down/round-center/round-statistically-neutral, I'll
    leave that to you). If the user manually edits the scale
    themselves, show a * in the second field too, *unless* they happen
    upon a known scale, in which case you can show that one (but all
    bets are off with REPEAT off)."
    Sam, 2026-10-16, having heard it: "key transform sounds fine, but
    use a darker lettering and the new house-style dropdowns" (done in
    0.8.10: panelkit's family menu, the scales grouped into submenus).
    What was built, and the choices that were left to Claude (heard and
    passed by Sam as a whole on 2026-10-16; none questioned):
    - Where: inside the screen, at the plot's top right, under the
      viewer keys. "Inside the panel" was read as inside the monitor,
      not a bezel key and not a plate fitting. If Sam meant the LAW
      plate, the lists move and a plate needs room.
    - The destination scale is the Keys target set itself: choosing
      writes every octave; a hand edit reads back as a listed scale
      from the destination's root, else `*`. With octaves that differ
      (Custom) it reads `*` and there is no remap.
    - Rounding, one rule everywhere: nearest, a tie going down. For a
      chromatic source that is the engine's nearest-target pull, as
      before (so F sharp goes to F or G by which side of it the pitch
      is; an exact tie goes to F), under the ROUNDING switch's
      hysteresis. It is neutral over real pitches, since an exact tie
      has measure zero.
    - A source scale maps degree to degree when the two scales have the
      same number of notes, else each source degree goes to its nearest
      destination note (tie down). The key change is the shortest way
      round; a tritone goes down. Both keys `*` is C.
    - 31 scales (`rt/engine/src/scales.rs`), no two the same set.
    - Not host parameters: product state in the document's section, as
      the keys are (optional member; version stays 3, 0.7.x documents
      load). Choosing in a list turns SOURCE to KEYS.
    - Known gaps: THRESHOLD still spares an in-tune object, which under
      a key change leaves it untransposed; the lists are not in the
      family probe's geometry; not yet heard by Sam or run in a host.
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
  design-lab session and its farm, one process per machine. Sam later
  made this Mac a farm host too ("You can run blender jobs here
  too--just make sure it's strictly sequenced to one-at-a-time, same
  locking mechanism as those two"). It shares ~/farm/.lock with leilan
  and solidgoldmagikarp, but jobs are still the farm's, not this
  session's. bake.py's
  Blender steps refuse to run unless OPQ_BLENDER_FARM=1 (farm hosts only);
  `--only stepped --renders DIR` composites the farm's renders locally.
- **The strip and slider laws (Sam, 2026-10-10, template bc932bf,
  panelkit 3829893):** (1) sliders jump to a press and leave the cursor
  where the drag ended, knobs give it back at the grab point. OPQ has
  no sliders, and its knobs already return the cursor (panelkit's
  PointerLock). (2) No bypass button on the bottom strip: OPQ never had
  one, and Bypass is host-only. (3) The strip is spaced by each item's
  collapsed look with one gap: done in 0.7.9, with the widths fenced by
  a TextMetrics test (`the_bottom_row_is_spaced_by_its_collapsed_look`).
  Until 0.8.1 that test failed whenever the version changed length
  (Sam: "That seems a little silly"); now the version's slot fits any
  version and its text starts at the slot's left, so MIX never moves
  with it. OPQ exports
  family-probe/1 geometry since 0.7.14 (`panel-render --geometry`), and
  `tools/native_probe.py` runs the family's checks through
  open-cepstrum's signed app.
- **Double-click resets, right-click edits (Sam, 2026-10-10, family law,
  template 1e73c9d):** on every value control a double-click sets its
  default, and typed entry opens only from the right-click menu's "Edit
  value...". In OPQ the value controls are the six continuous knobs,
  Voices and MIX (0.7.7). The bat switches and the selector are
  positions thrown on a click, so they have no menu.
  - **Enter is its shortcut (Sam, 2026-10-10, reviewing 0.7.7's
    diff):** "it seems we lost enter-to-type-a-value; I think we oughta
    bring that back as a family rule, anything where right-click would
    bring up edit-value, ENTER should be a shortcut to get at that."
    Done in 0.7.13: Enter over a hovered value control opens its entry
    (not while one is held; Cmd+Enter stays the host's). Relayed to
    terrible-cepstra for the template law and the other products.
- **The CLI writes the family's Int24 (Sam via terrible-cepstra,
  2026-10-10):** "move to the standard system and forget the old
  hashes". The HOUSE fence was re-recorded in 0.7.2 from audiokit Int24
  renders. Before re-recording, every sample was checked against the
  old renders: same shapes and rates, at most 2 LSB moved, and 2 only
  above half scale. That is exactly the quantizer change.
- **Reference data stays out of git (Sam, 2026-10-09):** refpacks and
  PITCHMAP renders are gitignored, to keep the repo small.
- **The current sound survives (Sam, 2026-07-20):** HOUSE is a
  permanent algorithm choice; matching work adds, never replaces.
