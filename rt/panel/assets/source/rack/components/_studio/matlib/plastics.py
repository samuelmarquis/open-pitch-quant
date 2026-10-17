"""Plastic family: moulded thermoplastics, foams and cast phenolic resin."""
from .core import DEFAULT_CTX, _obj_pos, _obj_vec, base_material, imperfect, material, sheen
from .metals import _wavy_scratches


@material("white-plastic", family="plastic", finish="satin", solid=True,
          origin="matlib.mat_white_plastic")
def mat_white_plastic(*, ctx=DEFAULT_CTX):
    """Injection-moulded white ABS: subtle SSS, faint coat, low-freq sink marks."""
    m, nt, b = base_material("white_plastic")
    b.inputs["Base Color"].default_value = (0.74, 0.74, 0.72, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.14
    b.inputs["Subsurface Weight"].default_value = 0.20
    b.inputs["Subsurface Radius"].default_value = (0.6, 0.55, 0.5)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.04)
    sk = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(_obj_pos(nt), sk.inputs["Vector"])
    sk.inputs["Scale"].default_value = ctx.freq(1.43)
    skb = nt.nodes.new("ShaderNodeBump")
    skb.inputs["Strength"].default_value = 0.06
    skb.inputs["Distance"].default_value = ctx.length(skb.inputs["Distance"].default_value)
    nt.links.new(sk.outputs["Fac"], skb.inputs["Height"])
    nt.links.new(skb.outputs["Normal"], b.inputs["Normal"])
    imperfect(m, 0.30, 0.42, bump_strength=0.02, scale=61.2, ctx=ctx)
    return m


def _bead_height(nt, scale, radius=0.62, *, ctx=DEFAULT_CTX):
    """Round, fully-packed beads by sphere-packing: each Voronoi point becomes a
    spherical cap  h = sqrt(R^2 - d^2), d = distance to the nearest point. R is
    big enough that neighbouring caps MEET while each cap stays SPHERICAL (not
    polygonal cells). R is in cell units, not a spatial constant."""
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "F1"
    nt.links.new(_obj_pos(nt), vor.inputs["Vector"])
    vor.inputs["Scale"].default_value = ctx.freq(scale)
    d2 = nt.nodes.new("ShaderNodeMath")
    d2.operation = "POWER"
    d2.inputs[1].default_value = 2.0
    nt.links.new(vor.outputs["Distance"], d2.inputs[0])
    sub = nt.nodes.new("ShaderNodeMath")          # R^2 - d^2
    sub.operation = "SUBTRACT"
    sub.inputs[0].default_value = radius * radius
    nt.links.new(d2.outputs["Value"], sub.inputs[1])
    mx = nt.nodes.new("ShaderNodeMath")           # clamp >= 0 (outside the cap)
    mx.operation = "MAXIMUM"
    mx.inputs[1].default_value = 0.0
    nt.links.new(sub.outputs["Value"], mx.inputs[0])
    h = nt.nodes.new("ShaderNodeMath")            # sqrt -> spherical profile
    h.operation = "SQRT"
    nt.links.new(mx.outputs["Value"], h.inputs[0])
    return h.outputs["Value"]


@material("styrofoam", family="plastic", finish="matte", solid=True,
          origin="matlib.mat_styrofoam")
def mat_styrofoam(*, ctx=DEFAULT_CTX):
    """Expanded polystyrene: fully packed positive bead domes (two scales), SSS,
    dead matte."""
    m, nt, b = base_material("styrofoam")
    b.inputs["Base Color"].default_value = (0.82, 0.82, 0.81, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.86
    b.inputs["Subsurface Weight"].default_value = 0.38
    b.inputs["Subsurface Radius"].default_value = (0.9, 0.88, 0.85)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.05)
    # two bead scales chained as normal detail — Bump chain, not Mix (Mix
    # socket names are inconsistent)
    coarse = _bead_height(nt, 12.2, radius=1.5, ctx=ctx)   # R >> max cell dist -> caps
    fine = _bead_height(nt, 26.9, radius=0.85, ctx=ctx)    # fully overlap, no flat gaps
    b1 = nt.nodes.new("ShaderNodeBump")
    b1.inputs["Strength"].default_value = 0.7
    b1.inputs["Distance"].default_value = ctx.length(0.16)
    nt.links.new(coarse, b1.inputs["Height"])
    b2 = nt.nodes.new("ShaderNodeBump")
    b2.inputs["Strength"].default_value = 0.28
    b2.inputs["Distance"].default_value = ctx.length(0.05)
    nt.links.new(fine, b2.inputs["Height"])
    nt.links.new(b1.outputs["Normal"], b2.inputs["Normal"])
    nt.links.new(b2.outputs["Normal"], b.inputs["Normal"])
    return m


@material("beige-plastic", family="plastic", finish="satin", solid=True,
          origin="matlib.mat_beige_plastic")
def mat_beige_plastic(*, ctx=DEFAULT_CTX):
    """The 90s computer-case beige: warm, slightly yellowed, satin, with the
    characteristic fine leather/pebble grain moulded to hide sink marks."""
    m, nt, b = base_material("beige_plastic")
    b.inputs["Base Color"].default_value = (0.62, 0.55, 0.36, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.18
    b.inputs["Coat Roughness"].default_value = 0.38
    b.inputs["Subsurface Weight"].default_value = 0.14
    b.inputs["Subsurface Radius"].default_value = (0.7, 0.55, 0.4)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.03)
    peb = nt.nodes.new("ShaderNodeTexVoronoi")
    peb.feature = "SMOOTH_F1"
    nt.links.new(_obj_pos(nt), peb.inputs["Vector"])
    peb.inputs["Scale"].default_value = ctx.freq(98.0)
    pb = nt.nodes.new("ShaderNodeBump")
    pb.inputs["Strength"].default_value = 0.04
    pb.inputs["Distance"].default_value = ctx.length(0.003)
    nt.links.new(peb.outputs["Distance"], pb.inputs["Height"])
    nt.links.new(pb.outputs["Normal"], b.inputs["Normal"])
    imperfect(m, 0.38, 0.50, bump_strength=0.012, scale=69.4, ctx=ctx)
    return m


@material("sleek-black", family="plastic", finish="gloss", solid=True,
          params={"sheen_k": 0.25}, origin="matlib.mat_sleek_black")
def mat_sleek_black(sheen_k=1.0, *, ctx=DEFAULT_CTX):
    """Sleek piano-black plastic: near-zero base so it reads truly black, with a
    crisp glossy clearcoat that reflects the room (env stays glossy for this
    material, as for chrome) — the reflection, not the body, gives it form."""
    m, nt, b = base_material("sleek_black")
    b.inputs["Base Color"].default_value = (0.004, 0.004, 0.006, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.05    # crisp room reflection
    b.inputs["Roughness"].default_value = 0.22
    _wavy_scratches(nt, b, wav_scale=0.612, wav_strength=0.018, scr_strength=0.008, ctx=ctx)
    sheen(b, sheen_k)
    return m


_BAKELITE = dict(family="plastic", finish="satin", solid=True, origin="matlib.mat_bakelite")


@material("bakelite", **_BAKELITE)
@material("bakelite-butterscotch",
          params={"col": (0.52, 0.28, 0.05), "swirl": (0.68, 0.45, 0.11),
                  "name": "bakelite_butterscotch"}, **_BAKELITE)
def mat_bakelite(col=(0.24, 0.06, 0.04), swirl=(0.42, 0.16, 0.07),
                 name="bakelite", *, ctx=DEFAULT_CTX):
    """Marbled phenolic — the knob-chickenhead material, promoted to a panel.
    Cast catalin swirls two resin lots together, so the figure is a STRETCHED
    turbulent flow, not a blotch; over it, the deep glassy polish the material
    is loved for, and just enough translucency at the edges to show it is
    resin rather than paint."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.14
    b.inputs["Coat Weight"].default_value = 0.7
    b.inputs["Coat Roughness"].default_value = 0.06
    b.inputs["Specular IOR Level"].default_value = 0.6
    b.inputs["Subsurface Weight"].default_value = 0.12
    b.inputs["Subsurface Radius"].default_value = (0.5, 0.22, 0.14)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.02)
    sw = nt.nodes.new("ShaderNodeTexNoise")
    sw.inputs["Scale"].default_value = 3.2
    sw.inputs["Detail"].default_value = 8.0
    sw.inputs["Roughness"].default_value = 0.62
    sw.inputs["Distortion"].default_value = 2.4          # the pour
    nt.links.new(_obj_vec(nt, ctx.freq((1.0, 3.2, 1.0))), sw.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*col, 1)
    ramp.color_ramp.elements[1].color = (*swirl, 1)
    ramp.color_ramp.elements[0].position = 0.42     # tight stops = visible figure
    ramp.color_ramp.elements[1].position = 0.58
    nt.links.new(sw.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    imperfect(m, 0.10, 0.19, bump_strength=0.006, scale=65.3, ctx=ctx)
    return m
