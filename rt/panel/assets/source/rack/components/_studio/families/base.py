"""ComponentScene: the family-independent contract every generator is written against.

A generator subclasses a family scene and declares (class attributes):

  COMPONENT       components/ directory name: receipt prefix and the key into
                  matlib.units.MM_PER_UNIT
  SLOTS           {slot: default key spec}; a spec is `key` or `key@param=v,...`
  SLOT_SAME       {slot: other slot}: the slot also accepts `same`, which binds
                  the other slot's material datablock
  SLOT_HELP       {slot: help text} for the flag table
  SLOT_VALUES     {slot: {name: spec template}}: the slot value `name` resolves,
                  before validation, to the template formatted with the resolved
                  flags (`{preset}` = the selected preset; any other flag by its
                  key with `-` as `_`). The resolved spec is the receipt's value;
                  a name shadows a library key of the same name
  PRESETS         {name: {flag: value}}: named bundles (normally slots)
  DEFAULT_PRESET  the preset that reproduces canon (or None)
  PRESET_FLAG     key of the flag that selects a preset (default "preset"; a
                  family may name its roster flag, e.g. "variant")
  ALIASES         {flag key: [old names]}: an old name is a string (a rename,
                  `"face": ["--material"]`) or a scaffold.Alias (value-conditional,
                  `"preset": [Alias("--cap", values=("gold", "silver"))]`, or
                  valueless, `Alias("--noglare", const="off")`). The flag key is a
                  slot, the preset flag, or any other flag
  FLAGS           extra component flags: scaffold.Flag instances
  RES, SAMPLES, SCALE, SEED, DEFAULT_OUT       shared-vocabulary defaults
  RES_WXH         False: --res is N, a square frame; True: N or WxH
                  (scaffold.res_value; resolved WxH is the text `WxH`)
  RAW_SAMPLING    "off": --raw / a .exr OUT force --denoise and --adaptive off;
                  "keep": both keep their given or default values
  SCALE_SUPPORTED False when build() has no coherent zoom: --scale != 1 is
                  then an error, never ignored
  ZOOM            {slot: kinds}: after building, the slot's world-space material
                  distances are multiplied by --scale; kinds from ZOOM_KINDS:
                  "ao" (Ambient Occlusion Distance), "bump" (Bump Distance),
                  "subsurface" (Principled Subsurface Scale where Subsurface
                  Weight > 0); each such material is kept in self.zoomed as
                  (mat, kinds), so a composer that scales the built part
                  (rack's fit) zooms them by its scale too
  PARAM_ORIGINS   components whose keys accept bind's `params` / `lengths`
                  (None: every key)
  RENDER          keyword overrides for scaffold.setup_render (film, view, look)

and implements `build(self)`, which makes geometry, calls `bind` for every slot
and builds the studio. `main()` runs: parse -> factory-empty scene ->
scaffold.setup_render (Metal GPU only, CPU fallback) -> build -> render ->
receipt. Run a generator as `if __name__ == "__main__": Scene.main()` so it
can be imported (flag tables, tests) without rendering.

Flags: scaffold.common_flags (--scale --res --samples --seed --denoise
--adaptive --raw and the preset flag), family flags, one slot flag per SLOTS
entry, FLAGS. Resolution: flag default < preset < explicit flag. Slot keys and
params are validated against matlib.REGISTRY before any geometry is built.

Build unit (one rule for every family): a key whose origin is COMPONENT, or a
pre-standard library key (origin `matlib.*`), builds at its own calibration
unit (`meta(key).calib_mm_per_unit`, the unit its graph was authored at); every
other key builds at matlib.units.mm_per_unit(COMPONENT). A slot built at a unit
other than the component's adds `[calib:slot=mm]` to the receipt.

bind(slot, objects, scalar=None, params=None, force=None, lengths=None,
     state=None) -> Material
  Builds the slot's key once per (slot, state) and assigns it to every object:
  a mesh through own_material, a text or curve object through its data's
  material list. Later calls for the same (slot, state) reuse the datablock;
  bind all of a slot's objects in its first call (part-bound params are
  measured on them). Build params, lowest precedence first:
    params    {param: value} the generator supplies (a derived colour or level,
              a per-object value)
    lengths   {param: world length}: as params, converted into the key's
              calibration units (x build unit / calib)
    scalar    fills the key's one 0..1 character knob
    spec      the slot value's own `@param=v`
    force     {param: value}: state the generator owns (emission 0 when dark)
  Entries the key does not declare are dropped. With PARAM_ORIGINS set,
  `params` and `lengths` apply only to keys originating in those components.
  Part-bound params (meta(key).part_bound, meanings in matlib.core.PART_BOUNDS)
  not set above are filled from core.Bounds of the objects' evaluated meshes,
  each in its own object space, when the key's origin component is not
  COMPONENT; on the origin component the key's preset applies. Then ZOOM.
family_aliases() -> {flag key: [old names]}: aliases a family gives every member,
  applied ahead of ALIASES (hardware: `--preset` onto `--variant`).
bind_each(slot, pairs) -> [Material]: one datablock per (object, bind keyword
  dict) pair, never cached.
bind_faces(objects, slots, supply=None) -> [Material]: slots[k] on material index
  k, keeping each face's existing material_index; supply {slot: bind keywords}.
slot_entry(slot) -> matlib Entry of the slot's resolved key; build_mm(entry) ->
  the build unit above.

Receipt: scaffold's `<component> k=v ... [alias --old as --new]` (every resolved
flag and slot, sorted) plus `[bound:slot.param=v]` per filled part-bound param,
`[calib:slot=mm]`, and family notes, then ` -> OUT`. Tokens in brackets carry no
`k=v` key.

run_strip(scene_py, default_output): the body of a component's render_strip.py.
Runs `_studio/strip.py` under the calling (venv) Python; strip flags (--output
--blender --scale --res --samples --start --end --bleed --verify) are its own,
every other flag before or after `--` passes through to the scene.
"""

import inspect
import sys
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1]
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import scaffold  # noqa: E402
from scaffold import Alias, Flag, Preset, Schema  # noqa: E402

SAME = "same"
ZOOM_KINDS = ("ao", "bump", "subsurface")


class ComponentScene:
    COMPONENT = None
    SLOTS = {}
    SLOT_SAME = {}
    SLOT_HELP = {}
    SLOT_VALUES = {}
    PRESETS = {}
    DEFAULT_PRESET = None
    PRESET_FLAG = "preset"
    ALIASES = {}
    FLAGS = ()
    RES = 640
    RES_WXH = False
    RAW_SAMPLING = "off"
    SAMPLES = 220
    SCALE = 1.0
    SCALE_SUPPORTED = True
    SEED = 0
    DEFAULT_OUT = None
    ZOOM = {}
    PARAM_ORIGINS = None
    RENDER = {}

    # ------------------------------------------------------------------ schema
    @classmethod
    def family_flags(cls):
        """Flags a family adds between the shared vocabulary and the slots."""
        return []

    @classmethod
    def family_aliases(cls):
        """{flag key: [old names]} a family gives every member, ahead of ALIASES."""
        return {}

    @classmethod
    def slot_help(cls, slot):
        return cls.SLOT_HELP.get(slot, f"{slot} material")

    @classmethod
    def schema(cls):
        if not cls.COMPONENT:
            raise TypeError(f"{cls.__name__}: COMPONENT is not declared")
        for slot, other in cls.SLOT_SAME.items():
            if slot not in cls.SLOTS or other not in cls.SLOTS or other in cls.SLOT_SAME:
                raise TypeError(f"{cls.__name__}: SLOT_SAME {slot!r} -> {other!r} must name "
                                f"two SLOTS, the target not itself a `same` slot")
        for slot, kinds in cls.ZOOM.items():
            if slot not in cls.SLOTS or set(kinds) - set(ZOOM_KINDS):
                raise TypeError(f"{cls.__name__}: ZOOM {slot!r}: {kinds} must name a slot and "
                                f"kinds from {ZOOM_KINDS}")
        stray = sorted(set(cls.SLOT_VALUES) - set(cls.SLOTS))
        if stray:
            raise TypeError(f"{cls.__name__}: SLOT_VALUES {stray} are not SLOTS")
        flags = scaffold.common_flags(res=cls.RES, samples=cls.SAMPLES, scale=cls.SCALE,
                                      seed=cls.SEED, default_preset=cls.DEFAULT_PRESET,
                                      preset_flag="--" + cls.PRESET_FLAG,
                                      raw_sampling=cls.RAW_SAMPLING, res_wxh=cls.RES_WXH)
        if not cls.SCALE_SUPPORTED:
            flags[0].help = "only 1: this component has no coherent zoom"
        flags += list(cls.family_flags())
        for slot, spec in cls.SLOTS.items():
            help_ = cls.slot_help(slot)
            if slot in cls.SLOT_SAME:
                help_ += f"; `same` = the --{cls.SLOT_SAME[slot]} material"
            flags.append(Flag(f"--{slot}", str, spec, slot=True, help=help_))
        flags += [f.copy() for f in cls.FLAGS]
        by_key = {f.key: f for f in flags}
        for table in (cls.family_aliases(), cls.ALIASES):
            for key, olds in table.items():
                if key not in by_key:
                    raise TypeError(f"{cls.__name__}: ALIASES target --{key} is not a flag")
                by_key[key].aliases += [a if isinstance(a, Alias) else Alias(a) for a in olds]
        presets = [Preset(name, values) for name, values in cls.PRESETS.items()]
        if cls.DEFAULT_PRESET is not None and cls.DEFAULT_PRESET not in cls.PRESETS:
            raise TypeError(f"{cls.__name__}: DEFAULT_PRESET {cls.DEFAULT_PRESET!r} not in PRESETS")
        return Schema(cls.COMPONENT, flags, presets=presets, default_out=cls.DEFAULT_OUT,
                      preset_flag=cls.PRESET_FLAG, raw_sampling=cls.RAW_SAMPLING)

    @classmethod
    def help_markdown(cls):
        return scaffold.help_markdown(cls.schema())

    # ------------------------------------------------------------------- setup
    def __init__(self, argv=None):
        self.materials = {}
        self.notes = []
        self.zoomed = []
        self.scene = None
        self._ctx = None
        self.args = self.schema().parse(argv)
        self.validate()

    @property
    def preset_name(self):
        """The selected preset (the PRESET_FLAG value)."""
        return self.args.values.get(self.PRESET_FLAG)

    def validate(self):
        """Raise SystemExit for an invalid resolved flag. Families and generators
        extend it (call super)."""
        a = self.args
        self.resolve_slot_values()
        if a.scale <= 0:
            raise SystemExit(f"{self.COMPONENT}: --scale must be positive")
        if a.scale != 1.0 and not self.SCALE_SUPPORTED:
            raise SystemExit(f"{self.COMPONENT}: --scale is not supported (only 1)")
        if min(scaffold.res_size(a.res)) < 16 or a.samples < 1:
            raise SystemExit(f"{self.COMPONENT}: --res must be >= 16 and --samples >= 1")
        self.check_slots()

    def resolve_slot_values(self):
        values = self.args.values
        fmt = {k.replace("-", "_"): v for k, v in values.items()}
        fmt["preset"] = self.preset_name
        for slot, names in self.SLOT_VALUES.items():
            if values.get(slot) in names:
                values[slot] = names[values[slot]].format_map(fmt)

    def check_slots(self):
        from matlib import REGISTRY

        for slot in self.SLOTS:
            spec = self.args[slot]
            if slot in self.SLOT_SAME and spec == SAME:
                continue
            key, params = scaffold.slot_value(spec)
            if key not in REGISTRY:
                raise SystemExit(f"{self.COMPONENT}: --{slot} {key!r} is not a matlib key")
            unknown = sorted(set(params) - set(REGISTRY[key].params))
            if unknown:
                raise SystemExit(f"{self.COMPONENT}: --{slot} {key}: unknown params {unknown}; "
                                 f"has {sorted(REGISTRY[key].params)}")

    @property
    def local_dir(self):
        """The generator's own directory (component-local HDRIs win there)."""
        try:
            return Path(inspect.getfile(type(self))).resolve().parent
        except (TypeError, OSError):
            return None

    @property
    def ctx(self):
        """MaterialContext at the component's unit."""
        if self._ctx is None:
            from matlib import MaterialContext, mm_per_unit

            self._ctx = MaterialContext(mm_per_unit(self.COMPONENT))
        return self._ctx

    # ------------------------------------------------------------------- slots
    def slot_key(self, slot):
        """(key, explicit params) of a slot, following `same`."""
        spec = self.args[slot]
        if slot in self.SLOT_SAME and spec == SAME:
            return self.slot_key(self.SLOT_SAME[slot])
        return scaffold.slot_value(spec)

    def resolved_slot(self, slot):
        """The slot that owns the material `slot` binds (itself unless `same`)."""
        if slot in self.SLOT_SAME and self.args[slot] == SAME:
            return self.SLOT_SAME[slot]
        return slot

    def slot_entry(self, slot):
        from matlib import meta

        return meta(self.slot_key(self.resolved_slot(slot))[0])

    def build_mm(self, entry):
        """The unit `entry` builds at on this component (module docstring)."""
        from matlib.core import origin_component

        origin = origin_component(entry)
        if origin is None or origin == self.COMPONENT:
            return entry.calib_mm_per_unit
        return self.ctx.mm_per_unit

    def bind(self, slot, objects, scalar=None, params=None, force=None, lengths=None,
             state=None):
        if slot not in self.SLOTS:
            raise KeyError(f"{self.COMPONENT}: {slot!r} is not a declared slot")
        objects = list(objects)
        owner = self.resolved_slot(slot)
        cache = owner if state is None else (owner, state)
        mat = self.materials.get(cache)
        if mat is None:
            mat = self.materials[cache] = self.build_slot(owner, objects, scalar, params, force,
                                                          lengths)
        assign(objects, mat)
        return mat

    def bind_each(self, slot, pairs):
        owner = self.resolved_slot(slot)
        mats = []
        for ob, kw in pairs:
            mat = self.build_slot(owner, [ob], **kw)
            assign([ob], mat)
            mats.append(mat)
        return mats

    def bind_faces(self, objects, slots, supply=None):
        objects = list(objects)
        index = [[p.material_index for p in ob.data.polygons] for ob in objects]
        mats = [self.bind(s, objects, **(supply or {}).get(s, {})) for s in slots]
        for ob, idx in zip(objects, index):
            ob.data.materials.clear()
            for m in mats:
                ob.data.materials.append(m)
            ob.data.polygons.foreach_set("material_index", idx)
        return mats

    def build_slot(self, owner, objects, scalar=None, params=None, force=None, lengths=None):
        """Build the owner slot's key for `objects` (bind's precedence and notes)."""
        from matlib import MaterialContext, build, mm_per_unit
        from matlib.core import origin_component

        key, spec = self.slot_key(owner)
        entry = self.slot_entry(owner)
        declared = entry.params
        mm = self.build_mm(entry)
        merged = {}
        if self.PARAM_ORIGINS is None or origin_component(entry) in self.PARAM_ORIGINS:
            merged.update({p: v for p, v in (params or {}).items() if p in declared})
            k = mm / entry.calib_mm_per_unit
            merged.update({p: v * k for p, v in (lengths or {}).items() if p in declared})
        if scalar is not None and entry.scalar:
            merged[entry.scalar] = scalar
        merged.update(spec)
        merged.update({p: v for p, v in (force or {}).items() if p in declared})
        filled = self.part_bound_params(entry, merged, objects)
        notes = [f"[bound:{owner}.{p}={v:.6g}]" for p, v in filled.items()]
        if abs(mm - mm_per_unit(self.COMPONENT)) > 1e-9:
            notes.append(f"[calib:{owner}={mm:g}]")
        self.notes += [n for n in notes if n not in self.notes]
        mat = build(key, MaterialContext(mm), **merged, **filled)
        kinds = self.ZOOM.get(owner)
        if kinds:
            self.zoomed.append((mat, kinds))
            if self.args.scale != 1.0:
                zoom_world_distances(mat, self.args.scale, kinds)
        return mat

    def part_bound_params(self, entry, explicit, objects):
        from matlib.core import origin_component, part_bound_values

        todo = {p: m for p, m in entry.part_bound.items() if p not in explicit}
        if not todo or origin_component(entry) == self.COMPONENT:
            return {}
        if not objects:
            raise ValueError(f"{self.COMPONENT}: {entry.key} is part-bound; bind it to objects")
        return part_bound_values(todo, measure_bounds(objects))

    # ------------------------------------------------------------------ render
    @classmethod
    def main(cls, argv=None):
        return cls(argv).run()

    def run(self):
        import bpy

        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        self.device = scaffold.setup_render(self.scene, self.args, **self.RENDER)
        self.build()
        return self.render()

    def build(self):
        raise NotImplementedError

    def receipt(self):
        head, _, out = self.args.receipt().rpartition(" -> ")
        return " ".join([head, *self.notes]) + " -> " + out

    def render(self):
        import bpy

        self.scene.render.filepath = str(self.args.out)
        self.args.out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.render.render(write_still=True)
        line = self.receipt()
        print(line, flush=True)
        return line


def assign(objects, mat):
    """A mesh takes `mat` as its only material (own_material); any other object
    with material data (text, curve) takes it through its data's material list."""
    from matlib import own_material

    for ob in objects:
        if ob.type == "MESH":
            own_material(ob, mat)
        else:
            ob.data.materials.clear()
            ob.data.materials.append(mat)


def zoom_world_distances(mat, factor, kinds=ZOOM_KINDS):
    """Multiply `mat`'s world-space distances of `kinds` (ZOOM_KINDS) by `factor`."""
    for node in mat.node_tree.nodes:
        if node.bl_idname == "ShaderNodeAmbientOcclusion" and "ao" in kinds:
            node.inputs["Distance"].default_value *= factor
        elif node.bl_idname == "ShaderNodeBump" and "bump" in kinds:
            node.inputs["Distance"].default_value *= factor
        elif (node.bl_idname == "ShaderNodeBsdfPrincipled" and "subsurface" in kinds
              and node.inputs["Subsurface Weight"].default_value > 0.0):
            node.inputs["Subsurface Scale"].default_value *= factor


def measure_bounds(objects):
    """core.Bounds over the evaluated meshes of `objects`, each in its own
    object space."""
    import bpy
    import numpy as np
    from matlib.core import Bounds

    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    zmin, zmax, rmax = float("inf"), float("-inf"), 0.0
    for ob in objects:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            n = len(me.vertices)
            if not n:
                continue
            co = np.empty(n * 3, dtype=np.float64)
            me.vertices.foreach_get("co", co)
            co = co.reshape(n, 3)
            zmin = min(zmin, float(co[:, 2].min()))
            zmax = max(zmax, float(co[:, 2].max()))
            rmax = max(rmax, float(np.hypot(co[:, 0], co[:, 1]).max()))
        finally:
            ev.to_mesh_clear()
    if zmin > zmax:
        raise ValueError("no mesh vertices to measure")
    return Bounds(zmin, zmax, rmax)


# ------------------------------------------------------------------------- strip
STRIP_OWN = {"--output", "--blender", "--scale", "--res", "--samples", "--start", "--end",
             "--bleed", "--verify"}


def run_strip(scene_py, default_output, argv=None):
    import strip

    tokens = list(sys.argv[1:] if argv is None else argv)
    after = []
    if "--" in tokens:
        cut = tokens.index("--")
        tokens, after = tokens[:cut], tokens[cut + 1:]
    own, passthrough, i = [], [], 0
    while i < len(tokens):
        tok = tokens[i]
        name, eq, _ = tok.partition("=")
        takes = not eq and i + 1 < len(tokens) and not tokens[i + 1].startswith("--")
        group = own if name in STRIP_OWN else passthrough
        group += tokens[i:i + 2] if takes else [tok]
        i += 2 if takes else 1
    if not any(t.partition("=")[0] == "--output" for t in own):
        own += ["--output", str(default_output)]
    return strip.main([str(scene_py), *own, "--", *passthrough, *after])
