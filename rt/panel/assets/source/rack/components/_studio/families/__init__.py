"""Family layer: generator base classes over scaffold, matlib, rigs and strip.

    from families import ComponentScene, KnobScene, DisplayScene, Alias, Flag, run_strip

Importable without bpy (flag schemas, help tables, strip shims); Blender-only
work imports bpy lazily. Contracts: base.py (every generator) and one module
per family: knob.py, control.py (button.py, fader.py, indicator.py),
display.py, hardware.py, conduit.py, rail.py.
"""

from .base import (SAME, ZOOM_KINDS, Alias, ComponentScene, Flag, assign,  # noqa: F401
                   measure_bounds, run_strip, zoom_world_distances)
from .knob import FAMILY_SLOTS, KnobScene, throw_angle, throw_sweep  # noqa: F401
from .control import ControlScene  # noqa: F401
from .button import ButtonScene  # noqa: F401
from .fader import FaderScene  # noqa: F401
from .indicator import IndicatorScene  # noqa: F401
from .display import DisplayScene  # noqa: F401
from .hardware import HardwareScene  # noqa: F401
from .conduit import ClampedRun, ConduitScene  # noqa: F401
from .rail import PX_PER_UNIT, RailScene  # noqa: F401
