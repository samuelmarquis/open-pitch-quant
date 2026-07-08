# The drum

The plugin's one visual organ. A fixed 576×336 transect embedded in the
host's editor window: log-frequency vertical (C1 at the floor, C8 at the
roof, 48 px per octave), time scrolling leftward, one column per analysis
frame (~43 columns/s at 44.1 kHz — the plate holds ~13 s).

There is exactly one of it, and you cannot click it. The controls stay in
the host's generic parameter editor, which is already the honest control
surface: eighteen named, automatable parameters. The drum is not the
machine's face; it is an instrument for watching the machine work.

## The law of the drawing

**Draw the belief, not the signal.** Nothing on the drum comes from the
spectrum directly. Every mark is the tracker's actual output — the same
`VizFrame` stream the offline `--viz-dump` writes. Where the model believes
nothing, the field stays black. If the tracker is wrong, the drum is
visibly wrong; the display is forbidden to know more than the DSP.

**Refusal has its own ink.** Everything the engine declines to touch is
marked in rust ochre, and only in ochre.

## The marks

| Mark | Ink | Meaning (engine truth) |
|---|---|---|
| Rails | dim amber lines | the target grid: held notes (Custom) or every octave of held pitch-classes (Repeat, mask bit 127) |
| Spine | bone white, brightness ∝ claimed magnitude | a pitch object's fundamental (`f0`) |
| Teeth | faint white above the spine | only the harmonics the grouper claimed *this frame* (`hmask`) — a clarinet is a broken comb, honestly |
| The bend | amber trace | where synthesis actually put the spine (`out` = f0 × exact per-object multiplier: glide progress + feel). At a chord change every gripped voice slides live onto the new rails |
| Newborn dash | white, alternating columns, no bend | inside the newborn window, where the Transitions policy applies |
| Mercy stamp | ochre dot above a spine, bend absent | Threshold spared this object (`spared`; multiplier forced to 1) |
| Punch-through veil | full-height ochre wash | the frame's transient dry-blend; hard cuts read as hits because they are |
| Terminal tick | 3 px ochre | a belief present last column, gone now, while still loud — cut mid-word (starved, gated, or stopped). Quiet ends fade unmarked |
| Ceiling | dotted ochre line | Map Ceiling, when it is below C8 — above it the law does not reach |
| Weather | gray stipple in octave bands | residual magnitude, binned exactly as the engine bins it (`res_bands`) |

Palette, total: black field, bone white `#E8E4D8`, aviation amber
`#FFB300`, rust ochre `#A64B00`, weather gray `#383B40`. Amber is the law
and the bend; white is belief; ochre is every no.

## Fixed pixels

The plate is rendered CPU-side into a 576×336 RGBA buffer
(`src-plugin/src/drum.rs`, platform-free, unit-tested), then expanded by an
integer factor — the window's backing scale, rounded — and handed to the
view's layer at that exact density. Cocoa never interpolates. No vector
scaling, no fractional DPI, ever.

## Plumbing

audio thread: `Engine::viz_pop()` → `SharedState::publish_viz` (try_lock;
contention drops frames, never blocks) → 30 Hz main-run-loop `NSTimer`
drains and turns the drum → fresh `NSBitmapImageRep` → layer contents.
The mount (`src-plugin/src/gui.rs`) is a plain layer-backed `NSView` — no
webview, no toolkit, no subclass. macOS only; elsewhere the plugin stays
fully headless.

## Verifying by eye without a DAW

```
cargo test -p opq_plugin_wrac --lib --release -- --ignored render_plate
sips -s format png /tmp/opq-drum-plate.ppm --out /tmp/opq-drum-plate.png
```

runs the real engine over synthesized voices (chord change, noise burst,
hard silence) and writes the resulting plate.

## Open questions, honestly held

- No user zoom yet. The fixed-pixel decree wants integer window multiples
  (2×, 3×) as an explicit setting; today the plate is 1× logical with
  integer retina density.
- Gate refusals currently appear only as weather (unclaimed spectrum) —
  the engine does not yet report a per-frame gate bit.
- The drum shows ~13 s. The session-scale plate and the install-scale
  strata are different clocks and different artifacts, deliberately not
  crammed into this one organ.
