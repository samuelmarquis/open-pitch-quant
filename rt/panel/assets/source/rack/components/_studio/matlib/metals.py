"""Metal family: machined, plated, brushed, oxidised and anodised metals, and
the fastener metal.

The anisotropic brushed metals (brushed, worn-steel, copper, gold, anodized-*)
take their tangent from matlib.tangent.linear(axis="X"): object X carried to
world space, no UV map needed. The grain textures run along object X too, so
tangent and grain stay aligned on any part and turn with it.
"""
import bpy

from . import tangent
from .core import (DEFAULT_CTX, _lerp3, _obj_pos, _obj_vec, _warp, base_material, imperfect,
                   material, sheen, sheet_ripple)
from .nodes import _mix_rgba


_BRUSHED = dict(family="metal", finish="satin", solid=False, origin="matlib.mat_brushed")


# Tinted brushed plates (pass 45, from Nolan's crud_ui rack): the brushed grey
# multiplied by a colour, the grain coarse enough to read at a product's
# density (the plain key's (5, 300) runs under a pixel at 200 px/unit).
@material("brushed", **_BRUSHED)
@material("brushed-champagne", params={"tint": (1.25, 1.15, 0.95), "grain": (0.72, 21.6)},
          **_BRUSHED)
@material("brushed-cherry", params={"tint": (1.1, 0.12, 0.08), "grain": (0.8, 24.0)}, **_BRUSHED)
@material("brushed-brass", params={"tint": (1.7, 1.2, 0.42), "grain": (1.04, 31.2)}, **_BRUSHED)
def mat_brushed(rough_lo=0.09, rough_hi=0.34, aniso=0.9, edge_rough_lo=0.22,
                edge_rough_hi=0.40, edge_aniso=0.72, tint=(1.0, 1.0, 1.0), grain=(5.0, 300.0),
                *, ctx=DEFAULT_CTX):
    """Brushed aluminium: reflective satin, roughness low enough that the
    highlight concentrates and reads as grey metal; linear anisotropy along
    object X + directional grain along the same axis. `rough_lo`/`rough_hi`
    are the streak roughness range, `aniso` the stretch.

    FACE AND EDGE DIFFER (pass 38, p118). On the face the strokes carry the
    material, so it stays sharp and strongly anisotropic. Where the surface
    turns away from the part's face — a bevel, a rounded edge — it blends to
    the `edge_*` satin: a sharp brushed bevel mirrors one light as a 1-2 px hot
    line at product scale, which reads as aliasing. The blend runs off the
    object-space normal against object +Z, so it follows the part."""
    m, nt, b = base_material("brushed")
    b.inputs["Base Color"].default_value = (0.56 * tint[0], 0.56 * tint[1], 0.58 * tint[2], 1)
    b.inputs["Metallic"].default_value = 1.0
    nt.links.new(tangent.linear(nt, "X"), b.inputs["Tangent"])

    # face factor: 1 on a face within ~8 deg of object +Z, 0 past ~20 deg
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    to_obj = nt.nodes.new("ShaderNodeVectorTransform")
    to_obj.vector_type, to_obj.convert_from, to_obj.convert_to = "NORMAL", "WORLD", "OBJECT"
    nt.links.new(geo.outputs["Normal"], to_obj.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(to_obj.outputs["Vector"], nz.inputs["Vector"])
    face = nt.nodes.new("ShaderNodeMapRange")
    face.interpolation_type = "SMOOTHSTEP"
    face.inputs["From Min"].default_value = 0.94
    face.inputs["From Max"].default_value = 0.99
    nt.links.new(nz.outputs["Z"], face.inputs["Value"])
    an = nt.nodes.new("ShaderNodeMapRange")
    an.inputs["To Min"].default_value = edge_aniso
    an.inputs["To Max"].default_value = aniso
    nt.links.new(face.outputs["Result"], an.inputs["Value"])
    nt.links.new(an.outputs["Result"], b.inputs["Anisotropic"])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = ctx.freq((grain[0], grain[1], 1.0))   # long grooves along X
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    streak = nt.nodes.new("ShaderNodeTexNoise")
    streak.inputs["Detail"].default_value = 3.0
    streak.inputs["Roughness"].default_value = 0.75
    nt.links.new(mp.outputs["Vector"], streak.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = rough_lo  # reflective floor
    mr.inputs["To Max"].default_value = rough_hi
    nt.links.new(streak.outputs["Fac"], mr.inputs["Value"])
    er = nt.nodes.new("ShaderNodeMapRange")      # the same streaks, satin, on edges
    er.inputs["To Min"].default_value = edge_rough_lo
    er.inputs["To Max"].default_value = edge_rough_hi
    nt.links.new(streak.outputs["Fac"], er.inputs["Value"])
    rmix = nt.nodes.new("ShaderNodeMix")
    rmix.data_type = "FLOAT"
    nt.links.new(face.outputs["Result"], rmix.inputs["Factor"])
    nt.links.new(er.outputs["Result"], rmix.inputs["A"])
    nt.links.new(mr.outputs["Result"], rmix.inputs["B"])
    nt.links.new(rmix.outputs["Result"], b.inputs["Roughness"])
    sb = nt.nodes.new("ShaderNodeBump")
    sb.inputs["Strength"].default_value = 0.07
    sb.inputs["Distance"].default_value = ctx.length(0.02)
    nt.links.new(streak.outputs["Fac"], sb.inputs["Height"])
    nt.links.new(sb.outputs["Normal"], b.inputs["Normal"])
    return m


def _wavy_scratches(nt, b, wav_scale=0.57, wav_strength=0.022, scr_strength=0.01,
                    *, ctx=DEFAULT_CTX):
    """Very broad, shallow waviness (a flat mirror reflection gets gentle life,
    not a busy ripple or a hard binary horizon) + faint directional hair
    scratches. Shared by chrome and sleek-black gloss.

    Does NOT preserve an existing Normal link: call it first, then chain onto
    the head of its chain."""
    wav = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), wav.inputs["Vector"])
    wav.inputs["Scale"].default_value = ctx.freq(wav_scale)
    wav.inputs["Detail"].default_value = 1.0
    wb = nt.nodes.new("ShaderNodeBump")
    wb.inputs["Strength"].default_value = wav_strength
    wb.inputs["Distance"].default_value = ctx.length(0.05)
    nt.links.new(wav.outputs["Fac"], wb.inputs["Height"])
    # faint directional hair scratches
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = ctx.freq((26.0, 780.0, 1.0))
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    scr = nt.nodes.new("ShaderNodeTexNoise")
    scr.inputs["Detail"].default_value = 2.0
    nt.links.new(mp.outputs["Vector"], scr.inputs["Vector"])
    sb = nt.nodes.new("ShaderNodeBump")
    sb.inputs["Strength"].default_value = scr_strength
    sb.inputs["Distance"].default_value = ctx.length(0.0012)
    nt.links.new(scr.outputs["Fac"], sb.inputs["Height"])
    nt.links.new(wb.outputs["Normal"], sb.inputs["Normal"])
    nt.links.new(sb.outputs["Normal"], b.inputs["Normal"])


@material("chrome", family="metal", finish="mirror", solid=False,
          origin="matlib.mat_chrome")
def mat_chrome(*, ctx=DEFAULT_CTX):
    """Chromed steel: near-mirror that reflects a real room (env stays glossy
    for reflective materials). Large-scale waviness breaks the flat mirror so
    the reflection ripples instead of showing a binary horizon."""
    m, nt, b = base_material("chrome")
    b.inputs["Base Color"].default_value = (0.86, 0.87, 0.89, 1)
    b.inputs["Metallic"].default_value = 1.0
    # roughness: near-mirror, mottled a touch (never a perfect surface)
    rn = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), rn.inputs["Vector"])
    rn.inputs["Scale"].default_value = ctx.freq(36.7)
    rmr = nt.nodes.new("ShaderNodeMapRange")
    rmr.inputs["To Min"].default_value = 0.03
    rmr.inputs["To Max"].default_value = 0.075
    nt.links.new(rn.outputs["Fac"], rmr.inputs["Value"])
    nt.links.new(rmr.outputs["Result"], b.inputs["Roughness"])
    _wavy_scratches(nt, b, wav_scale=0.531, wav_strength=0.02, scr_strength=0.012, ctx=ctx)
    return m


@material("worn-steel", family="metal", finish="satin", solid=False,
          params={"name": "worn_steel", "rust": 0.0}, origin="matlib.mat_steel")
def mat_steel(name, rust=0.0, *, ctx=DEFAULT_CTX):
    """Worn steel plate. The read comes from BRUSHING (anisotropic directional
    grain smearing the reflection) plus crisscross wear scratches. `rust` in
    0..1 adds sparse oxide flecks: 0 = clean worn steel, high = heavily
    rusted."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Anisotropic"].default_value = 0.72
    nt.links.new(tangent.linear(nt, "X"), b.inputs["Tangent"])
    tc = nt.nodes.new("ShaderNodeTexCoord")

    # brushed directional grain -> roughness (grooves along X) = the steel read
    gmp = nt.nodes.new("ShaderNodeMapping")
    gmp.inputs["Scale"].default_value = ctx.freq((5.0, 320.0, 1.0))
    nt.links.new(tc.outputs["Object"], gmp.inputs["Vector"])
    grain = nt.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Detail"].default_value = 3.0
    grain.inputs["Roughness"].default_value = 0.72
    nt.links.new(gmp.outputs["Vector"], grain.inputs["Vector"])
    grough = nt.nodes.new("ShaderNodeMapRange")
    grough.inputs["To Min"].default_value = 0.13
    grough.inputs["To Max"].default_value = 0.50
    nt.links.new(grain.outputs["Fac"], grough.inputs["Value"])
    # broad worn tonal zones (shiny vs dull) — in ROUGHNESS, not colour;
    # smooth colour variation reads as marble
    tone = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(tc.outputs["Object"], tone.inputs["Vector"])
    tone.inputs["Scale"].default_value = ctx.freq(3.27)
    tone.inputs["Detail"].default_value = 8.0
    tmr = nt.nodes.new("ShaderNodeMapRange")
    tmr.inputs["To Min"].default_value = -0.09
    tmr.inputs["To Max"].default_value = 0.13
    nt.links.new(tone.outputs["Fac"], tmr.inputs["Value"])
    tadd = nt.nodes.new("ShaderNodeMath")
    tadd.operation = "ADD"
    tadd.use_clamp = True
    nt.links.new(grough.outputs["Result"], tadd.inputs[0])
    nt.links.new(tmr.outputs["Result"], tadd.inputs[1])
    rough_socket = tadd.outputs["Value"]

    # rust: sparse oxide flecks (colour + extra roughness), scaled by `rust`
    rust_normal_src = None
    if rust > 0:
        rv = nt.nodes.new("ShaderNodeTexVoronoi")
        rv.feature = "F1"
        rv.inputs["Scale"].default_value = ctx.freq(15.0)
        rmask = nt.nodes.new("ShaderNodeMapRange")
        rmask.inputs["From Min"].default_value = 0.0
        rmask.inputs["From Max"].default_value = 0.05 + 0.20 * rust   # more rust = bigger patches
        rmask.inputs["To Min"].default_value = 1.0
        rmask.inputs["To Max"].default_value = 0.0
        nt.links.new(rv.outputs["Distance"], rmask.inputs["Value"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.20, 0.23, 0.28, 1)   # dark blue-grey gunmetal
        ramp.color_ramp.elements[1].color = (0.28, 0.13, 0.06, 1)   # rust
        ramp.color_ramp.elements[1].position = 0.5
        nt.links.new(rmask.outputs["Result"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
        # rust patches read rougher (oxide is matte)
        rmul = nt.nodes.new("ShaderNodeMath")
        rmul.operation = "MULTIPLY"
        rmul.inputs[1].default_value = 0.5
        nt.links.new(rmask.outputs["Result"], rmul.inputs[0])
        radd = nt.nodes.new("ShaderNodeMath")
        radd.operation = "ADD"
        radd.use_clamp = True
        nt.links.new(rough_socket, radd.inputs[0])
        nt.links.new(rmul.outputs["Value"], radd.inputs[1])
        rough_socket = radd.outputs["Value"]
        rust_normal_src = rmask.outputs["Result"]
    else:
        b.inputs["Base Color"].default_value = (0.20, 0.23, 0.28, 1)   # dark blue-grey gunmetal
    nt.links.new(rough_socket, b.inputs["Roughness"])

    def scratches(sx, sy, strength, dist, prev_normal):
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = ctx.freq((sx, sy, 1.0))
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Detail"].default_value = 2.0
        nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = strength
        bmp.inputs["Distance"].default_value = ctx.length(dist)
        nt.links.new(n.outputs["Fac"], bmp.inputs["Height"])
        if prev_normal is not None:
            nt.links.new(prev_normal, bmp.inputs["Normal"])
        return bmp.outputs["Normal"]

    # fine brushed grain bump + crisscross wear scratches (+ rust pitting)
    gb = nt.nodes.new("ShaderNodeBump")
    gb.inputs["Strength"].default_value = 0.035
    gb.inputs["Distance"].default_value = ctx.length(0.0014)
    nt.links.new(grain.outputs["Fac"], gb.inputs["Height"])
    nrm = scratches(18.0, 620.0, 0.16, 0.0032, gb.outputs["Normal"])   # along X
    nrm = scratches(560.0, 22.0, 0.13, 0.0028, nrm)                    # along Y
    nrm = scratches(40.0, 300.0, 0.09, 0.0022, nrm)                    # diagonal-ish
    if rust_normal_src is not None:
        pit = nt.nodes.new("ShaderNodeBump")
        pit.inputs["Strength"].default_value = 0.10 * rust
        pit.inputs["Distance"].default_value = ctx.length(0.004)
        nt.links.new(rust_normal_src, pit.inputs["Height"])
        nt.links.new(nrm, pit.inputs["Normal"])
        nrm = pit.outputs["Normal"]
    nt.links.new(nrm, b.inputs["Normal"])
    return m


@material("brass", family="metal", finish="mirror", solid=True, tier="warm",
          origin="matlib.mat_brass")
def mat_brass(*, ctx=DEFAULT_CTX):
    """Polished brass bezel: warm gold metal, lightly mottled, on a rolled
    sheet's slow ripple."""
    mat, nt, bsdf = base_material("polished brass bezel")
    bsdf.inputs["Base Color"].default_value = (0.78, 0.60, 0.33, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    imperfect(mat, 0.13, 0.22, bump_strength=0.008, scale=36.7, ctx=ctx)
    sheet_ripple(nt, bsdf, ctx=ctx)
    return mat


def _warm_metal(name, col, rough_lo, rough_hi, scale=110.0, *, ctx=DEFAULT_CTX):
    """Shared body for the warm metals: a polished non-ferrous plate whose read
    comes from a BROAD roughness mottle plus matlib's micro-imperfection.

    The broad mottle is load-bearing, not garnish. A flat panel is flat, so by
    THE TRIANGLE it hides the world from glossy rays and takes its gloss from
    the authored overhead alone — which means a smooth metal has nothing in it
    but base colour and one soft gradient, and reads as pastel plastic. The
    tonal zones give the single highlight something to break up on. Same
    lesson mat_steel records: put worn variation in ROUGHNESS, not colour.

    `scale` is accepted and unused."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Anisotropic"].default_value = 0.8
    nt.links.new(tangent.linear(nt, "X"), b.inputs["Tangent"])
    # THE BRUSH is what makes it read as metal here. A smooth warm metal on a
    # flat panel has literally nothing in it but base colour and one soft
    # gradient, and comes out as pastel plastic (copper and gold both did,
    # and so does polished brass). Directional grain smearing the
    # highlight is the family's proven answer — brushed-alu and worn-steel both
    # read as metal under this exact matte rig for the same reason.
    grain = nt.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Detail"].default_value = 3.0
    grain.inputs["Roughness"].default_value = 0.72
    nt.links.new(_obj_vec(nt, ctx.freq((5.0, 130.0, 1.0))), grain.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = rough_lo
    mr.inputs["To Max"].default_value = rough_hi
    nt.links.new(grain.outputs["Fac"], mr.inputs["Value"])
    # broad polish zones on top — hand-finishing never lands even
    tone = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), tone.inputs["Vector"])
    tone.inputs["Scale"].default_value = ctx.freq(2.04)
    tone.inputs["Detail"].default_value = 6.0
    tmr = nt.nodes.new("ShaderNodeMapRange")
    tmr.inputs["To Min"].default_value = -0.04
    tmr.inputs["To Max"].default_value = 0.13
    nt.links.new(tone.outputs["Fac"], tmr.inputs["Value"])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    add.use_clamp = True
    nt.links.new(mr.outputs["Result"], add.inputs[0])
    nt.links.new(tmr.outputs["Result"], add.inputs[1])
    nt.links.new(add.outputs["Value"], b.inputs["Roughness"])
    gb = nt.nodes.new("ShaderNodeBump")
    gb.inputs["Strength"].default_value = 0.07
    gb.inputs["Distance"].default_value = ctx.length(0.004)
    nt.links.new(grain.outputs["Fac"], gb.inputs["Height"])
    # _wavy_scratches builds wav -> scr -> Normal and does NOT preserve an
    # existing link, so it goes first and the grain is chained onto the HEAD of
    # its chain. Wiring gb into the tail instead silently drops the waviness.
    _wavy_scratches(nt, b, wav_scale=0.653, wav_strength=0.016, scr_strength=0.010, ctx=ctx)
    scr = b.inputs["Normal"].links[0].from_node
    wav = scr.inputs["Normal"].links[0].from_node
    nt.links.new(gb.outputs["Normal"], wav.inputs["Normal"])
    sheet_ripple(nt, b, ctx=ctx)            # the rolled sheet's slow waves (p134)
    return m


@material("copper", family="metal", finish="mirror", solid=False, tier="warm",
          origin="matlib.mat_copper")
def mat_copper(*, ctx=DEFAULT_CTX):
    """Polished copper: the warmest metal in the bin, and the only one whose
    reflection tints the room pink."""
    return _warm_metal("copper", (0.72, 0.35, 0.22), 0.10, 0.22, ctx=ctx)


@material("gold", family="metal", finish="mirror", solid=False, tier="warm",
          origin="matlib.mat_gold")
def mat_gold(*, ctx=DEFAULT_CTX):
    """Polished gold: softer and rounder than brass — lower roughness spread,
    so the highlight stays whole instead of breaking up."""
    return _warm_metal("gold", (0.86, 0.66, 0.26), 0.07, 0.15, scale=140.0, ctx=ctx)


_VERDIGRIS = dict(family="metal", solid=False, origin="matlib.mat_verdigris")


@material("verdigris", finish="matte", scalar="oxidization", **_VERDIGRIS)
@material("verdigris-exposed", finish="satin",
          params={"oxidization": 0.30, "name": "verdigris_exposed"}, **_VERDIGRIS)
@material("verdigris-weathered", finish="matte",
          params={"oxidization": 0.65, "name": "verdigris_weathered"}, **_VERDIGRIS)
@material("verdigris-full", finish="matte",
          params={"oxidization": 1.0, "name": "verdigris_full"}, **_VERDIGRIS)
def mat_verdigris(oxidization=0.95, name="verdigris", *, ctx=DEFAULT_CTX):
    """Oxidised copper, on a 0..1 AGEING AXIS.

        0.00  bare polished copper, no crust at all
        0.30  exposed — the metal dulls, the first dark films appear
        0.65  weathered — patchy crust, plenty of copper still showing
        0.95  the reference plate (refs/verdigris.png): crust dominant,
              copper torn through as the minority
        1.00  fully oxidised, crust wall to wall

    Two BSDFs through a Mix Shader: bare metal on the proud, a matte
    non-metallic carbonate crust elsewhere. The patina is DIELECTRIC — that is
    the whole difference between verdigris and a green metal, and the reason it
    kills the reflection wherever it sits.

    `oxidization` drives four things at once, because real ageing does: how
    much of the plate the crust covers, how THICK it is (early patina is a
    film, late patina is a crust you could scrape), how far the exposed copper
    has dulled, and how far the crust has travelled from dark brown-teal toward
    chalky turquoise."""
    ox = min(max(oxidization, 0.0), 1.0)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    out = nt.nodes["Material Output"]
    metal = nt.nodes["Principled BSDF"]
    # BRIGHT polished copper, not aged brown: in the reference the exposed
    # metal is the brightest thing on the plate, pink-orange and near-specular,
    # and that contrast against the crust is half the material.
    # The metal dulls FIRST — that is what "exposed" means, before any crust
    # is visible at all — so the copper's ageing is front-loaded against the
    # coverage sweep rather than tracking it linearly.
    dull = ox ** 0.5
    metal.inputs["Base Color"].default_value = (
        *_lerp3((0.82, 0.46, 0.29), (0.52, 0.24, 0.14), dull), 1)
    metal.inputs["Metallic"].default_value = 1.0
    metal.inputs["Roughness"].default_value = 0.14 + 0.30 * dull

    # WHERE the crust sits: big irregular continents with torn coastlines and
    # bare copper veins running between them. Warping the lookup is what gives
    # the coastline its ragged, eaten-away edge.
    pn = nt.nodes.new("ShaderNodeTexNoise")
    pn.inputs["Scale"].default_value = 3.2
    pn.inputs["Detail"].default_value = 9.0
    pn.inputs["Roughness"].default_value = 0.70
    nt.links.new(_warp(nt, _obj_vec(nt, ctx.freq((1.0, 0.55, 1.0))), 0.55, 9.0),
                 pn.inputs["Vector"])
    mask = nt.nodes.new("ShaderNodeMapRange")
    # The reference plate is 86% crust: copper is the MINORITY, showing through
    # as veins and torn patches; near 50/50 reads as salmon camouflage.
    # Mix Shader Fac 0 -> patina, 1 -> metal, so a HIGHER window means MORE
    # crust: only noise above it stays exposed copper. Moving the window down
    # does the opposite of what it looks like it should.
    #
    # The curve is calibrated so ox=0.95 reproduces the ratified plate exactly
    # (centre 0.64) and only the last 5% closes the remaining copper — ageing
    # is not linear at the end, the last bare metal goes quickly.
    # The driving noise lives in roughly 0.30..0.75, so a window below that is
    # simply "all metal" and the axis does nothing for its first half. Start the
    # sweep just under the noise floor instead, and reserve the last 5% for
    # closing the final bare patches — ageing is not linear at the end.
    centre = 0.28 + 0.379 * ox if ox <= 0.95 else 0.64 + (ox - 0.95) * 3.2
    mask.inputs["From Min"].default_value = centre - 0.06
    mask.inputs["From Max"].default_value = centre + 0.06   # torn, not feathered
    nt.links.new(pn.outputs["Fac"], mask.inputs["Value"])

    pat = nt.nodes.new("ShaderNodeBsdfPrincipled")
    pat.inputs["Metallic"].default_value = 0.0
    pat.inputs["Roughness"].default_value = 0.86
    pat.inputs["Diffuse Roughness"].default_value = 0.7
    pat.inputs["Specular IOR Level"].default_value = 0.28

    # THE CRUST IS GRANULAR — a dense field of tiny crystals, like coarse sugar
    # stuck to the plate. That granularity is the whole read; a smooth patina
    # reads as paint. Warped Voronoi so the crystals are irregular, not cells.
    gv = nt.nodes.new("ShaderNodeTexVoronoi")
    gv.feature = "F1"
    gv.inputs["Scale"].default_value = 42.0
    gv.inputs["Randomness"].default_value = 1.0
    nt.links.new(_warp(nt, _obj_vec(nt, ctx.freq((1.0, 1.0, 1.0))), 0.45, 40.0),
                 gv.inputs["Vector"])
    gfine = nt.nodes.new("ShaderNodeTexVoronoi")
    gfine.feature = "F1"
    gfine.inputs["Scale"].default_value = 115.0
    gfine.inputs["Randomness"].default_value = 1.0
    nt.links.new(_warp(nt, _obj_vec(nt, ctx.freq((1.0, 1.0, 1.0))), 0.3, 90.0),
                 gfine.inputs["Vector"])

    # TURQUOISE, not green: measured off refs/verdigris.png, 86% of the plate
    # falls in hue 180-210deg, lit around sRGB (127,175,186).
    # ORDER MATTERS AND IT IS EASY TO GET BACKWARDS: Voronoi F1 Distance is
    # ZERO at a feature point and grows toward the cell edge, so position 0 is
    # a crystal CROWN and the high end is the crevice between crystals. Running
    # it the other way lights the pits and shades the tops, which reads as a
    # flat, washed mint. Bright crown -> body -> near-black pit is what makes
    # the crust read as GRANULAR.
    pramp = nt.nodes.new("ShaderNodeValToRGB")
    young = min(1.0, ox / 0.9)                       # how far the colour has run
    pramp.color_ramp.elements[0].color = (
        *_lerp3((0.20, 0.26, 0.24), (0.52, 0.82, 0.82), young), 1)   # crystal crown
    pramp.color_ramp.elements[1].color = (
        *_lerp3((0.075, 0.135, 0.130), (0.200, 0.560, 0.605), young), 1)
    pramp.color_ramp.elements[1].position = 0.46
    pit = pramp.color_ramp.elements.new(0.86)
    pit.color = (0.020, 0.090, 0.100, 1)                            # wet, dark pit
    nt.links.new(gv.outputs["Distance"], pramp.inputs["Fac"])
    # broad tonal drift across the continents, so the crust is not one tone
    drift = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), drift.inputs["Vector"])
    drift.inputs["Scale"].default_value = ctx.freq(2.04)
    drift.inputs["Detail"].default_value = 5.0
    dr = nt.nodes.new("ShaderNodeMapRange")
    dr.inputs["To Min"].default_value = 0.78
    dr.inputs["To Max"].default_value = 1.22
    nt.links.new(drift.outputs["Fac"], dr.inputs["Value"])
    _vx, vf, va, vb2, vres = _mix_rgba(nt, "MULTIPLY")
    vf.default_value = 1.0
    nt.links.new(pramp.outputs["Color"], va)
    nt.links.new(dr.outputs["Result"], vb2)
    nt.links.new(vres, pat.inputs["Base Color"])

    cb = nt.nodes.new("ShaderNodeBump")                 # the crystal granules
    cb.inputs["Strength"].default_value = 1.0
    cb.inputs["Distance"].default_value = ctx.length(0.060 * (0.25 + 0.75 * ox))
    nt.links.new(gv.outputs["Distance"], cb.inputs["Height"])
    cbf = nt.nodes.new("ShaderNodeBump")                # finer crystal dust
    cbf.inputs["Strength"].default_value = 0.6
    cbf.inputs["Distance"].default_value = ctx.length(0.020 * (0.25 + 0.75 * ox))
    nt.links.new(gfine.outputs["Distance"], cbf.inputs["Height"])
    nt.links.new(cb.outputs["Normal"], cbf.inputs["Normal"])
    clump = nt.nodes.new("ShaderNodeTexVoronoi")        # crystals grow in MASSES
    clump.feature = "F1"
    clump.inputs["Scale"].default_value = 14.0
    clump.inputs["Randomness"].default_value = 1.0
    nt.links.new(_warp(nt, _obj_vec(nt, ctx.freq((1.0, 1.0, 1.0))), 0.6, 10.0),
                 clump.inputs["Vector"])
    clb = nt.nodes.new("ShaderNodeBump")
    clb.inputs["Strength"].default_value = 0.7
    clb.inputs["Distance"].default_value = ctx.length(0.085 * (0.15 + 0.85 * ox))
    nt.links.new(clump.outputs["Distance"], clb.inputs["Height"])
    nt.links.new(cbf.outputs["Normal"], clb.inputs["Normal"])
    cb2 = nt.nodes.new("ShaderNodeBump")                # the crust's own thickness
    cb2.inputs["Strength"].default_value = 0.5
    cb2.inputs["Distance"].default_value = ctx.length(0.045 * (0.2 + 0.8 * ox))
    nt.links.new(pn.outputs["Fac"], cb2.inputs["Height"])
    nt.links.new(clb.outputs["Normal"], cb2.inputs["Normal"])
    nt.links.new(cb2.outputs["Normal"], pat.inputs["Normal"])

    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(mask.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(pat.outputs["BSDF"], mix.inputs[1])
    nt.links.new(metal.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return m


_ANODIZED = dict(family="metal", finish="satin", solid=False, origin="matlib.mat_anodized")


@material("anodized-red", **_ANODIZED)
@material("anodized-signal-red", params={"col": (0.50, 0.022, 0.018),
                                         "name": "anodized_signal_red"}, **_ANODIZED)
@material("anodized-blue", params={"col": (0.06, 0.13, 0.36), "name": "anodized_blue"},
          **_ANODIZED)
@material("anodized-black", params={"col": (0.020, 0.020, 0.024), "name": "anodized_black",
                                    "sheen_k": 0.5},
          **_ANODIZED)
def mat_anodized(col=(0.42, 0.08, 0.07), name="anodized", sheen_k=1.0, *, ctx=DEFAULT_CTX):
    """Coloured anodised aluminium: the dye lives INSIDE a transparent oxide
    layer grown on brushed metal, so the brush grain reads straight through the
    colour. Metallic with a tinted base and a hard coat, grain in roughness."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Coat Weight"].default_value = 0.28        # the oxide
    b.inputs["Coat Roughness"].default_value = 0.34     # a crisp coat hides the brush
    b.inputs["Anisotropic"].default_value = 0.8
    nt.links.new(tangent.linear(nt, "X"), b.inputs["Tangent"])
    grain = nt.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Detail"].default_value = 3.0
    grain.inputs["Roughness"].default_value = 0.7
    nt.links.new(_obj_vec(nt, ctx.freq((4.0, 90.0, 1.0))), grain.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.14
    mr.inputs["To Max"].default_value = 0.46      # wide: the brush must SHOW
    nt.links.new(grain.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    gb = nt.nodes.new("ShaderNodeBump")
    gb.inputs["Strength"].default_value = 0.10
    gb.inputs["Distance"].default_value = ctx.length(0.006)
    nt.links.new(grain.outputs["Fac"], gb.inputs["Height"])
    nt.links.new(gb.outputs["Normal"], b.inputs["Normal"])
    sheen(b, sheen_k)       # metallic: only the oxide coat scales
    sheet_ripple(nt, b, ctx=ctx)            # the rolled sheet's slow waves (p134)
    return m


_TITANIUM = dict(family="metal", finish="mirror", solid=False, tier="titanium",
                 origin="matlib.mat_titanium")


@material("titanium", **_TITANIUM)
@material("titanium-deep", params={"lo": 140.0, "hi": 380.0, "name": "titanium_deep",
                                   "film": 25.0},
          **_TITANIUM)
def mat_titanium(lo=210.0, hi=620.0, name="titanium", film=0.0, *, ctx=DEFAULT_CTX):
    """Anodised titanium: see _titanium. `film` (nm) adds a finer oxide
    variation over the broad fields."""
    return _titanium(lo, hi, name, film, ctx=ctx)


@material("titanium-heat-tint", family="metal", finish="mirror", solid=False, tier="titanium",
          origin="knob-chrome heat tint (pass 44, p136-p142)")
def mat_titanium_heat_tint(*, ctx=DEFAULT_CTX):
    """Torch-coloured titanium on knob-chrome's dome: the oxide grows with the
    heat, so the colours run in rings from where the flame sat — yellow at the
    rim, a wide violet band, a teal heart (one hue cycle, 200-285 nm) — the
    rings wandering on a slow noise, and a second, hotter touch on the
    indicator dimple (the next colour order, a green-gold halo) so the value
    reads through the colour. Laid out in knob-chrome's object space: dome
    radius 1.0, dimple at 0.62 / 225 deg. Every value is Sam's pick on
    p136-p142; none is exposed."""
    return _titanium(200.0, 285.0, "titanium_heat_tint", 0.0, radial=0.9, radial_r=1.0,
                     radial_warp=0.7, radial_curve=0.7, spot=1.8, spot_x=-0.438,
                     spot_y=-0.438, spot_r=0.4, ctx=ctx)


def _titanium(lo, hi, name, film, radial=0.0, radial_r=0.55, radial_warp=0.0,
              radial_curve=1.0, spot=0.0, spot_x=0.0, spot_y=0.0, spot_r=0.3, *,
              ctx=DEFAULT_CTX):
    """Anodised titanium — the rainbow. NOT a painted gradient: the colour is
    real THIN-FILM INTERFERENCE, which is what anodising titanium actually
    does. Growing the oxide thicker shifts the reflected hue through bronze,
    violet, blue, cyan, gold, so driving Principled's Thin Film Thickness with
    a noise field (nm, `lo`..`hi`) reproduces the whole sequence for free and
    in the right ORDER — no ramp of invented colours could land that. First-
    order fringes are the saturated ones; past ~700 nm the orders overlap and
    wash to pale pink.

    IT IS A MIRROR. All three references (refs/titanium*.{png,jpeg}) are
    polished to near-chrome and carry BROAD, SMOOTH colour fields — the Zippo
    measures saturation 0.76 / value 220 across huge magenta and cyan zones.
    Brushed satin under fine mottled noise reads as pale camouflage: brushing
    scatters the very reflection the interference lives in, and high-frequency
    thickness noise dices the colour fields into confetti. So: low roughness,
    no brush, and a thickness field measured in whole panels.
    `brass`/`copper`/`gold`/`titanium` all take the glossy room in panel-board
    for the same reason."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.62, 0.61, 0.60, 1)   # titanium
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Thin Film IOR"].default_value = 2.55                 # TiO2
    b.inputs["Roughness"].default_value = 0.10                     # polished
    # oxide thickness: two BROAD fields, the way a torch lays heat on — one
    # sweeping gradient plus a slower swirl, no fine detail anywhere.
    th = nt.nodes.new("ShaderNodeTexNoise")
    th.inputs["Scale"].default_value = 1.15
    th.inputs["Detail"].default_value = 2.0
    th.inputs["Roughness"].default_value = 0.40
    th.inputs["Distortion"].default_value = 0.5
    nt.links.new(_obj_vec(nt, ctx.freq((1.0, 1.5, 1.0)), 0.5), th.inputs["Vector"])
    sweep = nt.nodes.new("ShaderNodeTexNoise")
    sweep.inputs["Scale"].default_value = 0.55
    sweep.inputs["Detail"].default_value = 1.0
    nt.links.new(_obj_vec(nt, ctx.freq((1.0, 0.7, 1.0)), -0.4), sweep.inputs["Vector"])
    blend = nt.nodes.new("ShaderNodeMath")
    blend.operation = "MULTIPLY_ADD"
    blend.inputs[1].default_value = 0.65
    blend.inputs[2].default_value = 0.0
    nt.links.new(th.outputs["Fac"], blend.inputs[0])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(blend.outputs["Value"], add.inputs[0])
    swm = nt.nodes.new("ShaderNodeMath")
    swm.operation = "MULTIPLY"
    swm.inputs[1].default_value = 0.35
    nt.links.new(sweep.outputs["Fac"], swm.inputs[0])
    nt.links.new(swm.outputs["Value"], add.inputs[1])
    field = add.outputs["Value"]
    if radial > 0:
        # torch-coloured titanium: the oxide grows with the heat, which falls
        # off from where the flame sat, so the colours run in rings from the
        # centre out (a knob's heat-tint rainbow). `radial` blends the rings
        # (1 at the centre -> 0 at `radial_r` object units) into the fields.
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Object"], sep.inputs[0])
        vec = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(sep.outputs["X"], vec.inputs["X"])
        nt.links.new(sep.outputs["Y"], vec.inputs["Y"])
        ln = nt.nodes.new("ShaderNodeVectorMath")
        ln.operation = "LENGTH"
        nt.links.new(vec.outputs[0], ln.inputs[0])
        r = ln.outputs["Value"]
        if radial_warp > 0:
            # a flame never lays heat evenly: the rings wander (+-radial_warp
            # object units on the radius, a slow noise)
            wn = nt.nodes.new("ShaderNodeTexNoise")
            wn.inputs["Scale"].default_value = 1.0     # the Mapping carries the frequency
            wn.inputs["Detail"].default_value = 3.0
            wn.inputs["Distortion"].default_value = 0.6
            nt.links.new(_obj_vec(nt, ctx.freq((1.5, 1.5, 1.5))), wn.inputs["Vector"])
            wm = nt.nodes.new("ShaderNodeMapRange")
            wm.inputs["To Min"].default_value = -radial_warp
            wm.inputs["To Max"].default_value = radial_warp
            nt.links.new(wn.outputs["Fac"], wm.inputs["Value"])
            wa = nt.nodes.new("ShaderNodeMath")
            wa.operation = "ADD"
            nt.links.new(r, wa.inputs[0])
            nt.links.new(wm.outputs["Result"], wa.inputs[1])
            r = wa.outputs["Value"]
        rr = nt.nodes.new("ShaderNodeMapRange")
        rr.inputs["From Min"].default_value = 0.0
        rr.inputs["From Max"].default_value = radial_r
        rr.inputs["To Min"].default_value = 1.0
        rr.inputs["To Max"].default_value = 0.0
        nt.links.new(r, rr.inputs["Value"])
        ring = rr.outputs["Result"]
        if radial_curve != 1.0:
            # < 1 holds the inner colours out toward the rim, the rim's own
            # colour squeezed into a thin band at radial_r
            pw = nt.nodes.new("ShaderNodeMath")
            pw.operation = "POWER"
            pw.use_clamp = True
            pw.inputs[1].default_value = radial_curve
            nt.links.new(ring, pw.inputs[0])
            ring = pw.outputs["Value"]
        if spot > 0:
            # a second, smaller torch touch at (spot_x, spot_y): its own rings,
            # hotter wins — on a knob, centred on the indicator so the value
            # reads through the colour (it turns with the part)
            off = nt.nodes.new("ShaderNodeVectorMath")
            off.operation = "SUBTRACT"
            nt.links.new(vec.outputs[0], off.inputs[0])
            off.inputs[1].default_value = (spot_x, spot_y, 0.0)
            sd = nt.nodes.new("ShaderNodeVectorMath")
            sd.operation = "LENGTH"
            nt.links.new(off.outputs[0], sd.inputs[0])
            sr = nt.nodes.new("ShaderNodeMapRange")
            sr.inputs["From Min"].default_value = 0.0
            sr.inputs["From Max"].default_value = spot_r
            sr.inputs["To Min"].default_value = spot
            sr.inputs["To Max"].default_value = 0.0
            nt.links.new(sd.outputs["Value"], sr.inputs["Value"])
            hot = nt.nodes.new("ShaderNodeMath")
            hot.operation = "MAXIMUM"
            nt.links.new(ring, hot.inputs[0])
            nt.links.new(sr.outputs["Result"], hot.inputs[1])
            ring = hot.outputs["Value"]
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "FLOAT"
        mix.inputs["Factor"].default_value = radial
        nt.links.new(field, mix.inputs["A"])
        nt.links.new(ring, mix.inputs["B"])
        field = mix.outputs["Result"]
    tmr = nt.nodes.new("ShaderNodeMapRange")
    tmr.clamp = spot <= 1.0          # a spot hotter than the rings runs past hi
    tmr.inputs["To Min"].default_value = lo
    tmr.inputs["To Max"].default_value = hi
    nt.links.new(field, tmr.inputs["Value"])
    thick = tmr.outputs["Result"]
    if film > 0:
        # a finer oxide variation on top of the broad fields (+-film nm): the
        # colour shimmers across a panel instead of sitting in flat zones
        fn = nt.nodes.new("ShaderNodeTexNoise")
        fn.inputs["Scale"].default_value = 1.0     # the Mapping carries the frequency
        fn.inputs["Detail"].default_value = 2.0
        nt.links.new(_obj_vec(nt, ctx.freq((5.0, 7.0, 7.0))), fn.inputs["Vector"])
        fm = nt.nodes.new("ShaderNodeMapRange")
        fm.inputs["To Min"].default_value = -film
        fm.inputs["To Max"].default_value = film
        nt.links.new(fn.outputs["Fac"], fm.inputs["Value"])
        fa = nt.nodes.new("ShaderNodeMath")
        fa.operation = "ADD"
        nt.links.new(thick, fa.inputs[0])
        nt.links.new(fm.outputs["Result"], fa.inputs[1])
        thick = fa.outputs["Value"]
    nt.links.new(thick, b.inputs["Thin Film Thickness"])
    # polish is never perfect, but it stays far below the colour fields
    _wavy_scratches(nt, b, wav_scale=0.612, wav_strength=0.012, scr_strength=0.006, ctx=ctx)
    rn = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), rn.inputs["Vector"])
    rn.inputs["Scale"].default_value = ctx.freq(24.5)
    rmr = nt.nodes.new("ShaderNodeMapRange")
    rmr.inputs["To Min"].default_value = 0.075
    rmr.inputs["To Max"].default_value = 0.130
    nt.links.new(rn.outputs["Fac"], rmr.inputs["Value"])
    nt.links.new(rmr.outputs["Result"], b.inputs["Roughness"])
    return m


@material("steel-hw", family="metal", finish="satin", solid=True,
          origin="matlib.steel_hw")
def steel_hw(*, ctx=DEFAULT_CTX):
    """Bright brushed-steel fastener: rough enough to READ on dark panels — a
    mirror finish reflects the dark void and vanishes."""
    m, nt, b = base_material("steel_hw")
    b.inputs["Base Color"].default_value = (0.62, 0.63, 0.64, 1)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.30
    imperfect(m, 0.24, 0.38, bump_strength=0.01, scale=2730.0, ctx=ctx)
    return m
