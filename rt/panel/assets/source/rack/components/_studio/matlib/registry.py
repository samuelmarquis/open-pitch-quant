"""Registry views over every self-registered family module.

Importing this module imports every family module in the package (any module
that is not infrastructure), which registers their keys through @material.

    MATS[key]()                 zero-arg builder at the calibration context
    MATS_SCALAR[key](value)     keys with one 0..1 character knob
    build(key, ctx=None, **params)
    meta(key) -> core.Entry     family, finish, solid, params, calib, origin,
                                scalar, part_bound, tier
"""
import importlib
import pkgutil
from pathlib import Path

from .core import REGISTRY, resolve_ctx

_INFRA = {"core", "nodes", "tangent", "registry", "selftest", "units", "finishes"}

# MATS iterates these keys first, in this order; any other key follows in
# registration order.
MATS_ORDER = (
    "black-paint", "brushed", "chrome", "white-plastic", "styrofoam", "beige-plastic",
    "sleek-black", "worn-steel", "painted-steel", "brass",
    "felt", "felt-crimson", "felt-mustard", "felt-ink", "felt-baize", "damask",
    "damask-teal", "corduroy", "denim", "burlap", "knit", "knit-cream", "knit-chunky",
    "leather", "leather-oxblood", "leather-black", "tweed", "paper", "cardboard", "cork",
    "wood-oak", "wood-walnut", "wood-birch", "wood-rosewood", "wood-ebony",
    "wood-greenheart", "copper", "gold", "verdigris", "verdigris-exposed",
    "verdigris-weathered", "verdigris-full", "anodized-red", "anodized-blue",
    "anodized-black", "titanium", "titanium-deep", "glass-teal", "glass-amber",
    "glass-cobalt", "glass-rose", "glass-clear", "tolex", "tolex-red", "tolex-cream",
    "bakelite", "bakelite-butterscotch",
)

FAMILY_MODULES = tuple(
    importlib.import_module(f"{__package__}.{m.name}")
    for m in sorted(pkgutil.iter_modules([str(Path(__file__).parent)]), key=lambda m: m.name)
    if m.name not in _INFRA and not m.name.startswith("_"))


def build(key, ctx=None, **params):
    """Build `key` at `ctx` (MaterialContext, mm-per-unit number, or None for
    the calibration context), overriding any of its preset params."""
    entry = REGISTRY[key]
    unknown = set(params) - set(entry.params)
    if unknown:
        raise TypeError(f"{key}: unknown params {sorted(unknown)}; "
                        f"has {sorted(entry.params)}")
    return entry.fn(**{**entry.params, **params}, ctx=resolve_ctx(ctx))


def meta(key):
    return REGISTRY[key]


def _preset(key):
    def make():
        return build(key)
    make.__name__ = make.__qualname__ = f"MATS[{key!r}]"
    return make


def _scalar(key, knob):
    def make(value=None, name=None, *, ctx=None, **params):
        if value is not None:
            params[knob] = value
        if name is not None:
            params["name"] = name
        return build(key, ctx, **params)
    make.__name__ = make.__qualname__ = f"MATS_SCALAR[{key!r}]"
    return make


def _ordered_keys():
    first = [k for k in MATS_ORDER if k in REGISTRY]
    return first + [k for k in REGISTRY if k not in MATS_ORDER]


MATS = {k: _preset(k) for k in _ordered_keys()}
MATS_SCALAR = {k: _scalar(k, REGISTRY[k].scalar) for k in _ordered_keys()
               if REGISTRY[k].scalar is not None}
