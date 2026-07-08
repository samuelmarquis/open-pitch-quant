# Panel asset provenance

Everything the panel collages is either computed by `tools/bake-assets` or
taken from the public domain. The baked `.rgba`/`.font` bins under
`wrac/plugins/opq/src-plugin/assets/` are the only runtime artifacts; the
bakery regenerates them from these sources.

## Wikimedia Commons (all Public Domain)

- `gray907.rgba` — Henry Gray, *Anatomy* (1858), plate 907: the osseous
  labyrinth of the inner ear.
  https://commons.wikimedia.org/wiki/File:Gray907.png (PD-old)
- `phonautograph.rgba` — Édouard-Léon Scott de Martinville's phonautograph,
  1859 engraving: sound written onto a rotating drum, two decades before
  playback existed. The panel's chart recorder is tagged REC-1859 after it.
  https://commons.wikimedia.org/wiki/File:Phonautograph_1859.jpg (PD-old)
- `blake_ear.rgba` — "Fig. 15", Clarence John Blake's phonautograph (1880),
  which wrote sound traces using an excised human middle ear mounted on the
  stand. https://commons.wikimedia.org/wiki/File:Fig_13_The_Phonautograph_of_Clarence_John_Blake_(1880).jpg
  (PD-old)

Rejected during selection: "Helmholtz's double siren.jpg" (photograph,
CC BY-SA 4.0 — share-alike, not taken).

## Local / computed

- `redon_ghost.rgba` — processed from `design-refs/ugliness.jpg` (Odilon
  Redon, *The Cyclops*, c. 1914; painting is PD, artist d. 1916).
- `chladni.rgba` — computed square-plate Chladni figures (seven frames,
  indexed live by the number of held pitch-classes).
- `trefoil.rgba` — raymarched glass trefoil-knot turntable, 24 frames
  (SPECIMEN 001; tinted live by Mix).

## Type

- `haas10/14/30.font` — alpha atlases rasterized (via `fontdue`) from the
  system's Helvetica Neue, the direct descendant of Neue Haas Grotesk.
  Typeface designs are not copyrightable in the US and no font program is
  redistributed, only fixed bitmap rasters. If broader distribution ever
  wants cleaner provenance, rebake from URW Nimbus Sans (free, metric
  Helvetica cognate) by pointing `font_atlas()` at it — one line.
- The 5×7 machine stencil (`src/font.rs`) is hand-authored, original.
