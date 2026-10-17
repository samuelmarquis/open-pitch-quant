"""Paint family: dielectric coatings over a substrate."""
import bpy

from .core import DEFAULT_CTX, base_material, material, sheen


@material("black-paint", family="paint", finish="matte", solid=False,
          params={"sheen_k": 0.25}, origin="matlib.mat_black_paint")
def mat_black_paint(sheen_k=1.0, *, ctx=DEFAULT_CTX):
    """Rack-panel black: deep black dielectric paint deformed at several scales
    — broad warp, orange-peel, fine scuffs, hair scratches — so no single texel
    frequency stands out."""
    m, nt, b = base_material("black_paint")
    b.inputs["Base Color"].default_value = (0.002, 0.002, 0.003, 1)   # nearly true black
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.0    # no clearcoat: its broad specular greys the black
    b.inputs["Specular IOR Level"].default_value = 0.28   # kill most of the base spec too
    # normal octaves stacked so the highlight breaks up at every scale
    prev = None
    tc = nt.nodes.new("ShaderNodeTexCoord")
    for scale, strength, dist, detail in (
            (1.43, 0.05, 0.02, 2.0),    # broad panel warp (not perfectly flat)
            (38.8, 0.06, 0.006, 2.0),   # orange-peel
            (171.0, 0.03, 0.002, 3.0),  # fine scuff
    ):
        n = nt.nodes.new("ShaderNodeTexNoise")
        nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
        n.inputs["Scale"].default_value = ctx.freq(scale)
        n.inputs["Detail"].default_value = detail
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = strength
        bmp.inputs["Distance"].default_value = ctx.length(dist)
        nt.links.new(n.outputs["Fac"], bmp.inputs["Height"])
        if prev is not None:
            nt.links.new(prev.outputs["Normal"], bmp.inputs["Normal"])
        prev = bmp
    # fine hair scratches: stretched high-freq streaks
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = ctx.freq((30.0, 900.0, 1.0))
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    sc = nt.nodes.new("ShaderNodeTexNoise")
    sc.inputs["Detail"].default_value = 2.0
    nt.links.new(mp.outputs["Vector"], sc.inputs["Vector"])
    scb = nt.nodes.new("ShaderNodeBump")
    scb.inputs["Strength"].default_value = 0.02
    scb.inputs["Distance"].default_value = ctx.length(0.001)
    nt.links.new(sc.outputs["Fac"], scb.inputs["Height"])
    nt.links.new(prev.outputs["Normal"], scb.inputs["Normal"])
    nt.links.new(scb.outputs["Normal"], b.inputs["Normal"])
    # roughness mottling
    rn = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(tc.outputs["Object"], rn.inputs["Vector"])
    rn.inputs["Scale"].default_value = ctx.freq(24.5)
    rmr = nt.nodes.new("ShaderNodeMapRange")
    rmr.inputs["To Min"].default_value = 0.52     # matte: spreads spec thin = darker
    rmr.inputs["To Max"].default_value = 0.68
    nt.links.new(rn.outputs["Fac"], rmr.inputs["Value"])
    nt.links.new(rmr.outputs["Result"], b.inputs["Roughness"])
    sheen(b, sheen_k)
    return m


@material("painted-steel", family="paint", finish="satin", solid=False,
          origin="matlib.mat_painted_steel")
def mat_painted_steel(paint_col=(0.24, 0.34, 0.28), *, ctx=DEFAULT_CTX):
    """Chipping / peeling industrial paint over a rusted steel substrate. Two
    BSDFs (paint + rust) composited by a chip mask through a Mix Shader (robust
    vs the Mix node's inconsistent 5.2 sockets). Paint is mostly intact with
    flaked patches where the rust shows through."""
    m = bpy.data.materials.new("painted_steel")
    m.use_nodes = True
    nt = m.node_tree
    out = nt.nodes["Material Output"]
    paint = nt.nodes["Principled BSDF"]
    pos = nt.nodes.new("ShaderNodeTexCoord").outputs["Object"]

    # chip mask: 1 = paint intact, 0 = chipped (rust shows). High-detail noise
    # thresholded hard = irregular flakes with jagged edges.
    cn = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, cn.inputs["Vector"])
    cn.inputs["Scale"].default_value = ctx.freq(2.86)
    cn.inputs["Detail"].default_value = 10.0
    cn.inputs["Roughness"].default_value = 0.8
    chip = nt.nodes.new("ShaderNodeMapRange")
    chip.inputs["From Min"].default_value = 0.47     # narrow band -> HARD flake edges
    chip.inputs["From Max"].default_value = 0.51     # < 0.47 chipped (rust), > 0.51 paint
    nt.links.new(cn.outputs["Fac"], chip.inputs["Value"])

    # --- rust substrate BSDF ---
    rust = nt.nodes.new("ShaderNodeBsdfPrincipled")
    rust.inputs["Metallic"].default_value = 0.0      # iron oxide is matte, not metal
    rust.inputs["Roughness"].default_value = 0.9
    rn = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, rn.inputs["Vector"])
    rn.inputs["Scale"].default_value = ctx.freq(8.16)
    rn.inputs["Detail"].default_value = 8.0
    rramp = nt.nodes.new("ShaderNodeValToRGB")
    rramp.color_ramp.elements[0].color = (0.10, 0.04, 0.02, 1)   # dark corroded
    rramp.color_ramp.elements[1].color = (0.42, 0.17, 0.06, 1)   # orange rust
    nt.links.new(rn.outputs["Fac"], rramp.inputs["Fac"])
    nt.links.new(rramp.outputs["Color"], rust.inputs["Base Color"])
    rpit = nt.nodes.new("ShaderNodeBump")            # rough rust pitting
    rpit.inputs["Strength"].default_value = 0.35
    rpit.inputs["Distance"].default_value = ctx.length(0.01)
    nt.links.new(rn.outputs["Fac"], rpit.inputs["Height"])
    nt.links.new(rpit.outputs["Normal"], rust.inputs["Normal"])

    # --- paint BSDF ---
    paint.inputs["Base Color"].default_value = (*paint_col, 1)
    paint.inputs["Metallic"].default_value = 0.0
    paint.inputs["Roughness"].default_value = 0.44
    paint.inputs["Coat Weight"].default_value = 0.12
    # grime darkening + orange-peel on the paint
    pg = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, pg.inputs["Vector"])
    pg.inputs["Scale"].default_value = ctx.freq(2.45)
    pgr = nt.nodes.new("ShaderNodeValToRGB")
    pgr.color_ramp.elements[0].color = (paint_col[0] * 0.6, paint_col[1] * 0.6,
                                        paint_col[2] * 0.6, 1)   # grimed-down
    pgr.color_ramp.elements[1].color = (*paint_col, 1)
    nt.links.new(pg.outputs["Fac"], pgr.inputs["Fac"])
    nt.links.new(pgr.outputs["Color"], paint.inputs["Base Color"])
    # peeling relief
    peel = nt.nodes.new("ShaderNodeBump")
    peel.inputs["Strength"].default_value = 0.5     # paint stands proud; rust recessed
    peel.inputs["Distance"].default_value = ctx.length(0.012)
    nt.links.new(chip.outputs["Result"], peel.inputs["Height"])
    op = nt.nodes.new("ShaderNodeTexNoise")          # orange-peel on paint
    nt.links.new(pos, op.inputs["Vector"])
    op.inputs["Scale"].default_value = ctx.freq(53.1)
    opb = nt.nodes.new("ShaderNodeBump")
    opb.inputs["Strength"].default_value = 0.02
    opb.inputs["Distance"].default_value = ctx.length(opb.inputs["Distance"].default_value)
    nt.links.new(op.outputs["Fac"], opb.inputs["Height"])
    nt.links.new(peel.outputs["Normal"], opb.inputs["Normal"])
    nt.links.new(opb.outputs["Normal"], paint.inputs["Normal"])

    # composite: Fac 0 -> rust (chipped), Fac 1 -> paint (intact)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(chip.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(rust.outputs["BSDF"], mix.inputs[1])
    nt.links.new(paint.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return m
