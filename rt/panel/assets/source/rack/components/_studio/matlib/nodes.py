"""Shader node-graph DSL for new material code.

    g = Graph(mat.node_tree)
    h = g.noise(g.obj(ctx.freq((1.0, 4.0, 1.0))), 30.0, detail=3.0).outputs["Fac"]
    n = g.bump_chain([(h, 0.4, ctx.length(0.02))])
    g.link(n, bsdf.inputs["Normal"])

Every method that takes an input accepts either a socket (linked) or a
constant (written to the socket's default). Outputs come back as sockets,
except texture methods, which return the node (Fac vs Color vs Distance).

Laws this module exists to stop anyone paying for twice:

- Mix sockets are looked up by IDENTIFIER. The Mix node names four different
  pairs of inputs "A"/"B" and three outputs "Result", so `node.inputs["A"]`
  depends on data_type. `sock` / `mix` resolve by identifier.
- A Mapping node SCALES BEFORE IT ROTATES. A single node glues the stretch
  axis to X/Y whatever rotation it carries; rotate in its own Mapping first
  (`obj(scale, rot)` does).
- Voronoi F1 Distance is 0 AT the feature point and grows toward the cell
  edge: ramp position 0 is a crown, the high end is the crevice.
- `imperfect()` LINKS a Map Range into Roughness, overriding any Roughness
  default set before it.
- AgX lifts shadows at an effective gamma of ~3.7: an 11:1 albedo ratio lands
  on screen near 2:1, so a tint has to be steepened before the transform
  (`deep`).
- A Tangent node pointed at a UV map the mesh does not have yields a ZERO
  tangent and anisotropic metal renders black; use `matlib.tangent`.
- Several mixes chained toward one colour compound until the base is gone:
  sum ONE density scalar, then lerp once (`dye_density`).
"""


def sock(node, ident):
    """Socket by IDENTIFIER, not name. The Mix node names four different pairs
    of sockets "A"/"B" and three outputs "Result", so `node.inputs["A"]` is a
    coin flip that depends on data_type — the family gotcha, made safe."""
    for s in list(node.inputs) + list(node.outputs):
        if s.identifier == ident:
            return s
    raise KeyError(f"{node.bl_idname}: no socket {ident!r}")


def mix_rgba(nt, blend="MIX"):
    """A Mix node wired for colour, returned with its sockets already resolved:
    (node, factor, a, b, result)."""
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = blend
    return (n, sock(n, "Factor_Float"), sock(n, "A_Color"),
            sock(n, "B_Color"), sock(n, "Result_Color"))


_sock = sock
_mix_rgba = mix_rgba


def deep(col, k):
    """Steepen a tint by exponent `k` against AgX's shadow lift (effective
    gamma ~3.7): the ratio between channels survives the view transform only
    if it is exaggerated before it."""
    return tuple(c ** k for c in col)


_SCALAR_VMATH = ("DOT_PRODUCT", "LENGTH", "DISTANCE")
_MIX_IDS = {"FLOAT": ("Factor_Float", "A_Float", "B_Float", "Result_Float"),
            "VECTOR": ("Factor_Float", "A_Vector", "B_Vector", "Result_Vector"),
            "RGBA": ("Factor_Float", "A_Color", "B_Color", "Result_Color")}


class Graph:
    """Thin builder over one node tree."""

    def __init__(self, nt):
        self.nt = nt

    # -- plumbing ------------------------------------------------------------
    def node(self, kind, **props):
        n = self.nt.nodes.new(kind)
        for key, value in props.items():
            setattr(n, key, value)
        return n

    def link(self, src, dst):
        self.nt.links.new(src, dst)

    def feed(self, socket, value):
        """Link a socket, or write a constant; an RGB triple into a colour
        socket gets alpha 1."""
        if value is None:
            return
        if hasattr(value, "is_output"):
            self.link(value, socket)
            return
        if isinstance(value, (tuple, list)):
            n = len(socket.default_value)
            value = tuple(value) + (1.0,) * (n - len(value))
        socket.default_value = value

    sock = staticmethod(sock)

    # -- coordinates -----------------------------------------------------------
    def coord(self, space="Object"):
        return self.node("ShaderNodeTexCoord").outputs[space]

    def mapping(self, vector, scale=None, rotation=None, location=None):
        """Mapping scales BEFORE it rotates: for an angled stretch rotate in a
        separate mapping first (see `obj`)."""
        n = self.node("ShaderNodeMapping")
        self.feed(n.inputs["Vector"], vector)
        self.feed(n.inputs["Location"], location)
        self.feed(n.inputs["Rotation"], rotation)
        self.feed(n.inputs["Scale"], scale)
        return n.outputs["Vector"]

    def obj(self, scale=(1.0, 1.0, 1.0), rot=0.0):
        """Object coords, rotated about Z in their own Mapping, then scaled.
        `scale` is the chain's frequency (pass it through ctx.freq once)."""
        src = self.coord("Object")
        if abs(rot) > 1e-6:
            src = self.mapping(src, rotation=(0.0, 0.0, rot))
        return self.mapping(src, scale=scale)

    # -- math ------------------------------------------------------------------
    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.feed(n.inputs[0], a)
        self.feed(n.inputs[1], b)
        self.feed(n.inputs[2], c)
        return n.outputs["Value"]

    def vmath(self, op, a, b=None, scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.feed(n.inputs[0], a)
        self.feed(n.inputs[1], b)
        if scale is not None:
            self.feed(n.inputs["Scale"], scale)
        return n.outputs["Value" if op in _SCALAR_VMATH else "Vector"]

    def map_range(self, value, from_min=0.0, from_max=1.0, to_min=0.0, to_max=1.0,
                  clamp=True, interpolation="LINEAR"):
        n = self.node("ShaderNodeMapRange", clamp=clamp, interpolation_type=interpolation)
        self.feed(n.inputs["Value"], value)
        self.feed(n.inputs["From Min"], from_min)
        self.feed(n.inputs["From Max"], from_max)
        self.feed(n.inputs["To Min"], to_min)
        self.feed(n.inputs["To Max"], to_max)
        return n.outputs["Result"]

    def smoothstep(self, value, edge0, edge1, to_min=0.0, to_max=1.0):
        return self.map_range(value, edge0, edge1, to_min, to_max, clamp=True,
                              interpolation="SMOOTHSTEP")

    # -- colour ----------------------------------------------------------------
    def mix(self, fac, a, b, data_type="RGBA", blend="MIX", clamp_factor=True):
        """Mix node with sockets resolved by IDENTIFIER. Factor 0 -> a, 1 -> b."""
        n = self.node("ShaderNodeMix", data_type=data_type, blend_type=blend,
                      clamp_factor=clamp_factor)
        f, ia, ib, out = (sock(n, i) for i in _MIX_IDS[data_type])
        self.feed(f, fac)
        self.feed(ia, a)
        self.feed(ib, b)
        return out

    def mix_shader(self, fac, a, b):
        n = self.node("ShaderNodeMixShader")
        self.feed(n.inputs["Fac"], fac)
        self.link(a, n.inputs[1])
        self.link(b, n.inputs[2])
        return n.outputs["Shader"]

    def ramp(self, fac, stops, interpolation="LINEAR"):
        """Colour ramp from [(position, rgb|rgba), ...] in position order.
        Stops follow the driving signal's DISTRIBUTION, not its range: a Wave
        Factor is arcsine-distributed and a MAX of two piles up near 1."""
        n = self.node("ShaderNodeValToRGB")
        cr = n.color_ramp
        cr.interpolation = interpolation
        if len(stops) == 1:
            cr.elements.remove(cr.elements[1])
        for i, (pos, col) in enumerate(stops):
            el = cr.elements[i] if i < 2 else cr.elements.new(pos)
            el.position = pos
            el.color = tuple(col) + (1.0,) * (4 - len(col))
        self.feed(n.inputs["Fac"], fac)
        return n.outputs["Color"]

    def dye_density(self, terms, pool, base, lo=0.30, hi=1.40):
        """ONE dye-density scalar, then ONE lerp pool -> base.

        `terms` is [(field_socket, weight), ...]; the weighted sum is mapped
        lo..hi -> 1..0 and used as the factor from `pool` (dense dye) to `base`.
        Chaining a mix per term compounds toward the pool colour until the base
        and the grain contrast are gone."""
        density = None
        for src, weight in terms:
            scaled = self.math("MULTIPLY", src, weight)
            density = scaled if density is None else self.math("ADD", density, scaled)
        tone = self.map_range(density, lo, hi, 1.0, 0.0)
        return self.mix(tone, pool, base)

    deep = staticmethod(deep)

    # -- textures (return the node) ----------------------------------------------
    # No vector = bare Object coords, never the node's own default (Generated:
    # bounding-box normalised, so features stretch with the part's aspect).
    def _vec(self, vector):
        return self.coord("Object") if vector is None else vector

    def noise(self, vector=None, scale=5.0, detail=2.0, roughness=0.5,
              distortion=0.0, dimensions="3D"):
        n = self.node("ShaderNodeTexNoise", noise_dimensions=dimensions)
        self.feed(n.inputs["Vector"], self._vec(vector))
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = roughness
        n.inputs["Distortion"].default_value = distortion
        return n

    def voronoi(self, vector=None, scale=5.0, feature="F1", randomness=1.0,
                smoothness=None):
        """F1 Distance is 0 AT the feature point: low = crown, high = crevice.
        `smoothness` exists only on SMOOTH_F1."""
        n = self.node("ShaderNodeTexVoronoi", feature=feature)
        self.feed(n.inputs["Vector"], self._vec(vector))
        n.inputs["Scale"].default_value = scale
        n.inputs["Randomness"].default_value = randomness
        if smoothness is not None:
            n.inputs["Smoothness"].default_value = smoothness
        return n

    def wave(self, vector=None, scale=5.0, kind="BANDS", direction=None,
             profile="SIN", distortion=0.0, detail=2.0, phase=None):
        """Distortion is a cliff: past ~0.5 bands stop being bands. `direction`
        is bands_direction for BANDS, rings_direction for RINGS."""
        n = self.node("ShaderNodeTexWave", wave_type=kind, wave_profile=profile)
        if direction is not None:
            setattr(n, "bands_direction" if kind == "BANDS" else "rings_direction", direction)
        self.feed(n.inputs["Vector"], self._vec(vector))
        n.inputs["Scale"].default_value = scale
        n.inputs["Distortion"].default_value = distortion
        n.inputs["Detail"].default_value = detail
        if phase is not None:
            n.inputs["Phase Offset"].default_value = phase
        return n

    # -- relief --------------------------------------------------------------------
    def bump(self, height, strength=1.0, distance=0.001, normal=None, invert=False):
        """`distance` is a length: pass it through ctx.length."""
        n = self.node("ShaderNodeBump", invert=invert)
        n.inputs["Strength"].default_value = strength
        n.inputs["Distance"].default_value = distance
        self.feed(n.inputs["Height"], height)
        self.feed(n.inputs["Normal"], normal)
        return n.outputs["Normal"]

    def bump_chain(self, layers, normal=None):
        """[(height, strength, distance), ...] chained so each layer perturbs
        the previous one's normal; returns the last normal."""
        for height, strength, distance in layers:
            normal = self.bump(height, strength, distance, normal)
        return normal

    def ao_thickness(self, distance, inside=True, only_local=True, samples=16):
        """Ambient-occlusion thickness proxy; returns the AO socket.

        inside=True casts into the solid: AO near 1 = wall thicker than
        `distance`, lower = thinner. inside=False reads cavities. `distance` is
        a world-space length: pass it through ctx.length."""
        n = self.node("ShaderNodeAmbientOcclusion", inside=inside,
                      only_local=only_local, samples=samples)
        n.inputs["Distance"].default_value = distance
        return n.outputs["AO"]
