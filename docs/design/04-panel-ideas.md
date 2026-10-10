# Panel ideas (2026-10-10)

A dump of ideas for the rebuilt panel (`rt/panel`, catalogue v07–v10),
written while Sam does the look test. None of this is built. Each idea
names the data it would show, and that data already exists unless it
says otherwise: almost everything comes from the engine's `VizFrame`
(`flux`, `transient`, `grid_mask`, `in_energy`, `res_energy`,
`res_bands`, and per object `f0`, `tgt`, `out`, `amp`, `nh`, `hmask`,
`spared`, `newborn`). The design law still holds: every fitting is
wired to something real, and alarms are honest.

Effort marks: **S** an evening, **M** a session, **L** needs a new
engine feed or new art.

## The screen (the transect)

1. **Harmonic ladders** (S; `hmask`, `f0`). Each object gets a short
   comb of ticks at h·f0 above its lane, lit where the de-mixer
   claimed that harmonic this frame. This shows what the engine
   believes the object *is*, not just where it sits. Toggle it with a
   tab beside MIDI | KEYS.
2. **Basins** (S; the grid). Faint dashed separators at the
   log-midpoints between adjacent targets: everything between two
   separators lands on the same note. This makes Keys mode readable at
   a glance, because excluding a key visibly widens its neighbours'
   basins.
3. **Ownership ribbon** (S; `amp`). Draw each object's output path as a
   ribbon whose width is its claimed amplitude rather than a fixed line.
   Loud voices read loud, and ghosts read thin.
4. **Onset floor** (S; `flux`, `transient`). A thin trace along the
   transect's bottom edge: spectral flux against the TRANSIENTS
   threshold line, with the dry blend as a grey wash rising into the
   plot. This explains every "why did that note go dry" moment.
5. **Residual octaves** (S; `res_bands`). Eight cells down the ruler's
   right edge, one per octave, filled by unowned energy. Under ORACLE
   they're lettered DISCARDED (refusal ink); under HOUSE, CARRIED. This
   is the old board's NO BIJECTION plate reborn on the screen.
6. **Births and mercy** (S; `newborn`, `spared`). A one-frame spark
   where an object is born, and a small check on objects Threshold left
   alone (already in tune).
7. **Piano ruler** (S). Draw the key ruler as actual white and black
   keys, still coloured by state (target mint, bypass ochre, excluded
   dark). Under REPEAT, a faint bracket shows that an edit hits every
   octave.
8. **Hover a lane** (S). Pointing at an object's path highlights it and
   puts "A3 → C4, +12 c bend, 9 harmonics" on the strip.
9. **Zoom** (S). Command-wheel (Ctrl on Windows) over the screen
   changes the span (36 → 24 → 60 notes), centred on the pointer.
10. **Hold** (M). Press and hold on the transect to freeze the history
    and scrub back through it with the pointer. Audio keeps running.

## The LCD

11. **Pages** (M). Clicking the LCD steps through pages, and a page
    indicator glyph sits in its corner:
    - **MAP**: today's chord and classes.
    - **VOICES**: one row per object, `f0 → tgt  ±cents`.
    - **TUNER**: the loudest object's needle in cents.
    - **TALLY**: born, onsets and time running.
    - **SCOPE**: a 96-column pixel spectrum with the grid's teeth.
12. **Chord names** (S). "C MAJ7 / E" instead of "C4 E4 G4 B4" when the
    held set is a known chord, falling back to the notes.
13. **Honest alarms on the LCD** (S):
    - "VOICES FULL", flashing when the tracker hit its Voices limit.
    - "NOTHING TO MAP", when audio is present but the grid is empty
      (MIDI mode, no chord held).
    - "KEYS: ALL BYPASSED", when a Keys setup can't move anything.
14. **The mutter, restored** (S). The crawl uses the old drum's mutter
    voice (one lowercase line of true session arithmetic,
    `03-the-panel.md`), not only the tally.

## The plates

15. **Backlit cut titles** (M; known nit, title-bake/1). Bake the plate
    titles as cut-through backlit letters like panel-board's, not drawn
    text.
16. **Engraved scales** (M; bake). Value legends cut around the knobs
    where the numbers mean something: GLIDE in ms, THRESHOLD in cents,
    MAP CEILING in Hz, VOICES 1–12.
17. **Bend meter** (M; new art). A small moving-coil needle on OUTPUT,
    reading the mean absolute bend in cents across the objects: how
    hard the plug-in is working right now.
18. **A MAP SOURCE key switch** (S). A physical two-position switch on
    the LAW plate mirroring the tabs, so the source is visible even with
    the screen scrolled to show nothing interesting.
19. **More lamps** (S). DISCARDING (Oracle is throwing residue away),
    BYPASS KEYS ACTIVE, and TRANSIENT (flashing on a dry blend).
20. **A serial plate** (S). A tiny riveted plate with the version,
    format and sample rate; the strip's version moves there.

## Interaction that leads into the PITCHMAP remainder

21. **Shift-click a key: sine reference** (M; engine). PITCHMAP's
    audition tone at the key's pitch while held. It needs a small sine
    voice in the engine, mixed post-map.
22. **Right-click the ruler: scale presets** (M; Key Transform). Root
    plus scale (major, minor, modes, pentatonics) writes the key states.
    This is PITCHMAP's Key Transform on a context menu, and it needs
    panelkit's menu or an LCD picker.
23. **Snapshots** (M; state). Eight small buttons on a plate that store
    and recall key states plus mapping, PITCHMAP's snapshots. They
    belong in the document's product section beside the keys.
24. **Mapping sliders view** (L). A second screen mode where each of
    the 128 source notes has a this-goes-there slider (−12…+23),
    PITCHMAP's per-source mapping. It's the biggest piece of the
    remainder and wants its own design pass.

## Parked from the old board

25. **The old stations** (L): the old board's right rail (onset flux,
    the session register, the target census; `03-the-panel.md`,
    Stations) and its unbuilt organs, waiting for the board to need
    them.

## What I'd do first

My pick, if Sam's notes leave room: 2 (basins), 5 (residual octaves),
1 (ladders) and 13 (alarms). They're cheap, they explain the engine's
decisions rather than decorate, and they turn the two algorithms'
difference into something you can see.
