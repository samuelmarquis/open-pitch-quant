# open pitch quant

An open reimplementation of the *idea* of Zynaptiq PITCHMAP — real-time
**polyphonic pitch remapping**, MIDI-sidechain flavor: hold a chord, and
everything pitched in the audio is pulled onto it. Chords to chords, no
stem separation, ~93 ms latency, live.

## What's here

- **`rt/engine`** — the DSP, plain Rust. Pitch-object de-mixing on a
  chromatic grid: STFT → instantaneous frequency → greedy multi-F0
  grouping → per-object retuning via kernel-stamped partials with
  per-harmonic phase accumulators. **Read
  [`docs/DSP.md`](docs/DSP.md) for the full walkthrough.**
- **`rt/cli`** — offline renderer (`opq in.wav out.wav --midi part.mid`),
  used by the listening-test bench; also dumps analysis traces
  (`--viz-dump`).
- **`wrac/`** — the plugin: CLAP + VST3 + AU (`aumf`, so hosts route MIDI
  to it), built on NovoNotes' WRAC template (MIT) through the family's
  shared shell, the sibling checkout `../open-wrac` (lineage in
  `wrac/PROVENANCE.txt`).
- **`rt/panel`** — the editor board, in the family idiom (open-panelkit,
  wgpu; no webview, no toolkit), 1100×768, resizable. A monitor carries
  three viewers, ink on a paper-white screen, picked by the keys on its
  top bezel (right to left). All three share the key ruler, the pitch
  axis, the targets as blue lanes (fainter for Repeat octaves) and the
  map ceiling (a dashed line that shows while the Ceiling knob is in use
  or its value moves, then fades):
  - **TRANSECT** (the default): each pitch object's source pitch
    (pencil), the pitch it is sung at (black ink; sepia where Threshold
    spared it, vermilion while newborn), and onsets, over the last ten
    seconds. Now is at the left, against the key ruler, so each sung
    pitch lands beside its key; the past runs out to the right.
  - **LADDERS**: one column per live object, low to high, showing its
    harmonics over the last second. A rung is inked where the object
    claimed that harmonic's spectrum and pencilled where it didn't. At
    the column's right are its target (blue) and its sung pitch. At its
    foot are the heard note with its cents, the target note, and how
    many harmonics it holds.
  - **SCOPE**: the spectrum laid on the pitch axis, level running right
    (−96 dB to a full-scale sine). What came in is a pencil wash; what
    the map sang (the wet signal, before MIX) is an ink wash over it.
    Faint ink ticks hold the sung peaks of the last second.

  The viewer is the editor's own choice, not saved with the project. A
  scroll bar on the screen's right, always shown, moves the view through
  all 128 notes. Under the monitor, the infotext line names what the
  pointer is over and its value, then types in what it does. Beneath,
  three baked plates, one control per parameter (Bypass is the host's):
  CAPTURE (Voices, a stepped knob whose amber ring counts the voices;
  Tonality Gate, Map Ceiling, Gate Mode, Map Unowned, Transients), LAW
  (the Algorithm selector, Feel, Glide, Map Source, MIDI Scope,
  Threshold, Rounding) and FINISH (Purify, Grit, Formant, Carry,
  Coherence, Transitions). **MIX** is text in the bottom row, beside the
  version. A knob's caption shows its value while it is in use, and
  briefly whenever the value moves (automation, the host's panel). Knobs
  and MIX drag vertically (Command, or Ctrl on Windows, for fine;
  double-click resets to the default). The wheel works too, and a burst
  of notches is one undo step in the host. Switches throw on a click. To
  type a value, right-click a knob or MIX and choose **Edit value...**,
  or press Enter with the pointer over it; type it in place ("75" or
  "75%"), and press Enter; Escape cancels. While the editor isn't typing
  or in its menu, every other key, Space included, stays the host's.

  **Map Source** (the SOURCE switch on LAW, beside SCOPE): under **MIDI**
  the targets are the notes held on the MIDI side chain (PITCHMAP's MIDI
  MAP). Under **KEYS** they are set on the screen's key ruler, PITCHMAP's
  Lower Keyboard without MIDI: click a key to make it a target or exclude
  it (an excluded pitch is pulled to its nearest target), Option/Alt-click
  to bypass it (anything sitting on it passes unbent, drawn in sepia), and
  drag to paint the same state over every key you cross. SCOPE applies:
  Repeat edits every octave of the key, Custom only that key. Keys start
  chromatic (every note a target). The key states are saved with the
  project, not automatable. The wheel over the screen scrolls the pitch
  view as content, following the system's natural-scrolling setting
  (knobs always follow the wheel's physical direction).

  **Key Transform** (the four lists at the screen's top right, reading
  *source key, source scale → destination key, destination scale*):
  where PITCHMAP's scale presets assume the input is in C major, here
  you say what it is in. Each key list is `*` then C to B; each scale
  list has 31 scales (chromatic, major, minor, the modes, harmonic and
  melodic minor, pentatonics, blues, whole tone, diminished, Neapolitan
  and more): Chromatic, Major and Minor at the top, the rest in five
  groups that open beside it. Click a slot (or Enter, the arrows and a
  typed first letter once open) to choose; the current choice is
  dotted. It starts at `* CHROMATIC → * CHROMATIC`, which does
  nothing.
  - The **destination** scale is the targets: choosing one writes it to
    the key ruler in every octave. Edit the keys by hand and it reads
    `*`, unless the keys happen to spell a listed scale from the
    destination's key, in which case it names that. With SCOPE at
    Custom a hand edit sets single notes, so it reads `*` and the
    source side has nothing to map onto.
  - A key of `*` takes the other side's key (both `*` is C).
  - With a **chromatic source** in the destination's key, each pitch is
    pulled to its nearest target, as ever: `* CHROMATIC → F MAJOR` keeps
    F at F, and a pitch between F and G goes to whichever is nearer.
    ROUNDING decides how readily a voice hops between neighbours.
  - With a **source scale**, each pitch is first taken to its nearest
    source degree, and that degree is sung at the destination's same
    degree: `C MAJOR → C MINOR` sings E as E flat, A as A flat and B as
    B flat. If the keys differ the whole thing moves the shortest way
    (C to F is up a fourth, C to G down a fourth, a tritone down). If
    the two scales have different numbers of notes, each source degree
    goes to the nearest destination note instead, a tie going down.
  Choosing anything in the lists turns SOURCE to KEYS. The transform is
  saved with the project and is not automatable; a project saved by
  0.7.x opens with none.
  `cargo run --release -p opq-panel --bin
  panel-render -- --out DIR` renders it offline from the real engine;
  `rt/panel/assets/bake.py` bakes the plates and vendors the family
  artwork, with provenance. The old panel's design is
  [`docs/design/03-the-panel.md`](docs/design/03-the-panel.md) (history).
- **`opq/`** — the frozen Python prototype lab (nine listened iterations;
  the Rust engine is canonical).
- **`docs/research/`** — the PITCHMAP evidence corpus this was built
  against. **`LISTENING-LOG.md`** — every listening batch and verdict.
  **`PATHS-NOT-TAKEN.md`** — deferred design branches, with reasons.

## Build

Nix (flake) carries the toolchain:

```sh
nix develop

# offline CLI
cd rt && cargo build --release
./target/release/opq in.wav out.wav --notes C4,E4,G4 --rounding intelligent --feel 0.35

# plugin (CLAP + VST3 + AU)
cargo xtask install -p opq_plugin_wrac --release   # --release matters: debug DSP underruns
```

The build expects the family's kits checked out beside this repo:
`../open-wrac`, `../open-pluginkit`, `../open-panelkit` and
`../open-audiokit`.
macOS needs only Command Line Tools (open-wrac's build is patched to not
require full Xcode; the optional standalone-app target is the one
exception — it wants `ibtool`).

## Status

Working and daily-driven in Ableton (VST3). AU validates (`auval -v aumf
Opq1 Opqt`). Reference A/B against actual PITCHMAP renders: **measured** — see
[`docs/research/04-pitchmap-measured.md`](docs/research/04-pitchmap-measured.md)
(bench: `make_ab_pack.py` → `check_ab_returns.py` → `render_ab_ours.py` →
`compare_ab.py`; protocol: `testdata/REFERENCE-RENDERS.md`). No license chosen yet; if you want to
use this for something, open an issue.

## Changes

- **0.9.10** — no visible change yet: the panel's parts are being
  rendered in the shared scene, with a template fix for how parts sit on
  their plates.
- **0.9.9** — no visible change yet: the panel's rendered parts move to
  the family's shared pipeline, where the whole board is one lit scene and
  each part is rendered in it over its plate. This replaces three separate
  plate scenes. The new renders arrive in a coming build.
- **0.9.8** — no visible change yet: the rendered parts move to the
  family's shared lighting, one light over the whole window instead of
  one per plate. The new renders arrive in the next build.
- **0.9.7** — GRIT's catalin knob renders as its true deep amber, not
  pale peach; the rest of FINISH is re-rendered with it
  (catalogue/v27-rack-knobs.png, updated).
- **0.9.6** — every knob is now part of its plate's render: the ten
  continuous knobs turn through 101 rendered positions each, with their real
  shadows and reflections, and LAW is back on the mirror brass. A faint
  outline that showed through every rendered part is gone
  (catalogue/v27-rack-knobs.png).
- **0.9.5** — no visible change yet: you preferred the mirror brass for
  LAW (p217), so it goes back to that with the knob renders.
- **0.9.4** — no visible change: the knobs' rack renders are on DESIGN's
  farm, and the bake script no longer copies open-cepstrum's knob images.
- **0.9.3** — no visible change: the ten knobs' rack renders are set up
  and sent to DESIGN's farm.
- **0.9.2** — LAW's plate is a satin brass, an even gold, in place of
  the mirror brass that read cream with a dark band. Voices' knob and its
  amber ring are part of CAPTURE's render, with real shadows, stepping
  through all 12 positions. A neighbour's switch no longer covers the
  ALGORITHM caption (catalogue/v26-rack-voices.png).
- **0.9.1** — no visible change yet: LAW's brass face switches to a satin
  brass, and the Voices knob is being rendered into CAPTURE's scene. Both
  arrive in the next build.
- **0.9.0** — the plates are rendered as one lit scene each: CAPTURE, LAW
  and FINISH, each with its switches and the ALGORITHM selector, under the
  family's shared studio lighting with real shadows. Every two-way switch is
  now a tab switch (your p214 pick). Each tab's position labels sit
  further out to clear it. On LAW, SOURCE and SCOPE move right and the
  selector moves up. The knobs are unchanged for now (still
  catalogue/v25-rack-plates.png).
- **0.8.24** — no visible change: the ALGORITHM knob's rack render is
  sized to match today's knob.
- **0.8.23** — the plates' rack bake is set up and on DESIGN's farm. You
  picked the tab switch (p214 D) for all seven switches, and it goes in
  with the plates.
- **0.8.22** — records only: the tab switch option's slot was checked
  and is sound; the green in it is a reflection.
- **0.8.21** — records only: the bat switch's base is fixed in the
  family template; you have the four switch options to pick from.
- **0.8.20** — records only: you passed the FINISH plate as one rack
  scene. The bat switch's base is being fixed, and other switches are being
  tried for the board.
- **0.8.19** — records only: how the trial FINISH plate's jade would
  be adjusted, if wanted.
- **0.8.18** — no visible change: the FINISH plate's trial render
  as one rack scene is done and waiting on a design ruling.
- **0.8.17** — the viewer keys are re-baked dead-on, as the family's rack
  now draws every raised part (catalogue/v24-deadon-keys.png).
- **0.8.16** — the screen glass from 0.8.15 is now installed (its
  still is catalogue/v23-glass.png). Under the family's dead-on rack
  ruling, the viewer keys are queued for a re-bake.
- **0.8.15** — the screen gets the family's glass: the housing's
  vignette and its reflection (at 1/3), laid over the paper screen and
  under the menus. Built but not installed yet: it's waiting on a design
  ruling.
- **0.8.14** — records only: the family's screen glass (the reflection
  at 1/3, plus the vignette) is planned for the paper screen. Its bake is on
  DESIGN's farm; nothing you hear or see changes yet.
- **0.8.13** — on audition: a HOUSE FEEL dropdown on the bottom strip
  switches HOUSE's Feel law between A (as frozen) and three fixes for its
  warble on a note change: B holds it within 50 cents, C measures it
  afresh on each new note, D does both. It is saved with the project
  and is not a host parameter. A sounds exactly as before; ORACLE
  ignores it. Infotext no longer reads the control under an open menu.
- **0.8.12** — nothing changes in the plugin; a fix for HOUSE's Feel warble is measured and awaits a listen.
- **0.8.11** — nothing changes in the sound: each voice's glide, hold and retarget debounce now come from the family's DSP kit (audiokit), shared with the harmonizer. HOUSE and ORACLE renders are byte-identical.
- **0.8.10** — the Key Transform's lists are the family's menus: white
  paper set in a serif, the current choice marked and the cursor on it.
  The scales past Chromatic, Major and Minor open from five groups
  (Modes, Harmonic & melodic, Pentatonic & blues, Symmetric, Exotic).
  The four slots are lettered in the same serif, in darker ink.
- **0.8.9** — nothing changes in the sound or the panel; the scale list now comes from the family's DSP kit (audiokit), shared with the harmonizer. HOUSE renders are byte-identical.
- **0.8.8** — nothing changes in the plugin; the plan to share the scale list with the family's DSP kit is recorded.
- **0.8.7** — nothing changes in the plugin; the native test's drag on Voices is sized to cross a step.
- **0.8.6** — Voices drags on the same speed curve as the other knobs:
  a slow drag works toward the next voice count and lands on it (about
  64 px a step), and a flick crosses the whole range.
- **0.8.5** — nothing changes in the plugin; the beige viewer keys are confirmed.
- **0.8.4** — knob drags speed up with the hand, as across the family:
  moved slowly a knob (and MIX) needs 700 px for its whole range, moved
  fast 350 px. It was a fixed 180 px, so knobs now turn much more
  finely. Voices kept its fixed 180 px until 0.8.6.
- **0.8.3** — nothing changes in the plugin; a session rule was retired.
- **0.8.2** — the infotext is rewritten in plain words, and a switch
  now explains the position it is in, so throwing it shows you the
  other half. The CEILING line on the screen shows only while the
  Ceiling knob is touched or its value moves, then fades.
- **0.8.1** — the bottom row no longer depends on how long the version
  number is: the version line sits a touch further left, always one gap
  from MIX.
- **0.8.0** — the **Key Transform**: four lists inside the screen, top
  right, set a source key and scale and a destination key and scale
  (`A MINOR → * MAJOR`). Unlike PITCHMAP's presets it never assumes
  what key the input is in. The destination scale is written to the key
  ruler and read back from it; a source scale maps degree to degree.
  The default, `* CHROMATIC → * CHROMATIC`, changes nothing, and HOUSE
  is unchanged. Projects saved by 0.7.x still open
  (catalogue/v20-transform, v20-transform-list).
- **0.7.15** — the TRANSECT runs the other way: now is at the left,
  beside the key ruler, and history scrolls out to the right, so you
  can read which note each voice lands on. The viewer keys are the
  housing's beige with dark legends, not black (catalogue/v19*).
- **0.7.14** — nothing changes in the plugin. The editor now reports
  its controls to the family's native test host, which checked 0.7.13
  on a Mac: every knob and MIX (drag, wheel, double-click reset, the
  cursor returned), the keys left to the host, and typing a value from
  the menu and by Enter.
- **0.7.13** — Enter is back as the shortcut to typing a value: with
  the pointer over any knob or MIX, Enter opens its typed entry, the
  same as its menu's **Edit value...** (0.7.7 had dropped it).
- **0.7.12** — the viewer keys are re-baked on the family's key-row
  standard: each sits exactly on its place, about 2 px left and 1 px
  down from before, and TRANSECT no longer overhangs the bezel's inner
  edge (catalogue/v18*).
- **0.7.11** — nothing you can see or hear yet: the viewer keys' bake
  job moves to the family's key-row standard, ready for a re-bake that
  will seat the keys exactly on their places (they sit about 2 px right
  and 1 px low today).
- **0.7.10** — the bottom row's gap is the family's 12 px (it was 16),
  and the version line is measured again for its extra digit.
- **0.7.9** — the bottom row is spaced by what it shows (the family's
  rule): MIX now sits one even gap left of the version line, not about
  100 px out. Offline stills show the product's real version.
- **0.7.8** — the editor's window sizing comes from the family's shared
  code (panelkit). It behaves the same.
- **0.7.7** — under the family's rule (double-click resets, right-click
  edits), every knob and MIX has a right-click menu with **Edit
  value...**, which opens typed entry in place. Knobs can be typed now,
  not only MIX, and Enter over MIX no longer opens it. A burst of wheel
  notches is now one host gesture (one undo step) instead of one per
  notch (catalogue/v17-menu, v17-typing).
- **0.7.6** — on macOS, the editor opens in every format a host loads.
  Live with both the AU and the VST3 used to show a blank editor for the
  second. Every resize the editor proposes to a host is now one it
  accepts; a reattached editor used to refuse its own size.
- **0.7.5** — the viewer keys are set into the bezel (through-mounted,
  with a thin escutcheon), their legends one shared size, their LEDs in
  true colour, and the lit key pressed in (catalogue/v16, v16-ladders,
  v16-scope).
- **0.7.4** — Glide can be typed in microseconds ("120000 μs", "µs" or
  "us"), under the family's rule that typing accepts every spelling. Host-
  typed text now reaches the plugin as UTF-8 over VST3 (open-wrac).
  Nothing we display needed changing: no value of ours reads "inf" or
  "us".
- **0.7.3** — the viewer keys are baked keys on the bezel, with the
  shown viewer's LED lit (catalogue/v15, v15-ladders, v15-scope). The
  monitor housing is rebaked under the template's corrected rack light,
  which removes a band that crossed its bezel.
- **0.7.2** — the offline CLI's 24-bit WAVs use the family's standard
  rounding (audiokit's Int24: scaled by 2^23 and rounded, where it used
  to truncate at 2^23 − 1). Its renders move by at most 2 LSB, and the
  HOUSE regression fence is re-recorded from them. The plugin is
  unchanged.
- **0.7.1** — the offline CLI (`opq`) reads AIFF and FLAC as well as
  WAV, through the family's sample loader (audiokit). Its 24-bit WAV
  output is byte-identical to before. The plugin is unchanged.
- **0.7.0** — the screen has three viewers, picked by keys on the
  monitor's top bezel (catalogue/v14, v14-ladders, v14-scope): TRANSECT
  (as before), LADDERS (each object's harmonics, and which of them it
  claimed) and SCOPE (the spectrum in and out on the pitch axis). The
  engine now reports a scope spectrum with each analysis frame; the sound
  is unchanged (HOUSE byte-identical). The keys are flat stand-ins until
  their baked art arrives.
- **0.6.2** — a percentage typed without its % sign means percent: "75"
  is 75%, in MIX's entry and in the host's own parameter text entry
  (pluginkit's fix). Before, a bare 75 clamped to 100%.
- **0.6.1** — MIX can be typed in place: right-click or Enter over it,
  Enter commits, Escape cancels. The editor now takes keys from the host
  by the family's shared policy (panelkit), on both macOS and Windows.
- **0.6.0** — the OUTPUT plate is gone (catalogue/v13):
  - MIX is text in the bottom row, the family's (panelkit's strip).
  - The OUTPUT plate's backlit LCD (chord, pitch classes, session tally)
    and its three lamps went with it.
  - The other three plates widen to fill the rack.
  - Voices is a stepped knob: an ivory boss whose amber ring lights one
    lens per voice.
- **0.5.2** — the monitor housing is beige plastic, baked for this panel
  (no longer a stretched copy of OpenCepstrum's dark one), and FINISH's
  face is polished catalin jade (catalogue/v12).
- **0.5.1** — Map Source is a switch (MIDI/KEYS) beside SCOPE, not a
  knob: a two-position control is a switch.
- **0.5.0** — the panel's first round of Sam's notes (catalogue/v11):
  - The screen is ink on paper: a paper-white field with dark markings.
    It has an always-shown scroll bar, and the wheel follows natural
    scrolling there. Its header text is gone.
  - The infotext line between the monitor and the plates says what the
    pointer is over (panelkit's hover line). Knobs no longer show their
    values all the time; the caption shows the value while in use.
  - Map Source is now a knob on LAW beside SCOPE (the screen's MIDI/KEYS
    tabs are gone).
  - The Bypass control is gone; the host's bypass is Bypass.
  - FEEL, GLIDE and THRESHOLD use the plain black knob. CAPTURE is
    anodized blue.
  - Tonality Gate reads with one decimal; it is continuous.

  Still to come: display-mode keys.
- **0.4.6** — no change to the sound (every HOUSE render is
  byte-identical). The STFT framing, FFTs and overlap-add come from the
  family's shared frame, `audiokit::stft`, and the audio thread no
  longer allocates memory at all; a test now checks that.
- **0.4.5** — no change to the sound (every HOUSE render is
  byte-identical). The pitch analysis (instantaneous frequency, peaks and
  regions, the multi-F0 that carves pitch objects) now comes from the
  family's audio kit, `../open-audiokit` (`audiokit::pitch`), and no
  longer allocates memory on the audio thread. The plug-in build needs
  that checkout beside this repo.
- **0.4.4** — on Windows the editor prefers a Vulkan adapter (DirectX 12
  as the fallback), so it no longer opens blank for about 20 seconds.
  This replaces 0.4.3's fix, whose linked-in shader compiler broke the
  Windows build. No change on macOS or to the sound.
- **0.4.3** — *does not build on Windows* (its linked-in DirectX shader
  compiler conflicts with the wrapper's C runtime). It meant to stop the
  editor opening blank for about 20 seconds there; 0.4.4 does that.
- **0.4.2** — the lowest octave's notes are named C-1…B-1 (they read as
  a huge unsigned number at the bottom of the ruler), and the strip names
  the bypass modifier as Windows does (Alt-click) there. Checked on
  Windows in Live 12: the editor, Live's own controls with the device on
  or off (including saving while off), automation and the Keys source.
- **0.4.1** — a knob drag's release anchor is measured with panelkit's
  `Grabbed::press` (against where the knob is drawn); no visible change.
- **0.4.0** — PITCHMAP without MIDI: a 21st parameter, **Map Source**
  (MIDI / Keys), and the screen's key ruler as a Lower Keyboard with
  per-key target, exclude and bypass (see `rt/panel` above). The wheel
  scrolls the transect through all 128 notes. The saved document is
  version 3, with the key states as its product section: **projects saved
  with 0.3.x do not load** (pre-1.0). The knob drag's release anchor is
  panelkit's `Grabbed` (same behaviour).
- **0.3.2** — the bat toggles and the Algorithm selector are rendered under
  the family's footprint contract (the knobs' framing, extended to the
  switches by the template), so they sit at the knobs' size with every
  position in register. Built on open-wrac's guard for automated lanes:
  the host's automation echoes are not forwarded.
- **0.3.1** — panel nits: the bat toggles and the Algorithm selector are
  drawn at the family's size (their renders are cropped to the part); the
  transect gets a time axis (seconds before now), its octave names sit
  under their rules, and target names no longer crowd; the bypass lamp
  sits beside its toggle; the strip shows the plug-in's own version.
  Built on open-wrac's P27: a value set from the host's own controls
  (Live's device panel) now reaches the plug-in even while the device is
  off, and for list parameters such as Algorithm.
- **0.3.0** — a new editor, rebuilt from scratch in the family idiom (see
  `rt/panel` above): a monitor with the belief transect over a rack of
  baked plates and controls, with an LCD module, on open-panelkit's GPU
  canvas and native mounts (macOS and Windows; knobs drag with the cursor
  hidden and land back on the knob). Algorithm and Purify now have
  controls. The old CPU-pixel panel, its engravings and its bakery are
  gone. The plug-in also handles a host reset by reporting its
  parameters at once, and reports a block's parameters even when the
  host's audio buffers fail.
- **0.2.1** — no change to the sound or the parameters. The plugin's entry
  point, audio ports and sample conversion come from the family's shared
  shell. The audio ports are still one main pair, mono or stereo (the
  side chain is MIDI); they now tell the host they take 64-bit audio and
  can process in place. A host that gives no input now feeds the engine
  silence.
- **0.2.0** — the host sees 20 parameters. Two are new:
  - **Algorithm** (House / Oracle, default House). House is the sound the
    plugin has always had; Oracle is the PITCHMAP-faithful policy measured
    in research 04 (map-or-discard, onset-only glide, belief-feel).
  - **Purify** (0–100 %, default 0): the one-sided denoise, for both
    algorithms. At 0 nothing changes; toward 100 % the unowned residual,
    claimed-noise synthesis and carry fade, leaving pure stamps.

  Both are host parameters only for now; the panel's controls for them
  come with the panel's rebuild. Parameters and saved state now come from
  the family's kits (pluginkit's schema and document, wrac_shell's host
  view). **Projects saved with 0.1.x do not load in 0.2.0**; their
  OpenPitchQuant comes back at defaults. Typed and displayed values read
  slightly differently: percentages as `25%`, Map Ceiling with one
  decimal, Threshold in `cents`, and a bare number typed into Glide is
  milliseconds.
- **0.1.1** — housekeeping, no change to the sound or the parameters. The
  plugin shell comes from `../open-wrac`; the old nih-plug shell
  (`rt/plugin`) and the template's demo plugin are gone. The installed
  plugin still pins the HOUSE algorithm and PURIFY at 0.
- **0.1.0** (2026-07-04) — first public build.

*This project reimplements a publicly documented idea from scratch — no
Zynaptiq code, no disassembly; see `docs/research/` for the sources. Not
affiliated with Zynaptiq. Go buy PITCHMAP, it rules.*
