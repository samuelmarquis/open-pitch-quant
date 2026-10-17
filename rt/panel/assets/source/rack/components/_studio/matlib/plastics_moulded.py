"""Plastic family, moulded thermoplastics: injection-moulded ABS, nylon, POM and
acetal bodies — knob bodies, button caps and bodies, connector and gland
mouldings, insulators.

`imperfect()` routes through the core calibration (25 mm/unit); builders
calibrated elsewhere hand it `_imp_ctx(ctx, calib)`, which is `ctx` itself at
25 and gives the same factors as `ctx` at `calib`.

Calibration per origin component: units.MM_PER_UNIT.
"""
from .core import (CALIB_MM_PER_UNIT, DEFAULT_CTX, MaterialContext, _obj_pos, base_material,
                   imperfect, material, sheen)
from .units import mm_per_unit

BOSS_MM = mm_per_unit("knob-boss")
DAVIES_MM = mm_per_unit("knob-davies")
JACK_MM = mm_per_unit("jack-socket")
BEZEL_MM = mm_per_unit("button-bezel")
CONDUIT_MM = mm_per_unit("conduit-corrugated")
RIBBON_MM = mm_per_unit("conduit-ribbon")
CONSOLE_MM = mm_per_unit("button-console")
FADER_MM = mm_per_unit("fader-desk")


def _imp_ctx(ctx, calib):
    """The context `imperfect()` (calibrated at 25) needs so its constants
    scale as if calibrated at `calib`."""
    if calib == CALIB_MM_PER_UNIT:
        return ctx
    return MaterialContext(CALIB_MM_PER_UNIT * (ctx.mm_per_unit / calib))


def _set(b, socket, value):
    if socket in b.inputs:
        b.inputs[socket].default_value = value


# ---------------------------------------------------------------------------
# conduit terminal mouldings


def _moulded_terminal(name, base, sss_weight, sss_radius, sss_scale, coat, coat_rough,
                      specular, rough_lo, rough_hi, sink, ctx, calib, freq):
    """`freq`: (sink marks, tool grain) in cycles per world unit at `calib`."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Subsurface Weight"].default_value = sss_weight
    b.inputs["Subsurface Radius"].default_value = sss_radius
    b.inputs["Subsurface Scale"].default_value = ctx.length(sss_scale, calib)
    b.inputs["Coat Weight"].default_value = coat
    if coat_rough is not None:
        _set(b, "Coat Roughness", coat_rough)
    _set(b, "Specular IOR Level", specular)
    sk = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), sk.inputs["Vector"])
    sk.inputs["Scale"].default_value = ctx.freq(freq[0], calib)
    sk.inputs["Detail"].default_value = 4.0
    skb = nt.nodes.new("ShaderNodeBump")
    skb.inputs["Strength"].default_value = sink
    skb.inputs["Distance"].default_value = ctx.length(0.006, calib)
    nt.links.new(sk.outputs["Fac"], skb.inputs["Height"])
    nt.links.new(skb.outputs["Normal"], b.inputs["Normal"])
    imperfect(m, rough_lo, rough_hi, bump_strength=0.03, scale=freq[1],
              ctx=_imp_ctx(ctx, calib))
    return m


_WHITE_TERMINAL = {"name": "terminal_white", "base": (0.74, 0.735, 0.71),
                   "sss_weight": 0.55, "sss_radius": (1.0, 0.92, 0.80), "coat": 0.05,
                   "coat_rough": 0.35, "specular": 0.40, "rough_lo": 0.40,
                   "rough_hi": 0.54, "sink": 0.07}
_TERMINAL = dict(family="plastic", solid=True)


@material("abs-black", finish="matte", calib_mm_per_unit=CONDUIT_MM,
          origin="conduit-corrugated:terminal_black:1329", **_TERMINAL)
@material("pom-white", finish="satin", params={**_WHITE_TERMINAL, "sss_scale": 0.32 * 0.16},
          calib_mm_per_unit=CONDUIT_MM, origin="conduit-corrugated:terminal_white:1329",
          **_TERMINAL)
def mat_moulded_terminal(name="terminal_black", base=(0.030, 0.030, 0.034), sss_weight=0.30,
                         sss_radius=(0.55, 0.52, 0.58), sss_scale=0.11 * 0.16, coat=0.0,
                         coat_rough=None, specular=0.30, rough_lo=0.46, rough_hi=0.60,
                         sink=0.05, *, ctx=DEFAULT_CTX):
    """Moulded gland body: random-walk scatter pulled out of the gloss register,
    roughness around 0.5, the form carried by moulding relief (broad sink marks
    at 5 per unit, then imperfect()'s fine tool grain at 499 chained on that
    normal) instead of by a highlight.

    `abs-black`: carbon-black ABS — no coat, a short scatter whose albedo is the
    near-black base, so it softens the terminator without greying the body.
    `pom-white`: nylon / POM — genuinely translucent, thin flange rims glow
    through, a trace of coat.

    `sss_scale` is a length at the calibration unit; the canon values are
    0.11 x / 0.32 x the conduit's tube radius 0.16. `coat_rough` None leaves
    the node default. conduit-smooth:terminal_black/terminal_white:1531 build
    the identical graphs at the same radius.
    Duplicate candidate: abs-black-fine, pom-white-fine; white-plastic."""
    return _moulded_terminal(name, base, sss_weight, sss_radius, sss_scale, coat, coat_rough,
                             specular, rough_lo, rough_hi, sink, ctx, CONDUIT_MM, (4.99, 499.0))


@material("abs-black-fine", finish="matte", calib_mm_per_unit=RIBBON_MM,
          origin="conduit-ribbon:terminal_plastic:1159", **_TERMINAL)
@material("pom-white-fine", finish="satin", params={**_WHITE_TERMINAL, "sss_scale": 0.85 * 0.06},
          calib_mm_per_unit=RIBBON_MM, origin="conduit-ribbon:terminal_plastic:1159",
          **_TERMINAL)
def mat_moulded_terminal_fine(name="terminal_black", base=(0.030, 0.030, 0.034),
                              sss_weight=0.30, sss_radius=(0.55, 0.52, 0.58),
                              sss_scale=0.30 * 0.06, coat=0.0, coat_rough=None,
                              specular=0.30, rough_lo=0.46, rough_hi=0.60, sink=0.05,
                              *, ctx=DEFAULT_CTX):
    """The conduit terminal moulding recipe (see `abs-black` / `pom-white`)
    calibrated on an IDC ribbon connector body (sink marks 3.7 per unit, tool
    grain 370, at conduit-ribbon's unit). `sss_scale` canon values are 0.30 x /
    0.85 x the ribbon's insulation radius 0.06.
    Duplicate candidate: abs-black, pom-white."""
    return _moulded_terminal(name, base, sss_weight, sss_radius, sss_scale, coat, coat_rough,
                             specular, rough_lo, rough_hi, sink, ctx, RIBBON_MM, (3.70, 370.0))


# ---------------------------------------------------------------------------
# knob bodies


_MOULDED_BLACK = dict(family="plastic", solid=True, calib_mm_per_unit=BOSS_MM)


@material("moulded-black-satin", finish="satin", params={"sheen_k": 0.25},
          origin="knob-boss:black_material:271", **_MOULDED_BLACK)
@material("moulded-black-matte", finish="matte",
          params={"rough_lo": 0.38, "rough_hi": 0.52, "coat": 0.08, "grain": 90.6},
          origin="knob-led:black_material:155", **_MOULDED_BLACK)
def mat_moulded_black(rough_lo=0.19, rough_hi=0.31, coat=0.24, grain=126.0,
                      name="moulded black", sheen_k=1.0, *, ctx=DEFAULT_CTX):
    """Moulded black knob plastic: near-black base under a thin clearcoat
    (roughness 0.16), fine mottled roughness and micro-bump from imperfect() at
    `grain`.
    `moulded-black-satin` is knob-boss's body; `moulded-black-matte` is
    knob-led's, and knob-heady:black_material:275 builds the identical graph.
    Duplicate candidate: abs-black-sink, moulded-black-flat, sleek-black."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.006, 0.007, 0.008, 1)
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.16
    sheen(b, sheen_k)
    return imperfect(m, rough_lo, rough_hi, bump_strength=0.010, scale=grain, ctx=ctx)


@material("abs-black-sink", family="plastic", finish="satin", solid=True,
          calib_mm_per_unit=DAVIES_MM, origin="knob-davies:moulded_black:329")
def mat_abs_black_sink(name="moulded black ABS", *, ctx=DEFAULT_CTX):
    """Flat black moulded ABS: no coat, slow mould-sink / flow waviness
    (Object-space noise, scale 7) under imperfect()'s fine mottling.
    Duplicate candidate: moulded-black-satin."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.021, 0.021, 0.023, 1)
    b.inputs["Coat Weight"].default_value = 0.0
    b.inputs["Coat Roughness"].default_value = 0.11
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sink = nt.nodes.new("ShaderNodeTexNoise")
    sink.inputs["Scale"].default_value = ctx.freq(7.0)
    sink.inputs["Detail"].default_value = 2.0
    nt.links.new(coord.outputs["Object"], sink.inputs["Vector"])
    sink_bump = nt.nodes.new("ShaderNodeBump")
    sink_bump.inputs["Strength"].default_value = 0.045
    sink_bump.inputs["Distance"].default_value = ctx.length(
        sink_bump.inputs["Distance"].default_value)
    nt.links.new(sink.outputs["Fac"], sink_bump.inputs["Height"])
    nt.links.new(sink_bump.outputs["Normal"], b.inputs["Normal"])
    return imperfect(m, 0.13, 0.24, bump_strength=0.014, scale=60.4, ctx=ctx)


# ---------------------------------------------------------------------------
# button bodies and caps


@material("moulded-black-flat", family="plastic", finish="matte", solid=True,
          calib_mm_per_unit=BEZEL_MM, params={"sheen_k": 0.25},
          origin="button-bezel:matte black moulded plastic:205")
def mat_moulded_black_flat(name="matte black moulded plastic", sheen_k=1.0, *,
                           ctx=DEFAULT_CTX):
    """Dead-matte near-black moulding: specular 0.18, no coat, roughness
    0.62-0.78. Duplicate candidate: moulded-black-matte."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.004, 0.005, 0.006, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.18
    b.inputs["Coat Weight"].default_value = 0.0
    sheen(b, sheen_k)
    imperfect(m, 0.62, 0.78, bump_strength=0.018, scale=147.0, ctx=_imp_ctx(ctx, BEZEL_MM))
    return m


@material("moulded-satin", family="plastic", finish="satin", solid=True,
          calib_mm_per_unit=BEZEL_MM, origin="button-bezel:custom button body:222")
def mat_moulded_satin(color=(36 / 255.0, 40 / 255.0, 45 / 255.0), name="custom button body",
                      *, ctx=DEFAULT_CTX):
    """Pigmented satin moulding in any colour: coat 0.18 at roughness 0.28 over
    a 0.34-0.48 body. `color` is the linear base colour the component supplies
    (button-bezel's default 24282d read as linear)."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.18
    b.inputs["Coat Roughness"].default_value = 0.28
    imperfect(m, 0.34, 0.48, bump_strength=0.014, scale=125.0, ctx=_imp_ctx(ctx, BEZEL_MM))
    return m


_GLOSS_CAP = dict(family="plastic", finish="satin", solid=True,
                  calib_mm_per_unit=CONSOLE_MM, origin="button-console:capm:169")


@material("gloss-cap", **_GLOSS_CAP)
@material("gloss-cap-blue", params={"color": (0.015, 0.09, 0.30), "roughness": 0.30},
          **_GLOSS_CAP)
@material("gloss-cap-yellow", params={"color": (0.62, 0.45, 0.015), "roughness": 0.20},
          **_GLOSS_CAP)
@material("gloss-cap-green", params={"color": (0.06, 0.26, 0.04), "roughness": 0.26},
          **_GLOSS_CAP)
@material("gloss-cap-black", params={"color": (0.010, 0.010, 0.012), "roughness": 0.32},
          **_GLOSS_CAP)
@material("gloss-cap-ivory", params={"color": (0.58, 0.52, 0.40), "roughness": 0.34,
                                     "subsurface": 0.35}, **_GLOSS_CAP)
def mat_gloss_cap(color=(0.30, 0.020, 0.012), roughness=0.24, subsurface=0.0, name="capm",
                  *, ctx=DEFAULT_CTX):
    """Pigmented moulded cap under a 0.35 clearcoat, flat roughness, no
    relief. `subsurface` > 0 adds the ivory scatter (radius 0.9/0.8/0.6, scale
    0.03). fader-desk:plastic(spec):250 builds the identical graphs for its red,
    blue, yellow, green and ivory caps. Duplicate candidate: metalflake-cap,
    bakelite-solid."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.35
    if subsurface > 0:
        b.inputs["Subsurface Weight"].default_value = subsurface
        b.inputs["Subsurface Radius"].default_value = (0.9, 0.8, 0.6)
        b.inputs["Subsurface Scale"].default_value = ctx.length(0.03, CONSOLE_MM)
    return m


@material("metalflake-cap", family="plastic", finish="gloss", solid=True,
          calib_mm_per_unit=FADER_MM, origin="fader-desk:plastic(spec):250")
def mat_metalflake_cap(color=(0.010, 0.010, 0.012), roughness=0.38, name="plastic",
                       *, ctx=DEFAULT_CTX):
    """Black metal-flake cap plastic: coat 0.9 over a 0.75-metallic body whose
    roughness drops to 0.02 on sparse Voronoi flakes (1930 per unit, ramp
    0.085-0.13), with a white-noise glint bump.
    Duplicate candidate: gloss-cap-black."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Coat Weight"].default_value = 0.9
    b.inputs["Metallic"].default_value = 0.75
    pos = _obj_pos(nt)
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    nt.links.new(pos, vor.inputs["Vector"])
    vor.inputs["Scale"].default_value = ctx.freq(1930.0, FADER_MM)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.085
    ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
    ramp.color_ramp.elements[1].position = 0.13
    ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
    nt.links.new(vor.outputs["Distance"], ramp.inputs["Fac"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = roughness
    mr.inputs["To Max"].default_value = 0.02
    nt.links.new(ramp.outputs["Color"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    wnz = nt.nodes.new("ShaderNodeTexWhiteNoise")
    wnz.noise_dimensions = "3D"
    nt.links.new(pos, wnz.inputs["Vector"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.10
    bmp.inputs["Distance"].default_value = ctx.length(bmp.inputs["Distance"].default_value,
                                                      FADER_MM)
    nt.links.new(wnz.outputs["Value"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


@material("acetal-black", family="plastic", finish="satin", solid=True,
          calib_mm_per_unit=FADER_MM, origin="fader-desk:stemm:350")
def mat_acetal_black(name="stemm", *, ctx=DEFAULT_CTX):
    """Dark acetal stem stock: flat near-black at roughness 0.5, no relief."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.02, 0.02, 0.022, 1)
    b.inputs["Roughness"].default_value = 0.5
    b.inputs["Metallic"].default_value = 0.0
    return m


# ---------------------------------------------------------------------------
# connector mouldings


_NYLON = dict(family="plastic", finish="satin", solid=True, calib_mm_per_unit=JACK_MM,
              origin="jack-socket:mat_insulator:198")


@material("pigmented-nylon", **_NYLON)
@material("pigmented-nylon-black", params={"color": (0.014, 0.014, 0.016)}, **_NYLON)
def mat_pigmented_nylon(color=(0.26, 0.014, 0.010), name="insulator", *, ctx=DEFAULT_CTX):
    """Banana-socket insulator: saturated pigment through the body, a satin
    moulding coat (0.18 at 0.40), and a hair of subsurface (0.16, radius
    0.7/0.35/0.30, scale 0.02) so the colour has depth."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.18
    b.inputs["Coat Roughness"].default_value = 0.40
    b.inputs["Subsurface Weight"].default_value = 0.16
    b.inputs["Subsurface Radius"].default_value = (0.7, 0.35, 0.30)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.02)
    imperfect(m, 0.30, 0.44, bump_strength=0.014, scale=600.0, ctx=ctx)
    return m


@material("glass-filled-nylon", family="plastic", finish="matte", solid=True,
          calib_mm_per_unit=JACK_MM, origin="jack-socket:mat_insert:231")
def mat_glass_filled_nylon(name="xlr_insert", *, ctx=DEFAULT_CTX):
    """Glass-filled nylon (an XLR insert): matte, faintly speckled by the fill
    (Smooth-F1 Voronoi at 423 per unit into a 0.002 bump), deliberately no
    clearcoat — a coat on a flat disc facing the camera mirrors the softbox as
    a hard line. Duplicate candidate: epoxy-package."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.016, 0.016, 0.018, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.32
    fill = nt.nodes.new("ShaderNodeTexVoronoi")
    fill.feature = "SMOOTH_F1"
    nt.links.new(_obj_pos(nt), fill.inputs["Vector"])
    fill.inputs["Scale"].default_value = ctx.freq(423.0)
    fb = nt.nodes.new("ShaderNodeBump")
    fb.inputs["Strength"].default_value = 0.05
    fb.inputs["Distance"].default_value = ctx.length(0.002)
    nt.links.new(fill.outputs["Distance"], fb.inputs["Height"])
    nt.links.new(fb.outputs["Normal"], b.inputs["Normal"])
    imperfect(m, 0.55, 0.68, bump_strength=0.014, scale=278.0, ctx=ctx)
    return m
