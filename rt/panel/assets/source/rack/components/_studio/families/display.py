"""DisplayScene: the display / meter / screen family standard (PLAN 2.9) over
ComponentScene. Members: display-nixie, display-segment, meter-vu, screen-monitor.

Family flags, between the shared vocabulary and the slots:
  --hue            emitter hue (roster key)
  --emit           emission strength
  --bloom on|off   veiling glare (also accepts 1|0)
  --bloom-threshold --bloom-size --bloom-strength
  --fill           subject width as a fraction of the frame
and the slot `--window` (the glass / window / envelope a display is seen
through). Each member documents what its values mean in its FLAG_HELP.

A generator declares ComponentScene's attributes plus:
  HUE, HUES        --hue default and roster (HUES None: any string)
  EMIT             --emit default
  BLOOM, BLOOM_THRESHOLD, BLOOM_SIZE, BLOOM_STRENGTH
  FILL
  FLAG_HELP        {family flag key: help}
  UNSUPPORTED      family flag keys the member has no meaning for: the flag
                   exists, any value other than its default is an error
  DERIVED_SLOTS    {slot: help}: slots whose default is `auto` (declare None in
                   SLOTS) and whose key `derived_slot(slot)` resolves from other
                   flags after parsing; the resolved spec is the receipt's value
  NONE_SLOTS       slots that also take `none` (the part is omitted)
Old valueless flags are ALIASES entries `Alias("--noglare", const="off")` on
the flag they set. A default of None on a family flag means "the member's own
value" (a variant's, a style's); the receipt prints `none`.

RAW_SAMPLING is "keep": `--raw` / a `.exr` OUT set the view transform to Raw and
the output to half-float EXR only; --denoise and --adaptive keep their given or
default values (the members' shipped bakes were extracted with the denoiser and
adaptive sampling on).

Slots bind through ComponentScene.bind: `state` keys the lit / dark or inner /
outer datablocks of one slot, `params` carries generator defaults and `force`
the state the generator owns (emission 0 when dark).
emission_params(slot, strength): {the slot key's emission param: strength}, the
  first of EMISSION_PARAMS the key has ({} if none).
new_pass(film_transparent, values=None): factory-empty scene + render setup,
  for multi-pass members (materials are rebuilt per pass); `values` overrides
  resolved flag values for scaffold.setup_render only.
"""

from .base import ComponentScene, Flag, SAME
import scaffold

EMISSION_PARAMS = ("emit", "emission", "strength", "level")
NONE = "none"
AUTO = "auto"

FAMILY_HELP = {
    "hue": "emitter hue (roster key)",
    "emit": "emission strength",
    "bloom": "veiling glare in the compositor",
    "bloom-threshold": "glare threshold, scene-linear",
    "bloom-size": "glare size",
    "bloom-strength": "glare strength",
    "fill": "subject width as a fraction of the frame",
}


def on_off(raw):
    text = str(raw).strip().lower()
    if text in ("on", "1", "true", "yes"):
        return "on"
    if text in ("off", "0", "false", "no"):
        return "off"
    raise ValueError(raw)


on_off.__name__ = "on|off"


class DisplayScene(ComponentScene):
    HUE = None
    HUES = None
    EMIT = None
    BLOOM = "on"
    BLOOM_THRESHOLD = None
    BLOOM_SIZE = None
    BLOOM_STRENGTH = None
    FILL = None
    FLAG_HELP = {}
    UNSUPPORTED = ()
    DERIVED_SLOTS = {}
    NONE_SLOTS = ()
    SCALE_SUPPORTED = False
    RAW_SAMPLING = "keep"
    SAMPLES = 256
    RES = 512

    # ------------------------------------------------------------------ schema
    @classmethod
    def _help(cls, key):
        if key in cls.UNSUPPORTED:
            return "not supported by this component (default only)"
        return cls.FLAG_HELP.get(key, FAMILY_HELP[key])

    @classmethod
    def family_flags(cls):
        h = cls._help
        return [
            Flag("--hue", str, cls.HUE, choices=cls.HUES, help=h("hue")),
            Flag("--emit", float, cls.EMIT, help=h("emit")),
            Flag("--bloom", on_off, cls.BLOOM, help=h("bloom")),
            Flag("--bloom-threshold", float, cls.BLOOM_THRESHOLD, help=h("bloom-threshold")),
            Flag("--bloom-size", float, cls.BLOOM_SIZE, help=h("bloom-size")),
            Flag("--bloom-strength", float, cls.BLOOM_STRENGTH, help=h("bloom-strength")),
            Flag("--fill", float, cls.FILL, help=h("fill")),
        ]

    @classmethod
    def slot_help(cls, slot):
        text = super().slot_help(slot)
        if slot in cls.DERIVED_SLOTS:
            text += f"; default {cls.DERIVED_SLOTS[slot]}"
        if slot in cls.NONE_SLOTS:
            text += "; `none` omits the part"
        return text

    @classmethod
    def schema(cls):
        if "window" not in cls.SLOTS:
            raise TypeError(f"{cls.__name__}: display family members declare a `window` slot")
        stray = sorted(set(cls.DERIVED_SLOTS) - set(cls.SLOTS))
        if stray:
            raise TypeError(f"{cls.__name__}: DERIVED_SLOTS {stray} are not SLOTS")
        s = super().schema()
        for slot in cls.DERIVED_SLOTS:
            s.flags[f"--{slot}"].default = AUTO
        s.flags["--raw"].help = "view Raw, half-float OPEN_EXR; implied by a .exr OUT"
        return s

    # ------------------------------------------------------------------- setup
    def validate(self):
        a = self.args
        flags = a.schema.flags
        for key in self.UNSUPPORTED:
            if a[key] != flags[f"--{key}"].default:
                raise SystemExit(f"{self.COMPONENT}: --{key} is not supported")
        super().validate()

    def derived_slot(self, slot):
        raise NotImplementedError(f"{self.COMPONENT}: derived slot {slot!r}")

    def check_slots(self):
        from matlib import REGISTRY

        self.derived = set()
        for slot in self.SLOTS:
            if self.args[slot] in (None, AUTO) and slot in self.DERIVED_SLOTS:
                self.args.values[slot] = self.derived_slot(slot)
                self.derived.add(slot)
            spec = self.args[slot]
            if (slot in self.SLOT_SAME and spec == SAME) or \
                    (slot in self.NONE_SLOTS and spec == NONE):
                continue
            key, params = scaffold.slot_value(spec)
            if key not in REGISTRY:
                raise SystemExit(f"{self.COMPONENT}: --{slot} {key!r} is not a matlib key")
            unknown = sorted(set(params) - set(REGISTRY[key].params))
            if unknown:
                raise SystemExit(f"{self.COMPONENT}: --{slot} {key}: unknown params {unknown}; "
                                 f"has {sorted(REGISTRY[key].params)}")

    def slot_none(self, slot):
        return slot in self.NONE_SLOTS and self.args[slot] == NONE

    # ------------------------------------------------------------------- slots
    def slot_meta(self, slot):
        from matlib import meta

        return meta(self.slot_key(slot)[0])

    def emission_params(self, slot, strength):
        params = self.slot_meta(slot).params
        for name in EMISSION_PARAMS:
            if name in params:
                return {name: strength}
        return {}

    # ------------------------------------------------------------------ passes
    def new_pass(self, film_transparent=True, values=None):
        """Factory-empty scene with the render set up; `values` overrides
        resolved flag values for scaffold.setup_render only."""
        import bpy

        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        self.materials = {}
        args = self.args if values is None else _Values({**self.args.values, **values})
        self.device = scaffold.setup_render(self.scene, args, film_transparent=film_transparent,
                                            **{k: v for k, v in self.RENDER.items()
                                               if k != "film_transparent"})
        return self.scene


class _Values:
    def __init__(self, values):
        self.values = values
