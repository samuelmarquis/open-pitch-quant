"""Glass family: cast, frosted, tinted sheet glass."""
from .core import DEFAULT_CTX, _obj_pos, base_material, material

_GLASS = dict(family="glass", finish="satin", solid=True, origin="matlib.mat_glass")


@material("glass-teal", **_GLASS)
@material("glass-amber", params={"col": (0.62, 0.30, 0.05), "frost": 0.30, "name": "glass_amber"},
          **_GLASS)
@material("glass-cobalt", params={"col": (0.07, 0.16, 0.55), "frost": 0.36, "name": "glass_cobalt"},
          **_GLASS)
@material("glass-rose", params={"col": (0.55, 0.15, 0.26), "frost": 0.32, "name": "glass_rose"},
          **_GLASS)
@material("glass-clear", params={"col": (0.80, 0.84, 0.82), "frost": 0.42, "name": "glass_clear"},
          **_GLASS)
def mat_glass(col=(0.16, 0.42, 0.38), frost=0.34, name="glass", *, ctx=DEFAULT_CTX):
    """Cast coloured glass: frosted, with the slow shallow undulation a rolled
    or slumped sheet keeps. Tinted transmission (the colour lives in the GLASS,
    not on it), roughness `frost` scattering the transmitted light, and a very
    low-frequency bump so the highlight wanders across the sheet instead of
    sitting still.

    On the panel rig it renders on transparent film with the studio behind it,
    so it reads backlit — which is what a glass panel IS. Composite it over
    something, as with any glass."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Transmission Weight"].default_value = 0.92
    b.inputs["IOR"].default_value = 1.52
    b.inputs["Roughness"].default_value = frost
    b.inputs["Coat Weight"].default_value = 0.25      # the fire-polished face
    b.inputs["Coat Roughness"].default_value = 0.10
    # SLOW bump: wavelength measured in whole panels, not millimetres. This is
    # the defining cue for cast glass — fast bump reads as etched or sandy.
    pos = _obj_pos(nt)
    slow = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, slow.inputs["Vector"])
    slow.inputs["Scale"].default_value = ctx.freq(0.898)
    slow.inputs["Detail"].default_value = 2.0
    sb = nt.nodes.new("ShaderNodeBump")
    sb.inputs["Strength"].default_value = 0.55
    sb.inputs["Distance"].default_value = ctx.length(0.16)
    nt.links.new(slow.outputs["Fac"], sb.inputs["Height"])
    # the frost itself: fine roughness mottle, so the scatter is not uniform
    fr = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, fr.inputs["Vector"])
    fr.inputs["Scale"].default_value = ctx.freq(36.7)
    fr.inputs["Detail"].default_value = 4.0
    fmr = nt.nodes.new("ShaderNodeMapRange")
    fmr.inputs["To Min"].default_value = max(frost - 0.12, 0.02)
    fmr.inputs["To Max"].default_value = frost + 0.12
    nt.links.new(fr.outputs["Fac"], fmr.inputs["Value"])
    nt.links.new(fmr.outputs["Result"], b.inputs["Roughness"])
    fb = nt.nodes.new("ShaderNodeBump")
    fb.inputs["Strength"].default_value = 0.10
    fb.inputs["Distance"].default_value = ctx.length(0.004)
    nt.links.new(fr.outputs["Fac"], fb.inputs["Height"])
    nt.links.new(sb.outputs["Normal"], fb.inputs["Normal"])
    nt.links.new(fb.outputs["Normal"], b.inputs["Normal"])
    return m
