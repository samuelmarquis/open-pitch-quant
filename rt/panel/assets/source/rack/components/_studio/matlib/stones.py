"""Stone family: polished mineral slabs. Object-space patterns at
panel-board's 25 mm/unit; each slab is an opaque, mirror-polished dielectric
of the mineral's index, no coat, its texture in colour alone.
"""
import math

from .core import DEFAULT_CTX, base_material, material

_STONE = dict(family="stone", finish="gloss", solid=False)


def _rebuild(name):
    """A material with an empty tree but its output and one Principled."""
    m, nt, b = base_material(name)
    return m, nt, b, next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")


def _pos(nt, seed_vec, ctx):
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = ctx.freq((1.0, 1.0, 1.0))
    mp.inputs["Location"].default_value = seed_vec
    nt.links.new(coord.outputs["Object"], mp.inputs["Vector"])
    return mp.outputs["Vector"]


@material("lapis", origin="open-cepstrum crud_ui wrapper lapis (pass 45)", **_STONE)
def mat_lapis(calcite=0.12, pyrite=0.6, veins=0.6, fabric=0.0, seed=1.0, polish=0.03,
              *, ctx=DEFAULT_CTX):
    """Polished lapis lazuli, high grade: a saturated ultramarine with deep
    indigo pools and pale mottle at 5-20 mm (stretched along a foliation by
    `fabric`) over a sugary sub-mm grain; calcite as blue-tinted haze that
    feathers into the blue with blue grains left through it (`calcite` its
    share); thin straight pale hairline veins (`veins`); brassy pyrite in
    clusters along the veins and the foliation plus a fine dust (`pyrite`).
    Opaque, mirror-flat, no coat, IOR 1.5: per-mineral roughness only
    (`polish` the lazurite's, calcite duller, pyrite metallic)."""
    m, nt, b, out = _rebuild("lapis")
    n, link = nt.nodes.new, nt.links.new
    pos = _pos(nt, (seed * 4.3, seed * 1.9, seed * 2.2), ctx)

    def math_(op, *args):
        node = n("ShaderNodeMath")
        node.operation = op
        for i, v in enumerate(args):
            if isinstance(v, (int, float)):
                node.inputs[i].default_value = v
            else:
                link(v, node.inputs[i])
        return node.outputs[0]

    def remap(v, a, bb, c=0.0, d=1.0):
        node = n("ShaderNodeMapRange")
        for sock, x in (("From Min", a), ("From Max", bb), ("To Min", c), ("To Max", d)):
            node.inputs[sock].default_value = x
        link(v, node.inputs["Value"])
        return node.outputs["Result"]

    def noise(vec, scale, detail, rough=0.55, out_="Fac"):
        node = n("ShaderNodeTexNoise")
        node.inputs["Scale"].default_value = scale
        node.inputs["Detail"].default_value = detail
        node.inputs["Roughness"].default_value = rough
        link(vec, node.inputs["Vector"])
        return node.outputs[out_]

    def warp(vec, scale, amount):
        centred = n("ShaderNodeVectorMath")
        centred.operation = "SUBTRACT"
        centred.inputs[1].default_value = (0.5, 0.5, 0.5)
        link(noise(vec, scale, 2.0, out_="Color"), centred.inputs[0])
        push = n("ShaderNodeVectorMath")
        push.operation = "SCALE"
        push.inputs["Scale"].default_value = amount
        link(centred.outputs[0], push.inputs[0])
        add = n("ShaderNodeVectorMath")
        add.operation = "ADD"
        link(vec, add.inputs[0])
        link(push.outputs[0], add.inputs[1])
        return add.outputs[0]

    def cells(vec, scale, feature="F1"):
        node = n("ShaderNodeTexVoronoi")
        node.feature = feature
        node.inputs["Scale"].default_value = scale
        link(vec, node.inputs["Vector"])
        return node

    def channel(node, i):
        sep = n("ShaderNodeSeparateColor")
        link(node.outputs["Color"], sep.inputs["Color"])
        return sep.outputs[i]

    def mix(fac, a, bb):
        node = n("ShaderNodeMix")
        node.data_type = "RGBA"
        link(fac, node.inputs["Factor"])
        for sock, v in (("A", a), ("B", bb)):
            if isinstance(v, tuple):
                node.inputs[sock].default_value = (*v, 1.0)
            else:
                link(v, node.inputs[sock])
        return node.outputs["Result"]

    def scale_rgb(col, k):
        node = n("ShaderNodeMix")
        node.data_type, node.blend_type = "RGBA", "MULTIPLY"
        node.inputs["Factor"].default_value = 1.0
        link(col, node.inputs["A"])
        link(k, node.inputs["B"])
        return node.outputs["Result"]

    # foliation: the macro features stretched along a direction 10 deg off x
    fab = n("ShaderNodeMapping")
    fab.inputs["Scale"].default_value = (1.0, 1.0 + 2.5 * fabric, 1.0)
    fab.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(10.0 * fabric))
    link(pos, fab.inputs["Vector"])
    fpos = fab.outputs["Vector"]
    wpos = warp(fpos, 0.8, 0.5)

    # the sugary grain: ~0.2 mm crystals blurred by a finer speckle
    fine = cells(pos, 130.0)
    g1 = channel(fine, 0)
    grain = math_("MULTIPLY_ADD", g1, 0.55, math_("MULTIPLY", noise(pos, 160.0, 1.0), 0.45))

    # two-scale mottle, 10-20 mm clouds and 4-6 mm patches of pale and
    # indigo, their edges broken grain by grain
    m1 = noise(wpos, 1.6, 3.0, 0.5)
    mot = math_("MULTIPLY_ADD", m1, 0.62, math_("MULTIPLY", noise(wpos, 4.5, 3.0, 0.6), 0.38))
    mot = math_("MULTIPLY_ADD", math_("SUBTRACT", grain, 0.5), 0.10, mot)
    body = mix(remap(mot, 0.36, 0.52), (0.005, 0.004, 0.065), (0.010, 0.017, 0.30))
    body = mix(remap(mot, 0.55, 0.70), body, (0.065, 0.10, 0.80))
    # a few pale grains
    body = scale_rgb(body, remap(grain, 0.2, 0.8, 0.72, 1.30))
    body = mix(remap(g1, 0.990, 0.996, 0.0, 0.45), body, (0.12, 0.20, 0.60))

    # calcite haze: feathered clouds, pale blue thin and grey-white thick,
    # blue lazurite grains left standing through them
    t = 0.72 - 0.22 * calcite
    field = math_("MULTIPLY_ADD", math_("SUBTRACT", g1, 0.5), 0.03, noise(wpos, 1.3, 6.0, 0.62))
    haze = remap(field, t, t + 0.13)
    blue = cells(pos, 85.0)
    left = remap(channel(blue, 1), 0.70, 0.71)
    cal = math_("MULTIPLY", haze, math_("MULTIPLY_ADD", left, -0.7, 1.0))
    calcol = mix(remap(field, t + 0.05, t + 0.2), (0.24, 0.34, 0.70), (0.58, 0.58, 0.54))
    body = mix(cal, body, calcol)

    # hairline veins: level lines of long stretched noise, so they run nearly
    # straight across the piece; a main family along the fabric and a weaker
    # cross family, each fading in and out along its length
    def vein_family(angle, stretch, seed_z, strength):
        vm = n("ShaderNodeMapping")
        vm.inputs["Scale"].default_value = (0.25, stretch, 1.0)
        vm.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(angle))
        vm.inputs["Location"].default_value = (0.0, 0.0, seed_z)
        link(pos, vm.inputs["Vector"])
        off = math_("ABSOLUTE", math_("SUBTRACT", noise(vm.outputs["Vector"], 0.5, 1.5, 0.4), 0.5))
        off = math_("MULTIPLY", off, remap(noise(pos, 3.0, 1.0), 0.3, 0.7, 1.8, 0.6))
        line = remap(off, 0.0012, 0.0032, 1.0, 0.0)
        near_ = remap(off, 0.0, 0.035, 1.0, 0.0)
        fade = remap(noise(vm.outputs["Vector"], 0.9, 1.0), 0.40, 0.52, 0.0, strength * veins)
        return math_("MULTIPLY", line, fade), math_("MULTIPLY", near_, fade)

    l1, n1 = vein_family(-10.0 * fabric - 4.0, 2.5, 3.0, 1.0)
    l2, n2 = vein_family(58.0, 2.5, 7.0, 0.6)
    vline, near = math_("MAXIMUM", l1, l2), math_("MAXIMUM", n1, n2)
    body = mix(math_("MULTIPLY", vline, remap(g1, 0.0, 1.0, 0.25, 0.6)), body, (0.26, 0.36, 0.62))

    # pyrite: brassy clusters along the veins and the foliation bands, plus dust
    band = remap(noise(wpos, 1.0, 2.0), 0.58, 0.72, 0.0, 0.6)
    zone = math_("MAXIMUM", near, band)
    blob = math_("MULTIPLY_ADD", math_("SUBTRACT", g1, 0.5), 0.10, noise(wpos, 6.0, 3.0, 0.65))
    clus = remap(math_("MULTIPLY_ADD", zone, 0.28 * pyrite, blob), 0.70, 0.72)
    pg = cells(pos, 110.0)
    inside = math_("MULTIPLY", clus, remap(channel(pg, 0), 0.28, 0.30))
    dustv = cells(pos, 80.0)
    dust = math_("MULTIPLY", remap(channel(dustv, 0), 1.0 - 0.012 * pyrite, 1.0 - 0.012 * pyrite + 0.001),
                 remap(dustv.outputs["Distance"], 0.25, 0.32, 1.0, 0.0))
    pyr = math_("MAXIMUM", inside, dust)
    brass = mix(channel(pg, 2), (0.50, 0.42, 0.16), (0.68, 0.56, 0.22))
    body = mix(pyr, body, brass)
    link(body, b.inputs["Base Color"])
    link(pyr, b.inputs["Metallic"])

    # per-mineral polish, no relief: lazurite `polish`, calcite duller, pyrite
    rough = n("ShaderNodeMix")
    rough.data_type = "FLOAT"
    link(cal, rough.inputs["Factor"])
    rough.inputs["A"].default_value = polish
    rough.inputs["B"].default_value = max(0.07, polish * 2.0)
    rough2 = n("ShaderNodeMix")
    rough2.data_type = "FLOAT"
    link(pyr, rough2.inputs["Factor"])
    link(rough.outputs["Result"], rough2.inputs["A"])
    rough2.inputs["B"].default_value = 0.22
    link(rough2.outputs["Result"], b.inputs["Roughness"])
    b.inputs["IOR"].default_value = 1.5
    b.inputs["Coat Weight"].default_value = 0.0
    return m
