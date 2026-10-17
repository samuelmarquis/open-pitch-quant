"""rack: a whole panel as ONE scene — every element built from its own
generator at its place in a layout, under one light, through one camera.

  blender -b -P components/_studio/rack.py -- LAYOUT.json OUT.png|OUT.exr
      [--light rack] [--density 2] [--samples 256] [--view 12] [--region x,y,w,h]
      [--light-set KEY=V ...] [--denoise on|off] [--adaptive on|off] [--dark]
      [--states ID:FLAG=SPEC]

--light and --view default to the layout's "light" and "view" (else rack, 12).
An OUT ending .exr is written raw (scene-linear, view Raw). --dark lights
nothing — a black world, no rig — so only what the elements emit remains
(title-bake/1's dark layer, with the plate's own --dark among its flags).

--states renders the element `ID` through values of its flag FLAG in one
run, under the same light and camera: per state only that element is rebuilt
(its previous objects removed; the moved-objects check below still holds for
everything else) and rendered to OUT formatted with {i}, the state's index,
and {v}, its value (OUT = rail/{i:03}.png), one receipt line per state. SPEC
is a list, 0,1,2, or a range a..b/n: n values from a to b inclusive
(--states imprint-follow:--value=0..1/101 is a rail's 101 frames, frame i at
value i/100). ID may name several elements, ID,ID2: each is rebuilt with the
same FLAG value per state (a knob and its ring stepping together).

The layout (JSON) is the consumer's panel:

  {"px_per_unit": 100,                       logical px per world unit
   "window": [x, y, w, h],                   the product's whole window, logical px
                                             (required). The rig is the window's and
                                             nothing else: light and camera centred on
                                             it, span its larger side, reflection cards
                                             over all of it, so every product is lit
                                             the same way wherever its plates sit. A
                                             layout cut from a panel (one part's bake)
                                             carries the panel's window. The camera
                                             frames the window (or --region).
   "elements": [
     {"id": "mutation", "component": "panel-board",
      "flags": ["--w", 1.96, "--h", 2.33, "--face", "brushed", ...],
      "rect": [x, y, w, h]},                 logical px; the element's own origin sits
     ...]}                                   at the rect centre (y down in the layout);
                                             "fit": "width" makes its built width
                                             the rect's (below); "fit": "diameter"
                                             draws it filling the rect's circle
                                             (a knob, below);
                                             "z" lifts it, world units; "z": "seat"
                                             rests it on the surface under it (below);
                                             "script" + "class" (+ "argv") build a
                                             consumer's product wrapper instead, and
                                             "origin": "board" places an element
                                             built in board coordinates;
                                             "units_px" scales one modelled at
                                             that many logical px per unit;
                                             "turn": degrees turns it in the
                                             panel plane, clockwise as drawn,
                                             before it is fitted (90: a
                                             switch's up points right);
                                             "matte": true keeps it in the
                                             scene but draws only the shadow
                                             cast on it (below);
                                             "orthographic": true draws it
                                             where an orthographic camera
                                             would (below);
                                             "key": [MONITOR, I, W] in place of
                                             "rect" makes it a panel key on
                                             that screen-monitor's bezel (below)

"key": [MONITOR, I, W] places a panel key (button-bezel, button-stage) in the
row on the top bezel of the screen-monitor element MONITOR; W is its width,
logical px. The row starts on the vertical line through the bezel's inner
edge (the aperture's side, read from the monitor's own solve) and runs
inward, KEY_GAP (1 mm) between keys: I = 0, 1, 2, ... from the left inner
edge rightward, -1, -2, ... from the right inner edge leftward (a row's
indices run unbroken from 0 or -1). Each key is centred on the band between
the frame's top and the aperture's, built at W ("fit": "width"), seated
("z": "seat") and drawn "orthographic" (a key raised on the bezel would
otherwise be thrown outward by distance * height / view, 2.7 px at OPQ's
right edge); rack writes its "rect", which the layout leaves out.

"orthographic": true is for an element laid out by an orthographic drawing
(a cable whose raised loop the perspective camera would throw outward past
the board's edge): after it is built and placed, every vertex of its geometry
is pulled toward the camera axis by its height, (x, y) *= (view - z) / view,
so the rack camera projects each point exactly at its (x, y). It stays at its
true height, so its light, reflections and shadows stay physical; only its
plan shrinks, by z / view. Its geometry is frozen to plain meshes in world
space (modifiers applied).

"fit": "width" never squashes an element and never scales a housing's
depth with its width. A generator that takes its width as a dimension
(screen-monitor: class attribute `fit_width`, world units) is handed the
rect's width and builds the frame at it, its thickness, bevel and fasteners
at their own world sizes (1 world unit = 100 logical px = 25 mm, the
panel-board's TH 0.16 = 4 mm; an lcd bezel 0.12 = 3 mm deep at any width),
and the composer only checks the built width (1e-3, else it raises). Any
other element (a button modelled at its own size) is scaled uniformly, as
its own --scale law would.

"fit": "diameter" is how a knob is sized from its rect: the rect is the
circle the knob fills on screen (its footprint, pointer and fin sweep
included), min(w, h) across. The rack camera draws it as a camera straight
over the rect centre would: the element is sheared along the camera ray
through that centre (its parent inverses; geometry, object-space textures
and materials stay the generator's), so an off-axis knob's side is not
thrown outward and every height's ring is concentric on the rect centre —
perspective otherwise smears a raised knob's silhouette radially by
distance * height / view (3 px at a board's edge). Then it is scaled
uniformly until its largest drawn distance from the rect centre, max over
rendered vertices of |(x, y) * view / (view - z) - centre|, z the world
height with the "z" lift, is the rect's radius. It absorbs the generator's
--footprint and --scale (a consumer may emit either or neither). Any part
rack scales whole (a fit, "units_px") has its ZOOM materials' world-space
distances (AO, bump, subsurface) zoomed by that scale, as its own --scale
would: a glaze's AO-read thickness otherwise breaks pale on a small knob. With
"orthographic" there is no shear (that pull already centres it) and the plan
distance is the measure. --footprint alone does not size a knob for the
rack: it is measured at the knob camera (4.29 away) in one step at the
modelled size, where raised geometry magnifies most, so a raised knob lands
short (chrome 0.93 of its rect, led 0.92). A consumer whose knob rect is a
sprite frame rather than the knob (open-cepstrum: --scale sprite_px / 100 /
SPRITE_UNITS, the knob about 0.92 of it) keeps its own --scale and no "fit".

Every other raised element (a switch, a key, a guard; not "orthographic"
and not board-origin) is drawn dead-on the same way, sheared onto the ray
through its rect centre in its own frame (a "turn" rotates it) but not
scaled, so a lever stands straight up out of the board wherever it is.

"z": "seat" puts the element's mounting face on the top surface of whatever
else in the scene lies under it, so a part sits on the housing or plate it
is laid over at that surface's built depth (a key on a screen-monitor's
bezel, a knob on a panel-board's face), where a hand-set "z" goes stale the
moment the surface's thickness changes. After every element is built (and
before catchers settle, orthographic pulls and the render): its footprint is
the points of a 9 x 9 grid over its plan box where its own geometry lies
over them; from each, a ray straight down from above the scene hits the
other elements' rendered meshes (held catchers excluded), and the highest
hit is the surface. The element then moves in z (a "fit": "diameter" knob is
re-sheared onto its ray and refitted at the new height, any other part
re-placed on its ray) until its mounting
face is at that height; seated elements resting on seated elements settle
by repeating that to a fixpoint, so the layout's order does not matter.
The surfaces are read uncut: a --states rebuild, like the first build, seats
before the rack's cuts apply, so a part in another element's cut (a needle
in a meter's window) stays on the host's face.
Nothing under the footprint is an error. The mounting face is read from the
element's own geometry, no per-family table:
  - an element that brings a shadow catcher (the surface it is cut into: a
    rail's or radio's plate, knob-ring's --cut-in plate) mounts at that
    catcher's top — its slot and wells sink below it into the cut apertures;
  - else, an element with parts lying wholly at or below its own origin
    plane (button-console's well, button-bezel's key well: a recess into
    the panel, rim at z = 0) mounts at its origin plane;
  - else its lowest point: a knob's skirt underside (every knob generator
    builds from z = 0 up).
A numeric "z" keeps placing the element exactly as given.

Each element is its generator's own build — geometry and materials exactly as
the generator makes them — with the generator's light, camera and world taken
away: rig builders are stubbed while it builds, any light or camera it adds
is deleted, and the world restored. A shadow catcher it adds stands in for
the surface it is cut into: where a panel-board in the scene lies under the
catcher's centre, that real board takes the shadow — the catcher's
"apertures" (a rail's slot and wells) are cut into it and the catcher is
dropped; where none does (a part baked alone) the catcher is kept as a matte.
A part's "rack_hole" (a through-mounted key's invisible cut) over a host — a
panel-board or a screen-monitor housing, a ray down at the hole's centre
meeting it — is cut into that host the same way, so a key stands in a real
cut; over none the hole stays as its generator made it.

A matte is a surface in the scene — it occludes, takes shadow, reflects and
bounces — that the output does not draw: its pixels carry only the shadow
the other elements cast on it, as black at alpha 1 - shadowed/unshadowed
luminance, both taken as displayed (through the view transform, decoded to
linear): display-space alpha over black, so the sprite composited 'over' the
separately baked plate, in linear light on the decoded PNGs, shows the plate
exactly as darkened as the whole scene renders it (an .exr OUT, view Raw,
takes the ratio scene-linear, the space it is composited in). Mattes
are kept catchers and every element marked "matte": true (bake a part with
its real plate as a matte: exact cut-in apertures, the plate's own gloss,
and anything of the part that dips behind it held out). Cycles' shadow
catcher cannot do this: it ignores mesh emitters, and the rack light is all
mesh emitters. With a matte present each render is three: F (mattes held
out), S (mattes, parts invisible to the camera) and G (mattes alone, once
per run, shared by every --states state). Then
rigs.rack_studio lights the whole
scene (RACK_LIGHTS[--light], keys overridden by --light-set) at the window's
span, its reflection cards laid out over the window as the camera sees it
(rigs.place_cards), and one perspective camera `--view` world units over the
window's centre frames the window (or `--region`, lens-shifted, so a region
renders exactly as it sits in the whole). Film is transparent outside the
elements.

Blender exits 0 after a script exception: check OUT and the receipt line
`rack light=... elements=N [frame:WxH] -> OUT`.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

STUDIO = Path(__file__).resolve().parent
COMPONENTS = STUDIO.parent
sys.path.insert(0, str(STUDIO))
import rigs  # noqa: E402
import scaffold  # noqa: E402
from families.base import ComponentScene, zoom_world_distances  # noqa: E402

STUBBED = ("knob_studio", "panel_camera", "bloom", "house_world")
# the surfaces a part mounts through: a "rack_hole" over one is cut into it
HOSTS = ("panel-board", "screen-monitor")
KEY_GAP = 0.04  # world units (1 mm) between neighbouring keys in a "key" row


def parse(argv):
    out = {"light": None, "density": 2.0, "samples": 256, "view": None, "region": None,
           "denoise": "on", "adaptive": "on", "dark": False, "set": {}, "states": None}
    layout, path = Path(argv[0]), Path(argv[1])
    it = iter(argv[2:])
    for flag in it:
        if flag == "--dark":
            out["dark"] = True
            continue
        v = next(it)
        if flag in ("--denoise", "--adaptive"):
            if v not in ("on", "off"):
                raise SystemExit(f"rack: {flag} takes on|off, not {v}")
            out[flag[2:]] = v
        elif flag == "--light":
            out["light"] = v
        elif flag == "--density":
            out["density"] = float(v)
        elif flag == "--samples":
            out["samples"] = int(v)
        elif flag == "--view":
            out["view"] = float(v)
        elif flag == "--region":
            out["region"] = [float(p) for p in v.split(",")]
        elif flag == "--light-set":
            k, _, val = v.partition("=")
            out["set"][k] = None if val == "none" else (val if k == "cards" else
                                                        (val == "on" if k == "dark_room"
                                                         else float(val)))
        elif flag == "--states":
            out["states"] = parse_states(v)
        else:
            raise SystemExit(f"rack: unknown flag {flag}")
    return layout, path, out


def parse_states(v):
    """ID:FLAG=SPEC -> (ID, FLAG, [value text, ...]); SPEC a,b,c or a..b/n."""
    eid, _, rest = v.partition(":")
    flag, _, spec = rest.partition("=")
    if not (eid and flag.startswith("--") and spec):
        raise SystemExit(f"rack: --states takes ID:FLAG=SPEC, not {v}")
    if ".." in spec:
        span, _, n = spec.partition("/")
        a, b = (float(p) for p in span.split(".."))
        n = int(n)
        if n < 2:
            raise SystemExit(f"rack: --states range {spec} needs n >= 2")
        values = [f"{round(a + (b - a) * i / (n - 1), 6):g}" for i in range(n)]
    else:
        values = spec.split(",")
    return eid, flag, values


def generator_class(component):
    """The ComponentScene subclass a component's generator defines."""
    gen = sorted((COMPONENTS / component / "generator").glob("*_scene.py"))
    if len(gen) != 1:
        raise SystemExit(f"rack: {component} has {len(gen)} *_scene.py generators")
    spec = importlib.util.spec_from_file_location(f"rack_{component.replace('-', '_')}", gen[0])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    found = [c for c in vars(mod).values() if isinstance(c, type) and issubclass(c, ComponentScene)
             and getattr(c, "COMPONENT", None) == component]
    if len(found) != 1:
        raise SystemExit(f"rack: {component}'s generator defines {len(found)} scenes for it")
    return found[0]


def wrapper_class(script, name, argv):
    """A consumer's product wrapper (a script that subclasses a canonical
    scene and runs it at import): its module run with sys.argv = argv and its
    top-level `X(...).run()` / `.main()` calls removed, then class `name`."""
    import ast

    path = Path(script)
    tree = ast.parse(path.read_text())
    tree.body = [n for n in tree.body if not (
        isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Attribute) and n.value.func.attr in ("run", "main"))]
    saved = sys.argv
    sys.argv = [str(path), "--", *argv]
    try:
        ns = {"__file__": str(path), "__name__": f"rack_wrapper_{name}"}
        exec(compile(tree, str(path), "exec"), ns)
    finally:
        sys.argv = saved
    return ns[name]


def place_keys(layout, ppu):
    """Each "key": [MONITOR, I, W] element's rect, fit and seat (module
    docstring), from MONITOR's housing solve at its rect's width."""
    els = {el["id"]: el for el in layout["elements"]}
    rows = {}
    for el in layout["elements"]:
        if "key" in el:
            if "rect" in el:
                raise SystemExit(f"rack: {el['id']} is a key; rack writes its rect")
            mon, i, w = el["key"]
            rows.setdefault((mon, i < 0), []).append((abs(i) - (i < 0), w, el))
    for (mon, right), keys in rows.items():
        m = els.get(mon)
        if m is None or m.get("component") != "screen-monitor":
            raise SystemExit(f"rack: key {keys[0][2]['id']} names {mon}, not a screen-monitor")
        if sorted(k[0] for k in keys) != list(range(len(keys))):
            raise SystemExit(f"rack: {mon}'s {'right' if right else 'left'} key row has indices "
                             f"{sorted(k[2]['key'][1] for k in keys)}, not an unbroken run")
        x, y, w, h = m["rect"]
        cls = generator_class("screen-monitor")
        g = sys.modules[cls.__module__].Geo(cls([f"/tmp/rack-{mon}.png",
                                                 *map(str, m.get("flags", []))]).args, w / ppu)
        cx, cy = x + w / 2, y + h / 2
        top, inner = cy - g.out_h / 2 * ppu, cy - (g.win_cy + g.ghh) * ppu
        edge = cx + (g.win_cx + (g.ghw if right else -g.ghw)) * ppu
        for _, kw, el in sorted(keys, key=lambda k: k[0]):
            el["rect"] = [edge - kw if right else edge, top, kw, inner - top]
            el["fit"], el["z"], el["orthographic"] = "width", "seat", True
            edge += -(kw + KEY_GAP * ppu) if right else kw + KEY_GAP * ppu


def build_element(scene, el, world_xy):
    """Build one element in `scene` with its generator's own light, camera and
    world removed; parent it under an empty placed at `world_xy`."""
    argv = [f"/tmp/rack-{el['id']}.png", *map(str, el.get("flags", []))]
    if "script" in el:
        cls = wrapper_class(el["script"], el["class"], [*map(str, el.get("argv", [])), *argv])
    else:
        cls = generator_class(el["component"])
    inst = cls(argv)
    inst.scene, inst.device = scene, None
    if el.get("fit") == "width" and hasattr(inst, "fit_width"):
        # a housing that takes its width as a dimension builds at the rect's
        inst.fit_width = el["rect"][2] / el["_ppu"]
    before, world, camera = set(scene.objects), scene.world, scene.camera
    # what a build may set for its own render, which is the rack's
    kept = [(scene.render, k, getattr(scene.render, k)) for k in
            ("film_transparent", "resolution_x", "resolution_y", "resolution_percentage")]
    kept.append((scene.view_settings, "exposure", scene.view_settings.exposure))
    # an element builds with no camera (a rebuild under --states would
    # otherwise hand it the rack's, which a wrapper may pin)
    scene.camera = None
    bpy.context.view_layer.update()
    placed = {ob: ob.matrix_world.copy() for ob in before}
    saved = {name: getattr(rigs, name) for name in STUBBED}
    for name in STUBBED:
        setattr(rigs, name, lambda *a, **k: dict(world=None, camera=None, lights=[], cards=[]))
    try:
        inst.build()
    finally:
        for name, fn in saved.items():
            setattr(rigs, name, fn)
    # an element builds only its own objects: one that moves what is already
    # in the scene (a recentre over scene.objects) corrupts every element
    # before it
    bpy.context.view_layer.update()
    moved = [ob.name for ob, m in placed.items()
             if ob.name in scene.objects and ob.matrix_world != m]
    if moved:
        raise SystemExit(f"rack: building {el['id']} moved {len(moved)} objects already in the "
                         f"scene (e.g. {', '.join(moved[:3])})")
    # a shadow catcher stands in for the surface a part is cut into: held,
    # unrendered, until settle_catchers knows whether a real board is under it
    for ob in [o for o in scene.objects if o not in before and (
            o.type in ("LIGHT", "CAMERA") or o.is_shadow_catcher)]:
        if ob.type in ("LIGHT", "CAMERA"):
            bpy.data.objects.remove(ob)
        else:
            ob["rack_catcher"] = el["id"]
            ob.hide_render = True
    scene.world, scene.camera = world, camera
    for owner, k, v in kept:
        setattr(owner, k, v)
    root = bpy.data.objects.new(f"element {el['id']}", None)
    root["rack_id"] = el["id"]
    scene.collection.objects.link(root)
    for ob in [o for o in scene.objects if o not in before and o.parent is None and o is not root]:
        ob.parent = root
    if el.get("turn"):
        root.rotation_euler.z = -math.radians(float(el["turn"]))
    if el.get("fit") == "width":
        # uniform, never a squash: a housing built at the rect's width is
        # only checked; a part modelled at its own size is scaled whole
        bpy.context.view_layer.update()
        xs = [(ob.matrix_world @ v.co).x for ob in root.children_recursive
              if ob.type == "MESH" for v in ob.data.vertices]
        k = (el["rect"][2] / el["_ppu"]) / (max(xs) - min(xs))
        if getattr(inst, "fit_width", None) is not None:
            if abs(k - 1) > 1e-3:
                raise SystemExit(f"rack: {el['id']} built {max(xs) - min(xs):.4f} wide at "
                                 f"fit_width {inst.fit_width:.4f} (rect {el['rect'][2]} px)")
        else:
            root.scale = (k, k, k)
    elif "units_px" in el:
        # modelled at its own logical px per world unit (open-cepstrum's
        # rails and radios: 42)
        k = el["units_px"] / el["_ppu"]
        root.scale = (k, k, k)
    if el.get("origin") == "board":
        # built in the consumer's board coordinates (x right, y = -logical / ppu
        # from its top-left): place by the rack centre, not the rect
        cx, cy = el["_centre"]
        world_xy = (-cx / el["_ppu"], cy / el["_ppu"])
    seated = el.get("z") == "seat"
    root.location = (world_xy[0], world_xy[1], 0.0 if seated else float(el.get("z", 0.0)))
    root["component"] = el["component"]
    if el.get("fit") == "diameter":
        fit_diameter(root, el)
    elif not el.get("orthographic") and el.get("origin") != "board":
        stand_on_ray(root, el)
    # a part scaled whole (a fit, units_px) zooms its world-space material
    # distances with it, as its own --scale would: a glaze's AO-read
    # thickness at a third of its size otherwise breaks pale everywhere
    zoom = root.scale.x
    if abs(zoom - 1.0) > 1e-6:
        for mat, kinds in getattr(inst, "zoomed", []):
            zoom_world_distances(mat, zoom, kinds)
    if el.get("orthographic") and not seated:
        # a seated element is pulled once it is seated (main)
        orthographic(root, el["_view"])
    return inst, root


def stand_on_ray(root, el):
    """A raised part drawn as a camera straight over its rect centre c would
    draw it (fit_diameter's shear without its scale): the root moved onto
    the camera ray through c at its height, and every height dz above the
    root sheared (x, y) += -c * dz / view, in the root's own frame (a
    "turn" rotates it), so a lever or a nub stands up out of the board
    instead of leaning away from the board centre."""
    from mathutils import Matrix, Vector

    view = el["_view"]
    cx, cy = el["_xy"]
    az = root.location.z
    root.location = (cx * (view - az) / view, cy * (view - az) / view, az)
    if not root.get("rack_sheared"):
        loc = root.rotation_euler.to_matrix().inverted() @ Vector((cx, cy, 0.0))
        shear = Matrix.Identity(4)
        shear[0][2], shear[1][2] = -loc.x / view, -loc.y / view
        for ch in root.children:
            ch.matrix_parent_inverse = shear @ ch.matrix_parent_inverse
        root["rack_sheared"] = True


def fit_diameter(root, el):
    """"fit": "diameter": the element drawn by the rack camera as a camera
    straight over the rect centre c would draw it, filling the rect's
    inscribed circle. A shear in its parent inverses, (x, y) += -c * dz / view
    per height dz over the root (texture spaces untouched), stands its axis on
    the camera ray through c, so every height's ring projects concentric on c;
    then a uniform scale, iterated (a scale moves the heights the projection
    divides by), brings the largest projected distance from c, max |P.xy *
    view / (view - P.z) - c| over the rendered vertices, to the rect's radius.
    Under "orthographic" (which pulls every vertex onto its own plan) no
    shear, and the plan distance from c is the measure."""
    import numpy as np
    from mathutils import Matrix

    view, ppu, ortho = el["_view"], el["_ppu"], bool(el.get("orthographic"))
    target = min(el["rect"][2], el["rect"][3]) / 2 / ppu
    cx, cy = el["_xy"]
    az = root.location.z
    if not ortho:
        # the axis at the root's height on the ray through c, sheared along it
        # (once: a seat refits at a new height without shearing again)
        root.location = (cx * (view - az) / view, cy * (view - az) / view, az)
        if not root.get("rack_sheared"):
            shear = Matrix.Identity(4)
            shear[0][2], shear[1][2] = -cx / view, -cy / view
            for ch in root.children:
                ch.matrix_parent_inverse = shear @ ch.matrix_parent_inverse
            root["rack_sheared"] = True
    else:
        root.location = (cx, cy, az)
    for _ in range(12):
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        pts = []
        for ob in root.children_recursive:
            if (ob.type not in ("MESH", "CURVE", "SURFACE", "META", "FONT") or ob.hide_render
                    or "rack_catcher" in ob):
                continue
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            co = np.empty(len(me.vertices) * 3, dtype=np.float64)
            me.vertices.foreach_get("co", co)
            ev.to_mesh_clear()
            mw = np.array(ev.matrix_world, dtype=np.float64)
            pts.append(co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])
        if not pts:
            raise SystemExit(f"rack: {el['id']} has no geometry to fit its diameter")
        p = np.vstack(pts)
        k = 1.0 if ortho else view / (view - p[:, 2])
        s = target / float(np.max(np.hypot(p[:, 0] * k - cx, p[:, 1] * k - cy)))
        root.scale = tuple(v * s for v in root.scale)
        if abs(s - 1) < 1e-7:
            break


def orthographic(root, view):
    """Draw an element where an orthographic camera would: every vertex of its
    geometry (modifiers applied) pulled toward the camera axis, world (0, 0),
    by its height, (x, y) *= (view - z) / view, so the rack camera `view` over
    it projects each point at its own (x, y). The geometry keeps its true
    height, so its light and shadow stay physical; only its plan shrinks, by
    z / view (under 5% at 0.54 of 12). Each object keeps its own transform, so
    an object-space texture (a stone's figure) stays where the generator put
    it."""
    import numpy as np

    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    obs = list(root.children_recursive)
    world = {ob: ob.matrix_world.copy() for ob in obs}
    built = {}
    for ob in obs:
        if ob.type in ("MESH", "CURVE", "SURFACE", "META", "FONT") and "rack_catcher" not in ob:
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True,
                                                 depsgraph=dg)
            me.transform(world[ob])
            co = np.empty(len(me.vertices) * 3, dtype=np.float64)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            co[:, :2] *= ((view - co[:, 2]) / view)[:, None]
            me.vertices.foreach_set("co", co.ravel())
            me.transform(world[ob].inverted())      # back in the object's own space
            me.update()
            built[ob] = me
    for ob in obs:
        # flat under the root, each keeping its place in the world
        ob.parent = root
        ob.matrix_parent_inverse = root.matrix_world.inverted()
        ob.matrix_world = world[ob]
    for ob, me in built.items():
        placed = world[ob]
        if ob.type != "MESH":
            new = bpy.data.objects.new(ob.name, me)
            for col in ob.users_collection:
                col.objects.link(new)
            new.parent, new.matrix_parent_inverse = root, root.matrix_world.inverted()
            for k in ("visible_camera", "visible_shadow", "hide_render", "is_holdout"):
                setattr(new, k, getattr(ob, k))
            bpy.data.objects.remove(ob)
            ob = new
        else:
            ob.modifiers.clear()
            ob.data = me
        ob.matrix_world = placed


GEOMETRY = ("MESH", "CURVE", "SURFACE", "META", "FONT")


def rendered(root):
    """An element's rendered geometry objects (held catchers apart)."""
    return [ob for ob in root.children_recursive if ob.type in GEOMETRY and not ob.hide_render
            and "rack_catcher" not in ob]


def triangles(obs, dg):
    """World vertices (n, 3) and triangles (m, 3) of `obs`, modifiers applied."""
    import numpy as np

    vs, ts, n = [np.empty((0, 3))], [np.empty((0, 3), dtype=np.int64)], 0
    for ob in obs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get("co", co)
        tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("vertices", tri)
        mw = np.array(ev.matrix_world, dtype=np.float64)
        ev.to_mesh_clear()
        vs.append(co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])
        ts.append(tri.reshape(-1, 3) + n)
        n += len(co) // 3
    return np.vstack(vs), np.vstack(ts)


def mounting_face(root, dg):
    """World z of an element's mounting face ("z": "seat", module docstring):
    its catcher's top, else its origin plane when parts of it lie wholly at
    or below that plane (a recess into the panel), else its lowest point."""
    cats = [ob for ob in root.children_recursive if "rack_catcher" in ob and ob.type in GEOMETRY]
    if cats:
        return float(triangles(cats, dg)[0][:, 2].max())
    oz = root.matrix_world.translation.z
    lows = []
    for ob in rendered(root):
        z = triangles([ob], dg)[0][:, 2]
        if len(z) and z.max() <= oz + 1e-6:
            return oz
        if len(z):
            lows.append(z.min())
    return float(min(lows))


def seat(layout, roots, ids):
    """"z": "seat" for the elements `ids` (module docstring): each moved in z
    until its mounting face is on the highest surface of the other elements
    under its footprint, repeated to a fixpoint (seated on seated)."""
    els ={el["id"]: el for el in layout["elements"]}
    # the surfaces as built: every element first seats before any cut is made
    # (seat_and_pull), so a --states rebuild seats on them uncut too — a part
    # in another element's cut (a needle in a meter's window) stays on the
    # host's face, not on what the cut opened under it
    cuts = [m for ob in bpy.context.scene.objects for m in getattr(ob, "modifiers", [])
            if m.type == "BOOLEAN" and m.object is not None and "rack_cutter" in m.object
            and m.show_viewport]
    for m in cuts:
        m.show_viewport = False
    try:
        _seat(roots, els, ids)
    finally:
        for m in cuts:
            m.show_viewport = True
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    for eid in ids:
        surface, n = els[eid]["_seat"]
        print(f"rack seat {eid}: face z={mounting_face(roots[eid], dg):.5f} on surface "
              f"z={surface:.5f} ({n} rays) root z={roots[eid].location.z:.5f}", flush=True)


def _seat(roots, els, ids):
    from mathutils.bvhtree import BVHTree

    for _ in range(8):
        moved, last = 0.0, {}
        for eid in ids:
            root, el = roots[eid], els[eid]
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            ov, ot = triangles(rendered(root), dg)
            if not len(ot):
                raise SystemExit(f"rack: {eid} has no geometry to seat")
            (x0, y0), (x1, y1) = ov[:, :2].min(0), ov[:, :2].max(0)
            # another element's "rack_hole" is a cut to be made, not a surface
            near = [ob for r in roots.values() if r is not root for ob in rendered(r)
                    if not ob.get("rack_hole") and overlaps(xy_box(ob), (x0, x1, y0, y1))]
            uv, ut = triangles(near, dg)
            if not len(ut):
                raise SystemExit(f"rack: {eid} is seated but nothing lies under it")
            own = BVHTree.FromPolygons(ov.tolist(), ot.tolist())
            under = BVHTree.FromPolygons(uv.tolist(), ut.tolist())
            top = float(max(ov[:, 2].max(), uv[:, 2].max())) + 1.0
            hits = []
            for i in range(9):
                for j in range(9):
                    p = Vector((x0 + (x1 - x0) * (i + 0.5) / 9, y0 + (y1 - y0) * (j + 0.5) / 9, top))
                    if own.ray_cast(p, Vector((0, 0, -1)))[0] is None:
                        continue
                    hit = under.ray_cast(p, Vector((0, 0, -1)))[0]
                    if hit is not None:
                        hits.append(hit.z)
            if not hits:
                raise SystemExit(f"rack: {eid} is seated but nothing lies under its footprint")
            surface, face = max(hits), mounting_face(root, dg)
            dz = surface - face
            if abs(dz) > 1e-7:
                root.location.z += dz
                if el.get("fit") == "diameter":
                    fit_diameter(root, el)
                elif root.get("rack_sheared"):
                    stand_on_ray(root, el)
            moved = max(moved, abs(dz))
            last[eid] = dz
            el["_seat"] = (surface, len(hits))
        if moved < 1e-6:
            break
    else:
        raise SystemExit(f"rack: seating did not settle (last moves: "
                         f"{', '.join(f'{k} {v:+.2e}' for k, v in last.items() if abs(v) > 1e-7)})")


def xy_box(ob):
    box = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return (min(p.x for p in box), max(p.x for p in box),
            min(p.y for p in box), max(p.y for p in box))


def overlaps(a, b):
    """Two (x0, x1, y0, y1) plan boxes overlap."""
    return a[0] < b[1] and a[1] > b[0] and a[2] < b[3] and a[3] > b[2]


def settle_catchers(scene, roots):
    """Each held catcher: a panel-board under its centre -> cut its apertures
    into the boards and drop it; none -> keep it as a matte surface (Cycles'
    own catcher ignores mesh emitters, which are all the rack light has)."""
    bpy.context.view_layer.update()
    plates = [ob for r in roots if r["component"] == "panel-board"
              for ob in r.children_recursive if ob.type == "MESH"]
    for cat in [o for o in scene.objects if "rack_catcher" in o and o.is_shadow_catcher
                and o.hide_render]:
        x0, x1, y0, y1 = xy_box(cat)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        boxes = [xy_box(ob) for ob in plates]
        if any(b[0] < cx < b[1] and b[2] < cy < b[3] for b in boxes):
            if "apertures" in cat:
                cut_apertures(scene, cat, plates)
            bpy.data.objects.remove(cat)
        else:
            cat.is_shadow_catcher, cat.hide_render = False, False
            cat["rack_matte"] = True
    cut_holes(scene, [[ob for ob in r.children_recursive if ob.type == "MESH"]
                      for r in roots if r["component"] in HOSTS])


def matte_split(layout, roots):
    """(matte objects, part objects): the matte elements' and kept catchers'
    objects, and every other element's."""
    elems, matte = set(), set()
    for el in layout["elements"]:
        obs = set(roots[el["id"]].children_recursive)
        elems |= obs
        if el.get("matte"):
            matte |= obs
    matte |= {o for o in elems if o.get("rack_matte")}
    return matte, elems - matte


def render_pass(scene, tmp):
    """Render to a scene-linear EXR and read it back: (h, w, 4) premultiplied."""
    import numpy as np

    s, r = scene.render.image_settings, scene.render
    saved = (s.file_format, s.color_depth, s.color_mode, r.filepath)
    s.file_format, s.color_depth, s.color_mode = "OPEN_EXR", "32", "RGBA"
    r.filepath = tmp
    bpy.ops.render.render(write_still=True)
    s.file_format, s.color_depth, s.color_mode, r.filepath = saved
    im = bpy.data.images.load(tmp)
    px = np.empty(len(im.pixels), dtype=np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(r.resolution_y, r.resolution_x, 4)


def displayed(scene, px, tmp):
    """(h, w, 4) scene-linear pixels as the output shows them: through the
    scene's view transform, display-encoded, decoded back to linear (rgb; the
    space a consumer composites the sprite in). A Raw view (an .exr OUT) is
    composited scene-linear, so it is returned as it is."""
    import numpy as np

    if scene.view_settings.view_transform == "Raw":
        return px
    im = bpy.data.images.new("rack displayed", px.shape[1], px.shape[0], alpha=True,
                             float_buffer=True)
    im.pixels.foreach_set(px.ravel())
    s = scene.render.image_settings
    saved = (s.file_format, s.color_depth, s.color_mode)
    s.file_format, s.color_depth, s.color_mode = "PNG", "16", "RGBA"
    im.save_render(f"{tmp}/displayed.png", scene=scene)
    s.file_format, s.color_depth, s.color_mode = saved
    bpy.data.images.remove(im)
    im = bpy.data.images.load(f"{tmp}/displayed.png")
    im.colorspace_settings.name = "Non-Color"
    out = np.empty(len(im.pixels), dtype=np.float32)
    im.pixels.foreach_get(out)
    bpy.data.images.remove(im)
    out = out.reshape(px.shape)
    c = out[..., :3]
    out[..., :3] = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return out


def render_matte(scene, path, matte, parts, ground):
    """The parts over a matte: F (matte held out), S (the matte with the parts'
    shadows, parts unseen by the camera) and G (the matte alone, rendered once
    into `ground`); out = F's parts, plus black at alpha 1 - S/G (luminance)
    where the matte shows, S and G taken as displayed (`displayed`): the ratio
    is the one the consumer's composite over the baked plate reproduces, which
    a scene-linear ratio is not under a tone-mapping view (AgX darkens it about
    2x on a white plate). Written through the scene's view like a render."""
    import tempfile

    import numpy as np

    tmp = tempfile.mkdtemp(prefix="rack-matte-")
    lum = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    for ob in matte:
        ob.is_holdout = True
    f = render_pass(scene, f"{tmp}/f.exr")
    for ob in matte:
        ob.is_holdout = False
    for ob in parts:
        ob.visible_camera = False
    s = render_pass(scene, f"{tmp}/s.exr")
    if "g" not in ground:
        for ob in parts:
            ob.hide_render = True
        ground["g"] = render_pass(scene, f"{tmp}/g.exr")
        ground["gd"] = displayed(scene, ground["g"], tmp)
        for ob in parts:
            ob.hide_render = False
    for ob in parts:
        ob.visible_camera = True
    g = ground["g"]
    gl, sl = ground["gd"][..., :3] @ lum, displayed(scene, s, tmp)[..., :3] @ lum
    shadow = np.where(gl > 1e-4, np.clip(1 - sl / np.maximum(gl, 1e-4), 0, 1), 0) * g[..., 3]
    out = f.copy()
    out[..., 3] = f[..., 3] + (1 - f[..., 3]) * shadow
    im = bpy.data.images.new("rack matte", scene.render.resolution_x, scene.render.resolution_y,
                             alpha=True, float_buffer=True)
    im.pixels.foreach_set(out.ravel())
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save_render(str(path), scene=scene)
    bpy.data.images.remove(im)


def cut_apertures(scene, cat, plates):
    """Cut a held catcher's apertures (a rail's slot and wells, its board
    rects at its face z_top) into the panel-board faces under them, so the
    part's wells open through the real plate instead of hiding inside it."""
    import bmesh

    m, a, z = cat.matrix_world, list(cat["apertures"]), cat["z_top"]
    for i in range(0, len(a), 4):
        x0, x1, y0, y1 = a[i:i + 4]
        lo, hi = m @ Vector((x0, y0, z - 0.2)), m @ Vector((x1, y1, z + 0.2))
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = Vector((lo.x if v.co.x < 0 else hi.x, lo.y if v.co.y < 0 else hi.y,
                           lo.z if v.co.z < 0 else hi.z))
        me = bpy.data.meshes.new("aperture cutter")
        bm.to_mesh(me)
        cutter = bpy.data.objects.new("aperture cutter", me)
        cutter["rack_cutter"] = cat["rack_catcher"]
        scene.collection.objects.link(cutter)
        cut_into(plates, cutter, (lo.x, hi.x, lo.y, hi.y))


def cut_into(plates, cutter, box):
    """A DIFFERENCE of `cutter` on every board whose xy box meets `box`; the
    cutter is hidden."""
    for ob in plates:
        bx0, bx1, by0, by1 = xy_box(ob)
        if bx0 < box[1] and bx1 > box[0] and by0 < box[3] and by1 > box[2]:
            # MANIFOLD over a triangulated board: EXACT empties the
            # board, and MANIFOLD over its n-gon face leaves a sliver
            # of face across the hole (probed by ray, pass 45)
            if "triangulate" not in ob.modifiers:
                ob.modifiers.new("triangulate", "TRIANGULATE")
            mod = ob.modifiers.new("aperture", "BOOLEAN")
            mod.operation, mod.solver, mod.object = "DIFFERENCE", "MANIFOLD", cutter
    cutter.hide_render = cutter.hide_viewport = True


def cut_holes(scene, hosts):
    """A part's hole in its host ("rack_hole": a through-mounted key's
    invisible cut, families.button host_cut) is cut into the host it lies
    over and hidden: the real host opens round the key. `hosts` holds each
    HOSTS element's meshes; a host is under the hole when a ray straight down
    at the hole's plan centre meets one of its meshes. Over none the hole
    stays as its generator made it."""
    from mathutils.bvhtree import BVHTree

    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    trees = []
    for meshes in hosts:
        v, t = triangles(meshes, dg)
        trees.append((meshes, BVHTree.FromPolygons(v.tolist(), t.tolist()) if len(t) else None,
                      float(v[:, 2].max()) + 1.0 if len(v) else 0.0))
    for hole in [o for o in scene.objects if o.get("rack_hole") and not o.hide_render]:
        x0, x1, y0, y1 = xy_box(hole)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        under = [ob for meshes, tree, top in trees if tree is not None
                 and tree.ray_cast(Vector((cx, cy, top)), Vector((0, 0, -1)))[0] is not None
                 for ob in meshes]
        if not under:
            continue
        root = hole
        while root.parent is not None and "rack_id" not in root:
            root = root.parent
        hole["rack_cutter"] = root.get("rack_id", "")
        hole.is_holdout = False
        cut_into(under, hole, (x0, x1, y0, y1))


def remove_element(scene, root):
    """Take an element out of the scene for a rebuild: its objects, and the
    apertures its catcher cut into the boards."""
    eid = root["rack_id"]
    cutters = [o for o in scene.objects if o.get("rack_cutter") == eid]
    for ob in scene.objects:
        for mod in [m for m in getattr(ob, "modifiers", []) if m.type == "BOOLEAN"
                    and m.object in cutters]:
            ob.modifiers.remove(mod)
    for ob in {*root.children_recursive, root, *cutters}:
        bpy.data.objects.remove(ob)
    bpy.data.orphans_purge(do_recursive=True)


def main():
    layout_path, out_path, o = parse(sys.argv[sys.argv.index("--") + 1:])
    layout = json.loads(layout_path.read_text())
    ppu = float(layout.get("px_per_unit", 100.0))
    place_keys(layout, ppu)
    stale = [k for k in ("centre", "span", "lit", "frame") if k in layout]
    if stale or "window" not in layout:
        raise SystemExit(f"rack: {layout_path} must give its \"window\" and nothing else for "
                         f"the rig ({', '.join(stale) or 'no window'}): centre, span and lit "
                         "come from the window")
    wx, wy, ww, wh = (float(v) for v in layout["window"])
    cx, cy = wx + ww / 2, wy + wh / 2
    o["light"] = o["light"] or layout.get("light", "rack")
    o["view"] = o["view"] or float(layout.get("view", 12.0))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    class Values:
        values = {"samples": o["samples"], "denoise": o["denoise"], "adaptive": o["adaptive"],
                  "raw": out_path.suffix == ".exr", "res": 64}

    scaffold.setup_render(scene, Values())
    world = bpy.data.worlds.new("rack placeholder")
    scene.world = world
    states = []
    if o["states"]:
        eid, flag, values = o["states"]
        for sid in eid.split(","):
            el = next((el for el in layout["elements"] if el["id"] == sid), None)
            if el is None:
                raise SystemExit(f"rack: --states names {sid}, which the layout does not hold")
            base = [str(f) for f in el.get("flags", [])]
            if flag in base:
                del base[base.index(flag):base.index(flag) + 2]
            el["flags"] = [*base, flag, values[0]]
            states.append(el)
    roots = {}
    for el in layout["elements"]:
        x, y, w, h = el["rect"]
        el["_ppu"], el["_centre"], el["_view"] = ppu, (cx, cy), o["view"]
        el["_xy"] = ((x + w / 2 - cx) / ppu, (cy - (y + h / 2)) / ppu)
        roots[el["id"]] = build_element(scene, el, el["_xy"])[1]

    def seat_and_pull(els):
        # seated after every build, then pulled (orthographic), then catchers settle
        ids = [el["id"] for el in els if el.get("z") == "seat"]
        if ids:
            seat(layout, roots, ids)
        for el in els:
            if el["id"] in ids and el.get("orthographic"):
                orthographic(roots[el["id"]], el["_view"])
        settle_catchers(scene, roots.values())

    seat_and_pull(layout["elements"])

    span = max(ww, wh) / ppu
    if o["dark"]:
        # no light at all: only what the elements emit themselves (a lit
        # title's letters, for title-bake/1's dark layer)
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        if bg is not None:
            bg.inputs["Strength"].default_value = 0.0
        world.color = (0.0, 0.0, 0.0)
    else:
        lit = (0.0, 0.0, ww / ppu, wh / ppu)
        rigs.rack_studio(scene, span, lit, o["view"], light=o["light"], local_dir=str(STUDIO),
                         **o["set"])

    rx, ry, rw, rh = o["region"] or [wx, wy, ww, wh]
    bpy.ops.object.camera_add(location=(0.0, 0.0, o["view"]))
    cam = bpy.context.object
    cam.name = "rack camera"
    wu = rw / ppu
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.sensor_width = 36.0
    cam.data.lens = o["view"] * 36.0 / wu
    cam.data.shift_x = ((rx + rw / 2 - cx) / ppu) / wu
    cam.data.shift_y = ((cy - (ry + rh / 2)) / ppu) / wu
    cam.data.clip_start, cam.data.clip_end = 0.01, 100.0 * o["view"]
    scene.camera = cam
    r = scene.render
    r.resolution_x = round(rw * o["density"])
    r.resolution_y = round(rh * o["density"])
    r.resolution_percentage = 100

    ground = {}

    def render(path, note=""):
        matte, parts = matte_split(layout, roots)
        if matte:
            render_matte(scene, path, matte, parts, ground)
            note += f" matte={len(matte)}"
        else:
            r.filepath = str(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.render.render(write_still=True)
        print(f"rack light={'dark' if o['dark'] else o['light']} set={o['set']} "
              f"denoise={o['denoise']} adaptive={o['adaptive']} raw={out_path.suffix == '.exr'} "
              f"elements={len(layout['elements'])}{note} "
              f"span={span:.3f} [frame:{r.resolution_x}x{r.resolution_y}] -> {path}", flush=True)

    if not states:
        render(out_path)
        return
    for i, v in enumerate(values):
        if i:
            for el in states:
                el["flags"][-1] = v
                remove_element(scene, roots[el["id"]])
                roots[el["id"]] = build_element(scene, el, el["_xy"])[1]
            seat_and_pull(states)
        render(Path(str(out_path).format(i=i, v=v)), f" state={eid}:{flag}={v} [{i}/{len(values)}]")


if __name__ == "__main__":
    main()
