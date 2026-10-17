"""Finish layers: what handling, polishing, ageing and a clear coat do to any
material, chained onto a Principled BSDF `b` in node tree `nt`. Shared by the
finished keys (rack.py's materials, pass 45) and by panel-board's finish flags.
From Nolan's crud_ui rack (open-cepstrum 0.16.0), brought into matlib.

Every layer reads what is already wired into the socket it changes and chains
onto it, so layers stack in any order.
"""
import math

from .core import DEFAULT_CTX


def _source(nt, socket, node_input):
    """Wire `socket`'s current source (link or default) into `node_input`."""
    if socket.links:
        nt.links.new(socket.links[0].from_socket, node_input)
    else:
        node_input.default_value = socket.default_value


def tint(nt, b, rgb):
    """Multiply the base colour by the linear colour `rgb` (a grey metal made
    brass, champagne, cherry ...)."""
    socket = b.inputs["Base Color"]
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    _source(nt, socket, mul.inputs["A"])
    mul.inputs["B"].default_value = (*rgb, 1.0)
    nt.links.new(mul.outputs["Result"], socket)


def darken(nt, b, k):
    """Scale the base colour by `k`, whether it is a value or a texture."""
    socket = b.inputs["Base Color"]
    if not socket.links:
        socket.default_value = (*(c * k for c in socket.default_value[:3]), 1.0)
        return
    tint(nt, b, (k, k, k))


def handled(nt, b, k, *, ctx=DEFAULT_CTX):
    """A handled surface: soft blotches of smudge and wipe, a hand's size and
    stretched along the wipe, raise and lower the roughness by up to `k` of
    itself, so the gloss varies across the face."""
    coord = nt.nodes.new("ShaderNodeTexCoord")
    stretch = nt.nodes.new("ShaderNodeMapping")
    stretch.inputs["Scale"].default_value = ctx.freq((1.4, 3.2, 1.0))
    stretch.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(25.0))
    nt.links.new(coord.outputs["Object"], stretch.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.2
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.6
    nt.links.new(stretch.outputs["Vector"], noise.inputs["Vector"])
    swing = nt.nodes.new("ShaderNodeMapRange")
    for sock, v in (("From Min", 0.3), ("From Max", 0.7), ("To Min", 1.0 - k), ("To Max", 1.0 + k)):
        swing.inputs[sock].default_value = v
    nt.links.new(noise.outputs["Fac"], swing.inputs["Value"])
    socket = b.inputs["Roughness"]
    scaled = nt.nodes.new("ShaderNodeMath")
    scaled.operation, scaled.use_clamp = "MULTIPLY", True
    _source(nt, socket, scaled.inputs[0])
    nt.links.new(swing.outputs["Result"], scaled.inputs[1])
    nt.links.new(scaled.outputs[0], socket)


def tarnished(nt, b, k, *, ctx=DEFAULT_CTX):
    """Uneven tarnish: soft blotches a few centimetres across darken and warm
    the base colour by up to `k` and roughen it where they sit."""
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = ctx.freq((3.5, 3.5, 3.5))
    nt.links.new(coord.outputs["Object"], mp.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.62
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    spots = nt.nodes.new("ShaderNodeMapRange")
    for sock, v in (("From Min", 0.48), ("From Max", 0.72), ("To Max", k)):
        spots.inputs[sock].default_value = v
    nt.links.new(noise.outputs["Fac"], spots.inputs["Value"])
    socket = b.inputs["Base Color"]
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
    nt.links.new(spots.outputs["Result"], mix.inputs["Factor"])
    _source(nt, socket, mix.inputs["A"])
    mix.inputs["B"].default_value = (0.35, 0.22, 0.12, 1.0)
    nt.links.new(mix.outputs["Result"], socket)
    rough = b.inputs["Roughness"]
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.inputs[1].default_value = 0.35
    nt.links.new(spots.outputs["Result"], add.inputs[0])
    _source(nt, rough, add.inputs[2])
    nt.links.new(add.outputs[0], rough)


def scratched(nt, b, k, *, ctx=DEFAULT_CTX):
    """Fine polishing wear: sparse hairline scratches in three directions
    (stretched noise ridges, thresholded thin) raise the roughness — the
    coat's where there is one — by up to `k` along them."""
    coord = nt.nodes.new("ShaderNodeTexCoord")
    total = None
    for angle in (12.0, 71.0, 133.0):
        orient = nt.nodes.new("ShaderNodeMapping")
        orient.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(angle))
        orient.inputs["Scale"].default_value = ctx.freq((4.0, 90.0, 1.0))
        nt.links.new(coord.outputs["Object"], orient.inputs["Vector"])
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 1.0
        noise.inputs["Detail"].default_value = 0.0
        nt.links.new(orient.outputs["Vector"], noise.inputs["Vector"])
        ridge = nt.nodes.new("ShaderNodeMapRange")
        ridge.inputs["From Min"].default_value = 0.72
        ridge.inputs["From Max"].default_value = 0.78
        nt.links.new(noise.outputs["Fac"], ridge.inputs["Value"])
        if total is None:
            total = ridge.outputs["Result"]
        else:
            mx = nt.nodes.new("ShaderNodeMath")
            mx.operation = "MAXIMUM"
            nt.links.new(total, mx.inputs[0])
            nt.links.new(ridge.outputs["Result"], mx.inputs[1])
            total = mx.outputs[0]
    coated = b.inputs["Coat Weight"].default_value > 0 or b.inputs["Coat Weight"].links
    socket = b.inputs["Coat Roughness"] if coated else b.inputs["Roughness"]
    rough = nt.nodes.new("ShaderNodeMath")
    rough.operation = "MULTIPLY_ADD"
    rough.inputs[1].default_value = k
    nt.links.new(total, rough.inputs[0])
    _source(nt, socket, rough.inputs[2])
    nt.links.new(rough.outputs[0], socket)


def undulated(nt, b, k, *, ctx=DEFAULT_CTX):
    """A polished, hand-finished surface: a smooth, slow swell (about two waves
    across a plate) chained onto the Normal at strength `k`, the coat's too,
    so reflections bend along it instead of mirroring a flat rectangle."""
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = ctx.freq((0.9, 0.9, 0.9))
    nt.links.new(coord.outputs["Object"], mp.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0
    noise.inputs["Detail"].default_value = 0.0
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = k
    bump.inputs["Distance"].default_value = ctx.length(0.08)
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    if b.inputs["Normal"].links:
        nt.links.new(b.inputs["Normal"].links[0].from_socket, bump.inputs["Normal"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Coat Normal"])


def coat_follows(nt, b):
    """A clear coat lies on the surface it covers: it takes the relief beneath
    it instead of mirroring the lights as one flat sheet."""
    if b.inputs["Normal"].links:
        nt.links.new(b.inputs["Normal"].links[0].from_socket, b.inputs["Coat Normal"])


def even_wall(material, ao=0.54):
    """A cast resin reads its wall thickness from inside ambient occlusion, so a
    flat plate's rim reads thin and glows pale; a plate is one thickness
    throughout: every inside-AO read becomes the constant `ao`."""
    nt = material.node_tree
    for node in [n for n in nt.nodes if n.bl_idname == "ShaderNodeAmbientOcclusion" and n.inside]:
        for link in list(node.outputs["AO"].links):
            link.to_socket.default_value = ao
            nt.links.remove(link)


def principled(material):
    return [n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"]
