"""Shared studio rigs: the house world, authored emitters, cameras and the bloom compositor.

Blender 5.2 / Cycles, `bpy` only. ONE house rig lights every Blender component
(`knob_studio`); a composed panel is lit as one scene by the rack light
(`rack_studio`, through components/_studio/rack.py).

  knob_studio(scene, scale)          THE HOUSE RIG: house world + 3 gradient emitters + zenith scrim + rake + 85 mm camera
  rack_studio(scene, span, lit, view, light)    the rack light: knob_studio at a panel's span, dark room, reflection cards over its lit rect
  zenith_scrim(scale, radiance)      the house mirror-direction source (knob_studio's)
  panel_camera(scene, w, h, tilt)    85 mm framing for a w x h panel
  house_world(scene, strength)       the house world alone
  bloom(scene, ...)                  RLayers-fed Glare(Bloom) compositor group (display-segment)
  emitter(name, sx, sy, loc, rot, e) gradient mesh emitter: the house light source
  isolate(scene, keep)               bake layers: `keep` the only light (black world, every other source hidden)

THE HOUSE LIGHTING STANDARD
- The house world is `studio_kominka_03_4k.hdr` (HOUSE_HDRI) at yaw 0: amorphous
  in a mirror, so a chrome dome reads as metal and not as a room full of strip
  tubes.
- Every authored source is a GRADIENT MESH EMITTER (`emitter`): a plane carrying
  a radial gradient that reaches zero before its border, so it has no silhouette
  a mirror can read. Sizes and watts are area-light values; the rig multiplies
  by its solved emitter scale (KNOB_EMIT_K).
- In `knob_studio` the world IS VISIBLE TO GLOSSY RAYS: a part's flat glossy
  faces take their reflections from the house world, the emitters and the
  zenith scrim together.
- `knob_studio`'s overhead fill sits OFF-AXIS at (0.15, 1.6, 2.0), aimed at the
  part: a near-overhead fill images as a splotch in the centre of a dome.

Solved exposure (grey-probe solve, matte 0.18 Lambertian subject, 160 px / 256
samples / Raw / Rec.709 mean): knob_studio's world at HOUSE_KNOB_STR 0.42552,
its emitters at KNOB_EMIT_K 1.22759.

Contracts:
- Builders use `bpy.ops.object.*_add`, so they add to the active collection of the
  context scene; pass that scene.
- HDRIs resolve through `hdri_path(name, local_dir)`: a file of that name in the
  component's own generator dir wins, else `components/_studio/`.
- A shared rig adds NO `LIGHT` OBJECT: its sources are mesh objects, and the
  objects a builder returns are those meshes. To blank a rig, hide the objects
  the builder returned (or use `isolate`); zeroing `LIGHT` energy blanks nothing.
- `bloom` settings are input SOCKETS in 5.2; the group must be fed by an
  `RLayers` node (a `NodeGroupInput` source renders white with zero alpha).
"""

import math
from pathlib import Path

import bpy
from mathutils import Vector

STUDIO = Path(__file__).resolve().parent

HOUSE_HDRI = "studio_kominka_03_4k.hdr"     # Poly Haven studio_kominka_03, CC0
HOUSE_YAW_DEG = 0.0
HOUSE_KNOB_STR = 0.42552                    # kominka strength in knob_studio

GRADIENT_WIDEN = 1.5        # each emitter axis, for a broader and softer feather
GRADIENT_ZERO = 0.85        # ramp stop: radiance is zero from here to the border
KNOB_EMIT_K = 1.22759       # solved emitter scale, knob_studio


def hdri_path(name, local_dir=None):
    """A component-local HDRI of that name if present, else the shared one."""
    if local_dir is not None:
        local = Path(local_dir) / name
        if local.exists():
            return local
    return STUDIO / name


def house_world(scene, strength, name="house studio", local_dir=None,
                yaw_deg=HOUSE_YAW_DEG, pitch_deg=0.0):
    """The house world: HOUSE_HDRI through TexCoord(Generated) -> Mapping ->
    Environment -> Background at `strength`. Returns the world."""
    world = bpy.data.worlds.new(name)
    scene.world = world
    world.use_nodes = True
    wn = world.node_tree.nodes
    wl = world.node_tree.links
    env = wn.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(hdri_path(HOUSE_HDRI, local_dir)))
    map_node = wn.new("ShaderNodeMapping")
    texcoord = wn.new("ShaderNodeTexCoord")
    map_node.inputs["Rotation"].default_value = (math.radians(pitch_deg), 0,
                                                 math.radians(yaw_deg))
    wl.new(texcoord.outputs["Generated"], map_node.inputs["Vector"])
    wl.new(map_node.outputs["Vector"], env.inputs["Vector"])
    wl.new(env.outputs["Color"], wn["Background"].inputs["Color"])
    wn["Background"].inputs["Strength"].default_value = strength
    return world


def _emissive(name, color, strength_builder):
    """Add(Transparent, Emission): it adds light and blocks nothing, so the world
    still reaches the part undimmed through the emitter's own plane."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    n, links = nt.nodes, nt.links
    for node in list(n):
        n.remove(node)
    out = n.new("ShaderNodeOutputMaterial")
    add = n.new("ShaderNodeAddShader")
    transparent = n.new("ShaderNodeBsdfTransparent")
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1.0)
    links.new(transparent.outputs[0], add.inputs[0])
    links.new(em.outputs[0], add.inputs[1])
    links.new(add.outputs[0], out.inputs["Surface"])
    strength_builder(n, links, em)
    return mat


def emitter(name, sx, sy, loc, rot, e, color=(1.0, 1.0, 1.0), scale=1.0,
            widen=GRADIENT_WIDEN):
    """THE HOUSE LIGHT SOURCE: a gradient mesh emitter standing in for an
    `sx` x `sy` rectangle area light of `e` W at `loc`, Euler `rot`.

    The plane is `widen`x that size on each axis and carries a radial gradient
    that peaks at the centre and reaches zero at GRADIENT_ZERO of the way out, so
    it has NO SILHOUETTE: a mirror sees a feathered patch with no edge anywhere.
    Peak radiance is `e / area * scale`, and it is hidden from camera rays.
    Returns the object."""
    sx, sy = sx * widen, sy * widen
    bpy.ops.mesh.primitive_plane_add(size=2.0, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.name = name
    ob.scale = (sx / 2.0, sy / 2.0, 1.0)
    ob.visible_camera = False
    radiance = e / (sx * sy) * scale

    def build(n, links, em):
        tc = n.new("ShaderNodeTexCoord")
        grad = n.new("ShaderNodeTexGradient")
        grad.gradient_type = "SPHERICAL"        # 1 at the centre, 0 at |v| = 1
        links.new(tc.outputs["Object"], grad.inputs["Vector"])
        ramp = n.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "EASE"
        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[1].position = GRADIENT_ZERO
        links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
        amp = n.new("ShaderNodeMath")
        amp.operation = "MULTIPLY"
        amp.inputs[1].default_value = radiance
        links.new(ramp.outputs["Color"], amp.inputs[0])
        links.new(amp.outputs["Value"], em.inputs["Strength"])

    ob.data.materials.append(_emissive(name, color, build))
    return ob


# ------------------------------------------------------------------ bake isolate
def _socket_live(sock, zero):
    return sock.is_linked or any(abs(v) > zero for v in
                                 (sock.default_value if hasattr(sock.default_value, "__len__")
                                  else (sock.default_value,)))


def _tree_emits(tree, seen=None):
    """True if a shader tree can emit: an Emission/Background node or a
    Principled emission whose strength AND colour are live (linked, or nonzero),
    looking inside node groups."""
    seen = set() if seen is None else seen
    if tree is None or tree.name in seen:
        return False
    seen.add(tree.name)
    for node in tree.nodes:
        t = node.bl_idname
        if t in ("ShaderNodeEmission", "ShaderNodeBackground"):
            if _socket_live(node.inputs["Strength"], 0.0) and \
                    _socket_live(node.inputs["Color"], 0.0):
                return True
        elif t == "ShaderNodeBsdfPrincipled":
            if _socket_live(node.inputs["Emission Strength"], 0.0) and \
                    _socket_live(node.inputs["Emission Color"], 0.0):
                return True
        elif t == "ShaderNodeGroup" and _tree_emits(node.node_tree, seen):
            return True
    return False


def isolate(scene, keep):
    """BAKE ISOLATE: leave `keep` (the objects whose emission the layer holds) as
    the ONLY light in `scene`. Isolate the emitter, do not enumerate the rig: a
    rig's returned dict has missed a source before (pass 43's rake), so this
    finds every source by what it IS —
      * the world -> a black world (every Background in the old one is moot),
      * every LIGHT object -> energy 0 and hidden,
      * every object outside `keep` with an emissive material and invisible to
        the camera (a rig emitter, scrim, rake, reflection card) -> hidden.
    An emissive object the CAMERA sees that is not in `keep` is part of the
    subject: hiding it would change the frame, and leaving it lit would leak,
    so that is an error, not a guess. Returns the names hidden."""
    keep = {ob.name for ob in keep}
    black = bpy.data.worlds.new("isolate: black")
    black.use_nodes = True
    black.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    black.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    scene.world = black
    hidden, subject = [], []
    for ob in scene.objects:
        if ob.name in keep or ob.hide_render:
            continue
        if ob.type == "LIGHT":
            ob.data.energy = 0.0
            ob.hide_render = True
            hidden.append(ob.name)
            continue
        mats = [s.material for s in getattr(ob, "material_slots", ()) if s.material]
        if not any(m.use_nodes and _tree_emits(m.node_tree) for m in mats):
            continue
        if ob.visible_camera:
            subject.append(ob.name)
        else:
            ob.hide_render = True
            hidden.append(ob.name)
    if subject:
        raise SystemExit(f"isolate: camera-visible emitters outside keep: {subject}")
    return hidden


# ------------------------------------------------------------------ knob studio
KNOB_AIM = (0.0, 0.0, 0.29)             # the camera target: the off-axis fill aims here
KNOB_FILL_LOC = (0.15, 1.60, 2.00)      # off-axis: an overhead fill images dead centre
KNOB_FILL_ROT = tuple((Vector(KNOB_AIM) - Vector(KNOB_FILL_LOC))
                      .to_track_quat("-Z", "Y").to_euler())


PANEL_STOPS = -1.3   # the house light: panel-board (p116) and the knob family (p120), pass 38

# THE ZENITH (pass 40, p123-p125). A face-up flat face reflects ONE direction,
# straight up past the camera, and the rig alone left that at 0.08 of the light
# the face receives (over pi): every flat metal read 1.2-1.7 stops under the
# grey card. The zenith scrim sets it to ZENITH_R (Sam: 0.275; 0.20 too cold,
# 0.35 too hot). Calibration at PANEL_STOPS, grey18 and a mirror under a unit
# scrim: a mirror sees 0.0885 + 0.973 L, the face receives 1.132 + 0.314 L, so
# L = (1.132 R - 0.0885) / (0.973 - 0.314 R), and ZENITH_K re-gains the whole
# rig to hold grey18 where it was (0.204): K = 1.132 / (1.132 + 0.314 L).
ZENITH_R = 0.275
ZENITH_L = 0.2513            # scrim centre radiance at PANEL_STOPS, before ZENITH_K
ZENITH_K = 0.9349            # whole-rig gain that holds grey18
ZENITH_HEIGHT = 2.2          # x rig scale above the part
ZENITH_CORE = 1.1            # x rig scale: flat half-width
ZENITH_HALF = 1.6            # x rig scale: feathered to zero here
ZENITH_TILT = (1.12, 0.88)   # radiance x, front (-y, the key side) to back
ZENITH_COLOR = (1.0, 0.97, 0.93)
# THE SOFT EDGE (pass 43, p134): a flat metal reflects the scrim point for
# point, and an even scrim gives it nothing to show; a soft-edged falloff across
# the part's diagonal is the product photographer's gradient reflection, which
# the sheet's ripple (matlib sheet_ripple) then bends. x EDGE_HI on the upper
# left to x EDGE_LO on the lower right, smoothstep over +-EDGE_W rig scale;
# it averages 1 across the part, so grey cards hold. Sam: "soft edge/ripple on
# seems like the answer" (bands were rejected: they stripe a chrome knob).
ZENITH_EDGE_HI, ZENITH_EDGE_LO, ZENITH_EDGE_W = 1.45, 0.55, 0.18


# THE RAKE (pass 43). A light skimming the face from the upper left brings out
# weave, grain and knurl; a flat face's mirror direction points away from it, so
# smooth metal barely sees it. `rake` is the share of a face-up surface's light
# it supplies; the rest of the rig and the zenith scrim are re-solved together
# (rake_balance) so a grey card and a face-up mirror are both unmoved: flat
# metals and R 0.275 stay as they were (p132 r1 re-gained the whole rig and
# dimmed the metals).
# The elevation sets how hard it skims. GREY_E_OVER_PI is the face-up irradiance
# over pi the rig delivers at PANEL_STOPS (grey18 0.204 / 0.18, pass 40).
RAKE = 0.375                 # Sam, p132: "somewhere between gentle and strong"
RAKE_ELEV = 16.0             # deg above the face (gentle 20, strong 12)
RAKE_AZIM = 135.0            # deg from +x: the upper left of a dead-on frame
RAKE_DIST = 8.0              # x rig scale
RAKE_SIZE = (3.0, 0.5)       # x rig scale: wide and shallow — soft, but a low sheet
GREY_E_OVER_PI = 1.133
# pass 40's calibration at PANEL_STOPS: the world alone puts 0.0885 in a face-up
# mirror; a scrim of radiance L adds 0.973 L to the mirror and 0.314 L to a face
ZENITH_WORLD_MIRROR, SCRIM_MIRROR, SCRIM_FACE = 0.0885, 0.973, 0.314


def rake_balance(rake):
    """(k, s): the gain on the world and three emitters and the factor on the
    scrim's radiance that hold BOTH a grey card (the face-up light) and a
    face-up mirror (what flat metal shows, Sam's R 0.275) with the rake adding
    `rake` of the face-up light. Two linear equations at PANEL_STOPS:
        k (E - f Lb) + f L = E (1 - rake)          grey card
        k Zw + m L = Zw + m Lb                      mirror
    with Lb = ZENITH_L K, Zw = ZENITH_WORLD_MIRROR K, E = GREY_E_OVER_PI."""
    lb, zw, e = ZENITH_L * ZENITH_K, ZENITH_WORLD_MIRROR * ZENITH_K, GREY_E_OVER_PI
    f, m = SCRIM_FACE, SCRIM_MIRROR
    a = e - f * lb
    det = a * m - f * zw
    k = (e * (1.0 - rake) * m - f * (zw + m * lb)) / det
    lr = (a * (zw + m * lb) - zw * e * (1.0 - rake)) / det
    return k, lr / lb


def _ramp_mean(n=200):
    """The house emitter's mean radiance over its plane, as a fraction of its
    peak: EASE(clamp((1 - r) / GRADIENT_ZERO)) over [-1, 1]^2."""
    s = 0.0
    for i in range(n):
        for j in range(n):
            x, y = (i + 0.5) / n * 2 - 1, (j + 0.5) / n * 2 - 1
            t = min(max((1 - math.hypot(x, y)) / GRADIENT_ZERO, 0.0), 1.0)
            s += t * t * (3 - 2 * t)
    return s / (n * n)


def rake_emitter(scale, rake, elev_deg, gain):
    """The rake as a house gradient emitter, its power solved so a face-up
    surface at the origin receives `rake` x GREY_E_OVER_PI x pi x `gain` from
    it (distant-source approximation: E = P x mean x sin(elev) / D^2)."""
    rs = max(scale, 0.55)
    e, az = math.radians(elev_deg), math.radians(RAKE_AZIM)
    dist = RAKE_DIST * rs
    loc = Vector((math.cos(e) * math.cos(az), math.cos(e) * math.sin(az), math.sin(e))) * dist
    rot = (-loc).to_track_quat("Z", "Y").to_euler()
    target = rake * GREY_E_OVER_PI * math.pi * gain
    watts = target * dist * dist / (_ramp_mean() * math.sin(e))
    return emitter("rake", RAKE_SIZE[0] * rs / GRADIENT_WIDEN, RAKE_SIZE[1] * rs / GRADIENT_WIDEN,
                   tuple(loc), tuple(rot), watts, color=(1.0, 0.96, 0.90), scale=1.0)


def zenith_scrim(scale, radiance):
    """The house rig's mirror-direction source: a square plane ZENITH_HEIGHT x the
    rig scale over the part, flat to ZENITH_CORE and eased to zero at
    ZENITH_HALF (no silhouette in a mirror), with a gentle front-to-back tilt so
    flat metal reads as a surface and not a fill. Add(Transparent, Emission) and
    hidden from camera and shadow rays: it ADDS `radiance` to whatever reflects
    it and blocks nothing — the world and the emitters are untouched."""
    rs = max(scale, 0.55)
    half, core = ZENITH_HALF * rs, ZENITH_CORE * rs
    bpy.ops.mesh.primitive_plane_add(size=2.0 * half, location=(0, 0, ZENITH_HEIGHT * rs))
    ob = bpy.context.object
    ob.name = "zenith scrim"
    ob.visible_camera = False
    ob.visible_shadow = False

    def build(n, links, em):
        sep = n.new("ShaderNodeSeparateXYZ")
        links.new(n.new("ShaderNodeTexCoord").outputs["Object"], sep.inputs[0])
        ax, ay, mx = (n.new("ShaderNodeMath") for _ in range(3))
        ax.operation = ay.operation = "ABSOLUTE"
        mx.operation = "MAXIMUM"                  # square core, square feather
        links.new(sep.outputs["X"], ax.inputs[0])
        links.new(sep.outputs["Y"], ay.inputs[0])
        links.new(ax.outputs[0], mx.inputs[0])
        links.new(ay.outputs[0], mx.inputs[1])
        fall = n.new("ShaderNodeMapRange")
        fall.interpolation_type = "SMOOTHERSTEP"
        for sock, v in (("From Min", core), ("From Max", half), ("To Min", 1.0), ("To Max", 0.0)):
            fall.inputs[sock].default_value = v
        links.new(mx.outputs[0], fall.inputs["Value"])
        tilt = n.new("ShaderNodeMapRange")
        tilt.clamp = False
        for sock, v in (("From Min", -core), ("From Max", core),
                        ("To Min", ZENITH_TILT[0]), ("To Max", ZENITH_TILT[1])):
            tilt.inputs[sock].default_value = v
        links.new(sep.outputs["Y"], tilt.inputs["Value"])
        # the soft edge across the diagonal u = (x - y) / sqrt 2, in rig scale
        diag = n.new("ShaderNodeMath")
        diag.operation = "SUBTRACT"
        links.new(sep.outputs["X"], diag.inputs[0])
        links.new(sep.outputs["Y"], diag.inputs[1])
        edge = n.new("ShaderNodeMapRange")
        edge.interpolation_type = "SMOOTHSTEP"
        k = math.sqrt(2) * rs
        for sock, v in (("From Min", -ZENITH_EDGE_W * k), ("From Max", ZENITH_EDGE_W * k),
                        ("To Min", ZENITH_EDGE_HI), ("To Max", ZENITH_EDGE_LO)):
            edge.inputs[sock].default_value = v
        links.new(diag.outputs[0], edge.inputs["Value"])
        shape, lit, amp = (n.new("ShaderNodeMath") for _ in range(3))
        shape.operation = lit.operation = amp.operation = "MULTIPLY"
        amp.label = "radiance"
        amp.inputs[1].default_value = radiance
        links.new(fall.outputs[0], shape.inputs[0])
        links.new(tilt.outputs[0], shape.inputs[1])
        links.new(shape.outputs[0], lit.inputs[0])
        links.new(edge.outputs["Result"], lit.inputs[1])
        links.new(lit.outputs[0], amp.inputs[0])
        links.new(amp.outputs[0], em.inputs["Strength"])

    ob.data.materials.append(_emissive("zenith scrim", ZENITH_COLOR, build))
    return ob


def knob_studio(scene, scale=1.0, local_dir=None, camera=True, stops=0.0, zenith=True,
                rake=None, rake_elev=None):
    """The knob studio: the house world (kominka, yaw 0) at HOUSE_KNOB_STR,
    VISIBLE TO GLOSSY RAYS, three gradient emitters scaled by max(scale, 0.55),
    and an 85 mm / 36 mm camera 4*max(scale, 1) above (0, 0, 0.29*scale) looking
    straight down.

      keybar soft strip   2.80 x 0.52  @ (-1.40, -1.15, 2.75)  125 W  warm
      hard square kicker  0.10 x 0.10  @ ( 1.25, -0.75, 1.55)   62 W  cool
      top metal reader    1.20 x 0.38  @ ( 0.15,  1.60, 2.00)   52 W  white, aimed at the part

    Every emitter carries KNOB_EMIT_K, the solved scale that holds the part's
    diffuse level. The rig is SCALE-INVARIANT: at `scale` s every emitter sits s x
    farther and carries s^2 x the watts, so a part s x larger is lit to the same
    level. That is what lets a panel take it (panel-board `--studio knob`).
    `camera=False` adds no camera, for a caller that frames its own (camera None).

    `stops` scales the whole rig's light (world and every emitter) by 2^stops.
    The solve above holds a KNOB's diffuse level; a face-up panel catches the
    whole overhead and lands ~1.3 stops hot (grey18 173/255, pass 38), so a
    panel passes PANEL_STOPS. It is a light gain, not view exposure, so an
    emissive part (an LED, a nixie) keeps its own radiance under a dimmer rig.

    `zenith` (the house default) adds the zenith scrim at ZENITH_R and re-gains
    the whole rig by ZENITH_K; the scrim's radiance follows `stops` like every
    other source. `zenith=False` is the base rig alone (the self-test's
    comparison against its source).
    Returns dict(world, key, kicker, fill, zenith, rake, camera)."""
    rake = RAKE if rake is None else rake
    rake_elev = RAKE_ELEV if rake_elev is None else rake_elev
    base = 2.0 ** stops * (ZENITH_K if zenith else 1.0)
    # the rake's light comes out of the world and the three emitters, and the
    # scrim is re-solved with them, so a grey card AND a face-up mirror (what
    # flat metal shows: Sam's R 0.275) are both unmoved (rake_balance)
    k, s = rake_balance(rake) if zenith else (1.0 - rake, 1.0)
    if k <= 0:
        raise ValueError(f"rake {rake}: nothing left in the rig to take it from")
    gain = base * k
    world = house_world(scene, HOUSE_KNOB_STR * gain, name="knob studio", local_dir=local_dir)

    rig_scale = max(scale, 0.55)

    def source(name, size, size_y, location, energy, rot, color=(1.0, 0.93, 0.84)):
        return emitter(name, size * rig_scale, size_y * rig_scale,
                       tuple(v * rig_scale for v in location), rot,
                       energy * rig_scale * rig_scale * gain, color=color, scale=KNOB_EMIT_K)

    key = source("keybar soft strip", 2.8, 0.52, (-1.4, -1.15, 2.75), 125,
                 (math.radians(18), 0, math.radians(-32)))
    kicker = source("hard square kicker", 0.10, 0.10, (1.25, -0.75, 1.55), 62,
                    (math.radians(28), math.radians(18), math.radians(24)),
                    color=(0.72, 0.84, 1.0))
    fill = source("top metal reader", 1.20, 0.38, KNOB_FILL_LOC, 52, KNOB_FILL_ROT,
                  color=(1.0, 1.0, 1.0))
    top = zenith_scrim(scale, ZENITH_L * base * s * 2.0 ** -PANEL_STOPS) if zenith else None
    raking = None
    if rake > 0:
        # its target: `rake` of the face-up light the rig delivers at these
        # stops, relative to the rig at PANEL_STOPS (where GREY_E_OVER_PI holds)
        raking = rake_emitter(scale, rake, rake_elev, base * 2.0 ** -PANEL_STOPS / ZENITH_K)

    if not camera:
        return dict(world=world, key=key, kicker=kicker, fill=fill, zenith=top, rake=raking,
                    camera=None)
    frame_scale = max(scale, 1.0)
    target = Vector((0, 0, 0.29 * scale))
    cam_loc = target + Vector((0, 0, 4.0 * frame_scale))
    bpy.ops.object.camera_add(location=cam_loc)
    cam = bpy.context.object
    cam.name = "85mm dead-on panel camera"
    cam.data.lens = 85
    cam.data.sensor_width = 36
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    return dict(world=world, key=key, kicker=kicker, fill=fill, zenith=top, rake=raking,
                camera=cam)


# ------------------------------------------------------------------ rack studio
# ONE LIGHT FOR A WHOLE PANEL (pass 45; Nolan's crud_ui rack light, adopted by
# Sam). The house knob studio is built at the RACK's span and every element
# sits where it is under it, so the whole panel is lit as one scene; what flat
# faces reflect can be a DARK ROOM (the zenith scrim and rake still light the
# faces but are hidden from reflections) with REFLECTION CARDS over it:
# feathered softboxes seen only in reflection. Lengths are rack world units
# from its centre, y up.
CARD_FALLOFF = 0.6       # a card's centre this much brighter than its corners


def reflection_card(name, x, y, w, h, feather, z, radiance, turn_deg=0.0, tilt_deg=0.0):
    """A w x h softbox card at (x, y), height z, unseen by the camera but seen
    in reflection and lighting the faces below it like the softbox it is:
    full inside, eased to nothing across `feather`, its centre CARD_FALLOFF
    brighter than its corners, at `radiance`. `turn_deg` turns it about the
    vertical; `tilt_deg` 90 stands it up as a wall facing -y."""
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(x, y, z))
    ob = bpy.context.object
    ob.name = name
    ob.scale = (w + 2 * feather, h + 2 * feather, 1.0)
    ob.rotation_euler = (math.radians(tilt_deg), 0.0, math.radians(turn_deg))
    for ray in ("camera", "shadow", "transmission", "volume_scatter"):
        setattr(ob, "visible_" + ray, False)

    def build(n, links, em):
        sep = n.new("ShaderNodeSeparateXYZ")
        coord = n.new("ShaderNodeTexCoord")
        links.new(coord.outputs["Generated"], sep.inputs[0])
        masks = []
        for axis, size in (("X", w), ("Y", h)):
            full = size + 2 * feather
            centred, dist, ramp = n.new("ShaderNodeMath"), n.new("ShaderNodeMath"), \
                n.new("ShaderNodeMapRange")
            centred.operation, dist.operation = "SUBTRACT", "ABSOLUTE"
            centred.inputs[1].default_value = 0.5
            links.new(sep.outputs[axis], centred.inputs[0])
            links.new(centred.outputs[0], dist.inputs[0])
            ramp.interpolation_type = "SMOOTHSTEP"
            for sock, v in (("From Min", size / 2 / full), ("From Max", 0.5),
                            ("To Min", 1.0), ("To Max", 0.0)):
                ramp.inputs[sock].default_value = v
            links.new(dist.outputs[0], ramp.inputs["Value"])
            masks.append(ramp.outputs["Result"])
        both = n.new("ShaderNodeMath")
        both.operation = "MULTIPLY"
        links.new(masks[0], both.inputs[0])
        links.new(masks[1], both.inputs[1])
        off = n.new("ShaderNodeVectorMath")
        off.operation = "SUBTRACT"
        off.inputs[1].default_value = (0.5, 0.5, 0.0)
        links.new(coord.outputs["Generated"], off.inputs[0])
        reach = n.new("ShaderNodeVectorMath")
        reach.operation = "MULTIPLY"
        reach.inputs[1].default_value = (2.0, 2.0, 0.0)
        links.new(off.outputs[0], reach.inputs[0])
        r2 = n.new("ShaderNodeVectorMath")
        r2.operation = "DOT_PRODUCT"
        links.new(reach.outputs[0], r2.inputs[0])
        links.new(reach.outputs[0], r2.inputs[1])
        hot = n.new("ShaderNodeMapRange")
        for sock, v in (("From Min", 0.0), ("From Max", 2.0), ("To Min", 1.0),
                        ("To Max", 1.0 - CARD_FALLOFF)):
            hot.inputs[sock].default_value = v
        links.new(r2.outputs["Value"], hot.inputs["Value"])
        shaped, amp = n.new("ShaderNodeMath"), n.new("ShaderNodeMath")
        shaped.operation = amp.operation = "MULTIPLY"
        amp.label = "radiance"
        amp.inputs[1].default_value = radiance
        links.new(both.outputs[0], shaped.inputs[0])
        links.new(hot.outputs["Result"], shaped.inputs[1])
        links.new(shaped.outputs[0], amp.inputs[0])
        links.new(amp.outputs[0], em.inputs["Strength"])

    ob.data.materials.append(_emissive(name, ZENITH_COLOR, build))
    return ob


# Card sets: (x, y, w, h, feather, radiance x the zenith scrim's centre, z,
# turn deg[, tilt deg]), world units from the centre of the LIT RECT they were
# laid out over: CARD_LIT, w x h, open-cepstrum's plates. rack_studio lays a
# set out over a panel's own lit rect (place_cards).
CARD_LIT = (7.78, 2.33)
CARD_SETS = {
    # Nolan's rack light: one big softbox hung high, turned so its lower edge
    # runs diagonally through the middle of the rack; a rim wall behind the
    # rack's top edge for the plates' upper bevels; a faint fill. At half his
    # radiance: one gain for the whole scene, low enough that a clear coat
    # doesn't haze over (open-cepstrum cut it per plate, which no one scene can)
    "rack": [(-0.27, 1.05, 8.0, 2.4, 0.35, 3.0, 2.6, -12.6),
             (0.0, 1.6, 10.0, 1.0, 0.1, 6.0, 0.5, 0.0, 90.0),
             (0.0, 0.0, 9.0, 3.5, 1.5, 0.125, 1.6)],
}

# Whole-panel light presets for rack_studio: (stops, rake, rake_elev, dark room,
# card set). `rack` is the panel light: Nolan's crud_ui rack light
# (open-cepstrum 0.16.0) in a dark room. `house` is the knob studio as it
# lights a single part, at the panel's span, for comparison.
RACK_LIGHTS = {
    "rack": dict(stops=-0.6, rake=0.6, rake_elev=25.0, dark_room=True, cards="rack"),
    "house": dict(stops=PANEL_STOPS, rake=None, rake_elev=None, dark_room=False, cards=None),
}


def place_cards(cards, lit, view):
    """A card set laid out over the lit rect `lit` = (x, y, w, h), its centre
    and size in world units, seen by a camera `view` over the origin: the set
    is scaled uniformly by k = max(w / CARD_LIT[0], h / CARD_LIT[1]) (it
    covers the rect; each card keeps its solid angle from the rect and its
    radiance) and each card centred where the rect's centre reflects at the
    card's height z * k, (x, y) * (1 + z * k / view), plus its own offset * k.
    So every point of the rect sees the set as open-cepstrum's plates see it
    from that camera. Returns the cards' reflection_card args."""
    lx, ly, lw, lh = lit
    k = max(lw / CARD_LIT[0], lh / CARD_LIT[1])
    out = []
    for c in cards:
        x, y, w, h, feather, gain, z, *turn = c
        m = 1.0 + z * k / view
        out.append((lx * m + x * k, ly * m + y * k, w * k, h * k, feather * k, z * k, gain,
                    *turn))
    return out


def rack_studio(scene, span, lit, view, light="rack", local_dir=None, **over):
    """One light for a whole panel `span` world units across: the house knob
    studio at that span (no camera), under the RACK_LIGHTS preset `light`
    (any of its keys overridden by keyword), its zenith scrim and rake hidden
    from reflections in a dark room, and the preset's reflection cards at
    multiples of the scrim's centre radiance, laid out over the lit rect `lit`
    (x, y, w, h world units: what the cards light, the panel's plates) for the
    camera `view` over the origin (place_cards). Returns knob_studio's dict
    plus `cards`."""
    p = {**RACK_LIGHTS[light], **over}
    rig = knob_studio(scene, scale=span, local_dir=local_dir, camera=False, stops=p["stops"],
                      rake=p["rake"], rake_elev=p["rake_elev"])
    if p["dark_room"]:
        for ob in scene.objects:
            if ob.name.startswith("zenith scrim") or ob.name.startswith("rake"):
                ob.visible_glossy = False
    rake = RAKE if p["rake"] is None else p["rake"]
    s = rake_balance(rake)[1]
    unit = ZENITH_L * ZENITH_K * s * 2.0 ** (p["stops"] - PANEL_STOPS)
    cards = []
    for i, c in enumerate(place_cards(CARD_SETS.get(p["cards"]) or [], lit, view)):
        x, y, w, h, feather, z, gain, *turn = c
        cards.append(reflection_card(f"reflection card {i}", x, y, w, h, feather, z,
                                     gain * unit, *turn))
    rig["cards"] = cards
    return rig


# ----------------------------------------------------------------- panel camera
def panel_camera(scene, w, h, tilt_deg=0.0, tab_edge=None, tab_depth=0.22):
    """The camera for any rig lighting a w x h panel: 85 mm framing w to ~80 %
    at `tilt_deg`, widened by `tab_depth` toward `tab_edge`."""
    tilt = math.radians(float(tilt_deg))
    lens, sensor = 85.0, 36.0
    half_fov = math.atan((sensor / 2) / lens)
    fw, fh, aim_x, aim_y = w, h, 0.0, 0.0
    if tab_edge is not None:
        if tab_edge in ("top", "bottom"):
            fh += tab_depth
            aim_y = (tab_depth / 2) * (1 if tab_edge == "top" else -1)
        else:
            fw += tab_depth
            aim_x = (tab_depth / 2) * (1 if tab_edge == "right" else -1)
    dist = (max(fw, fh * 1.5) * 0.62) / math.tan(half_fov)
    bpy.ops.object.camera_add(
        location=(aim_x,
                  aim_y * math.cos(tilt) - dist * math.sin(tilt),
                  dist * math.cos(tilt) + aim_y * math.sin(tilt)),
        rotation=(tilt, 0, 0))
    cam = bpy.context.object
    cam.data.lens = lens
    scene.camera = cam
    return cam


# ------------------------------------------------------------------------ bloom
def bloom(scene, threshold=0.35, strength=0.55, size=5.0, smoothness=0.75,
          glare_type="Bloom", quality="High", name="segment_glare", attach=True):
    """Veiling glare as a CompositorNodeTree: RLayers -> Glare -> group output.
    Threshold is in scene-linear emission units. `attach=False` builds the group
    without assigning `scene.compositing_node_group` (display-segment's
    `--noglare`). Returns the node group."""
    ng = bpy.data.node_groups.new(name, "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="INPUT", socket_type="NodeSocketColor")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    gi = ng.nodes.new("CompositorNodeRLayers")
    gi.scene = scene
    go = ng.nodes.new("NodeGroupOutput")
    gl = ng.nodes.new("CompositorNodeGlare")
    gl.inputs["Type"].default_value = glare_type
    gl.inputs["Quality"].default_value = quality
    gl.inputs["Threshold"].default_value = threshold
    gl.inputs["Smoothness"].default_value = smoothness
    gl.inputs["Strength"].default_value = strength
    gl.inputs["Size"].default_value = size
    ng.links.new(gi.outputs[0], gl.inputs["Image"])
    ng.links.new(gl.outputs["Image"], go.inputs[0])
    if attach:
        scene.compositing_node_group = ng
        scene.use_nodes = True
    return ng
