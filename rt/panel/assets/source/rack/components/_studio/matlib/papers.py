"""Paper family: laid sheets and pressed board."""
from .core import DEFAULT_CTX, _obj_pos, base_material, material
from .nodes import _mix_rgba
from .textiles import _fibres, _nap, _tone_mottle


@material("paper", family="paper", finish="matte", solid=False, origin="matlib.mat_paper")
def mat_paper(col=(0.74, 0.71, 0.63), name="paper", *, ctx=DEFAULT_CTX):
    """Laid printmaking paper: a felted mat of fibres with the chain/laid lines
    of the mould still in it, and enough translucency that the sheet glows
    slightly rather than sitting flat. Dead matte — no coat, low spec."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.93
    b.inputs["Diffuse Roughness"].default_value = 0.75
    b.inputs["Specular IOR Level"].default_value = 0.20
    b.inputs["Subsurface Weight"].default_value = 0.30      # the sheet glows
    b.inputs["Subsurface Radius"].default_value = (0.9, 0.86, 0.78)
    b.inputs["Subsurface Scale"].default_value = ctx.length(0.02)
    _tone_mottle(nt, b, col, amount=0.055, scale=2.04, ctx=ctx)
    pos = _obj_pos(nt)
    laid = nt.nodes.new("ShaderNodeTexWave")                # the mould's wires
    laid.wave_type, laid.bands_direction, laid.wave_profile = "BANDS", "Y", "SIN"
    nt.links.new(pos, laid.inputs["Vector"])
    laid.inputs["Scale"].default_value = ctx.freq(22.5)
    laid.inputs["Distortion"].default_value = 0.5
    lb = nt.nodes.new("ShaderNodeBump")
    lb.inputs["Strength"].default_value = 0.22
    lb.inputs["Distance"].default_value = ctx.length(0.014)
    nt.links.new(laid.outputs["Factor"], lb.inputs["Height"])
    chain = nt.nodes.new("ShaderNodeTexWave")               # chain lines, sparse
    chain.wave_type, chain.bands_direction, chain.wave_profile = "BANDS", "X", "SIN"
    nt.links.new(pos, chain.inputs["Vector"])
    chain.inputs["Scale"].default_value = ctx.freq(2.45)
    cb = nt.nodes.new("ShaderNodeBump")
    cb.inputs["Strength"].default_value = 0.14
    cb.inputs["Distance"].default_value = ctx.length(0.018)
    nt.links.new(chain.outputs["Factor"], cb.inputs["Height"])
    nt.links.new(lb.outputs["Normal"], cb.inputs["Normal"])
    _fibres(nt, b, scales=((65.3, 0.22, 0.011), (171.0, 0.12, 0.004)),
            prev=cb.outputs["Normal"], ctx=ctx)
    return m


@material("cardboard", family="paper", finish="matte", solid=False,
          origin="matlib.mat_cardboard")
def mat_cardboard(col=(0.46, 0.34, 0.21), name="cardboard", *, ctx=DEFAULT_CTX):
    """Kraft board: recycled pulp, so it carries visible dark specks of the
    fibre that never bleached, plus the faint ghost of the flute beneath the
    liner. Matte, slightly fuzzy at grazing."""
    m, nt, b = base_material(name)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.94
    b.inputs["Diffuse Roughness"].default_value = 0.8
    b.inputs["Specular IOR Level"].default_value = 0.18
    _nap(b, weight=0.45, rough=0.4)
    base_ramp = _tone_mottle(nt, b, col, amount=0.10, scale=2.45, ctx=ctx)
    # dark pulp specks, sparse and hard-edged
    pos = _obj_pos(nt)
    sp = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, sp.inputs["Vector"])
    sp.inputs["Scale"].default_value = ctx.freq(36.7)
    sp.inputs["Detail"].default_value = 2.0
    spm = nt.nodes.new("ShaderNodeMapRange")
    spm.inputs["From Min"].default_value = 0.70
    spm.inputs["From Max"].default_value = 0.76
    nt.links.new(sp.outputs["Fac"], spm.inputs["Value"])
    # Fac 0 -> A (the board), Fac 1 -> B (a speck). The mask is ~0 almost
    # everywhere, so specks stay sparse; inverting these two floods the sheet.
    _sx, sfac, sa, sb2, sres = _mix_rgba(nt)
    sb2.default_value = (col[0] * 0.42, col[1] * 0.38, col[2] * 0.34, 1)
    nt.links.new(spm.outputs["Result"], sfac)
    nt.links.new(base_ramp.outputs["Color"], sa)
    nt.links.new(sres, b.inputs["Base Color"])
    flute = nt.nodes.new("ShaderNodeTexWave")
    flute.wave_type, flute.bands_direction, flute.wave_profile = "BANDS", "X", "SIN"
    nt.links.new(pos, flute.inputs["Vector"])
    flute.inputs["Scale"].default_value = ctx.freq(10.6)
    flute.inputs["Distortion"].default_value = 0.3
    fb = nt.nodes.new("ShaderNodeBump")
    fb.inputs["Strength"].default_value = 0.22
    fb.inputs["Distance"].default_value = ctx.length(0.030)
    nt.links.new(flute.outputs["Factor"], fb.inputs["Height"])
    _fibres(nt, b, scales=((44.9, 0.32, 0.020), (122.0, 0.16, 0.007)),
            prev=fb.outputs["Normal"], ctx=ctx)
    return m
