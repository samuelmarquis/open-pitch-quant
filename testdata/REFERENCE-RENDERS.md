# PITCHMAP reference renders — operator protocol

This folder (`testdata/reference/`, built by `tools/make_ab_pack.py`) is a
self-contained work order for the machine that has PITCHMAP. `jobs/` holds
matched **(WAV, MID) pairs with identical stems**; each pair is exactly one
bounce, and **the filename is the complete settings sheet** for that bounce.
Nothing needs cross-referencing; if this document and a filename ever
disagree, the filename wins.

Every rendered pair becomes ground truth for A/B against our engine — the
same job WAV+MID feed both machines, byte for byte. So: exactness over
speed, and never "improve" anything (no normalizing, no trimming, no fades).

## The name is the settings

```
j24__05_sustain_vs_chordchange__repeat-near__th0_fe0_gl0_pu50_el50.wav
└┬┘  └────────┬─────────────┘  └────┬─────┘ └────────┬───────────┘
job#      input material       Edit Mode &      knob positions
                               Xclude Round.    (slider %, 0–100)
```

- `repeat` / `custom` → **EDIT MODE** = Repeat / Custom.
- `near` / `intel` → **XCLUDE ROUND. MODE** = Nearest / Intelligent.
- `th fe gl pu el` → **THRESHOLD, FEEL, GLIDE, PURIFY, ELECTRIFY**, as
  slider positions in percent (0 = bottom, 100 = top). If the readout
  shows other units, set the slider to that fraction of its travel and
  write the displayed value in `_RENDER-LOG.md`.
- Trailing flags override the constants below:
  - `__NONOTES` — the MID is empty **on purpose**: MIDI MAP stays ON,
    nothing is held. (Undocumented behavior we need to hear.)
  - `__NULL-CONTROL` (j00) — PITCHMAP **deactivated/removed**; bounces the
    bare render path. Do this one first.
  - `__algL` / `__algN` — ALGORITHM = Linear / Natural for that job only.
  - `__strict` — STRICT on for that job only.

## Constants (set once, hold for every job unless a flag says otherwise)

MIDI MAP **ON** · KEY EDIT = **XCLUDE** · ALGORITHM = **MEDIUM** ·
STRICT **off** · Low-Cut/High-Cut fully open · Mute off · no Key
Transform/Voicing · Input Ref. Tuning **440** · Output Tuning **440** ·
mapping sliders left at Reset (MIDI MAP ignores them) · snapshots unused.

## Session (Ableton Live on the Windows box)

1. New Live Set. **Sample rate 48000. Tempo exactly 120.00 BPM.**
   Options → Delay Compensation ON. Nothing on the Master.
2. Audio track with PITCHMAP as insert (VST3; if MIDI won't reach the
   VST3, use the VST2 and log it). MIDI track with **MIDI To → the audio
   track ▸ PITCHMAP**.
3. Set the constants above on the plugin.
4. Per job, one pair on the timeline at a time:
   - drag `jobs/<stem>.wav` to the audio track at **1.1.1** — then in Clip
     view turn **Warp OFF** (critical; alignment dies otherwise);
   - drag `jobs/<stem>.mid` to the MIDI track at **1.1.1**;
   - set Edit Mode, Xclude Round. Mode, and the five knobs to what the
     stem says (double-click a control for numeric entry if the GUI
     allows; otherwise closest position, log the displayed value);
   - select the audio clip → File → Export Audio/Video: Rendered Track =
     that audio track, **WAV, 48000, 32-bit (float), Normalize OFF**;
   - save as `renders/<stem>.wav` — **the identical stem**, only the
     folder differs;
   - tick the row in `_RENDER-LOG.md`, note anything odd.
5. Delete both clips before loading the next pair.

Sanity gates: render `j00` (plugin off) first — it should sound identical
to its job WAV. Then `j01`: pink noise should come back audibly *pitched
toward C major*, and PITCHMAP's keyboard/display should visibly react
while the MIDI clip plays. Silent or untouched output means routing is
broken — stop and fix before continuing.

(Reaper instead: insert media at 0.0 with stretch off, route the MIDI
track's sends to the FX track's MIDI input, render Time Selection =
item length, WAV 32-bit FP, no resample, no tail trim.)

## Order and stamina

Work in job order; `_RENDER-LOG.md` marks tiers — **A** first (the core:
null control, every baseline, the NONOTES probes), **B** is the knob
matrix, **C** only if energy remains. Stop anywhere: every completed pair
is immediately useful. The plugin reports 4096 samples latency — delay
compensation makes that invisible; don't correct for it by hand.

## If the operator is a Claude

Do the jobs in tier order; the filename is authoritative; never
normalize, warp, trim, fade, or resample; if an exact value is
unreachable, take the closest and record what the GUI displayed; if a
job can't be done as specified, log it and skip — do not improvise a
substitute. When finished (or stopping), zip the whole folder — renders
plus the filled `_RENDER-LOG.md` — and hand it back.

## Returning the goods

Zip `reference/` (at minimum `renders/` + `_RENDER-LOG.md`) back onto the
Mac at `testdata/reference/`. Everything here is local-only (the material
is private; git ignores all WAV/MID). Regenerate the pack any time:

```
nix develop --command python3 tools/make_ab_pack.py
```

which also drops a transport copy at `out/opq-pm-refpack.zip`.
