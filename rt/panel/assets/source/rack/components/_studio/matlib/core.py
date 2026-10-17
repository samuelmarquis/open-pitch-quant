"""Library core: the generic material helpers, the physical-scale context, and
the registry decorator every family module registers its builders through.

Every builder returns a bpy Material and must be called inside an active scene.
"""
import inspect
import math  # noqa: F401
from dataclasses import dataclass
from types import MappingProxyType

import bpy

from .units import DEFAULT_MM_PER_UNIT

FINISHES = ("matte", "satin", "gloss", "mirror")
CALIB_MM_PER_UNIT = DEFAULT_MM_PER_UNIT
# Studio exposure tiers, in precedence order (a scene lit for several keys takes
# the first tier any of them has). rigs.panel_studio documents what each sets.
TIERS = ("chrome", "sleek", "titanium", "warm", "matte")
_FINISH_TIER = {"mirror": "chrome", "gloss": "sleek", "satin": "matte", "matte": "matte"}


def own_material(ob, mat):
    # gotcha #1: booleans inject an empty slot ahead of ours -> force ours.
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for poly in ob.data.polygons:
        poly.material_index = 0


def base_material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree, m.node_tree.nodes["Principled BSDF"]


def sheen(b, s):
    """Scale a Principled BSDF's dielectric specular and coat by `s`; call it
    last. Under knob_studio a black's grey is its sheen, not its colour: the
    rig's broad key and fill sit in a rough black's specular lobe, and a flat
    panel is all lobe (pass 36, p113). s = 1 leaves the graph untouched."""
    if s == 1.0:
        return b
    for name in ("Specular IOR Level", "Coat Weight"):
        inp = b.inputs[name]
        if not inp.is_linked:
            inp.default_value *= s
    return b


# ---------------------------------------------------------------------------
# physical scale


def _scaled(v, k):
    if isinstance(v, (tuple, list)):
        return tuple(x * k for x in v)
    return v * k


@dataclass(frozen=True)
class MaterialContext:
    """The coordinate space a material samples: `mm_per_unit` millimetres per
    world unit. Builders keep their constants at the calibration unit and route
    each spatial one through the context at the socket it lands on:

        ctx.length(v)  distances   v * calib / mm_per_unit
                       (Bump / AO / bevel Distance, Subsurface Scale)
        ctx.freq(v)    frequencies v * mm_per_unit / calib
                       (a texture's Scale on bare Object coords, or the
                       scaling Mapping of an Object-coordinate chain)

    Both factors are 1.0 exactly at mm_per_unit == calib, so the node graph at
    the calibration unit is identical to the unscaled one.

    Every procedural texture reads OBJECT coordinates: a frequency is cycles
    per world unit at the calibration unit, the same on any part. Generated
    and UV (an unlinked Vector is Generated) normalise to the part's bounding
    box, so features stretch with its aspect; selftest fails them (the one
    allowed exception, an image fit to its card, is selftest's
    IMAGE_FIT_KEYS).

    A frequency is applied ONCE per coordinate chain: at the Mapping of an
    Object-coordinate chain (the texture's own Scale left alone), or at the
    texture's Scale on bare Object coords. Scaling both squares the factor. Offsets added in an already-scaled space (`_warp`
    amounts) are not spatial constants and stay as they are. Subsurface is
    scaled at Subsurface Scale only; Subsurface Radius is the per-channel
    profile."""
    mm_per_unit: float = CALIB_MM_PER_UNIT

    def length(self, v, calib=CALIB_MM_PER_UNIT):
        return _scaled(v, calib / self.mm_per_unit)

    def freq(self, v, calib=CALIB_MM_PER_UNIT):
        return _scaled(v, self.mm_per_unit / calib)


DEFAULT_CTX = MaterialContext()


def resolve_ctx(ctx):
    """None -> the calibration context; a number -> that many mm per unit."""
    if ctx is None:
        return DEFAULT_CTX
    if isinstance(ctx, (int, float)):
        return MaterialContext(float(ctx))
    return ctx


# ---------------------------------------------------------------------------
# generic helpers


def imperfect(mat, rough_lo, rough_hi, bump_strength=0.04, scale=60.0, ctx=None):
    """Roughness mottling + micro-bump — the no-perfect-surfaces helper.

    LINKS a Map Range into Roughness: any Roughness default set before this
    call is overridden. `scale` is a frequency in cycles per world unit on
    Object coordinates and the bump keeps the node's default Distance, both
    routed through `ctx`."""
    ctx = resolve_ctx(ctx)
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    pos = _obj_pos(nt)
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, n1.inputs["Vector"])
    n1.inputs["Scale"].default_value = ctx.freq(scale)
    n1.inputs["Detail"].default_value = 5.0
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = rough_lo
    mr.inputs["To Max"].default_value = rough_hi
    nt.links.new(n1.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    nt.links.new(pos, n2.inputs["Vector"])
    n2.inputs["Scale"].default_value = ctx.freq(scale * 3.0)
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump_strength
    bmp.inputs["Distance"].default_value = ctx.length(bmp.inputs["Distance"].default_value)
    nt.links.new(n2.outputs["Fac"], bmp.inputs["Height"])
    existing = b.inputs["Normal"].links[0].from_socket if b.inputs["Normal"].links else None
    if existing is not None:
        nt.links.new(existing, bmp.inputs["Normal"])
    nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return mat


def _obj_pos(nt):
    """Bare Object coords: the Vector of a texture that carries its frequency
    in its own Scale."""
    return nt.nodes.new("ShaderNodeTexCoord").outputs["Object"]


def _obj_vec(nt, scale=(1.0, 1.0, 1.0), rot=0.0):
    """Object-space coords through a Mapping — the library's standard way to
    get a tiled / anisotropically stretched vector, optionally AT AN ANGLE.

    ROTATION NEEDS ITS OWN MAPPING NODE, BEFORE the scaling one. A single
    Mapping applies scale first and rotation second, so the visible stretch
    axis stays glued to X/Y whatever rotation you pass — every "crossed" fibre
    layer combs the same way and wool renders as brushed metal. Rotating the
    coordinate first and stretching the rotated frame is what actually lays
    filaments at an angle.

    `scale` is this chain's frequency: callers pass it through ctx.freq."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    src = tc.outputs["Object"]
    if abs(rot) > 1e-6:
        rm = nt.nodes.new("ShaderNodeMapping")
        rm.inputs["Rotation"].default_value = (0.0, 0.0, rot)
        nt.links.new(src, rm.inputs["Vector"])
        src = rm.outputs["Vector"]
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    nt.links.new(src, mp.inputs["Vector"])
    return mp.outputs["Vector"]


# ROLLED-SHEET RIPPLE (pass 43, p134). Sheet metal is never optically flat: it
# waves, elongated along its rolling direction (x). Dead-on under the house
# rig's soft-edged zenith, the waves bend the edge's falloff and a flat metal
# face reads as a surface (brass, gold, zinc; "soft edge / ripple on seems like
# the answer", Sam). Measured on panel-board's folder (3.3 x 1.3 units at
# 25 mm/unit), so the constants calibrate there whatever key carries them.
RIPPLE_FREQ = (0.5, 1.2, 1.2)      # cycles per world unit at RIPPLE_CALIB
RIPPLE_DIST = 0.05                 # bump height scale, world units at RIPPLE_CALIB
RIPPLE_CALIB = 25.0                # panel-board's mm per unit
RIPPLE = 0.35                      # the bump strength the plate chose


def sheet_ripple(nt, b, strength=RIPPLE, *, ctx=None):
    """Chain a slow rolled-sheet waviness onto `b`'s Normal (after whatever
    is already there)."""
    ctx = resolve_ctx(ctx)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0      # the Mapping carries the frequency
    noise.inputs["Detail"].default_value = 2.0
    nt.links.new(_obj_vec(nt, ctx.freq(RIPPLE_FREQ, RIPPLE_CALIB)), noise.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = ctx.length(RIPPLE_DIST, RIPPLE_CALIB)
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    if b.inputs["Normal"].links:
        nt.links.new(b.inputs["Normal"].links[0].from_socket, bump.inputs["Normal"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return bump


def _warp(nt, vec, amount=0.35, scale=6.0):
    """Push a lookup vector around with noise before a texture reads it.

    THE anti-Voronoi tool: an undistorted Voronoi reads as "Voronoi" — even
    cell sizes, straight shared walls, that unmistakable machine look. Warping
    its input bends the walls and varies the cell sizes, so the same node
    becomes granulated cork or crystalline crust instead.

    `amount` and `scale` live in the space of `vec`; scale `vec`, not them."""
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = 4.0
    n.noise_dimensions = "3D"
    nt.links.new(vec, n.inputs["Vector"])
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    sc.inputs["Scale"].default_value = amount
    nt.links.new(n.outputs["Color"], sc.inputs[0])
    add = nt.nodes.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    nt.links.new(vec, add.inputs[0])
    nt.links.new(sc.outputs["Vector"], add.inputs[1])
    return add.outputs["Vector"]


def _lerp3(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# part-bound parameters


@dataclass(frozen=True)
class Bounds:
    """Union of a part's evaluated mesh vertices, each object in its OWN object
    space (the space an Object-coordinate material samples): lowest and highest
    z, and the largest distance from the object Z axis."""
    zmin: float
    zmax: float
    rmax: float

    @property
    def height(self):
        return self.zmax - self.zmin


# meaning -> (computation over Bounds b, formula). Each proportion is the origin
# part's own (quoted), so a key moved onto another part lands its feature at the
# same relative place. Values are in the part's world units, NOT ctx-scaled.
PART_BOUNDS = {
    "top_z": (lambda b: b.zmax,
              "zmax (knob-wood body: 0.680)"),
    "outer_radius": (lambda b: b.rmax,
                     "rmax (knob-witchhat skirt+cap: 0.550; knob-leather face: 0.430)"),
    "dip_z": (lambda b: b.zmin + (0.088 / 0.7625) * b.height,
              "zmin + 0.1154 height (knob-ceramic body: 0.088 on z 0..0.7625)"),
    "stitch_radius": (lambda b: (0.362 / 0.430) * b.rmax,
                      "0.8419 rmax (knob-leather face: 0.362 on r 0.430)"),
    "dome_rise": (lambda b: (0.120 / 0.430) * b.rmax,
                  "0.2791 rmax (knob-leather face: 0.120 on r 0.430)"),
    "flange_z": (lambda b: b.zmax - (0.120 / 0.430) * b.rmax,
                 "zmax - 0.2791 rmax (knob-leather face: 0.571 under zmax 0.691)"),
    "pointer_width": (lambda b: (0.034 / 0.545) * b.rmax,
                      "0.06239 rmax (knob-catalin body: 0.034 on r 0.545)"),
    "pointer_start": (lambda b: (0.070 / 0.545) * b.rmax,
                      "0.1284 rmax (knob-catalin body: 0.070 on r 0.545)"),
    "pointer_floor_z": (lambda b: b.zmin + (0.165 / 0.750) * b.height,
                        "zmin + 0.22 height (knob-catalin body: 0.165 on z 0..0.750)"),
}


def part_bound_values(part_bound, bounds):
    """{param: value} for a key's `part_bound` map measured on `bounds`."""
    return {p: float(PART_BOUNDS[m][0](bounds)) for p, m in part_bound.items()}


def origin_component(entry):
    """The components/ directory an entry's origin names, or None (matlib)."""
    head, sep, _ = entry.origin.partition(":")
    return head if sep else None


# ---------------------------------------------------------------------------
# registry


@dataclass(frozen=True)
class Entry:
    """One registry key. `params` are the keyword arguments `build` passes to
    `fn` (the builder's defaults overlaid with the key's preset values);
    `part_bound` maps the params that locate features on the origin part to a
    PART_BOUNDS meaning; `tier` is the studio exposure tier."""
    key: str
    fn: object
    family: str
    finish: str
    solid: bool
    params: MappingProxyType
    calib_mm_per_unit: float
    origin: str
    scalar: str = None
    part_bound: MappingProxyType = MappingProxyType({})
    tier: str = "matte"


REGISTRY = {}


def material(key, *, family, finish, solid, params=None,
             calib_mm_per_unit=CALIB_MM_PER_UNIT, origin=None, scalar=None,
             part_bound=None, tier=None):
    """Register a builder under `key`. Stack one decorator per key.

    The builder takes its parameters as keywords plus a keyword-only `ctx`
    (MaterialContext) and routes every spatial constant through it.

      family      metal | plastic | paint | textile | leather | paper | wood | glass | ...
      finish      matte | satin | gloss | mirror — mirror and gloss take the
                  glossy room in a two-world rig, matte and satin the matte room
      solid       True: a volume substance whose pattern reads right cut into any
                  shape (wood, cast resin, glass). False: a sheet, coating or
                  surface finish authored for a face (weave, paint, brushing,
                  plating, patina, anodising)
      params      preset keyword values for this key
      scalar      name of the one 0..1 character knob, if the key has one
                  (listed in MATS_SCALAR)
      part_bound  {param: PART_BOUNDS meaning}: params that are positions on the
                  origin part in its own world units (not ctx-scaled). A slot
                  binder on another component fills them from the target
                  part's bounds; on the origin component the preset applies
      tier        TIERS entry for a studio that exposes per key; default from
                  finish: mirror -> chrome, gloss -> sleek, satin/matte -> matte
    """
    if finish not in FINISHES:
        raise ValueError(f"{key}: finish {finish!r} not in {FINISHES}")
    tier = _FINISH_TIER[finish] if tier is None else tier
    if tier not in TIERS:
        raise ValueError(f"{key}: tier {tier!r} not in {TIERS}")
    bound = dict(part_bound or {})
    for n, m in bound.items():
        if m not in PART_BOUNDS:
            raise ValueError(f"{key}: part_bound {n!r} meaning {m!r} not in {sorted(PART_BOUNDS)}")

    def deco(fn):
        if key in REGISTRY:
            raise KeyError(f"material key {key!r} already registered "
                           f"by {REGISTRY[key].origin}")
        sig = inspect.signature(fn)
        if "ctx" not in sig.parameters:
            raise TypeError(f"{key}: builder {fn.__name__} takes no ctx")
        merged = {n: p.default for n, p in sig.parameters.items()
                  if n != "ctx" and p.default is not inspect.Parameter.empty}
        for n, v in (params or {}).items():
            if n not in sig.parameters or n == "ctx":
                raise TypeError(f"{key}: {fn.__name__} has no parameter {n!r}")
            merged[n] = v
        missing = [n for n, p in sig.parameters.items()
                   if n != "ctx" and n not in merged]
        if missing:
            raise TypeError(f"{key}: no value for required {missing}")
        if scalar is not None and scalar not in merged:
            raise TypeError(f"{key}: scalar knob {scalar!r} is not a parameter")
        stray = sorted(set(bound) - set(merged))
        if stray:
            raise TypeError(f"{key}: part_bound names non-parameters {stray}")
        REGISTRY[key] = Entry(key, fn, family, finish, bool(solid),
                              MappingProxyType(merged), float(calib_mm_per_unit),
                              origin or f"matlib.{fn.__name__}", scalar,
                              MappingProxyType(bound), tier)
        return fn
    return deco
