# The OPQ GUI — "the grove"

*(v2, 2026-07-07 — rounds 2+3 of Sam's interface notes: "overly
conventional… consider the outside… beat the everliving fuck out of
this, harmoniously." Design references in `design-refs/`.)*

![cosmos](img/gui-v1-cosmos.png)

## Two ways of seeing

**COSMOS** (default) — the mapping as a cosmogram, present-tense. Pitch
class is angle, octave is radius, so the pitch continuum is a spiral
through the wheel. Held MIDI notes are a lit constellation — **Repeat
scope lights entire pitch-class spokes, Custom lights single diamond
nodes**, so the scope switch is visible as geometry. Every pitch object
is a star at its OUTPUT pitch, tethered across the wheel to a hollow
ghost at its SOURCE pitch: the tether *is* the remap. Harmonic-comb ticks
spiral outward from each star (h2 = same angle one ring out, h3 = a fifth
around…). The residual layer is a nebula placed by true octave-band
energy from the engine; transients are shockwave rings from the core;
retunes leave comet-trail arcs.

**STRATA** — the time view: the echogram (leftward scroll, output ribbons
+ dashed source ghosts, strata, leader-line callouts, dust).

Switch bottom-right of the display; the choice persists.

## The star, anatomized

Each glyph is a live portrait of one pitch object — every visual channel
is an engine quantity:

| feature | meaning |
|---|---|
| spike count | harmonics claimed this frame (`nh`) |
| size | claimed spectral energy |
| tether particle stream | remap tension — matter dragged from source to target, more and faster with pull |
| positional wobble | the HEARD pitch: glide ramp + Feel × source deviation (Feel at 0 locks it) |
| edge roughness | the Grit knob |
| twinning | Coherence below 100% sunders each star into channel-twins |
| hollow + rays | newborn (inside the transition-policy window) |
| spike pattern & color | stable identity (hashed from the track uid) |

**Hover any star** for its dossier: source pitch and detune, target,
pull, harmonic count, relative amplitude.

## Controls

Reliquary blocks (see the Bestiary below): each continuous parameter's
face is its Warden, crossfaded between two painted aspects by the value,
with the readout and the Warden's italic name over a scrim. **Every
control has hover text** naming its Warden and describing mechanism +
musical result. Drag = coarse, shift-drag = fine, wheel = trim,
double-click = default, click the value = type. (Round 2's procedural
mechanism-diagrams were retired in round 3 — git has them.)

## Idle state

Before any audio arrives the display runs a small fractal-flame IFS
(chaos game over drifting sinusoidal/swirl variations, `flame.ts`) — the
plugin dreaming until you give it sound.

![strata](img/gui-v1-strata.png)
![idle](img/gui-v1-idle.png)

## Architecture

```
engine (rt/engine)          plugin (wrac/plugins/opq)         GUI (src-gui)
VizFrame ring (16, no      audio.rs publishes via try_lock    grove.ts renders
alloc) per hop; now    →   SharedState VecDeque (64)     →    both modes at rAF;
with residual octave       GUI timer (33ms) drains → JSON     controls.ts renders
bands                      over wxp Channel "viz-frames"      the reliquary rail
```

- Parameter manifest (`get_parameter_manifest`): Rust is the single
  source of truth for ranges/defaults/choices.
- Viz payload field names match the CLI `--viz-dump` JSON-lines format;
  browser demo mode replays a baked phylovox trace (`demoTrace.ts`,
  regenerate: CLI `--viz-dump` → `tools/make_demo_trace.mjs`).
- Window: default 1120×800, minimum 920×780 — **the rail never scrolls**
  at any allowed size.

## Dev workflow

- Browser: `npm run dev` in `src-gui` → demo mode. URL params:
  `?mode=strata` forces the time view, `?idle` keeps the feed empty (for
  the flame).
- Hot reload in a DAW: install a *debug* build (points at the Vite dev
  server). Debug DSP is ~50× slower — reinstall `--release` after.
- Screenshots without a browser: `tools/shot.swift` (offscreen
  WKWebView — the plugin's actual rendering engine).

## The Meltdown Bestiary (round 4: the films ARE the values)

Round 4 killed the widget: no boxes, borders, or chips anywhere on the
rail — the Wardens are pinned straight to the void, each at its own
slight angle, policy switches are bare ink with an acid underline. And
each Warden is now a **metamorphosis film**: WAN 2.5 transforms the
curated start frame into the high aspect over five seconds, extracted to
a 33-frame strip, and **the knob scrubs it** — 35% Feel is frame 12 of
the hand curling around its ember; VOICES at 6 is the star mid-division.

Curation was a kill floor: 66 start-frame candidates → 11 survivors
(83% rejected; the grinning homunculus at the Door was non-negotiable),
22 film candidates → 10 + one re-roll (the Choir's star vanished at low
values — re-shot with the star pinned). 44 hand-lettered name-card
attempts died on an API minimum; the italic serif whisper stays.
Contact sheets: `img/bestiary-candidates.png`, `img/bestiary-films.png`.

## The Meltdown Bestiary

Every continuous parameter is kept by a **Warden** — a specimen generated
by Flux (RunPod) in two painted aspects, unmulted onto the void
(luminance→alpha, so glowing edges survive), crossfaded by the value. The
Vessel (mix, drought↔flood) · the Tremble (feel) · the Stair (glide) ·
the Burr (grit) · the Mask (formant) · the Choir (voices) · the Door
(gate) · the Sky (ceiling) · the Mercy (thresh) · the Burden (carry) ·
the Twins (cohere). Three heroes (Vessel, Tremble, Burr) wake into
WAN-2.5-generated motion while dragged. Contact sheet:
`img/bestiary-contact.png`. Regeneration: `tools/` scripts pattern, needs
`RUNPOD=` in `~/.env`; ~$1.50 for the full set.

**The controls are the model** — the cosmos obeys them live: Feel scales
the star's re-injected source wobble (the star renders the *heard* pitch,
lema-EMA mirror of the engine); Glide becomes the on-screen retune ramp;
Mix crossfades visual weight between the wet star-layer and the dry
ghost-layer; Grit roughens every glyph's edges; Coherence at less than
100% sunders each star into two drifting channel-twins; remap tension is
matter — particle grains stream along each tether from source ghost into
the star, more and faster the harder the pull. Bypass stamps the field.

![bestiary](img/gui-v2-bestiary.png)
![cosmos physics](img/gui-v2-cosmos.png)

## Known limitations

- Standalone app target needs `ibtool` (full Xcode) for its menu nib;
  CLAP/VST3/AU unaffected.
- Star callouts cap at the loudest 8 objects (engine reports up to 24).
