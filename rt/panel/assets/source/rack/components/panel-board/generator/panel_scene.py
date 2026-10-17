"""panel-board generator: parametric mounting panel, any size, family materials.

  blender -b -P panel_scene.py -- OUT [flags]        flag table: ../README.md

A flat panel is one object (slot `face`); a bezel is a FRAME (slot `bezel`,
`same` = the face material) around a recessed FIELD (slot `face`). Fastener
heads take slot `fastener`. Every slot takes any matlib key.

A backlit TITLE (`--title`, pass 41) is cut THROUGH the face: each letter an
opening in the panel's own material, a smoked acrylic insert (slot `insert`)
just below the surface and a light behind every letter; unlit, the letters
read dark in the metal. A lit
letter differs from an unlit one only in its insert's emission, so a lit panel
is exactly the unlit render plus each letter's own light: `--title-lit` picks
the set and `--dark` (the rig off) renders one letter's light alone, a bake
layer. Letters are spaced optically (textkit.optical_word).

Studio: rigs.knob_studio at scale max(w, h), framed by rigs.panel_camera.
Blender exits 0 after a script exception: callers check OUT and the receipt line.
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
import meshlib  # noqa: E402
import textkit  # noqa: E402
from families import ComponentScene, Flag  # noqa: E402
from scaffold import SWITCH  # noqa: E402

TH = 0.16          # panel / frame thickness
BEZEL_IN = 0.17    # bezel frame width (how far the raised rim reaches in)
RECESS = 0.06      # how far the field sits below the frame top
TITLE_RECESS = 0.002   # the title inserts' top below the face (0.2 logical px)


def lit_value(text):
    """all | none | comma-separated 1-based letter indices."""
    text = text.strip().lower()
    if text in ("all", "none"):
        return text
    try:
        idx = sorted({int(t) for t in text.split(",") if t.strip()})
    except ValueError:
        raise SystemExit(f"--title-lit {text!r}: all | none | 1-based letter indices")
    return ",".join(map(str, idx)) if idx else "none"

# CCW quarter-turns that bring each edge to the TOP, and whether `pos` is flipped
# so 0->1 reads left->right (top/bottom) or bottom->top (left/right) on every edge.
_TAB_TURNS = {"top": 0, "right": 1, "bottom": 2, "left": 3}
_TAB_FLIP = {"top": False, "right": True, "bottom": True, "left": False}


def _rot90(pts, k):
    """Rotate a loop k quarter-turns CCW: (x, y) -> (-y, x)."""
    for _ in range(k % 4):
        pts = [(-y, x) for (x, y) in pts]
    return pts


def tabbed_loop(hx, hy, r, n, edge="top", pos=0.5, width=0.0, depth=0.22):
    """superellipse_loop with a file-folder TAB spliced into one edge's straight
    run: one closed CCW polygon, so extrude, bevel and brush UV need nothing
    extra. The sides leave the base straight at the taper angle; only the top
    corners round. `pos` 0..1 along the edge, `width`/`depth` world units;
    width <= 0 returns the plain loop."""
    pts = meshlib.superellipse_loop(hx, hy, r, n)
    if width <= 1e-4 or depth <= 1e-4:
        return pts
    k = _TAB_TURNS.get(edge, 0)
    if _TAB_FLIP.get(edge, False):
        pos = 1.0 - pos
    pts = _rot90(pts, k)

    ytop = max(p[1] for p in pts)
    idx = None
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        if abs(p[1] - ytop) < 1e-6 and abs(q[1] - ytop) < 1e-6 and p[0] > q[0]:
            idx = i
            break
    if idx is None:                            # fully-rounded edge: no flat run
        return _rot90(pts, -k)
    xr, xl = pts[idx][0], pts[(idx + 1) % len(pts)][0]

    run = xr - xl
    w = min(width, run * 0.92)
    xc = xl + run * min(max(pos, 0.0), 1.0)
    xc = min(max(xc, xl + w / 2), xr - w / 2)
    x0, x1 = xc + w / 2, xc - w / 2
    taper = min(depth * 0.14, w * 0.22)
    yt = ytop + depth
    rad = min(depth * 0.18, w * 0.13)

    A, B, C, D = (x0, ytop), (x0 - taper, yt), (x1 + taper, yt), (x1, ytop)
    tab = [A] + meshlib.fillet_corner(A, B, C, rad) + meshlib.fillet_corner(B, C, D, rad) + [D]

    pts = pts[:idx + 1] + tab + pts[idx + 1:]
    return _rot90(pts, -k)


def raw_box(hx, hy, hz, cz, name):
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, cz))
    ob = bpy.context.object
    ob.name = name
    ob.scale = (hx, hy, hz)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(scale=True)
    return ob


def raw_rounded(hx, hy, hz, cz, name, loop):
    """Extruded prism of a CCW (x, y) loop via bmesh."""
    bm = bmesh.new()
    verts = [bm.verts.new((x, y, cz - hz)) for (x, y) in loop]
    bottom = bm.faces.new(verts)
    res = bmesh.ops.extrude_face_region(bm, geom=[bottom])
    top = [v for v in res["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, 2 * hz))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def placed_box(hx, hy, hz, loc, name):
    """Placed cube (the fastener boolean cutters)."""
    bpy.ops.mesh.primitive_cube_add(location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = (hx, hy, hz)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(scale=True)
    return ob


class PanelBoard(ComponentScene):
    COMPONENT = "panel-board"
    DEFAULT_OUT = "/tmp/panel.png"
    RES = 512
    SAMPLES = 240
    SCALE_SUPPORTED = False
    SLOTS = {"face": "brushed", "bezel": "same", "fastener": "steel-hw",
             "thread": "thread-waxed-cream", "insert": "acrylic-smoke"}
    SLOT_SAME = {"bezel": "face"}
    SLOT_HELP = {
        "face": "flat panel, or the recessed field of a bezel",
        "bezel": "bezel frame material (`--edge bezel`)",
        "fastener": "screw / rivet head material",
        "thread": "saddle-stitch thread (`--stitch saddle`)",
        "insert": "the backlit title's letter inserts (`--title`; an acrylic key)",
    }
    ALIASES = {"face": ["--material"], "bezel": ["--bezel-material"]}
    FLAGS = (
        Flag("--w", float, 3.0, help="panel width, world units"),
        Flag("--h", float, 2.0, help="panel height, world units"),
        Flag("--edge", str, "flat", choices=("flat", "bezel"),
             help="bezel = raised frame + recessed field"),
        Flag("--fasteners", str, "screws", choices=("none", "screws", "rivets"),
             help="slotted screw heads or rivet domes at the corners"),
        Flag("--corner", float, 0.0, help="corner radius; 0 = sharp"),
        Flag("--corner-n", float, 4.0, help="superellipse exponent: 2 circular, 4 squircle"),
        Flag("--tab", float, 0.0, help="folder tab width; 0 = none"),
        Flag("--tab-depth", float, 0.22, help="folder tab protrusion"),
        Flag("--tab-pos", float, 0.5,
             help="0..1 along the edge (left->right, bottom->top), clamped to the flat run"),
        Flag("--tab-edge", str, "top", choices=("top", "bottom", "left", "right"),
             help="edge the tab stands off"),
        Flag("--oxidization", float, -1.0,
             help="scalar character knob of keys that have one (verdigris); -1 = key preset"),
        Flag("--bevel", float, 0.04,
             help="edge bevel width, world units (panel and bezel frame); "
                  "0.04 / 6 is the slightly rounded default (pass 38)"),
        Flag("--bevel-segments", int, 6,
             help="bevel segments; 2 = a faceted chamfer, 6+ reads as a rounded edge"),
        Flag("--stitch", str, "none", choices=("none", "saddle"),
             help="saddle: waxed saddle stitching inset from the outline (flat) or "
                  "along the bezel frame's midline (bezel)"),
        Flag("--stitch-inset", float, 0.14,
             help="stitch line inset from the outer edge, world units (flat edge)"),
        Flag("--stitch-pitch", float, 0.11, help="stitch pitch, world units"),
        Flag("--title", str, "", help="backlit title cut through the face; one light per letter"),
        Flag("--title-font", str, "mono-bold", choices=tuple(textkit.FONTS),
             help="the title's bundled face"),
        Flag("--title-cap", float, 0.10, help="title cap height, world units (0.01 = 1 logical px)"),
        Flag("--title-gap", float, 0.026,
             help="optical gap between title letters, world units: every pair's mean whitespace"),
        Flag("--title-top", float, 0.23, help="title centre below the panel's top edge, world units"),
        Flag("--title-lit", lit_value, "all", help="lit title letters: all | none | i,j,... (1-based)"),
        Flag("--title-emit", float, 1.0,
             help="a lit letter's backlight: white emission (a bake layer's unit)"),
        Flag("--dark", SWITCH, help="bake: the rig off; only the lit title letters' light"),
        Flag("--tilt", float, 0.0, help="camera downward tilt, deg; 0 = dead-on"),
        Flag("--handled", float, 0.0,
             help="finish: smudge and wipe vary the face's gloss by this share of its roughness"),
        Flag("--tarnish", float, 0.0, help="finish: uneven tarnish blotches, up to this darkening"),
        Flag("--scratches", float, 0.0,
             help="finish: hairline polishing scratches, up to this added roughness"),
        Flag("--undulate", float, 0.0,
             help="finish: a slow hand-finished swell on the face (and its coat), this strength"),
        Flag("--ortho-px", float, 0.0,
             help="the product view: dead-on orthographic at N px per world unit, the frame "
                  "the silhouette (overrides --res); 0 = the canon camera"),
    )

    # ------------------------------------------------------------- geometry
    @property
    def has_tab(self):
        return self.args.tab > 1e-4 and self.args.tab_depth > 1e-4

    def raw(self, hx, hy, hz, cz, name, r, tab=False):
        # a tab needs the bmesh path even on a sharp rectangle
        a = self.args
        if r > 1e-4 or tab:
            loop = (tabbed_loop(hx, hy, r, a.corner_n, a.tab_edge, a.tab_pos, a.tab, a.tab_depth)
                    if tab else meshlib.superellipse_loop(hx, hy, r, a.corner_n))
            return raw_rounded(hx, hy, hz, cz, name, loop)
        return raw_box(hx, hy, hz, cz, name)

    @staticmethod
    def inner_r(r):
        return max(r - BEZEL_IN, 0.0) if r > 1e-4 else 0.0

    def finish(self, ob):
        """meshlib.finish at --bevel. Auto-smooth stays at 20 deg, below a
        segment's facet angle (90 / segments) up to 4 segments, so 2 reads as a
        chamfer and 5+ smooths into a round."""
        a = self.args
        return meshlib.finish(ob, bevel_w=a.bevel, segments=a.bevel_segments)

    def build_plate(self):
        a = self.args
        return self.finish(self.raw(a.w / 2, a.h / 2, TH / 2, 0.0, "panel", a.corner,
                                    tab=self.has_tab))

    def build_frame(self):
        """Outer solid minus a through window; the tab belongs to the outer
        profile only."""
        a = self.args
        frame = self.raw(a.w / 2, a.h / 2, TH / 2, 0.0, "bezel", a.corner, tab=self.has_tab)
        win = self.raw(a.w / 2 - BEZEL_IN, a.h / 2 - BEZEL_IN, TH, 0.0, "win",
                       self.inner_r(a.corner))
        mod = frame.modifiers.new("window", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = win
        mod.solver = "EXACT"
        bpy.context.view_layer.objects.active = frame
        bpy.ops.object.modifier_apply(modifier="window")
        bpy.data.objects.remove(win)
        return self.finish(frame)

    def build_field(self):
        """The recessed working surface, oversized to tuck under the frame lip."""
        a = self.args
        fhx = a.w / 2 - BEZEL_IN + 0.02
        fhy = a.h / 2 - BEZEL_IN + 0.02
        fth = TH * 0.7
        top = TH / 2 - RECESS
        return meshlib.finish(self.raw(fhx, fhy, fth / 2, top - fth / 2, "field",
                                       self.inner_r(a.corner)))

    def add_screw(self, x, y, z_top, r=0.055):
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=r, depth=0.03,
                                            location=(x, y, z_top - 0.006))
        head = bpy.context.object
        bpy.ops.object.shade_auto_smooth(angle=math.radians(30))
        slot = placed_box(r * 1.15, r * 0.16, 0.02, (x, y, z_top + 0.004), "slot")
        mod = head.modifiers.new("slot", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = slot
        mod.solver = "EXACT"
        bpy.context.view_layer.objects.active = head
        bpy.ops.object.modifier_apply(modifier="slot")
        bpy.data.objects.remove(slot)
        self.bind("fastener", [head])
        head.select_set(False)

    def add_rivet(self, x, y, z_top, r=0.05):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(x, y, z_top))
        dome = bpy.context.object
        dome.scale = (1, 1, 0.45)
        bpy.context.view_layer.objects.active = dome
        bpy.ops.object.transform_apply(scale=True)
        cut = placed_box(r * 4, r * 4, 0.5, (x, y, z_top - 0.5), "rcut")
        mod = dome.modifiers.new("half", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = cut
        mod.solver = "EXACT"
        bpy.context.view_layer.objects.active = dome
        bpy.ops.object.modifier_apply(modifier="half")
        bpy.data.objects.remove(cut)
        bpy.ops.object.shade_smooth()
        self.bind("fastener", [dome])
        dome.select_set(False)

    def add_stitching(self, z_top):
        """Saddle stitching (stitchkit) on the outline inset by --stitch-inset,
        or on a bezel frame's midline. The tab is not followed: a stitch line
        runs the panel's body."""
        import stitchkit

        a = self.args
        inset = BEZEL_IN / 2.0 if a.edge == "bezel" else a.stitch_inset
        hx, hy = a.w / 2 - inset, a.h / 2 - inset
        if hx <= 0 or hy <= 0:
            raise SystemExit("panel-board: --stitch-inset leaves no panel to stitch")
        loop = meshlib.superellipse_loop(hx, hy, max(a.corner - inset, 0.0), a.corner_n)
        thread = stitchkit.saddle_stitches(loop, z_top, pitch=a.stitch_pitch)
        self.bind("thread", [thread])

    # ---------------------------------------------------------------- scene
    def add_title(self, host, z_face):
        """Cut --title through `host` (the face) and set an acrylic insert
        TITLE_RECESS below the face in every letter, lit per --title-lit.
        Returns the inserts, left to right. (No chamfer: at 10 px caps a 45 deg
        facet only glints the rig's lights as sparkle, p128.)"""
        a = self.args
        font = textkit.load_font(a.title_font)
        y = a.h / 2 - a.title_top
        cutters, span = textkit.optical_word("title cut", a.title, font, a.title_cap,
                                             z_face - TH - 0.05, z_face + 0.05, a.title_gap,
                                             at=(0.0, y))
        if span > a.w - 0.2:
            raise SystemExit(f"{self.COMPONENT}: --title spans {span:.3f}, the panel is {a.w:g}")
        bpy.context.view_layer.update()
        tool = cutters[0]
        with bpy.context.temp_override(active_object=tool, selected_editable_objects=cutters):
            bpy.ops.object.join()
        textkit.cut_text(host, tool)
        # the cut leaves the face as large smooth n-gons whose boundary corners
        # average in tilted neighbours (8 deg): brushed reads the tilt as its
        # satin edge and the triangulation spreads it into a diagonal seam
        # (p130). The face is flat, so it shades flat.
        for p in host.data.polygons:
            if p.normal.z > 0.999:
                p.use_smooth = False
        inserts, _ = textkit.optical_word("title", a.title, font, a.title_cap,
                                          z_face - TH * 0.9, z_face - TITLE_RECESS,
                                          a.title_gap, at=(0.0, y))
        n = len(a.title)
        lit = (set(range(1, n + 1)) if a.title_lit == "all" else set() if a.title_lit == "none"
               else {int(i) for i in a.title_lit.split(",")})
        if not lit <= set(range(1, n + 1)):
            raise SystemExit(f"--title-lit: letters are 1..{n}")
        for i, ob in enumerate(inserts, 1):
            level = a.title_emit if i in lit else 0.0
            self.bind("insert", [ob], params={"level": level}, state="lit" if level else "dark")
        self.notes.append(f"[title:{a.title} span:{span:.3f} lit:"
                          f"{','.join(map(str, sorted(lit))) or 'none'}]")
        return inserts

    def build(self):
        self.build_scene()
        if self.args.ortho_px > 0:
            self.frame_ortho(self.args.ortho_px)

    def frame_ortho(self, px):
        """The product view: the camera dead-on and ORTHOGRAPHIC, centred on
        the silhouette (tab included), the width filling the frame at `px`
        pixels per world unit."""
        a = self.args
        if a.tilt != 0.0:
            raise SystemExit(f"{self.COMPONENT}: --ortho-px is the dead-on view (--tilt 0)")
        tab = a.tab_depth if self.has_tab else 0.0
        if tab and a.tab_edge != "top":
            raise SystemExit(f"{self.COMPONENT}: --ortho-px frames top tabs only")
        cam = self.scene.camera
        cam.data.type = "ORTHO"
        cam.data.sensor_fit = "HORIZONTAL"
        cam.data.ortho_scale = a.w
        cam.data.clip_start, cam.data.clip_end = 0.01, 100.0 * max(a.w, a.h)
        cam.location = (0.0, tab / 2.0, 20.0 * max(a.w, a.h))
        cam.rotation_euler = (0.0, 0.0, 0.0)
        r = self.scene.render
        r.resolution_x, r.resolution_y = round(a.w * px), round((a.h + tab) * px)
        r.resolution_percentage = 100
        self.notes.append(f"[ortho:{r.resolution_x}x{r.resolution_y} {px:g}px/unit]")

    def finish_face(self, mat):
        """The face's finish layers (matlib.finishes): its clear coat always
        lies on its relief; --handled, --tarnish, --scratches, --undulate."""
        from matlib import finishes

        a = self.args
        nt = mat.node_tree
        for b in finishes.principled(mat):
            if a.tarnish:
                finishes.tarnished(nt, b, a.tarnish)
            if a.scratches:
                finishes.scratched(nt, b, a.scratches)
            if a.handled:
                finishes.handled(nt, b, a.handled)
            finishes.coat_follows(nt, b)
            if a.undulate:
                finishes.undulated(nt, b, a.undulate)

    def build_scene(self):
        import rigs

        a = self.args
        oxid = a.oxidization if a.oxidization >= 0.0 else None
        if a.edge == "bezel":
            frame = self.build_frame()
            field = self.build_field()
            if a.title:
                self.add_title(field, TH / 2 - RECESS)
            self.bind("face", [field], scalar=oxid)
            self.bind("bezel", [frame], scalar=oxid)
            frame.select_set(False)
            field.select_set(False)
        else:
            panel = self.build_plate()
            if a.title:
                self.add_title(panel, TH / 2)
            self.bind("face", [panel], scalar=oxid)
            panel.select_set(False)
        self.finish_face(self.materials["face"])

        z_top = TH / 2
        # Bezel fasteners sit mid-rim, between the field and outer corners' 45 deg
        # points (r*2^(-1/n) from the arc centre); flat panels take a corner margin.
        if a.fasteners in ("screws", "rivets"):
            k = 1 - 2 ** (-1 / a.corner_n)
            if a.edge == "bezel":
                r_in = self.inner_r(a.corner)
                mx = ((a.w / 2 - a.corner * k) + (a.w / 2 - BEZEL_IN - r_in * k)) / 2
                my = ((a.h / 2 - a.corner * k) + (a.h / 2 - BEZEL_IN - r_in * k)) / 2
            else:
                inset = max(0.16, a.corner * 0.72 + 0.03)
                mx, my = a.w / 2 - inset, a.h / 2 - inset
            placer = self.add_screw if a.fasteners == "screws" else self.add_rivet
            for x, y in [(sx * mx, sy * my) for sx in (-1, 1) for sy in (-1, 1)]:
                placer(x, y, z_top)

        if a.stitch == "saddle":
            self.add_stitching(z_top)

        if a.dark:
            if not a.title:
                raise SystemExit(f"{self.COMPONENT}: --dark is a --title bake layer")
            world = bpy.data.worlds.new("dark")
            world.use_nodes = True
            world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
            self.scene.world = world
            rigs.panel_camera(self.scene, a.w, a.h, a.tilt,
                              a.tab_edge if self.has_tab else None, a.tab_depth)
            self.notes.append("[studio:dark]")
            return
        # knob_studio is scale-invariant, so at the panel's span it lights the
        # panel as it lights a 1-unit part.
        rigs.knob_studio(self.scene, scale=max(a.w, a.h), local_dir=HERE, camera=False,
                         stops=rigs.PANEL_STOPS)
        rigs.panel_camera(self.scene, a.w, a.h, a.tilt,
                          a.tab_edge if self.has_tab else None, a.tab_depth)


if __name__ == "__main__":
    PanelBoard.main()
