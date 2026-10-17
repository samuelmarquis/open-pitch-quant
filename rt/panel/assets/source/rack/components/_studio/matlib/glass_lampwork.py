"""Glass family, lampwork: borosilicate encasement and what is worked inside
it — clear boro, seed bubbles, jet backing, coloured cane and frit.

Everything here is index-matched to borosilicate (IOR 1.47): the colour lives
in real geometry inside the clear volume, and interfaces between encased parts
carry little specular. IOR, transmission and colour are not spatial; texture
frequencies, bump distances and Subsurface Scale pass through ctx.
"""
from .core import DEFAULT_CTX, base_material, imperfect, material
from .units import mm_per_unit

KNOB_MM = mm_per_unit("knob-heady")
BORO_IOR = 1.47


@material("borosilicate-clear", family="glass", finish="gloss", solid=True,
          calib_mm_per_unit=KNOB_MM, origin="knob-heady:boro_material:283")
def borosilicate_clear(*, ctx=DEFAULT_CTX):
    """Clear colourless borosilicate (IOR 1.47), full transmission, a faint
    broad ripple bump and near-zero roughness mottle (0-0.03). A thick dome of
    it needs deep transmission bounces and an opaque backing behind it.

    Duplicate candidate: glass-clear (matlib cast glass is tinted and frosted;
    this is the untinted, unfrosted case)."""
    m, _nt, b = base_material("clear borosilicate")
    b.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = BORO_IOR
    return imperfect(m, 0.0, 0.03, bump_strength=0.0012, scale=4.42, ctx=ctx)


@material("borosilicate-seed-bubble", family="glass", finish="gloss", solid=True,
          calib_mm_per_unit=KNOB_MM, origin="knob-heady:air_material:292")
def borosilicate_seed_bubble(*, ctx=DEFAULT_CTX):
    """An air void inside borosilicate: the same clear IOR 1.47 dielectric on a
    mesh whose normals point INWARD, so the interface reads glass-to-air. The
    inverted normals are the caller's contract; with outward normals this is
    just another glass bead."""
    m, _nt, b = base_material("seed bubble air")
    b.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = BORO_IOR
    return imperfect(m, 0.0, 0.02, bump_strength=0.001, scale=94.8, ctx=ctx)


@material("glass-jet", family="glass", finish="satin", solid=True,
          calib_mm_per_unit=KNOB_MM, origin="knob-heady:jet_material:301")
def glass_jet(*, ctx=DEFAULT_CTX):
    """Opaque jet-black glass encased behind clear boro: near-black with a low
    specular level (0.2) so its interface with the encasement nearly vanishes,
    satin roughness mottle and micro-bump."""
    m, _nt, b = base_material("jet black backing")
    b.inputs["Base Color"].default_value = (0.0030, 0.0030, 0.0036, 1)
    b.inputs["Specular IOR Level"].default_value = 0.2
    return imperfect(m, 0.22, 0.36, bump_strength=0.004, scale=82.0, ctx=ctx)


@material("lampwork-colour", family="glass", finish="satin", solid=True,
          calib_mm_per_unit=KNOB_MM, origin="knob-heady:encased_material:309")
def lampwork_colour(name="latticino white", rgb=(0.88, 0.88, 0.84), sss=0.2, spec=0.25,
                    rough=(0.30, 0.44), *, ctx=DEFAULT_CTX):
    """Coloured glass worked inside a clear encasement (petals, stripes,
    latticino, cane, murrine rings): opaque `rgb` at a low specular level
    `spec`, optional subsurface `sss` (radius profile 1.0/0.7/0.5, scale 0.012;
    left at the Principled defaults when `sss` is 0), roughness mottle
    `rough` = (lo, hi) and micro-bump. `name` is the part's label; the
    component supplies one per inclusion."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Specular IOR Level"].default_value = spec
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.7, 0.5)
        b.inputs["Subsurface Scale"].default_value = ctx.length(0.012, KNOB_MM)
    return imperfect(m, rough[0], rough[1], bump_strength=0.004, scale=175.0, ctx=ctx)
