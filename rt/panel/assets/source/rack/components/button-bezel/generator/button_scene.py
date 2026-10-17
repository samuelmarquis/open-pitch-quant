"""button-bezel: compact and wide screen-bezel push buttons as transparent RGBA.

  blender -b -P button_scene.py -- OUT [flags]        flag table: ../README.md

A panel key through-mounted in its host: z = 0 is the host's face. A thin
escutcheon (TRIM mm, BORDER mm wide less the GAP) lies on the face around a
cut; a dark open well lines the cut under the face; the key stands in the cut,
CAP_PROUD mm above the face at rest and CAP_SUNK below it, so the shaded gap
around it is the well seen past the key. A flush LED lens in its recess and
the legend sit on the key face. The cut itself is family host_cut: a composer
cuts it into the host under the key (rack.py); alone, no host is drawn. Sizes
are millimetres before --scale (MM = 0.1 world units); the camera is an 85 mm
dead-on perspective camera fitted to the part. `--res N` is the frame height;
the width follows the button's aspect. families.ButtonScene owns flags, slots,
frame and receipt. Blender exits 0 after a script exception: callers check OUT
and the receipt line.
"""

import math
import sys
from pathlib import Path

import bpy
import mathutils

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
import scaffold  # noqa: E402
from families.base import Alias  # noqa: E402
from families.button import ButtonScene, Flag  # noqa: E402
from families.control import color_value  # noqa: E402

MM = 0.1
# through-mount, mm before --scale (module docstring)
BORDER = 0.9       # outer edge to key edge
GAP = 0.35         # key edge to cut edge: the shaded reveal
TRIM = 0.5         # escutcheon thickness on the face
CAP_PROUD = 1.4    # key face above the host face at rest
CAP_SUNK = 0.8     # key below the host face
WELL_LIP = 0.4     # well wall beyond the cut, under the escutcheon
WELL_DEPTH = 2.0   # well floor below the face
DEFAULT_SIZE = {
    "compact": (13.0, 24.0),
    "wide": (42.0, 16.0),
}
# pre-family --material value -> body key
MATERIALS = {
    "matte-black-plastic": "moulded-black-flat",
    "blackened-metal": "steel-blackened-bead-blast",
    "custom": "moulded-satin",
    "black-paint": "black-paint",
    "sleek-black": "sleek-black",
    "white-plastic": "white-plastic",
    "beige-plastic": "beige-plastic",
    "brushed": "brushed",
    "worn-steel": "worn-steel",
}
INKS = {"painted": "ink-screen-print", "deposited": "deposited-ink"}
MONO_FONT_CANDIDATES = (
    HERE / "SFNSMono.ttf",
    Path("/System/Library/Fonts/SFNSMono.ttf"),
    Path("/System/Library/Fonts/Supplemental/Andale Mono.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    Path("C:/Windows/Fonts/consola.ttf"),
)
BOLD_MONO_FONT_CANDIDATES = (
    HERE / "SF-Mono-Bold.otf",
    Path("/System/Applications/Utilities/Terminal.app/Contents/Resources/Fonts/SF-Mono-Bold.otf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
    Path("C:/Windows/Fonts/consolab.ttf"),
)


def bevelled_box(name, dims, location, bevel, segments=4):
    bpy.ops.mesh.primitive_cube_add(location=location)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if ob.data.uv_layers:
        ob.data.uv_layers[0].name = "brush"
    mod = ob.modifiers.new("moulded edge", "BEVEL")
    mod.width = max(0.0001, bevel)
    mod.segments = segments
    mod.limit_method = "ANGLE"
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    try:
        bpy.ops.object.shade_smooth_by_angle()
    except Exception:
        pass
    flat_faces(ob)
    return ob


def flat_faces(ob):
    """A bevelled box's flat (axis-aligned) faces shade flat; its bevel strips
    stay smooth. Smooth, a flat face takes normals interpolated from its
    bevelled corners, and a glossy coat mirrors a light across it as a streak."""
    for p in ob.data.polygons:
        if max(abs(c) for c in p.normal) > 0.9999:
            p.use_smooth = False
    ob.data.update()


def open_tray(name, w, h, depth):
    """A box w x h from z = -depth to 0 without its top face."""
    import bmesh

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = (v.co.x * w, v.co.y * h, (v.co.z - 0.5) * depth)
    bm.faces.ensure_lookup_table()
    top = [f for f in bm.faces if f.normal.z > 0.5]
    bmesh.ops.delete(bm, geom=top, context="FACES_ONLY")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def escutcheon(width, height, open_w, open_h, open_bevel, mm):
    """The thin frame on the host face, z 0 to TRIM, round an open_w x open_h cut."""
    frame = bevelled_box("escutcheon", (width, height, TRIM * mm), (0, 0, TRIM * mm / 2),
                         min(0.25 * mm, TRIM * mm * 0.45))
    opening = bevelled_box("escutcheon opening", (open_w, open_h, 4.0 * TRIM * mm),
                           (0, 0, TRIM * mm / 2), open_bevel)
    cut = frame.modifiers.new("opening", "BOOLEAN")
    cut.operation, cut.solver, cut.object = "DIFFERENCE", "EXACT", opening
    bpy.context.view_layer.objects.active = frame
    bpy.ops.object.modifier_apply(modifier=cut.name)
    bpy.data.objects.remove(opening)
    flat_faces(frame)      # the cut remeshes the frame's faces
    return frame


def vivid_led_color(color, saturation=3.5):
    mean = sum(color) / 3.0
    return tuple(min(1.0, max(0.0, mean + (channel - mean) * saturation))
                 for channel in color)


def add_led_glare(scene, threshold, size, strength):
    """Bloom the emission pass only, so painted labels stay flat and crisp."""
    scene.view_layers[0].use_pass_emit = True
    group = bpy.data.node_groups.new("button LED-only glare", "CompositorNodeTree")
    group.interface.new_socket("Image", in_out="INPUT", socket_type="NodeSocketColor")
    group.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    source = group.nodes.new("CompositorNodeRLayers")
    glare = group.nodes.new("CompositorNodeGlare")
    luma = group.nodes.new("CompositorNodeRGBToBW")
    halo = group.nodes.new("CompositorNodeSetAlpha")
    masked_halo = group.nodes.new("CompositorNodeSetAlpha")
    combine = group.nodes.new("CompositorNodeAlphaOver")
    output = group.nodes.new("NodeGroupOutput")
    glare.inputs["Type"].default_value = "Bloom"
    glare.inputs["Quality"].default_value = "High"
    glare.inputs["Threshold"].default_value = threshold
    glare.inputs["Smoothness"].default_value = 0.86
    glare.inputs["Strength"].default_value = strength
    glare.inputs["Saturation"].default_value = 1.15
    glare.inputs["Size"].default_value = size
    halo.inputs["Type"].default_value = "Replace Alpha"
    masked_halo.inputs["Type"].default_value = "Apply Mask"
    combine.inputs["Factor"].default_value = 1.0
    group.links.new(source.outputs["Emission"], glare.inputs["Image"])
    group.links.new(glare.outputs["Glare"], luma.inputs["Image"])
    group.links.new(glare.outputs["Glare"], halo.inputs["Image"])
    group.links.new(luma.outputs["Val"], halo.inputs["Alpha"])
    group.links.new(halo.outputs["Image"], masked_halo.inputs["Image"])
    group.links.new(source.outputs["Alpha"], masked_halo.inputs["Alpha"])
    group.links.new(source.outputs["Image"], combine.inputs["Background"])
    group.links.new(masked_halo.outputs["Image"], combine.inputs["Foreground"])
    group.links.new(combine.outputs["Image"], output.inputs[0])
    scene.compositing_node_group = group
    scene.use_nodes = True


def aim_object(ob, target):
    direction = mathutils.Vector(target) - ob.location
    ob.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_camera(scene, model_width, model_height, aspect, target_z):
    lens = 85.0
    sensor = 36.0
    hfov = 2.0 * math.atan(sensor / (2.0 * lens))
    vfov = 2.0 * math.atan(math.tan(hfov / 2.0) / aspect)
    half_w = model_width * 0.57
    half_h = model_height * 0.57
    distance = max(half_w / math.tan(hfov / 2.0), half_h / math.tan(vfov / 2.0))
    bpy.ops.object.camera_add(location=(0, 0, target_z + distance))
    camera = bpy.context.object
    camera.name = "85mm dead-on panel camera"
    camera.data.lens = lens
    camera.data.sensor_width = sensor
    camera.data.sensor_fit = "HORIZONTAL"
    aim_object(camera, (0, 0, target_z))
    scene.camera = camera


class BezelButton(ButtonScene):
    COMPONENT = "button-bezel"
    DEFAULT_OUT = "/tmp/button-bezel.png"
    RES = 720
    SAMPLES = 180
    STATES = ("active", "inactive")
    STATE = "active"
    HUE = "fbe48b"
    LEVEL = 2.6
    LEVEL_RANGE = (0.0, 8.0)
    LEVEL_HELP = "lens and local-spill level while active; 0 is visibly unlit"
    TEXT = "1"
    FONT = "mono"
    FONTS = ("sans", "mono")
    SLOTS = {
        "body": MATERIALS["matte-black-plastic"],
        "cap": "same",
        "seam": "rubber-seam",
        "lens": "acrylic-led-lens",
        "legend": INKS["painted"],
    }
    SLOT_SAME = {"cap": "body"}
    EXTRA_SLOTS = ("seam",)
    SLOT_HELP = {
        "body": "escutcheon on the host face (--body-color fills a key's colour)",
        "cap": "through-mounted labelled key",
        "seam": "key well (the gap around the key) and LED recess",
        "lens": "flush LED lens (--hue / --level / --state fill its colour and level)",
        "legend": "label ink (--text-color fills its colour)",
    }
    PRESETS = {name: {"ink-style": name, "legend": key} for name, key in INKS.items()}
    DEFAULT_PRESET = "painted"
    SCALE_HELP = "multiplier on every physical dimension; the camera refits the part"
    ALIASES = {
        "preset": [Alias("--ink-style", values=tuple(INKS))],
        "body": [Alias("--material", values=MATERIALS), "--material"],
        "hue": ["--led-color"],
        "level": ["--led-level"],
        "bloom-strength": ["--led-glow"],
    }
    FLAGS = (
        Flag("--variant", str, "compact", choices=tuple(DEFAULT_SIZE),
             help="compact: LED above/below the label; wide: LED beside it"),
        Flag("--ink-style", str, "painted", choices=tuple(INKS),
             help="flush rough screen print or raised deposited label (label geometry)"),
        Flag("--led-end", str, "auto", choices=("auto", "top", "bottom", "left", "right"),
             help="LED edge: top/bottom (compact), left/right (wide); auto = top/left"),
        Flag("--font-weight", str, "bold", choices=("regular", "bold"),
             help="mono face weight; ignored by sans"),
        Flag("--font-file", str, None, help="explicit .ttf/.otf legend face; overrides --font"),
        Flag("--body-color", color_value, None,
             help="colour for a body/cap key with a `color` param"),
        Flag("--text-color", color_value, "f7f8f7", help="legend colour"),
        Flag("--cap-height", float, None,
             help="legend cap height, mm (the face's H), shared by a row whatever the label "
                  "length; none = the largest that fits the key. Clamped to fit (receipt note)"),
        Flag("--ink-relief", float, None,
             help="legend height proud of the key face, mm; none = the --ink-style's own"),
        Flag("--travel", float, 0.0,
             help="key travel while --state active: key, lens and legend sit this far down, "
                  "mm, 0..0.9; 0 = flush"),
        Flag("--spill", str, "on", choices=("on", "off"),
             help="the lit LED's coloured local spill light"),
        Flag("--width", float, None, help="finished outer width, mm (variant default)"),
        Flag("--height", float, None, help="finished outer height, mm (variant default)"),
        Flag("--wide-led-height", float, 10.4, help="wide vertical lens height, mm"),
        Flag("--wide-led-gap", float, 2.4, help="wide lens-to-label clearance, mm"),
        Flag("--wide-opposite-pad", float, 1.6,
             help="extra wide-label margin opposite the LED, mm"),
        *scaffold.bloom_flags(threshold=0.01, size=5.0, strength=1.2),
    )

    # ---------------------------------------------------------------- contract
    def frame_aspect(self):
        return self.args.width / self.args.height

    def validate(self):
        a, values = self.args, self.args.values
        default_w, default_h = DEFAULT_SIZE[a.variant]
        values["width"] = default_w if a.width is None else a.width
        values["height"] = default_h if a.height is None else a.height
        if a.width <= 0 or a.height <= 0:
            raise SystemExit(f"{self.COMPONENT}: --width and --height must be positive")
        if a.led_end == "auto":
            values["led-end"] = "top" if a.variant == "compact" else "left"
        valid_ends = ("top", "bottom") if a.variant == "compact" else ("left", "right")
        if a.led_end not in valid_ends:
            raise SystemExit(f"{self.COMPONENT}: --variant {a.variant} uses --led-end "
                             f"{' or '.join(valid_ends)}")
        super().validate()
        if not 0.0 <= a.bloom_strength <= 2.0:
            raise SystemExit(f"{self.COMPONENT}: --bloom-strength must be in 0..2")
        if a.wide_led_height <= 0 or a.wide_led_gap < 0 or a.wide_opposite_pad < 0:
            raise SystemExit(f"{self.COMPONENT}: wide LED height must be positive; gap and "
                             "opposite padding must be non-negative")
        if not a.text.strip():
            raise SystemExit(f"{self.COMPONENT}: --text cannot be empty")
        if len(a.text) > 24:
            raise SystemExit(f"{self.COMPONENT}: --text is limited to 24 characters")
        if not 0.0 <= a.travel <= 0.9:
            raise SystemExit(f"{self.COMPONENT}: --travel must be in 0..0.9 mm")
        if a.cap_height is not None and a.cap_height <= 0:
            raise SystemExit(f"{self.COMPONENT}: --cap-height must be positive")
        if a.ink_relief is not None and a.ink_relief <= 0:
            raise SystemExit(f"{self.COMPONENT}: --ink-relief must be positive")
        if a.body_color is not None:
            from matlib import meta

            keys = {self.slot_key(s)[0] for s in ("body", "cap")}
            if not any("color" in meta(k).params for k in keys):
                raise SystemExit(f"{self.COMPONENT}: --body-color needs a body or cap key with "
                                 f"a colour param (have {sorted(keys)})")
        self.lit_level = a.level if a.state == "active" else 0.0

    def load_label_font(self):
        a = self.args
        if a.font_file:
            path = Path(a.font_file).expanduser().resolve()
            if not path.is_file():
                raise SystemExit(f"--font-file does not exist: {path}")
            return bpy.data.fonts.load(str(path), check_existing=True)
        if a.font == "sans":
            return None
        candidates = BOLD_MONO_FONT_CANDIDATES if a.font_weight == "bold" else MONO_FONT_CANDIDATES
        for path in candidates:
            if path.is_file():
                return bpy.data.fonts.load(str(path), check_existing=True)
        raise SystemExit(f"--font mono --font-weight {a.font_weight} requires --font-file "
                         "on this system")

    # ---------------------------------------------------------------- geometry
    def add_text(self, center, max_width, max_height, z, label_font):
        a = self.args
        bpy.ops.object.text_add(location=(center[0], center[1], z))
        ob = bpy.context.object
        ob.name = "button label"
        ob.data.body = a.text
        ob.data.align_x = "CENTER"
        ob.data.align_y = "CENTER"
        ob.data.size = 1.0
        ob.data.space_character = 1.0
        if label_font is not None:
            ob.data.font = label_font
        if a.ink_style == "painted":
            ob.data.extrude = 0.00008
            ob.data.bevel_depth = 0.0
        else:
            ob.data.extrude = 0.0012
            ob.data.bevel_depth = 0.00035
        self.bind("legend", [ob], params={"color": self.linear_rgb(a.text_color)})
        mm = a.scale * MM
        cap = None if a.cap_height is None else a.cap_height * mm
        fit = self.legend_fit(ob, max_width, max_height, cap, mm)
        if a.ink_relief is not None:
            # extrude is symmetric about the object: centre it half the relief
            # up, so the legend stands exactly --ink-relief proud of the face
            relief = a.ink_relief * mm
            ob.data.extrude = relief / 2 / fit
            ob.data.bevel_depth = 0.0
            ob.location.z = self.face_z + relief / 2 + 0.005 * mm
        return ob

    def build_button(self, label_font, led_color):
        """The key through-mounted in its host (module docstring): z = 0 is the
        host's face."""
        a = self.args
        body_fill = {} if a.body_color is None else {"color": self.linear_rgb(a.body_color)}
        width = a.width * a.scale * MM
        height = a.height * a.scale * MM
        scale = a.scale
        mm = scale * MM
        cap_w = width - 2.0 * BORDER * mm
        cap_h = height - 2.0 * BORDER * mm
        if cap_w <= 4.0 * mm or cap_h <= 6.0 * mm:
            raise SystemExit("button dimensions are too small for the key, label, and LED")
        cap_bevel = min(0.62 * mm, cap_w * 0.08, cap_h * 0.08)
        rest_z = CAP_PROUD * mm
        # an active key is latched down by --travel; the camera keeps the rest
        # face so every state shares one framing
        drop = a.travel * mm if a.state == "active" else 0.0
        face_z = self.face_z = rest_z - drop

        # the escutcheon: a thin frame on the host face around the cut
        open_w, open_h = cap_w + 2.0 * GAP * mm, cap_h + 2.0 * GAP * mm
        frame = escutcheon(width, height, open_w, open_h, cap_bevel + GAP * mm, mm)
        self.bind("body", [frame], params=body_fill)

        # the well lining the cut: an open tray under the face, seen through the gap
        well_w, well_h = open_w + 2.0 * WELL_LIP * mm, open_h + 2.0 * WELL_LIP * mm
        self.bind("seam", [open_tray("key well", well_w, well_h, WELL_DEPTH * mm)])
        self.host_cut("key cut", well_w, well_h, (WELL_DEPTH + 0.2) * mm, TRIM * mm)

        cap_depth = (CAP_PROUD + CAP_SUNK) * mm
        key = bevelled_box("through-mounted key", (cap_w, cap_h, cap_depth),
                           (0, 0, face_z - cap_depth / 2), cap_bevel)
        self.bind("cap", [key], params=body_fill)

        inset = 1.25 * mm
        if a.variant == "compact":
            led_w = min(8.6 * scale * MM, cap_w - 2.0 * inset)
            led_h = min(3.4 * scale * MM, cap_h * 0.21)
            sign = 1.0 if a.led_end == "top" else -1.0
            led_center = (0.0, sign * (cap_h / 2 - inset - led_h / 2))
            text_center = (0.0, -sign * cap_h * 0.13)
            text_max_w = cap_w - 1.65 * inset
            text_max_h = cap_h * 0.50
        else:
            led_w = min(2.5 * scale * MM, cap_w * 0.09)
            led_h = min(a.wide_led_height * scale * MM, cap_h - 2.0 * inset)
            sign = -1.0 if a.led_end == "left" else 1.0
            led_center = (sign * (cap_w / 2 - inset - led_w / 2), 0.0)
            gap = a.wide_led_gap * scale * MM
            opposite_pad = a.wide_opposite_pad * scale * MM
            if sign < 0:
                label_lo = led_center[0] + led_w / 2 + gap
                label_hi = cap_w / 2 - inset - opposite_pad
            else:
                label_lo = -cap_w / 2 + inset + opposite_pad
                label_hi = led_center[0] - led_w / 2 - gap
            text_center = ((label_lo + label_hi) / 2, 0.0)
            text_max_w = label_hi - label_lo
            text_max_h = cap_h - 1.9 * inset

        well_border = 0.58 * scale * MM
        well_depth = 0.34 * scale * MM
        lens_depth = 0.38 * scale * MM
        recess = bevelled_box("LED recess", (led_w + well_border, led_h + well_border, well_depth),
                              (led_center[0], led_center[1], face_z + well_depth / 2),
                              min(0.40 * scale * MM, (led_h + well_border) * 0.34,
                                  well_depth * 0.42), 5)
        self.bind("seam", [recess])
        lens = bevelled_box("flush LED lens", (led_w, led_h, lens_depth),
                            (led_center[0], led_center[1],
                             face_z + lens_depth / 2 + 0.015 * scale * MM),
                            min(0.52 * scale * MM, led_h * 0.42, lens_depth * 0.42), 6)
        self.bind("lens", [lens], params={"color": led_color, "level": self.lit_level})

        label_lift = (0.005 if a.ink_style == "painted" else 0.025) * scale * MM
        self.add_text(text_center, text_max_w, text_max_h, face_z + label_lift, label_font)

        if self.lit_level > 0 and a.spill == "on":
            bpy.ops.object.light_add(
                type="POINT",
                location=(led_center[0], led_center[1], face_z + 0.20 * scale * MM),
            )
            glow = bpy.context.object
            glow.name = "LED local spill"
            glow.data.color = led_color
            glow.data.energy = 0.16 * self.lit_level * max(height, 1.0) ** 2
            glow.data.shadow_soft_size = max(led_h * 0.45, 0.02)
        return width, height, rest_z

    def build(self):
        a = self.args
        self.scene.cycles.transparent_max_bounces = 12
        self.scene.view_settings.exposure = 0.0
        label_font = self.load_label_font()
        hue = self.linear_rgb(a.hue)
        led_color = vivid_led_color(hue) if self.lit_level > 0 else hue
        model_w, model_h, face_z = self.build_button(label_font, led_color)
        self.house_rig(max(model_w, model_h))
        w, h = self.frame
        add_camera(self.scene, model_w, model_h, w / h, face_z * 0.45)
        if self.lit_level > 0 and a.bloom == "on" and a.bloom_strength > 0:
            add_led_glare(self.scene, a.bloom_threshold, a.bloom_size, a.bloom_strength)


if __name__ == "__main__":
    BezelButton.main()
