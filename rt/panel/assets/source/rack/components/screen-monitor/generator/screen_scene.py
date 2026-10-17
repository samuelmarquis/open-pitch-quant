"""screen-monitor generator: the physical HOUSING of an in-vivo monitor.

  blender -b -P screen_scene.py -- --outdir DIR --sid screen-crt --style crt \
      --bezel beige-plastic --hue green-mono          flag table: ../README.md

Bakes the housing half of design-lab/shader-demo/SCREEN-TREATMENT.md as three
pre-registered layers plus a manifest in the output directory (`--outdir`, else
OUT, default /tmp/screen): <sid>_bezel.png, <sid>_refl.png, <sid>_vig.png,
<sid>.json.

  pass 1 bezel  frame + fasteners on transparent film under the house rig
                (rigs.knob_studio at the frame's width, PANEL_STOPS)
  pass 2 refl   the glass alone (slot `window`) mirroring the same house rig —
                its zenith scrim, emitters and world — through a Light-Path
                camera-black world, on black, then scaled by REFL_GAIN in
                linear light
  pass 3 vig    white diffuse glass occluded by a black bezel under a uniform
                white world (a mask, not a lit look)

Aperture mode (`--aperture X,Y,W,H`) inverts the geometry solve; a solve that
does not land the requested pixels raises before any file is written. Blender
exits 0 after a script exception: callers check the manifest and the receipt.
"""

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
import meshlib  # noqa: E402
import rigs  # noqa: E402
import scaffold  # noqa: E402
from families.base import Flag  # noqa: E402
from families.display import DisplayScene  # noqa: E402

OUT_W = 3.2                  # frame world width in both solves: bevel, screw and
                             # imperfect() noise scales stay the same object;
                             # also the house rig's scale. Every other size is
                             # a world size (1 world unit = 100 logical px =
                             # 25 mm, panel-board's): lcd th 0.12 = 3 mm, crt
                             # 0.22 = 5.5 mm, whatever the frame's width
REFL_GAIN = 1 / 3            # the reflection layer's level, display-linear (p211 C)
STYLE = {  # style -> defaults
    "crt": dict(th=0.22, bulge=0.09, cr=0.34, bw=0.30, corner_n=4.0, overscan=0.02,
                palette="green-mono", bow=0.09, peak=4.0, k1=0.06, k2=0.015),
    "lcd": dict(th=0.12, bulge=0.0, cr=0.12, bw=0.17, corner_n=3.0, overscan=0.0,
                palette="lcd-color", bow=0.05, peak=1.0, k1=0.0, k2=0.0),
}


class Geo:
    """The solved housing: world sizes, pixel aperture and pass constants."""

    def __init__(self, a, out_w=OUT_W):
        st = STYLE[a.style]
        self.out_w = out_w
        self.res_x, self.res_y = scaffold.res_size(a.res)
        self.th = st["th"]
        self.bulge = st["bulge"]
        self.corner_n = st["corner_n"] if a.corner_n is None else a.corner_n
        if a.aperture is None:
            if a.margin is not None:
                raise SystemExit("--margin is aperture-mode only: the legacy solve's margin is "
                                 "VIEW_W = OUT_W*1.05, a fraction of each dimension")
            self.bw = st["bw"]
            self.out_h = out_w * self.res_y / self.res_x
            self.view_w = out_w * 1.05
            self.ppu = self.res_x / self.view_w
            self.ghw = out_w / 2 - self.bw
            self.ghh = self.out_h / 2 - self.bw
            self.win_cx = self.win_cy = 0.0
        else:
            req = tuple(int(v) for v in a.aperture.split(","))
            rx, ry, rw, rh = req
            margin = a.margin or 0
            self.ppu = (self.res_x - 2 * margin) / out_w
            self.view_w = self.res_x / self.ppu
            self.out_h = (self.res_y - 2 * margin) / self.ppu
            self.ghw, self.ghh = rw / (2 * self.ppu), rh / (2 * self.ppu)
            self.win_cx = (rx + rw / 2 - self.res_x / 2) / self.ppu
            self.win_cy = -(ry + rh / 2 - self.res_y / 2) / self.ppu
            bands = {"left": rx - margin, "right": self.res_x - margin - (rx + rw),
                     "top": ry - margin, "bottom": self.res_y - margin - (ry + rh)}
            for side, px in bands.items():
                if px <= 0:
                    raise SystemExit(
                        f"APERTURE SOLVE FAILED: {side} bezel band is {px} px, must be > 0 "
                        f"(aperture {rx},{ry} {rw}x{rh}, margin {margin}, res {a.res})")
            self.bw = min(bands.values()) / self.ppu
        self.glass_cr = st["cr"] if a.corner_r is None else float(a.corner_r) / self.ppu
        # only modestly larger than the aperture radius: a big outer radius widens
        # the rim at the corners and drags the rim midpoint (the screws) inland
        self.outer_r = self.glass_cr + self.bw * 0.4
        self.ap_w = round(2 * self.ghw * self.ppu)
        self.ap_h = round(2 * self.ghh * self.ppu)
        self.ap_x = round(self.res_x / 2 + self.win_cx * self.ppu - self.ap_w / 2)
        self.ap_y = round(self.res_y / 2 - self.win_cy * self.ppu - self.ap_h / 2)
        self.corner_r_px = round(self.glass_cr * self.ppu)
        if a.aperture is not None and (self.ap_x, self.ap_y, self.ap_w, self.ap_h) != req:
            raise SystemExit(f"APERTURE SOLVE FAILED: requested {rx},{ry} {rw}x{rh}, solved "
                             f"{self.ap_x},{self.ap_y} {self.ap_w}x{self.ap_h}; no files written")
        if a.corner_r is not None and self.corner_r_px != round(float(a.corner_r)):
            raise SystemExit(f"APERTURE SOLVE FAILED: requested corner r{a.corner_r}, solved "
                             f"r{self.corner_r_px}; no files written")
        self.k1, self.k2 = st["k1"], st["k2"]
        self.overscan = st["overscan"] if a.overscan is None else a.overscan
        self.palette = st["palette"] if a.hue is None else a.hue
        self.glare_radius_px = round(a.bloom_size * self.res_x)
        self.refl_bow = st["bow"] if a.bow is None else a.bow
        self.peak = st["peak"] if a.peak is None else a.peak


# ------------------------------------------------------------------ geometry
def prism(loop, hz, cz, name, cx=0.0, cy=0.0):
    bm = bmesh.new()
    vs = [bm.verts.new((cx + x, cy + y, cz - hz)) for (x, y) in loop]
    f = bm.faces.new(vs)
    res = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [v for v in res["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, 2 * hz))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def build_bezel(g):
    """Rounded frame: outer superellipse solid minus the aperture window, bevelled,
    with a cube-projected `brush` UV for anisotropic bezel materials."""
    loop = lambda hx, hy, r: meshlib.superellipse_loop(hx, hy, r, g.corner_n, seg=22)  # noqa: E731
    frame = prism(loop(g.out_w / 2, g.out_h / 2, g.outer_r), g.th / 2, 0, "bezel")
    win = prism(loop(g.ghw, g.ghh, g.glass_cr), g.th, 0, "win", g.win_cx, g.win_cy)
    mod = frame.modifiers.new("w", "BOOLEAN")
    mod.operation, mod.object, mod.solver = "DIFFERENCE", win, "EXACT"
    bpy.context.view_layer.objects.active = frame
    bpy.ops.object.modifier_apply(modifier="w")
    bpy.data.objects.remove(win)
    bev = frame.modifiers.new("b", "BEVEL")
    bev.width, bev.segments, bev.limit_method, bev.angle_limit = 0.012, 2, "ANGLE", math.radians(30)
    bpy.ops.object.modifier_apply(modifier="b")
    uv = frame.data.uv_layers.get("brush") or frame.data.uv_layers.new(name="brush")
    frame.data.uv_layers.active = uv
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=1.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_auto_smooth(angle=math.radians(20))
    return frame


def build_glass(g, bulge=None, roll=1.0, peak=1.0):
    """Glass filling the aperture, recessed 0.03 behind the bezel front: a 96x96
    grid domed z = b*(1 - t^roll)^peak, t = (u^2 + v^2)/2 (b = the style bulge
    unless `bulge`). Under the ortho camera a glass point (x, y) mirrors the
    source-plane point Y = y*m(t), m = 1 + 2*b*L*(-f'(t))/GHH^2 >= 1 (L = the
    source plane's height over the glass: the house zenith scrim's): the
    paraboloid (roll = peak = 1) bends nothing; peak > 1 bends a straight edge
    into a U, roll > 1 into an arch."""
    b = g.bulge if bulge is None else bulge
    n = 96
    z0 = g.th / 2 - 0.03
    bm = bmesh.new()
    grid = []
    for iy in range(n + 1):
        row = []
        for ix in range(n + 1):
            u, v = ix / n * 2 - 1, iy / n * 2 - 1
            t = min(1.0, (u * u + v * v) / 2)
            dome = b * (1.0 - t ** roll) ** peak if b else 0.0
            row.append(bm.verts.new((g.win_cx + u * g.ghw, g.win_cy + v * g.ghh, z0 + dome)))
        grid.append(row)
    for iy in range(n):
        for ix in range(n):
            bm.faces.new((grid[iy][ix], grid[iy][ix + 1], grid[iy + 1][ix + 1], grid[iy + 1][ix]))
    me = bpy.data.meshes.new("glass")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("glass", me)
    bpy.context.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.shade_smooth()
    return ob


def fastener_heads(g, kind):
    """Corner heads centred on the rim, midway between the aperture corner and the
    exterior corner along the diagonal (a superellipse-n corner's 45 deg point is
    r*2^(-1/n) from its arc centre); slotted when `screws`."""
    if kind not in ("screws", "rivets"):
        return []
    k = 1 - 2 ** (-1 / g.corner_n)
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            ax, ay = g.win_cx + sx * (g.ghw - g.glass_cr * k), g.win_cy + sy * (g.ghh - g.glass_cr * k)
            ex, ey = sx * (g.out_w / 2 - g.outer_r * k), sy * (g.out_h / 2 - g.outer_r * k)
            x, y = (ax + ex) / 2, (ay + ey) / 2
            r = 0.05
            bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=r, depth=0.03,
                                                location=(x, y, g.th / 2 - 0.004))
            head = bpy.context.object
            bpy.ops.object.shade_auto_smooth(angle=math.radians(30))
            if kind == "screws":
                bpy.ops.mesh.primitive_cube_add(location=(x, y, g.th / 2 + 0.006))
                slot = bpy.context.object
                slot.scale = (r * 1.15, r * 0.16, 0.02)
                bpy.context.view_layer.objects.active = slot
                bpy.ops.object.transform_apply(scale=True)
                mm = head.modifiers.new("s", "BOOLEAN")
                mm.operation, mm.object, mm.solver = "DIFFERENCE", slot, "EXACT"
                bpy.context.view_layer.objects.active = head
                bpy.ops.object.modifier_apply(modifier="s")
                bpy.data.objects.remove(slot)
            out.append(head)
    return out


# ------------------------------------------------------------------- studio
def house(scene):
    """The house rig over the housing: rigs.knob_studio at the frame's width,
    no camera, at PANEL_STOPS (a bezel is a flat face, lit as panel-board lights
    its plate). The bezel pass and the reflection pass share it: the glass
    mirrors the room the bezel is lit in."""
    return rigs.knob_studio(scene, scale=OUT_W, local_dir=HERE, camera=False,
                            stops=rigs.PANEL_STOPS)


def camera_black(world):
    """Light Path `Is Camera Ray` mixes a black Background (camera) over the
    world (every other ray), so the reflection layer is the glass's own
    reflection on black and every pixel with no reflector under it stays 0."""
    nt = world.node_tree
    wn, links = nt.nodes, nt.links
    out = wn["World Output"]
    room = out.inputs["Surface"].links[0].from_socket
    black = wn.new("ShaderNodeBackground")
    black.inputs["Color"].default_value = (0, 0, 0, 1)
    black.inputs["Strength"].default_value = 0.0
    lp = wn.new("ShaderNodeLightPath")
    mix = wn.new("ShaderNodeMixShader")
    links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    links.new(room, mix.inputs[1])
    links.new(black.outputs["Background"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return world


def scale_layer(path, gain):
    """The PNG at `path` times `gain` in linear light (sRGB decoded, scaled,
    re-encoded), alpha untouched."""
    import numpy as np

    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = "Non-Color"
    px = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(px)
    c = px.reshape(-1, 4)[:, :3]
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4) * gain
    c[:] = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.maximum(lin, 0) ** (1 / 2.4) - 0.055)
    img.pixels.foreach_set(px)
    img.filepath_raw, img.file_format = str(path), "PNG"
    img.save()
    bpy.data.images.remove(img)


def white_world(scene):
    """A uniform white world at strength 1: the vignette mask's light."""
    world = bpy.data.worlds.new("white")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (1, 1, 1, 1)
    bg.inputs["Strength"].default_value = 1.0
    return world


def ortho_cam(scene, g, z=6.0):
    """Dead-on ORTHOGRAPHIC camera framing view_w."""
    bpy.ops.object.camera_add(location=(0, 0, z), rotation=(0, 0, 0))
    cam = bpy.context.object
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = g.view_w
    scene.camera = cam
    return cam


class ScreenMonitor(DisplayScene):
    COMPONENT = "screen-monitor"
    DEFAULT_OUT = "/tmp/screen"
    SAMPLES = 220
    RES = "1024x768"
    RES_WXH = True
    SLOTS = {"bezel": "beige-plastic", "fastener": "steel-hw", "window": "window-dark"}
    SLOT_HELP = {
        "bezel": "bezel frame material",
        "fastener": "corner screw / rivet head material",
        "window": "glass of the reflection pass",
    }
    ALIASES = {"bezel": ["--bezel-material"], "hue": ["--palette"]}
    BLOOM_SIZE = 0.03
    BLOOM_STRENGTH = 1.0
    # a composer's frame width, world units (rack.py "fit": "width" sets it
    # to the rect's): build() makes the housing at that width, its
    # thickness, bevel and fasteners at their own world sizes, instead of at
    # OUT_W for the composer to scale every axis by
    fit_width = None
    UNSUPPORTED = ("emit", "bloom", "bloom-threshold", "fill")
    FLAG_HELP = {
        "hue": "manifest palette_default; default green-mono (crt) / lcd-color (lcd)",
        "bloom-size": "manifest glare.radius as a fraction of the layer width",
        "bloom-strength": "manifest glare.strength: the runtime's gain on refl (1 = identity)",
    }
    FLAGS = (
        Flag("--outdir", str, None, help="output directory (wins over OUT)"),
        Flag("--sid", str, "screen-crt", help="screen id: file stem and manifest id"),
        Flag("--style", str, "crt", choices=("crt", "lcd"),
             help="crt = domed glass, barrel warp, chunky bezel; lcd = flat, identity warp"),
        Flag("--fasteners", str, "screws", choices=("none", "screws", "rivets"),
             help="slotted heads, domes, or none"),
        Flag("--aperture", str, None, help="X,Y,W,H px: inverse solve onto exactly these pixels"),
        Flag("--margin", int, None, help="aperture mode only: uniform px border outside the frame"),
        Flag("--corner-r", float, None, help="glass corner radius, px; default the style's world constant"),
        Flag("--corner-n", float, None, help="superellipse exponent; default 4 (crt) / 3 (lcd)"),
        Flag("--overscan", float, None, help="manifest overscan; default 0.02 (crt) / 0 (lcd)"),
        Flag("--coat-rough", float, None, help="window coat roughness (the key's coat_rough)"),
        Flag("--bow", float, None, help="reflection-pass dome height; default 0.09 (crt) / 0.05 (lcd)"),
        Flag("--roll", float, 1.0, help="dome profile exponent: > 1 curvature at the rim"),
        Flag("--peak", float, None, help="dome profile exponent: > 1 curvature in the centre; "
                                         "default 4 (crt) / 1 (lcd)"),
    )

    @classmethod
    def schema(cls):
        s = super().schema()
        s.flags["--res"].help = "layer size, px"
        return s

    def validate(self):
        super().validate()
        if self.args.raw:
            raise SystemExit(f"{self.COMPONENT}: --raw is not supported (PNG layers)")

    @property
    def outdir(self):
        return Path(self.args.outdir) if self.args.outdir is not None else self.args.out

    def receipt(self):
        head, _, _ = super().receipt().rpartition(" -> ")
        return f"{head} -> {self.outdir}"

    def layer_pass(self, g, film_transparent):
        return self.new_pass(film_transparent)

    def build(self):
        """The housing as geometry in the current scene — the bezel and its
        fasteners — for a composed panel (_studio/rack.py), which brings its own
        light and camera. The aperture stays open: the screen and its glass
        reflection are the consumer's runtime layers (run()'s refl and vig
        bakes), as they are on the product."""
        a = self.args
        g = Geo(a, OUT_W if self.fit_width is None else self.fit_width)
        frame = build_bezel(g)
        self.bind("bezel", [frame])
        for head in fastener_heads(g, a.fasteners):
            self.bind("fastener", [head])
        return frame

    def run(self):
        a = self.args
        g = Geo(a)
        out = self.outdir
        out.mkdir(parents=True, exist_ok=True)

        # pass 1: bezel, transparent aperture and surround
        scene = self.layer_pass(g, True)
        frame = build_bezel(g)
        self.bind("bezel", [frame])
        for head in fastener_heads(g, a.fasteners):
            self.bind("fastener", [head])
        house(scene)
        ortho_cam(scene, g)
        self.render_layer(scene, out / f"{a.sid}_bezel.png")

        # pass 2: refl, the glass mirroring the same house rig (dead-on it
        # images the zenith scrim and its soft edge ~1:1, the dome bending the
        # scrim's feather in at the rim), on black
        scene = self.layer_pass(g, False)
        glass = build_glass(g, bulge=g.refl_bow, roll=a.roll, peak=g.peak)
        self.bind("window", [glass], params=({} if a.coat_rough is None
                                              else {"coat_rough": a.coat_rough}))
        camera_black(house(scene)["world"])
        ortho_cam(scene, g)
        self.render_layer(scene, out / f"{a.sid}_refl.png")
        scale_layer(out / f"{a.sid}_refl.png", REFL_GAIN)

        # pass 3: vig, white diffuse glass, black occluding bezel, white world
        from matlib import build, own_material

        scene = self.layer_pass(g, False)
        glass = build_glass(g, roll=a.roll, peak=g.peak)
        own_material(glass, build("card-flat"))
        own_material(build_bezel(g), build("card-flat-black"))
        white_world(scene)
        ortho_cam(scene, g)
        # a mask is data: no view transform, so the clear glass reads 1
        scene.view_settings.view_transform, scene.view_settings.look = "Raw", "None"
        self.render_layer(scene, out / f"{a.sid}_vig.png")

        manifest = {
            "id": a.sid,
            "style": a.style,
            "res": [g.res_x, g.res_y],
            "aperture": {"x": g.ap_x, "y": g.ap_y, "w": g.ap_w, "h": g.ap_h},
            "corner": {"r": g.corner_r_px, "n": g.corner_n},
            "warp": {"type": "barrel", "k1": g.k1, "k2": g.k2},
            "overscan": g.overscan,
            "glare": {"radius": g.glare_radius_px, "strength": a.bloom_strength},
            "palette_default": g.palette,
            "notes": f"Blender housing bake (screen_scene.py, {self.args.bezel} bezel). "
                     "Edge-to-edge glass; subtle CRT bulge; drop-in for the stub.",
        }
        (out / f"{a.sid}.json").write_text(json.dumps(manifest, indent=2))
        print(f"manifest: aperture {g.ap_x},{g.ap_y} {g.ap_w}x{g.ap_h}  corner r{g.corner_r_px} "
              f"k1={g.k1}")
        line = self.receipt()
        print(line, flush=True)
        return line

    def render_layer(self, scene, path):
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    ScreenMonitor.main()
