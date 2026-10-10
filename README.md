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
  the **belief transect**, ink on a paper-white screen: each pitch
  object's source pitch (pencil), the pitch it is sung at (black ink;
  sepia where Threshold spared it, vermilion while newborn), the targets
  as blue lanes (fainter for Repeat octaves), the map ceiling, and onsets.
  A scroll bar on the screen's right, always shown, moves the view through
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
  double-click resets; the wheel works); switches throw on a click. MIX
  can also be typed: right-click it, or press Enter over it, then type a
  value with its % sign (for now a bare number is read as 0..1) and press
  Enter; Escape cancels. Every other key, Space included, stays the
  host's.

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
