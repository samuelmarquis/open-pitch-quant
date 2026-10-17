"""knob-boss: the compact BOSS-MID pedal knob at one value; the knob family's
reference rig and camera.

  blender -b -P knob_scene.py -- OUT [flags]        flag table: ../README.md

A black moulded base and a low elliptical C-ring (slot `accent`, `same` = the
body material) around a flat radial-brushed metal insert (slot `cap`) whose
integrated rounded pointer lies along local +X. The part is modelled at scale 1
on the object Z axis; families.KnobScene owns flags, slots, throw, studio,
camera and receipt. Blender exits 0 after a script exception: callers check OUT
and the receipt line.
"""

import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "_studio"))
import meshlib  # noqa: E402
from families import KnobScene  # noqa: E402

BODY_PROFILE = [(0.0, 0.500), (0.405, 0.500), (0.440, 0.480), (0.458, 0.435),
                (0.458, 0.070), (0.438, 0.018), (0.380, 0.0), (0.0, 0.0)]


def link_mesh(name, verts, faces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    return ob


def elliptical_c_ring(name, major_radius, tube_radius, vertical_radius,
                      half_gap, z_center, steps=192):
    """Low elliptical C-ring with one symmetric half-ellipsoid at each end."""
    cross_steps = 48
    cap_steps = 8
    start = math.radians(half_gap)
    sweep = 2.0 * math.pi - 2.0 * start
    angles = [start + sweep * i / (steps - 1) for i in range(steps)]
    verts = []
    faces = []

    def add_loop(angle, tangent_shift=0.0, section_scale=1.0, direction=1.0):
        radial = (math.cos(angle), math.sin(angle))
        tangent = (-math.sin(angle), math.cos(angle))
        center = (
            major_radius * radial[0] + direction * tangent_shift * tangent[0],
            major_radius * radial[1] + direction * tangent_shift * tangent[1],
        )
        loop = []
        for j in range(cross_steps):
            around = 2.0 * math.pi * j / cross_steps
            rr = tube_radius * section_scale * math.cos(around)
            zz = vertical_radius * section_scale * math.sin(around)
            loop.append(len(verts))
            verts.append((center[0] + rr * radial[0], center[1] + rr * radial[1],
                          z_center + zz))
        return loop

    main_loops = [add_loop(angle) for angle in angles]
    for i in range(steps - 1):
        for j in range(cross_steps):
            n = (j + 1) % cross_steps
            faces.append((main_loops[i][j], main_loops[i + 1][j],
                          main_loops[i + 1][n], main_loops[i][n]))

    def finish_cap(angle, boundary, direction, reverse):
        previous = boundary
        for i in range(1, cap_steps):
            phase = 0.5 * math.pi * i / cap_steps
            current = add_loop(angle, tangent_shift=tube_radius * math.sin(phase),
                               section_scale=math.cos(phase), direction=direction)
            for j in range(cross_steps):
                n = (j + 1) % cross_steps
                if reverse:
                    faces.append((previous[j], previous[n], current[n], current[j]))
                else:
                    faces.append((previous[j], current[j], current[n], previous[n]))
            previous = current

        radial = (math.cos(angle), math.sin(angle))
        tangent = (-math.sin(angle), math.cos(angle))
        tip = len(verts)
        verts.append((major_radius * radial[0] + direction * tube_radius * tangent[0],
                      major_radius * radial[1] + direction * tube_radius * tangent[1],
                      z_center))
        for j in range(cross_steps):
            n = (j + 1) % cross_steps
            faces.append((previous[j], previous[n], tip) if reverse
                         else (previous[j], tip, previous[n]))

    finish_cap(angles[0], main_loops[0], direction=-1.0, reverse=True)
    finish_cap(angles[-1], main_loops[-1], direction=1.0, reverse=False)

    ob = link_mesh(name, verts, faces)
    for polygon in ob.data.polygons:
        polygon.use_smooth = True
    return ob


def pointer_disc(name, base_radius, outer_tip, shoulder_angle, tip_radius,
                 z_bottom, z_top, steps=180):
    """Planar disc with a tangent-continuous, round-ended integrated pointer."""
    shoulder = math.radians(shoulder_angle)
    outline = []
    for i in range(steps + 1):
        angle = shoulder + (2.0 * math.pi - 2.0 * shoulder) * i / steps
        outline.append((base_radius * math.cos(angle), base_radius * math.sin(angle)))

    def cubic(p0, p1, p2, p3, t):
        u = 1.0 - t
        return (
            u ** 3 * p0[0] + 3.0 * u * u * t * p1[0] + 3.0 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3.0 * u * u * t * p1[1] + 3.0 * u * t * t * p2[1] + t ** 3 * p3[1],
        )

    transition_steps = 12
    cap_steps = 14
    lower_shoulder = outline[-1]
    cap_center_x = outer_tip - tip_radius
    lower_cap = (cap_center_x, -tip_radius)
    for i in range(1, transition_steps + 1):
        outline.append(cubic(lower_shoulder, (base_radius + 0.032, lower_shoulder[1]),
                             (cap_center_x - 0.024, -tip_radius), lower_cap,
                             i / transition_steps))
    for i in range(1, cap_steps + 1):
        angle = -0.5 * math.pi + math.pi * i / cap_steps
        outline.append((cap_center_x + tip_radius * math.cos(angle),
                        tip_radius * math.sin(angle)))
    upper_cap = (cap_center_x, tip_radius)
    upper_shoulder = outline[0]
    for i in range(1, transition_steps):
        outline.append(cubic(upper_cap, (cap_center_x - 0.024, tip_radius),
                             (base_radius + 0.032, upper_shoulder[1]), upper_shoulder,
                             i / transition_steps))

    count = len(outline)
    top_start, bottom_center, bottom_start = 1, count + 1, count + 2
    verts = [(0.0, 0.0, z_top)] + [(x, y, z_top) for x, y in outline]
    verts += [(0.0, 0.0, z_bottom)] + [(x, y, z_bottom) for x, y in outline]
    faces = []
    for i in range(count):
        j = (i + 1) % count
        faces.append((0, top_start + i, top_start + j))
        faces.append((bottom_center, bottom_start + j, bottom_start + i))
        faces.append((top_start + i, bottom_start + i, bottom_start + j, top_start + j))

    ob = link_mesh(name, verts, faces)
    for polygon in ob.data.polygons:
        polygon.use_smooth = polygon.index % 3 == 2
    return ob


class BossKnob(KnobScene):
    COMPONENT = "knob-boss"
    DEFAULT_OUT = "/tmp/knob-boss.png"
    SLOTS = {
        "body": "moulded-black-satin",
        "cap": "aluminium-spun",
        "accent": "same",
    }
    SLOT_SAME = {"accent": "body"}
    SLOT_HELP = {
        "body": "compact cylindrical base material",
        "cap": "flat insert with the integrated pointer",
        "accent": "low C-ring material",
    }

    def build_knob(self):
        body = meshlib.lathe(BODY_PROFILE, "compact cylindrical base")
        self.bind("body", [body])
        ring = elliptical_c_ring("low rounded outer C ring", major_radius=0.400,
                                 tube_radius=0.045, vertical_radius=0.024, half_gap=10.5,
                                 z_center=0.504, steps=192)
        self.bind("accent", [ring])
        top = pointer_disc("fully flat radial-brushed metal insert", base_radius=0.356,
                           outer_tip=0.436, shoulder_angle=7.4, tip_radius=0.028,
                           z_bottom=0.493, z_top=0.503, steps=180)
        self.bind("cap", [top])
        return [body, ring, top]


if __name__ == "__main__":
    BossKnob.main()
