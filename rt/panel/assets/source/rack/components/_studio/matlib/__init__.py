"""Family material library shared by every hardware generator.

    from matlib import MATS, MATS_SCALAR, steel_hw, base_material, imperfect, own_material
    from matlib import build, meta, MaterialContext

MATS maps a material key -> zero-arg builder; `build(key, ctx, **params)`
builds any registered key at a physical scale; `meta(key)` is its registry
entry; `mm_per_unit(component)` is a component's physical unit. Builders
return a bpy Material and must be called inside an active scene. Layout and
the @material contract: components/_studio/README.md.
"""
import math  # noqa: F401

import bpy  # noqa: F401

from . import nodes, tangent  # noqa: F401
from .core import (  # noqa: F401
    CALIB_MM_PER_UNIT, DEFAULT_CTX, FINISHES, REGISTRY, Entry, MaterialContext,
    _lerp3, _obj_vec, _warp, base_material, imperfect, material, own_material,
)
from .nodes import Graph, _mix_rgba, _sock, deep  # noqa: F401
from .registry import MATS, MATS_ORDER, MATS_SCALAR, build, meta  # noqa: F401
from .units import MM_PER_UNIT, mm_per_unit  # noqa: F401
from .glass import mat_glass  # noqa: F401
from .leathers import mat_leather  # noqa: F401
from .metals import (  # noqa: F401
    _warm_metal, _wavy_scratches, mat_anodized, mat_brass, mat_brushed, mat_chrome,
    mat_copper, mat_gold, mat_steel, mat_titanium, mat_verdigris, steel_hw,
)
from .paints import mat_black_paint, mat_painted_steel  # noqa: F401
from .papers import mat_cardboard, mat_paper  # noqa: F401
from .plastics import (  # noqa: F401
    _bead_height, mat_bakelite, mat_beige_plastic, mat_sleek_black, mat_styrofoam,
    mat_white_plastic,
)
from .textiles import (  # noqa: F401
    _fibres, _nap, _tone_mottle, _weave, _wool, mat_burlap, mat_corduroy, mat_damask,
    mat_denim, mat_felt, mat_knit, mat_tolex, mat_tweed,
)
from .woods import mat_cork, mat_wood  # noqa: F401
