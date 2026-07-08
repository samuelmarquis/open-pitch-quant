# The panel

1280×720 fixed pixels: a control board in the dialect of a plant that
processes music as if it were gas, collaged with the paper record of the
people who tried to write sound down before electricity. It replaces the
bare drum viewer (see [02-the-drum.md](02-the-drum.md) — the drum survives
inside it, at 1016×384, as the plant's chart recorder, tagged REC-1859
after the phonautograph it descends from).

The panel is **operable**. That is the point of it. The eighteen fittings
along the bottom are the parameters — drag a handwheel, throw a key, and
the edit goes to the host as a begin/perform/end gesture (automatable,
undoable) and to the engine at once. When automation moves a parameter,
the fitting moves. The controls are the model, with hands.

## Law

1. **Everything that indicates, indicates truly.** Manifold valves stand
   open exactly where the held chord stands; governors spin only for
   beliefs the tracker holds this frame (flyball spread = claimed
   harmonics); annunciator tiles alarm only on states the engine actually
   reaches; the census tallies real targets; the mutter reports real
   session arithmetic. The drum keeps its own stricter law (belief only,
   black elsewhere).
2. **Refusal keeps its ink.** Ochre, everywhere, only: punch-through
   veils, mercy stamps, terminal ticks, the ceiling, CUT MID-WORD.
3. **The furniture is declared.** The engravings, the glass specimen, the
   graffiti are the remainder any honest mapping carries — a map with no
   surplus would be a bijection, and bijection is physically impossible
   here (a bent STFT frame has no preimage; the panel shows a machine
   93 ms dead). The header plate says so: NO BIJECTION — REMAINDER IS
   CARRIED. Furniture never wears a gauge's face.

## Stations

- **HDR-2201 TARGET MANIFOLD** (left): twelve valves, one per pitch-class;
  held ones crack open — stem up, green POS lamp, dotted feed line into
  the drum. RPT OCT lamp when Repeat scope expands the grid.
- **REC-1859 BELIEF TRANSECT** (center): the drum, C0 floor to C8 roof,
  octave depth-marks, ~24 s across.
- **FLX-2205 / SESSION REGISTER / TARGET CENSUS** (right rail): onset flux
  strip-chart with the transient threshold dotted in ochre; mercies / cut /
  born counters (event counts, not frame counts); a tally of which
  pitch-classes the law actually sent objects to.
- **GOV-2230 PHASE GOVERNOR GALLERY**: twelve sockets. Live beliefs spin
  (ring ochre when Threshold spared them, dashed while newborn); sockets
  beyond the Voices cap read PLUGGED; empty lawful sockets read OPEN.
- **Fittings** (two rows, signal order — capture row, then rendering row):
  valve/key/thumbwheel/breaker glyphs, tag plates, live value text from
  the same formatter the host sees, and a caption in the folio voice
  ("WIDTH OF MERCY / IN CENTS"). BYPASS is the one red thing on the board.
- **Annunciator** (top right): NO SIDECHAIN, STALE FEED, CUT MID-WORD
  (latches; ACK clears), PUNCH THRU, CEIL PASS, MERCY HELD, GRID MOVED,
  VOICES FULL. Amber only; red is never spent.
- **PLATE FIGURE**: computed Chladni sand, its mode chosen by how many
  tones are held. **SPECIMEN 001**: a raymarched glass trefoil, tinted by
  Mix, bobbing slowly. It does not know it is held.
- **The mutter** (bottom): one lowercase line of true session arithmetic
  every ~3 s: `the map is c eb g + 4 of 6 voices + weather light + 2
  mercies + 1 cut + 15 born`.

## Fabric

Two text voices: a hand-authored 5×7 machine stencil for equipment, and
rasterized Helvetica Neue (né Neue Haas Grotesk) atlases for the human
layer — CRUNCH-thresholded for the title, scan-SLIPPED for graffiti.
Engravings ride as tinted transparencies (the phonautograph is pasted OVER
the fitting plates, collage-fashion). Print furniture at the edges: crop
marks, an ink control strip, DO NOT REDUCE.

Rendering: pure CPU into RGBA (`board.rs` + `canvas.rs`, platform-free,
unit-tested); static furniture is baked once into a base layer and
memcpy'd under each 30 Hz frame; the plate is expanded by an integer
factor (backing scale, rounded) so Cocoa never interpolates. The mount
(`gui.rs`) is one custom flipped NSView with mouse handlers — no webview,
no toolkit. macOS only; elsewhere the plugin stays headless.

## Verifying without a DAW

```
cargo test -p opq_plugin_wrac --lib --release -- --ignored render_panel
sips -s format png /tmp/opq-panel.ppm --out panel.png
```

runs the real engine (chord change, noise burst, hard silence) through the
real board. The `catalogue/` directory holds the versioned plates of this
panel's evolution, per the standing instruction to document the taste.

## Open questions, honestly held

- Integer window zoom (2×) as an explicit host-facing option.
- A per-frame gate bit from the engine (gate refusals currently appear
  only as weather).
- Blit cost at 2× retina is ~5 ms/tick on the UI thread; dirty-striping
  would halve it if Ableton ever complains.
