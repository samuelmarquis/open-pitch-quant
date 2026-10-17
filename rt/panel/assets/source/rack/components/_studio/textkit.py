"""textkit: panel text as real geometry, in the panel's own material.

The corpus has had four unrelated ways of putting text on a part — extruded
font curves (knob-witchhat), ad hoc Blender text objects (fader-desk,
display-segment, button-radio), hand-authored glyph geometry (display-nixie)
and PIL-rasterized textures baked OUTSIDE Blender (meter-vu, selector-drum).
The last one is why some labels never look like part of the panel: text
rasterized outside the render cannot take the scene's lighting, so it is a
sticker by construction.

This is the one place that makes panel text, as geometry, inside the render.

TREATMENTS
----------
    engraved        cut into the surface; walls catch the key light, the
                    opposite wall falls into shadow. The default for a machined
                    or moulded panel.
    engraved-fill   the same cut, flooded with paint. What most real panel
                    legends actually are.
    debossed        stamped: a flat-bottomed sink, no fill.
    raised          proud of the surface, the panel's own material (moulded-in
                    lettering, a cast badge).
    printed         flush: ink sitting a hair proud, no relief to speak of.
                    Screen print or pad print.

`engraved`, `engraved-fill` and `debossed` need a BOOLEAN against the host
surface — a letterform is not a rectangle, so the partition trick the rails use
does not apply. `cut_text` does that; the caller hands it the host object.

FONTS are bundled (`_studio/fonts/`, DejaVu, permissive licence) and resolved
by name. NEVER reference a system font by absolute path: every existing
component does, which is why this corpus cannot rebuild its own canon on
another machine.
"""
import math
from pathlib import Path

import bpy

import meshlib

FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONTS = {
    "sans": "DejaVuSans.ttf",
    "sans-bold": "DejaVuSans-Bold.ttf",
    "mono": "DejaVuSansMono.ttf",
    "mono-bold": "DejaVuSansMono-Bold.ttf",
}
TREATMENTS = ("engraved", "engraved-fill", "debossed", "raised", "printed")
EPS_LIFT = 4e-4          # coplanar tops z-fight; this clears them

# A cut needs the tool to poke out of BOTH faces of the region it cuts, or the
# boolean leaves a skin. This is how far past the surface the tool extends.
TOOL_OVERSHOOT = 0.05


def load_font(name):
    """A bundled font by key (`sans`, `mono-bold`, ...) or by file name."""
    fname = FONTS.get(name, name)
    path = FONT_DIR / fname
    if not path.is_file():
        raise SystemExit(
            f"textkit: no bundled font {name!r} ({path}). Bundled: "
            f"{', '.join(sorted(FONTS))}. Do not point at a system font — canon "
            "must rebuild on any machine.")
    for f in bpy.data.fonts:
        if f.filepath == str(path):
            return f
    return bpy.data.fonts.load(str(path))


def text_solid(name, text, font, cap_height, z0, z1, align="CENTER",
               spacing=1.0, at=(0.0, 0.0)):
    """The glyphs as one solid between z0 and z1, centred on `at`.

    `cap_height` is the CAP HEIGHT in world units, not Blender's font size:
    a panel legend is specified by how tall its capitals stand, and that is
    what has to survive at product scale. DejaVu's cap height is 0.729 em.
    """
    size = cap_height / 0.729
    mesh = meshlib.glyph_mesh(font, text, size=size, extrude=(z1 - z0) / 2.0,
                              space_character=spacing, align_x=align)
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    ob.location = (at[0], at[1] - cap_height / 2.0, (z0 + z1) / 2.0)
    return ob


PROFILE_ROWS = 160      # optical spacing: scanlines across the cap height
OPTICAL_DEPTH = 0.25    # x cap: open counter-space past a pair's tightest row
                        # counts only this deep (T's overhang, A's diagonal)


def ink_profiles(ob, cap_height):
    """A glyph solid's left and right ink edge on PROFILE_ROWS scanlines over
    [0, cap_height] in its own x (NaN where a row has no ink): its triangles
    rasterized in plan."""
    import numpy as np

    me = ob.data
    me.calc_loop_triangles()
    co = np.array([v.co[:2] for v in me.vertices])
    ys = (np.arange(PROFILE_ROWS) + 0.5) / PROFILE_ROWS * cap_height
    left = np.full(PROFILE_ROWS, np.inf)
    right = np.full(PROFILE_ROWS, -np.inf)
    for t in me.loop_triangles:
        p = co[list(t.vertices)]
        for k in range(3):                        # each edge's crossing of each row
            (x0, y0), (x1, y1) = p[k], p[(k + 1) % 3]
            if y0 == y1:
                continue
            m = (ys >= min(y0, y1)) & (ys <= max(y0, y1))
            x = x0 + (ys[m] - y0) * (x1 - x0) / (y1 - y0)
            left[m] = np.minimum(left[m], x)
            right[m] = np.maximum(right[m], x)
    left[~np.isfinite(left)] = np.nan
    right[~np.isfinite(right)] = np.nan
    return left, right


def optical_advance(right_a, left_b, gap, cap_height):
    """How far glyph b's origin sits right of glyph a's so that the mean
    whitespace between them — each row's gap, capped OPTICAL_DEPTH x cap past
    the pair's tightest row — equals `gap`. Monotone in the advance: bisect."""
    import numpy as np

    rows = np.isfinite(right_a) & np.isfinite(left_b)

    def mean_gap(d):
        g = d + left_b[rows] - right_a[rows]
        return np.minimum(g, g.min() + OPTICAL_DEPTH * cap_height).mean()

    lo, hi = -2 * cap_height, 4 * cap_height
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if mean_gap(mid) < gap else (lo, mid)
    return (lo + hi) / 2


def optical_word(name, text, font, cap_height, z0, z1, gap, at=(0.0, 0.0)):
    """`text` as one glyph solid PER LETTER (the caller lights or cuts each on
    its own), spaced OPTICALLY: every adjacent pair's mean whitespace is `gap`
    (the face's advances and kerning are not used; uniform tracking leaves TA
    and AT loose beside UT). Centred on `at`, cap band on y about at[1].
    Returns (letters, span)."""
    import numpy as np

    letters = [text_solid(f"{name} {i}", ch, font, cap_height, z0, z1, align="LEFT")
               for i, ch in enumerate(text, 1)]
    prof = [ink_profiles(o, cap_height) for o in letters]
    xs = [0.0]
    for (_, ra), (lb, _) in zip(prof, prof[1:]):
        xs.append(xs[-1] + optical_advance(ra, lb, gap, cap_height))
    lo = min(x + np.nanmin(l) for x, (l, _) in zip(xs, prof))
    hi = max(x + np.nanmax(r) for x, (_, r) in zip(xs, prof))
    for ob, x in zip(letters, xs):
        ob.location.x = at[0] + x - (lo + hi) / 2
        ob.location.y = at[1] - cap_height / 2.0
    return letters, hi - lo


SHARP_DEG = 30.0        # after a cut: face and groove walls flat, bevels smooth
MIN_CAP_PX = 12.0       # below this at the output density, regular weights break up


def cut_text(host, tool, keep_tool=False):
    """Difference `tool` out of `host`, APPLIED. A letterform is not a
    rectangle, so the boolean-free partition the rails use does not apply here;
    EXACT is the solver that keeps a clean edge on a flat face.

    Learned retrofitting open-cepstrum's contour-radio legends (2026-09-24):
      * the host's own modifiers (its bevel) are applied FIRST — cutting a
        live-bevelled, all-smooth-shaded cap smears its reflection across the
        letters;
      * the cut is applied, then sharp-by-angle (SHARP_DEG) so the face and
        groove walls shade flat while the bevels stay smooth;
      * tool solids must not be thickened with curve `offset`: offset glyph
        outlines self-intersect and EXACT shreds the host (get weight from the
        font — `sans-bold`).
      * a large flat face the cut leaves behind is a few big smooth n-gons whose
        boundary corners average in tilted neighbours; a caller whose material
        reads the normal (brushed's face/edge split) shades those faces flat
        (panel-board --title, pass 41).
    """
    bpy.context.view_layer.objects.active = host
    for m in list(host.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    n_slots = len(host.data.materials)
    mod = host.modifiers.new("text-cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = tool
    bpy.ops.object.modifier_apply(modifier=mod.name)
    # an applied EXACT cut leaves an EMPTY material slot on a host that had
    # none; a material the caller appends afterwards then lands in slot 1
    # while every face points at slot 0, and the host renders default white
    while len(host.data.materials) > n_slots and host.data.materials[-1] is None:
        host.data.materials.pop()
    host.data.set_sharp_from_angle(angle=math.radians(SHARP_DEG))
    tool.hide_render = True
    tool.hide_viewport = True
    if not keep_tool:
        tool.hide_set(True)
    return host


def place(host, text, *, treatment, font, cap_height, z_top, depth=0.020,
          at=(0.0, 0.0), align="CENTER", spacing=1.0, name="label", px_per_unit=None):
    """Put `text` on `host`'s top face at `z_top`, in `treatment`.

    Returns {"cut": [tool objects], "fill": [...], "proud": [...]} — the caller
    binds materials: `fill` takes the ink/engraving key, `proud` takes either
    ink (printed) or the host's own material (raised), and `cut` objects are
    boolean tools that render nothing. A cut treatment APPLIES the host's
    modifiers (see cut_text).

    `px_per_unit`, the output density, turns on a warning below MIN_CAP_PX of
    cap height: regular weights break into 1 px strokes there (use sans-bold).
    Fill ink: `engraving-fill-flat` reads as black paint on small letters;
    `engraving-fill-neutral`'s mottle and micro-bump, calibrated for a knob
    face, scatter the house light and read light grey at ~5 px strokes.
    """
    if treatment not in TREATMENTS:
        raise SystemExit(f"textkit: treatment must be one of {TREATMENTS}")
    if px_per_unit is not None and cap_height * px_per_unit < MIN_CAP_PX:
        print(f"textkit WARNING: {text!r} cap height {cap_height * px_per_unit:.1f} px "
              f"< {MIN_CAP_PX:g} px at the output density — use a bold weight or larger",
              flush=True)
    out = {"cut": [], "fill": [], "proud": []}

    if treatment in ("engraved", "engraved-fill", "debossed"):
        # the tool spans from below the groove floor to well above the face
        tool = text_solid(f"{name}-tool", text, font, cap_height,
                          z_top - depth, z_top + TOOL_OVERSHOOT, align, spacing, at)
        cut_text(host, tool)
        out["cut"].append(tool)
        if treatment == "engraved-fill":
            # the fill sits IN the groove, its top a hair below the face so the
            # cut still reads as a cut and the paint does not look printed on
            fill = text_solid(f"{name}-fill", text, font, cap_height,
                              z_top - depth, z_top - depth * 0.25, align, spacing, at)
            out["fill"].append(fill)
    elif treatment == "raised":
        proud = text_solid(f"{name}-proud", text, font, cap_height,
                           z_top - 0.002, z_top + depth, align, spacing, at)
        out["proud"].append(proud)
    else:                                   # printed: flush ink, no relief
        proud = text_solid(f"{name}-ink", text, font, cap_height,
                           z_top, z_top + EPS_LIFT, align, spacing, at)
        out["proud"].append(proud)
    return out
