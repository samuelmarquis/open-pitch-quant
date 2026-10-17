"""Plastic family, translucent and transmissive plastics: clear extruded vinyl
tube and dark smoked diffuser wells.

`imperfect()` routes through the core calibration (25 mm/unit); builders
calibrated elsewhere hand it `_imp_ctx(ctx, calib)`.

Calibration per origin component: units.MM_PER_UNIT.
"""
from .core import (CALIB_MM_PER_UNIT, DEFAULT_CTX, MaterialContext, base_material,
                   imperfect, material)
from .units import mm_per_unit

SMOOTH_MM = mm_per_unit("conduit-smooth")
RADIO_MM = mm_per_unit("button-radio")


def _imp_ctx(ctx, calib):
    """The context `imperfect()` (calibrated at 25) needs so its constants
    scale as if calibrated at `calib`."""
    if calib == CALIB_MM_PER_UNIT:
        return ctx
    return MaterialContext(CALIB_MM_PER_UNIT * (ctx.mm_per_unit / calib))


@material("pvc-clear", family="plastic", finish="gloss", solid=True,
          calib_mm_per_unit=SMOOTH_MM, origin="conduit-smooth:wall_clear:1413")
def mat_pvc_clear(radius=0.16, ior=1.41, rough_lo=0.055, rough_hi=0.115, absorb=8.0,
                  scatter=2.0, scatter_g=0.7, name="wall_clear", *, ctx=DEFAULT_CTX):
    """Colourless flexible PVC / vinyl tube wall: full transmission at IOR 1.41
    (1.45 would be a hard acrylic tube), faint extrusion die-lines along local Y
    under imperfect()'s roughness band, and a volume that makes the wall read
    solid: the thin dead-on wall stays water-clear while the long grazing path
    at the silhouette goes smoky.

    The volume is only well posed on a CLOSED MANIFOLD shell. It is two nodes,
    Volume Absorption (sigma_a) plus Volume Scatter (sigma_s): a single Volume
    Scatter's colour does not absorb, so collapsing them deletes the absorber.
    Neither colour is pure white (a white absorber is a no-op).

    `absorb` / `scatter` are densities per world unit at the calibration unit,
    quoted for a tube of radius 0.16 and rescaled by 0.16 / `radius`, so the
    wall reads the same at every tube size; as per-length quantities they go
    through ctx.freq.
    `radius` is the component's tube radius; the wall is 0.32 x radius thick
    at the canon wall ratio. Duplicate candidate: gummy-rubber-extruded."""
    m, nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.96, 0.96, 0.96, 1)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = ior
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = rough_lo
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = ctx.freq((2.5, 240.0, 240.0), SMOOTH_MM)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Detail"].default_value = 2.0
    nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.020
    bmp.inputs["Distance"].default_value = ctx.length(0.0022, SMOOTH_MM)
    nt.links.new(n.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    imperfect(m, rough_lo, rough_hi, bump_strength=0.012, scale=38.4,
              ctx=_imp_ctx(ctx, SMOOTH_MM))
    vol = []
    if absorb > 0:
        va = nt.nodes.new("ShaderNodeVolumeAbsorption")
        va.inputs["Color"].default_value = (0.80, 0.80, 0.80, 1)
        va.inputs["Density"].default_value = ctx.freq(absorb * (0.16 / radius), SMOOTH_MM)
        vol.append(va)
    if scatter > 0:
        vs = nt.nodes.new("ShaderNodeVolumeScatter")
        vs.inputs["Color"].default_value = (0.97, 0.97, 0.97, 1)
        vs.inputs["Density"].default_value = ctx.freq(scatter * (0.16 / radius), SMOOTH_MM)
        vs.inputs["Anisotropy"].default_value = scatter_g
        vol.append(vs)
    if vol:
        out = vol[0].outputs["Volume"]
        if len(vol) == 2:
            add = nt.nodes.new("ShaderNodeAddShader")
            nt.links.new(vol[0].outputs["Volume"], add.inputs[0])
            nt.links.new(vol[1].outputs["Volume"], add.inputs[1])
            out = add.outputs["Shader"]
        nt.links.new(out, nt.nodes["Material Output"].inputs["Volume"])
    return m


@material("smoked-diffuser", family="plastic", finish="matte", solid=True,
          calib_mm_per_unit=RADIO_MM, origin="button-radio:unlit_center_plastic:138")
def mat_smoked_diffuser(name="unlit_center_plastic", *, ctx=DEFAULT_CTX):
    """Unlit smoked diffuser well: near-black, a trace of transmission (0.02)
    and coat (0.04), roughness 0.54-0.72."""
    m, _nt, b = base_material(name)
    b.inputs["Base Color"].default_value = (0.004, 0.006, 0.007, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.64
    b.inputs["Transmission Weight"].default_value = 0.02
    b.inputs["Coat Weight"].default_value = 0.04
    imperfect(m, 0.54, 0.72, bump_strength=0.026, scale=1070.0, ctx=_imp_ctx(ctx, RADIO_MM))
    return m
