"""Generator scaffold: flag schema, receipt, output/EXR/deterministic render setup,
device selection, footprint normalization and README flag tables.

Parsing is pure Python (importable outside Blender); `setup_render`, `render`,
`select_devices` and `footprint_normalize` need `bpy`, imported lazily.

CLI contract (argv after `--`):
- The first token is OUT unless it starts with `--`; otherwise `default_out`.
- `--flag value` or `--flag=value`; switch flags take no value.
- A flag given twice (directly or through an alias) is an error, as is any
  unknown flag or stray positional: flags that silently fail to arrive are the
  failure this exists to stop. A repeatable flag (`Flag(repeat=SEP)`) is the
  exception: its occurrences, in order, resolve to one value joined by SEP.
- Resolution order: flag default < preset bundle (the schema's preset flag,
  `--preset` unless `Schema(preset_flag=...)` names another, else the schema's
  default preset) < explicit flag.
- `.exr` OUT forces raw. Raw means OPEN_EXR RGBA half-float ZIP, view Raw / look
  None. With `Schema(raw_sampling="off")` (the default) raw also forces
  `denoise=off` and `adaptive=off` (both are non-additive) and the resolved values
  say so; `raw_sampling="keep"` leaves both at their given or default values.
- `--res` is `N` (square, N x N) or `WxH`; `res_size(value)` -> (w, h).

Aliases: `Alias(old, values=None, const=None)` on a flag. With `values` (a dict
old->new value, or an iterable of accepted values kept as-is) the alias applies
only when the given value is in it; otherwise the old name is parsed as its own
flag if the schema has one (`--cap gold` -> `--preset gold`, `--cap verdigris` ->
slot `--cap`). With `const` the old name takes no value and sets the flag to
`const` (`--noglare` -> `--bloom off`). Every alias use is recorded in
`Args.aliased` as {old: new} and shown in the receipt.

Receipt: `<component> k=v k=v ... [alias --old as --new] -> OUT`, one token per
resolved flag, keys are flag names without `--`, sorted. Floats print `%.10g`,
switches `on|off`, values with whitespace are shell-quoted.

Slot values: `key` or `key@param=v,param=v` (`slot_value`). Numeric params
become int or float.

Devices: Metal GPU devices only; CPU is used only when no Metal device exists.
Enabling the CPU device alongside the GPU splits a render across devices by load
and makes repeat renders non-identical.

Footprint: `footprint_normalize(root, target, cam_z)` measures the apparent
radius at the panel plane z = 0 as max over every evaluated mesh vertex under
`root` (world space) of r*cam_z/(cam_z - z), multiplies `root.scale` by
target/apparent, and returns (apparent_native, factor). Call it with the root at
its final user scale and the camera height that scale implies, or before user
scale with target and cam_z for scale 1.
"""

import shlex
import sys
from pathlib import Path

SWITCH = "switch"


class Alias:
    def __init__(self, old, values=None, const=None):
        if not old.startswith("--"):
            raise ValueError(f"alias {old!r} must start with --")
        if values is not None and const is not None:
            raise ValueError(f"alias {old!r}: values and const are exclusive")
        self.old = old
        self.const = const
        if values is None or isinstance(values, dict):
            self.values = values
        else:
            self.values = {v: v for v in values}

    def applies(self, raw):
        return self.values is None or raw in self.values

    def map(self, raw):
        return raw if self.values is None else self.values[raw]


class Flag:
    """One CLI flag. `type` is a converter (float, int, str), or SWITCH for a
    valueless on/off flag. `slot=True` validates the value with `slot_value`.
    `repeat=SEP` makes the flag repeatable: each occurrence is converted, and the
    resolved value is the converted texts joined by SEP."""

    def __init__(self, name, type=str, default=None, choices=None, aliases=(),
                 help="", slot=False, repeat=None):
        if not name.startswith("--"):
            raise ValueError(f"flag {name!r} must start with --")
        if repeat is not None and type == SWITCH:
            raise ValueError(f"flag {name!r}: a switch cannot repeat")
        self.name = name
        self.type = type
        self.default = False if type == SWITCH and default is None else default
        self.choices = tuple(choices) if choices is not None else None
        self.aliases = [a if isinstance(a, Alias) else Alias(a) for a in aliases]
        self.help = help
        self.slot = slot
        self.repeat = repeat

    def copy(self):
        return Flag(self.name, self.type, self.default, self.choices, list(self.aliases),
                    self.help, self.slot, self.repeat)

    @property
    def key(self):
        return self.name[2:]

    @property
    def switch(self):
        return self.type == SWITCH

    def convert(self, raw):
        if self.switch:
            return bool(raw)
        if self.repeat is not None and isinstance(raw, list):
            return self.repeat.join(str(self.convert(r)) for r in raw)
        try:
            value = self.type(raw)
        except (TypeError, ValueError):
            tname = getattr(self.type, "__name__", str(self.type))
            raise SystemExit(f"{self.name}: {raw!r} is not a valid {tname}")
        if self.choices is not None and value not in self.choices:
            raise SystemExit(f"{self.name}: {raw!r} is not one of {list(self.choices)}")
        if self.slot and value is not None:
            slot_value(value)
        return value


class Preset:
    """A named bundle of flag values (normally slots): {"cap": "gold", ...}.
    Keys may be given with or without the leading `--`."""

    def __init__(self, name, values, help=""):
        self.name = name
        self.values = {k[2:] if k.startswith("--") else k: v for k, v in values.items()}
        self.help = help


def slot_value(text):
    """`verdigris@oxidization=0.6,grain=2` -> ("verdigris", {"oxidization": 0.6,
    "grain": 2}). A bare key returns (key, {})."""
    text = str(text)
    key, at, rest = text.partition("@")
    if not key:
        raise SystemExit(f"slot value {text!r} has no key")
    params = {}
    if at:
        if not rest:
            raise SystemExit(f"slot value {text!r} has an empty parameter list")
        for part in rest.split(","):
            name, eq, raw = part.partition("=")
            if not eq or not name or raw == "":
                raise SystemExit(f"slot value {text!r}: parameter {part!r} is not name=value")
            if name in params:
                raise SystemExit(f"slot value {text!r}: parameter {name!r} given twice")
            params[name] = _number(raw)
    return key, params


def _number(raw):
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def res_value(raw):
    """`N` -> int N (square); `WxH` -> the text `WxH`. Each side at least 1."""
    text = str(raw).strip().lower()
    w, sep, h = text.partition("x")
    try:
        dims = (int(w), int(h)) if sep else (int(w),)
    except ValueError:
        raise SystemExit(f"--res {raw!r} is not N or WxH")
    if min(dims) < 1:
        raise SystemExit(f"--res {raw!r}: sides must be positive")
    return dims[0] if len(dims) == 1 else "%dx%d" % dims


res_value.__name__ = "N|WxH"


def res_size(value):
    """(width, height) of a resolved --res value."""
    if isinstance(value, int):
        return value, value
    w, _, h = str(value).lower().partition("x")
    return (int(w), int(h)) if h else (int(w), int(w))


def format_value(value):
    if isinstance(value, bool):
        return "on" if value else "off"
    if value is None:
        return "none"
    if isinstance(value, float):
        return "%.10g" % value
    text = str(value)
    return shlex.quote(text) if (not text or any(c.isspace() for c in text)) else text


# ------------------------------------------------------------ shared vocabulary
def common_flags(res=640, samples=220, scale=1.0, seed=0, default_preset=None,
                 preset_aliases=(), preset_flag="--preset", raw_sampling="off", res_wxh=False):
    """--scale --res --samples --seed --denoise --adaptive --raw and the preset
    flag (`preset_flag`, default --preset; names are validated against the
    Schema's presets; `preset_aliases` are old colourway flags, e.g.
    Alias("--cap", values=("gold", ...))). `raw_sampling` is the Schema's:
    "off" (raw forces denoise and adaptive off) or "keep". `res_wxh`: --res
    also takes WxH (res_value); otherwise an int, square."""
    forced = raw_sampling == "off"
    return [
        Flag("--scale", float, scale, help="coherent zoom of part, rig and camera"),
        Flag("--res", res_value, res, help="render resolution, px: N (square) or WxH")
        if res_wxh else Flag("--res", int, res, help="square render resolution, px"),
        Flag("--samples", int, samples, help="Cycles samples"),
        Flag("--seed", int, seed, help="Cycles seed (animated seed off)"),
        Flag("--denoise", str, "on", choices=("on", "off"),
             help="denoiser; forced off by --raw" if forced else "denoiser (kept under --raw)"),
        Flag("--adaptive", str, "on", choices=("on", "off"),
             help="adaptive sampling; forced off by --raw" if forced
             else "adaptive sampling (kept under --raw)"),
        Flag("--raw", SWITCH, help="scene-linear OPEN_EXR, view Raw; implied by a .exr OUT"),
        Flag(preset_flag, str, default_preset, aliases=preset_aliases,
             help="named slot bundle"),
    ]


def emissive_flags(hue="red", level=1.0, emit=1.0, hues=None):
    return [Flag("--hue", str, hue, choices=hues, help="emitter hue (roster key)"),
            Flag("--level", float, level, help="emitter level 0..1"),
            Flag("--emit", float, emit, help="emission strength")]


def bloom_flags(threshold=0.35, size=5.0, strength=0.55):
    return [Flag("--bloom", str, "on", choices=("on", "off"), help="veiling glare"),
            Flag("--bloom-threshold", float, threshold, help="glare threshold, scene-linear"),
            Flag("--bloom-size", float, size, help="glare size"),
            Flag("--bloom-strength", float, strength, help="glare strength")]


# ----------------------------------------------------------------------- schema
class Args:
    """Resolved flags. Attribute access uses the key with `-` -> `_`
    (`args.start_deg`); `args["start-deg"]` also works."""

    def __init__(self, schema, out, values, aliased):
        self.schema = schema
        self.out = out
        self.values = values
        self.aliased = aliased

    def __getattr__(self, name):
        values = self.__dict__.get("values", {})
        key = name.replace("_", "-")
        if key in values:
            return values[key]
        if name in values:
            return values[name]
        raise AttributeError(name)

    def __getitem__(self, key):
        return self.values[key[2:] if key.startswith("--") else key]

    def slot(self, key):
        return slot_value(self[key])

    def receipt(self):
        return receipt(self.schema.component, self.values, self.out, self.aliased)


class Schema:
    def __init__(self, component, flags, presets=(), default_out=None, preset_flag="preset",
                 raw_sampling="off"):
        if raw_sampling not in ("off", "keep"):
            raise ValueError(f"raw_sampling {raw_sampling!r} is not off or keep")
        self.component = component
        self.flags = {}
        for f in flags:
            if f.name in self.flags:
                raise ValueError(f"flag {f.name} declared twice")
            self.flags[f.name] = f
        self.presets = {p.name: p for p in presets}
        self.default_out = default_out
        self.preset_flag = preset_flag[2:] if preset_flag.startswith("--") else preset_flag
        self.raw_sampling = raw_sampling
        self.aliases = {}
        for f in self.flags.values():
            for a in f.aliases:
                self.aliases.setdefault(a.old, []).append((f, a))
        for p in self.presets.values():
            for k in p.values:
                if "--" + k not in self.flags:
                    raise ValueError(f"preset {p.name!r} sets unknown flag --{k}")

    def _lookup(self, name, raw_value):
        """(flag, mapped raw value, alias-or-None) for a given CLI name."""
        for f, a in self.aliases.get(name, ()):
            if a.values is not None and raw_value is not None and a.applies(raw_value):
                return f, a.map(raw_value), a
        if name in self.flags:
            return self.flags[name], raw_value, None
        for f, a in self.aliases.get(name, ()):
            if a.const is not None:
                return f, a.const, a
            if a.values is None and a.const is None:
                return f, raw_value, a
        return None, raw_value, None

    def _takes_value(self, name):
        if name in self.flags:
            return not self.flags[name].switch
        return any(not f.switch and a.const is None for f, a in self.aliases.get(name, ()))

    def parse(self, argv=None):
        if argv is None:
            argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
        tokens = list(argv)
        if tokens and not tokens[0].startswith("--"):
            out = tokens.pop(0)
        elif self.default_out is not None:
            out = self.default_out
        else:
            raise SystemExit(f"{self.component}: missing OUT (first argument after --)")
        out = Path(out).expanduser().resolve()

        given, aliased, i = {}, {}, 0
        while i < len(tokens):
            tok = tokens[i]
            if not tok.startswith("--"):
                raise SystemExit(f"{self.component}: stray argument {tok!r}")
            name, eq, inline = tok.partition("=")
            if eq:
                raw = inline
                i += 1
            elif self._takes_value(name):
                if i + 1 >= len(tokens):
                    raise SystemExit(f"{self.component}: {name} needs a value")
                raw = tokens[i + 1]
                i += 2
            else:
                raw = None
                i += 1
            flag, mapped, alias = self._lookup(name, raw)
            if flag is None:
                raise SystemExit(f"{self.component}: unknown flag {name}")
            if (flag.switch or (alias is not None and alias.const is not None)) and eq:
                raise SystemExit(f"{self.component}: {name} is a switch and takes no value")
            if flag.repeat is not None:
                given.setdefault(flag.name, []).append(mapped)
            elif flag.name in given:
                raise SystemExit(f"{self.component}: {flag.name} given twice"
                                 + (f" (via {name})" if alias else ""))
            else:
                given[flag.name] = True if flag.switch else mapped
            if alias is not None:
                aliased[name] = flag.name

        values = {f.key: f.default for f in self.flags.values()}
        pkey = self.preset_flag
        preset_name = given.get("--" + pkey, values.get(pkey))
        if preset_name is not None:
            if preset_name not in self.presets:
                raise SystemExit(f"{self.component}: unknown preset {preset_name!r}; "
                                 f"have {sorted(self.presets)}")
            values.update(self.presets[preset_name].values)
        for name, raw in given.items():
            values[self.flags[name].key] = self.flags[name].convert(raw)
        for f in self.flags.values():
            if f.name not in given and f.slot and values[f.key] is not None:
                slot_value(values[f.key])

        if "raw" in values:
            values["raw"] = bool(values["raw"]) or out.suffix.lower() == ".exr"
            if values["raw"] and self.raw_sampling == "off":
                if "denoise" in values:
                    values["denoise"] = "off"
                if "adaptive" in values:
                    values["adaptive"] = "off"
        return Args(self, out, values, aliased)


def receipt(component, values, out, aliased=None):
    parts = [component] + [f"{k}={format_value(values[k])}" for k in sorted(values)]
    for old in sorted(aliased or {}):
        parts.append(f"[alias {old} as {aliased[old]}]")
    return " ".join(parts) + f" -> {out}"


def parse_receipt(line):
    """(component, {key: raw value string}, out) from a receipt line."""
    head, sep, out = line.rpartition(" -> ")
    if not sep:
        raise ValueError(f"not a receipt: {line!r}")
    tokens = shlex.split(head)
    values = {}
    for tok in tokens[1:]:
        k, eq, v = tok.partition("=")
        if eq and not k.startswith("["):
            values[k] = v
    return (tokens[0] if tokens else ""), values, out


def help_markdown(schema):
    """README flag table for a schema (plus its presets)."""
    def cell(text):
        return str(text).replace("|", "\\|")

    rows = ["| flag | default | values | aliases | meaning |",
            "|---|---|---|---|---|"]
    for f in schema.flags.values():
        default = "off" if f.switch and not f.default else format_value(f.default)
        if f.switch:
            values = "switch"
        elif f.choices is not None:
            values = " | ".join(format_value(c) for c in f.choices)
        elif f.slot:
            values = "key[@param=v,...]"
        else:
            values = getattr(f.type, "__name__", str(f.type))
        if f.repeat is not None:
            values += f"; repeatable, joined with `{f.repeat}`"
        aliases = ", ".join(
            f"`{a.old}`" + (f" (= {format_value(a.const)})" if a.const is not None else
                            "" if a.values is None else
                            " (" + ", ".join(f"{k}->{v}" for k, v in a.values.items()) + ")")
            for a in f.aliases)
        rows.append(f"| `{f.name}` | `{cell(default)}` | {cell(values)} | {cell(aliases)} "
                    f"| {cell(f.help)} |")
    if schema.presets:
        rows += ["", "| preset | sets |", "|---|---|"]
        for p in schema.presets.values():
            sets = " ".join(f"`--{k} {format_value(v)}`" for k, v in p.values.items())
            rows.append(f"| `{p.name}` | {cell(sets)} |")
    return "\n".join(rows) + "\n"


# ------------------------------------------------------------------ Blender side
def select_devices(scene):
    """Metal GPU devices only; CPU when there is none. Returns "GPU" or "CPU"."""
    import bpy

    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        metal = False
        for device in prefs.devices:
            device.use = device.type == "METAL"
            metal = metal or device.use
        if metal:
            scene.cycles.device = "GPU"
            return "GPU"
    except Exception:
        pass
    scene.cycles.device = "CPU"
    return "CPU"


def setup_render(scene, args, film_transparent=True, view="AgX",
                 look="AgX - Medium High Contrast", png_compression=15, size=None):
    """Cycles, samples, seed, denoise/adaptive, output format (PNG RGBA 8 or raw
    EXR), resolution at 100 % (`size` (w, h), else res_size(--res)), view
    transform, devices."""
    v = args.values
    raw = bool(v.get("raw", False))
    scene.render.engine = "CYCLES"
    scene.cycles.samples = v["samples"]
    scene.cycles.use_denoising = v.get("denoise", "on") == "on"
    if "seed" in v:
        scene.cycles.seed = v["seed"]
        scene.cycles.use_animated_seed = False
    scene.cycles.use_adaptive_sampling = v.get("adaptive", "on") == "on"
    scene.render.film_transparent = film_transparent
    ims = scene.render.image_settings
    if raw:
        ims.file_format = "OPEN_EXR"
        ims.color_mode = "RGBA"
        ims.color_depth = "16"
        ims.exr_codec = "ZIP"
    else:
        ims.file_format = "PNG"
        ims.color_mode = "RGBA"
        ims.color_depth = "8"
        ims.compression = png_compression
    scene.render.resolution_x, scene.render.resolution_y = size or res_size(v["res"])
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "Raw" if raw else view
    scene.view_settings.look = "None" if raw else look
    return select_devices(scene)


def render(scene, args):
    """Render a still to args.out, then print and return the receipt."""
    import bpy

    scene.render.filepath = str(args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)
    line = args.receipt()
    print(line)
    return line


def footprint_normalize(root, target=0.5, cam_z=4.29):
    import bpy
    import numpy as np

    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    apparent = 0.0
    for ob in [root] + list(root.children_recursive):
        if ob.type not in {"MESH", "CURVE", "SURFACE", "FONT", "META"}:
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            n = len(me.vertices)
            if n == 0:
                continue
            co = np.empty(n * 3, dtype=np.float32)
            me.vertices.foreach_get("co", co)
            co = co.reshape(n, 3).astype(np.float64)
            mw = np.array(ev.matrix_world, dtype=np.float64)
            world = co @ mw[:3, :3].T + mw[:3, 3]
            r = np.hypot(world[:, 0], world[:, 1])
            depth = cam_z - world[:, 2]
            if np.any(depth <= 0):
                raise ValueError(f"{ob.name}: geometry at or above cam_z {cam_z}")
            apparent = max(apparent, float(np.max(r * cam_z / depth)))
        finally:
            ev.to_mesh_clear()
    if apparent <= 0.0:
        raise ValueError(f"{root.name}: no mesh geometry to normalize")
    factor = target / apparent
    root.scale = tuple(s * factor for s in root.scale)
    bpy.context.view_layer.update()
    return apparent, factor
