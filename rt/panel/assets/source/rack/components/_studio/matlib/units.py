"""Physical unit of every component's world space: millimetres per world unit.

One table for the whole bin. A library key's `calib_mm_per_unit` is the unit
of the component its constants were authored on, looked up here; a generator
hands matlib a MaterialContext at its own `mm_per_unit(component)`. A builder
that routes constants through `ctx.freq(v, calib)` / `ctx.length(v, calib)`
must use the same value its key registers (selftest's calibration check fails
a key built at its registered unit whose ctx calls name another).

Plain Python, no bpy: tools outside Blender load this file directly.
"""

DEFAULT_MM_PER_UNIT = 25.0

MM_PER_UNIT = {  # physical millimetres per world unit, per component; the bin standard is 25
    "default": DEFAULT_MM_PER_UNIT,
    # declared in its generator (MM = 0.1)
    "button-bezel": 10.0,
    # declared in its generator (MM = button-bezel's 0.1)
    "button-stage": 10.0,
    # cap 0.30 x 0.22 units -> 15 x 11 mm console switch cap
    "button-console": 50.0,
    # key pitch 0.34 units -> 17 mm preset button bank
    "button-radio": 50.0,
    # tube radius 0.16 units -> 16 mm OD flexible conduit
    "conduit-corrugated": 50.0,
    # tube radius 0.16 units -> 16 mm OD tube
    "conduit-smooth": 50.0,
    # pipe radius 0.18 units -> 15 mm OD copper pipe
    "conduit-piping": 15.0 / 0.36,
    # 1.27 mm (0.050 in) IDC pitch over ribbon_scene's wire pitch
    # PITCH = 1.85 * R, R = 6 px * 0.01 = 0.111 units
    "conduit-ribbon": 1.27 / (1.85 * (6.0 * 0.01)),
    # cap 0.24 units -> 12 mm desk fader cap
    "fader-desk": 50.0,
    # lens radius 0.075 units -> 5 mm indicator LED
    "led-indicator": 100.0 / 3.0,
    # broadcast case ~2.95 units -> 89 mm (3.5 in) Sifam/Simpson panel meter
    "meter-vu": 30.0,
    # bezel screw head 0.10 units across -> 5.6 mm M3 slotted pan head (ISO 1580)
    "screen-monitor": 56.0,
    # 1/4-inch bushing over its 0.22-unit diameter
    "toggle-bat": 25.4 / 4 / 0.22,
}


def mm_per_unit(component):
    """Millimetres per world unit of `component` (a components/ directory
    name); every component not in the table is at the bin standard, 25."""
    return MM_PER_UNIT.get(component, DEFAULT_MM_PER_UNIT)
