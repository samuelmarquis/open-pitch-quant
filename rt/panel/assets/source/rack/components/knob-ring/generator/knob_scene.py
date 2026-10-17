"""knob-ring: the segmented modulation-indicator collar that straddles a knob.

  blender -b -P knob_scene.py -- OUT [flags]        flags and compositing: ../README.md

A panel-mounted ring of illuminated segment lenses inlaid through apertures in a
solid plate. The arc lights FROM `--from` TO `--value`, so the ring can disagree
with the knob's pointer. Every segment is a real diffusant lens: unlit it stays
a visible ghost.

Parts and slots: the plate (slot `housing`) is built as its own complement (an
inner band, an outer band and one web per gap between apertures; no booleans);
a sealed backing (slot `backing`) under the apertures; one lens per segment
(slot `diffuser`). `--hue`/`--lens` and `--ghost` fill the diffuser key's `hue`
and `ghost` params, and each lens state sets `emission` (lit: the spec's
`emission` or `--emit`; cursor: that x `--cursor-gain`; unlit: 0), when the key
declares them. Lit and unlit lenses differ in emission strength only, which is
what keeps `ring-bake/1` layers additive.

`--cut-in on` (old `--housing none`) makes the plate a shadow catcher and hides
the backing: the render carries only the lenses and the occlusion the cut casts,
for compositing over the consumer's own panel.

Registration: rigs.knob_studio and the knob family camera, so a ring frame and a
knob frame composite with no transform. Fit: the default `--inner` is derived
from the knob footprint standard (families.knob.STANDARD_FOOTPRINT, an apparent
radius at z = 0) so that the plate's inner edge, projected from its top corner
(inner + chamfer, z = --height), sits KNOB_TUCK_PX inside a standard knob's
silhouette at 640 px (`inner_default`). Bake flags: `--lit i|none` lights
exactly one segment (or none) and bypasses value, from and cursor; `--isolate`
leaves the lenses the only light (rigs.isolate: black world, every other
source hidden). Blender exits 0 after a script exception:
callers check OUT and the receipt line.
"""

import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
import meshlib  # noqa: E402
from families import Alias, ComponentScene, Flag  # noqa: E402
from families.knob import PANEL_CAM_Z, STANDARD_FOOTPRINT  # noqa: E402
from scaffold import SWITCH  # noqa: E402

# led-indicator's glow roster
HUES = {
    "green": (0.10, 1.00, 0.25),
    "amber": (1.00, 0.52, 0.07),
    "red": (1.00, 0.11, 0.05),
    "mcblue": (0.08, 0.60, 1.00),
    "white": (1.00, 0.95, 0.85),
}
BAND_RATIO = 0.663 / 0.535    # --outer default = --inner x this
KNOB_TUCK_PX = 2.5            # knob silhouette overlap of the plate's inner edge
CANON_RES = 640               # ... in pixels of this frame
LENS_MM, SENSOR_MM = 85.0, 36.0
PX_PER_UNIT = CANON_RES / (2.0 * PANEL_CAM_Z * (SENSOR_MM / 2.0) / LENS_MM)  # at z = 0


def plate_bevel(relief, height):
    """Top-edge chamfer: a wide chamfer on a thin plate draws a bright ring."""
    return 0.0025 if relief == "flat" else height * 0.18


def inner_default(height, bevel):
    """--inner whose top corner (inner + bevel, z = height) projects
    KNOB_TUCK_PX inside a STANDARD_FOOTPRINT knob's silhouette at CANON_RES."""
    apparent = STANDARD_FOOTPRINT - KNOB_TUCK_PX / PX_PER_UNIT
    return apparent * (PANEL_CAM_Z - height) / PANEL_CAM_Z - bevel
EPS = 0.003                   # solids overlap rather than abut
WEB_LIFT = 4e-4               # web tops clear the band tops (no coplanar faces)


def spun(name, profile):
    return meshlib.revolve(profile, name, steps=192, collapse_axis=False, order="angle",
                           smooth_angle=None)


class KnobRing(ComponentScene):
    COMPONENT = "knob-ring"
    DEFAULT_OUT = "/tmp/ring.png"
    SLOTS = {
        "housing": "paint-matte-dark",
        "backing": "paint-matte-dark",
        "diffuser": "diffusant-matte",
    }
    SLOT_HELP = {
        "housing": "plate the apertures are cut into; `plate` = the default key",
        "backing": "sealed backing under the apertures",
        "diffuser": "segment lens material",
    }
    FLAGS = (
        Flag("--value", float, 0.75, help="live / modulated level, 0..1"),
        Flag("--from", float, 0.0, help="where the lit arc starts (the set point), 0..1"),
        Flag("--mode", str, "bar", choices=("bar", "dot"),
             help="bar: arc from --from to --value; dot: the one segment at --value"),
        Flag("--cursor", str, "on", choices=("on", "off"),
             help="bar mode: brighten the segment at --value"),
        Flag("--cursor-gain", float, 1.7, help="cursor segment emission multiplier"),
        Flag("--hue", str, "red", help=f"lens colour: {' | '.join(HUES)}"),
        Flag("--lens", str, None, help="explicit lens colour r,g,b; overrides --hue"),
        Flag("--emit", float, 1.45, help="lit lens emission strength"),
        Flag("--ghost", float, 0.036, help="unlit lens albedo scale (ghost / lit contrast)"),
        Flag("--segments", int, 48, help="lens count across the sweep, >= 2"),
        Flag("--start-deg", float, -135.0,
             help="angle of value 0, deg CCW from 3 o'clock; angles run clockwise"),
        Flag("--end-deg", float, None, help="angle of value 1; equal to --start-deg = 360"),
        Flag("--sweep", float, 270.0, help="arc in degrees; used only without --end-deg"),
        Flag("--relief", str, "flat", choices=("flat", "raised"),
             help="flat: thin inlaid plate; raised: thick flat-bottomed plate"),
        Flag("--height", float, None, help="plate thickness; default 0.026 flat, 0.085 raised"),
        Flag("--aperture", str, "0.12,0.92",
             help="aperture band as two rising fractions of --inner..--outer"),
        Flag("--inner", float, None,
             help="plate inner radius, world units at scale 1; default tucks it "
                  f"{KNOB_TUCK_PX:g} px under a standard-footprint knob"),
        Flag("--outer", float, None, help="plate outer radius; default --inner x 0.663/0.535"),
        Flag("--gap", float, 0.34, help="fraction of each segment pitch left solid"),
        Flag("--cut-in", str, "off", choices=("on", "off"),
             help="plate as shadow catcher, backing hidden"),
        Flag("--lit", str, "auto", help="bake: light only segment i, or none; auto = --value/--from"),
        Flag("--isolate", SWITCH, help="bake: the lenses are the only light (rigs.isolate)"),
        Flag("--device", str, "gpu", choices=("gpu", "cpu"), help="cpu forces the CPU device"),
    )
    ALIASES = {
        "housing": [Alias("--housing", values={"plate": "paint-matte-dark"})],
        "cut-in": [Alias("--housing", values={"none": "on"})],
    }

    # ------------------------------------------------------------- resolve
    def validate(self):
        super().validate()
        a = self.args
        for name in ("value", "from"):
            if not 0.0 <= a[name] <= 1.0:
                raise SystemExit(f"knob-ring: --{name} must be in 0..1")
        if a.segments < 2:
            raise SystemExit("knob-ring: --segments must be at least 2")
        if a.lens:
            try:
                self.lens_rgb = tuple(float(c) for c in a.lens.split(","))
            except ValueError:
                self.lens_rgb = ()
            if len(self.lens_rgb) != 3:
                raise SystemExit("knob-ring: --lens must be r,g,b")
        elif a.hue in HUES:
            self.lens_rgb = HUES[a.hue]
        else:
            raise SystemExit(f"knob-ring: --hue must be one of {sorted(HUES)}, or pass --lens r,g,b")
        if a.end_deg is not None:
            self.sweep = a.start_deg - a.end_deg
            if self.sweep <= 0.0:
                self.sweep += 360.0
        else:
            self.sweep = a.sweep
        self.height = a.height if a.height is not None else (0.026 if a.relief == "flat" else 0.085)
        self.bevel = plate_bevel(a.relief, self.height)
        if a.inner is None:
            a.values["inner"] = inner_default(self.height, self.bevel)
        self.outer = a.outer if a.outer is not None else a.inner * BAND_RATIO
        if not 0.0 < a.inner < self.outer:
            raise SystemExit("knob-ring: --inner must be positive and less than --outer")
        try:
            self.ap = tuple(float(v) for v in a.aperture.split(","))
        except ValueError:
            self.ap = ()
        if len(self.ap) != 2 or not 0.0 <= self.ap[0] < self.ap[1] <= 1.0:
            raise SystemExit("knob-ring: --aperture must be two rising fractions in 0..1")
        if a.lit in ("auto", "none"):
            self.only_lit = None if a.lit == "auto" else -1
        else:
            try:
                self.only_lit = int(a.lit)
            except ValueError:
                raise SystemExit("knob-ring: --lit must be a segment index or none")

    def slot_key(self, slot):
        key, params = super().slot_key(slot)
        if slot == "backing":
            from matlib import meta

            if "name" in meta(key).params and "name" not in params:
                params["name"] = "ring backing"
        return key, params

    # ------------------------------------------------------------ geometry
    def band(self, name, r0, r1, bevel_in, bevel_out):
        """A full-360 flat band of the plate, chamfered only on a free edge."""
        h, bez = self.height, self.bevel
        prof = [(r0, 0.0)]
        prof += [(r0, h - bez), (r0 + bez, h)] if bevel_in else [(r0, h)]
        prof += [(r1 - bez, h), (r1, h - bez)] if bevel_out else [(r1, h)]
        prof += [(r1, 0.0)]
        return spun(name, prof)

    def build_plate(self, ap_lo, ap_hi, start_r, pitch, span):
        """Inner band, outer band, and one web per solid gap between apertures,
        walking clockwise from --start-deg; a sweep short of 360 adds the dead
        zone as one long web. A web fills the aperture band only, so it never
        protrudes past the bands' chamfers."""
        a = self.args
        plate = [self.band("ring plate inner", a.inner, ap_lo + EPS, True, False),
                 self.band("ring plate outer", ap_hi - EPS, self.outer, False, True)]
        sweep_r = math.radians(self.sweep)
        edges = [start_r]
        for i in range(a.segments):
            mid = start_r - pitch * (i + 0.5)
            edges += [mid + span / 2.0, mid - span / 2.0]
        edges.append(start_r - sweep_r)
        if self.sweep < 359.999:
            edges += [start_r - sweep_r, start_r - 2.0 * math.pi]
        for k in range(0, len(edges) - 1, 2):
            hi, lo = edges[k], edges[k + 1]
            if hi - lo < 1e-6:
                continue
            steps = max(2, min(96, int(math.degrees(hi - lo) / 2.0) + 2))
            plate.append(meshlib.sector(f"ring web{k // 2:03d}", ap_lo - EPS, ap_hi + EPS,
                                        0.0, self.height + WEB_LIFT, lo, hi, steps=steps))
        return plate

    def segment_states(self):
        """Per segment: 0 unlit, 1 lit, 2 cursor. Segment i covers the value band
        [i, i+1] / N and lights when that band overlaps the arc."""
        a = self.args
        n = a.segments
        lo_v, hi_v = min(a["from"], a.value), max(a["from"], a.value)
        cursor_i = min(n - 1, max(0, int(round(a.value * (n - 1)))))
        states = []
        for i in range(n):
            if self.only_lit is not None:
                states.append(1 if i == self.only_lit else 0)
                continue
            v0, v1 = i / n, (i + 1) / n
            on = (v1 > lo_v and v0 < hi_v) if a.mode == "bar" else (i == cursor_i)
            is_cursor = a.cursor == "on" and i == cursor_i and a.mode == "bar"
            states.append(2 if is_cursor else (1 if on else 0))
        return states

    def lens_materials(self, objects):
        """{state: material}: the diffuser key built once per lens state, part-bound
        params measured on every lens."""
        a = self.args
        emit = self.slot_key("diffuser")[1].get("emission", a.emit)
        fill = {"hue": self.lens_rgb, "ghost": a.ghost}
        return {state: self.build_slot("diffuser", objects, params={**fill, "name": name},
                                       force={"emission": emission})
                for state, name, emission in ((1, "lens lit", emit),
                                              (2, "lens cursor", emit * a.cursor_gain),
                                              (0, "lens off", 0.0))}

    # --------------------------------------------------------------- scene
    def build(self):
        import rigs
        from matlib import own_material

        a = self.args
        if a.device == "cpu":
            self.scene.cycles.device = "CPU"
        ap_lo = a.inner + (self.outer - a.inner) * self.ap[0]
        ap_hi = a.inner + (self.outer - a.inner) * self.ap[1]
        # the lens sits down in its aperture so the plate walls shadow it from the key
        inset = min(self.height * 0.42, 0.012) if a.relief == "flat" else self.height * 0.46
        pitch = math.radians(self.sweep) / a.segments
        span = pitch * (1.0 - a.gap)
        start_r = math.radians(a.start_deg)

        plate = self.build_plate(ap_lo, ap_hi, start_r, pitch, span)
        self.bind("housing", plate)
        backing = spun("ring backing", [(a.inner, -0.004), (a.inner, 0.0),
                                        (self.outer, 0.0), (self.outer, -0.004)])
        self.bind("backing", [backing])
        if a.cut_in == "on":
            for ob in plate:
                ob.is_shadow_catcher = True
            backing.hide_render = True

        lenses = []
        for i in range(a.segments):
            mid = start_r - pitch * (i + 0.5)
            # oversize and sunk: the overlap with the plate is buried in the solid
            lenses.append(meshlib.sector(f"lens{i:03d}", ap_lo - EPS, ap_hi + EPS,
                                         0.0, self.height - inset,
                                         mid - span / 2.0 - EPS, mid + span / 2.0 + EPS))
        mats = self.lens_materials(lenses)
        states = self.segment_states()
        for seg, state in zip(lenses, states):
            own_material(seg, mats[state])
        self.notes.append(f"[n_on={sum(1 for s in states if s)}]")

        root = bpy.data.objects.new("ring root", None)
        bpy.context.collection.objects.link(root)
        root.scale = (a.scale, a.scale, a.scale)
        for ob in plate + [backing] + lenses:
            ob.parent = root
            ob.matrix_parent_inverse = root.matrix_world.inverted()

        rigs.knob_studio(self.scene, a.scale, local_dir=self.local_dir)
        if a.isolate:
            # A bake layer holds one segment's contribution and nothing else. The
            # shared helper finds every source by what it is, not by the rig's
            # dict (enumerating that dict missed pass 43's rake, which lit the
            # whole plate in every layer).
            hidden = rigs.isolate(self.scene, keep=lenses)
            self.notes.append(f"[isolate:hidden={len(hidden)}]")


if __name__ == "__main__":
    KnobRing.main()
