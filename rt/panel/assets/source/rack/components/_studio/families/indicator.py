"""IndicatorScene: the indicator family standard (PLAN 2.9) over ControlScene.
Member: led-indicator.

A generator declares ControlScene's attributes plus, where its canon differs
from the family defaults:

  HUE = "red"      default --hue (a HUES key)
  LEVELS = 16      brightness steps; --level is 0..LEVELS-1
  LEVEL = 15       default --level

HUES is the family glow roster {name: glow rgb}, in the order drivers bake it.
PRESETS are keyed by hue (hue_presets); a hue value given as --hue or its
alias --color selects that preset, which sets --hue and the lens key.

Flags added to the shared vocabulary:
  --hue H        emitter hue, a HUES key
  --level N      brightness index 0..LEVELS-1

Slots: lens (the emitting dome), collar (the ring around it); SLOTS declares any
subset plus EXTRA_SLOTS.

level_fraction() -> --level / (LEVELS - 1).

Glow: the halo is not rendered (Cycles glare writes no film alpha). A driver
composites it into the sprite's alpha with halo(), bpy-free:
  halo(src, dst, glow, level, levels=16)
    radial two-scale halo (sigma 0.135 W and 0.40 W, weights 1.20 and 0.60,
    intensity (level/(levels-1))^0.95) in `glow`, alpha 0.9 x halo, under the
    sprite, then a screened core (sigma 0.060 W, 0.70) over it; level 0 copies
    the sprite unchanged.
"""

from .base import Alias
from .control import ControlScene, Flag

FAMILY_SLOTS = ("lens", "collar")
FAMILY_SLOT_HELP = {"lens": "emitting dome", "collar": "ring around the lens"}
HUES = {
    "green": (0.10, 1.00, 0.25),
    "amber": (1.00, 0.52, 0.07),
    "red": (1.00, 0.11, 0.05),
    "mcblue": (0.08, 0.60, 1.00),
    "white": (1.00, 0.95, 0.85),
}


def hue_presets(lens_keys, **extra):
    """PRESETS {hue: {"hue": hue, "lens": key, **extra}} from {hue: lens key}."""
    return {h: {"hue": h, "lens": k, **extra} for h, k in lens_keys.items()}


def hue_aliases(*old):
    """ALIASES entries mapping --hue and each old flag's hue values onto --preset."""
    return [Alias(name, values=tuple(HUES)) for name in ("--hue", *old)]


def halo(src, dst, glow, level, levels=16):
    import numpy as np
    from PIL import Image

    led = Image.open(src).convert("RGBA")
    W = H = led.width
    lvl = level / (levels - 1)
    if lvl <= 0.001:
        led.save(dst)
        return
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2)
    sigma1, sigma2 = W * 0.135, W * 0.40
    inten = (lvl ** 0.95)
    field = inten * (1.20 * np.exp(-(r / sigma1) ** 2) + 0.60 * np.exp(-(r / sigma2) ** 2))
    field = np.clip(field, 0, 1)
    g = np.array(glow)
    halo_rgb = (field[..., None] * g[None, None, :] * 255).astype(np.uint8)
    halo_a = (field * 255 * 0.9).astype(np.uint8)
    halo_img = Image.fromarray(np.dstack([halo_rgb, halo_a]))
    out = Image.alpha_composite(halo_img, led)
    core = inten * np.exp(-(r / (W * 0.060)) ** 2) * 0.70
    core_rgb = np.asarray(out).astype(np.float32)
    add = core[..., None] * np.array([*(c * 255 for c in g), 0.0])[None, None, :]
    core_rgb = np.clip(core_rgb + add, 0, 255).astype(np.uint8)
    Image.fromarray(core_rgb).save(dst)


class IndicatorScene(ControlScene):
    FAMILY_SLOTS = FAMILY_SLOTS
    FAMILY_SLOT_HELP = FAMILY_SLOT_HELP
    HUE = "red"
    LEVELS = 16
    LEVEL = 15

    @classmethod
    def family_flags(cls):
        return [Flag("--hue", str, cls.HUE, choices=tuple(HUES),
                     help="emitter hue (selects that preset)"),
                Flag("--level", int, cls.LEVEL, help=f"brightness index 0..{cls.LEVELS - 1}")]

    def validate(self):
        super().validate()
        if not 0 <= self.args.level <= self.LEVELS - 1:
            raise SystemExit(f"{self.COMPONENT}: --level must be in 0..{self.LEVELS - 1}")

    def level_fraction(self):
        return self.args.level / (self.LEVELS - 1)
