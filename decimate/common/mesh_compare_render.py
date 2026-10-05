"""Render two mesh variants from an IDENTICAL camera so a person can judge them.

This exists because every numeric check on this problem has misled me:

  - face count says how much went, never whether it was visible
  - silhouette occupancy counted interior vertices, so hidden geometry scored as
    part of the outline and its removal looked like damage
  - bounding box extent only catches a branch going missing at the very tip, and
    says nothing about a branch that got thinner, kinked or holed
  - ambient occlusion thresholds were swept on the wrong scale entirely

So the verdict comes from a picture. Two variants, one camera, one material, one
light rig, rendered wide and then zoomed into the densest part of the arbor, which
is where decimation does its damage and where a soma's hidden shells would be.

  blender --background --python mesh_compare_render.py -- \
      a=path\to\RAW.obj b=path\to\CLEAN.obj out=D:\Meshes\renders\cmp [zoom=0.22]

Renders four images: a_wide, b_wide, a_zoom, b_zoom.
"""
import math
import os
import sys
import time

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)

PATH_A = opts["a"]
PATH_B = opts["b"]
OUT = opts.get("out", r"D:\Meshes\renders\cmp")
ZOOM = float(opts.get("zoom", 0.22))
RES = tuple(int(x) for x in opts.get("res", "1600x1600").split("x"))
SAMPLES = int(opts.get("samples", 64))
LENS, SENSOR = 50.0, 36.0
TARGET = 10.0

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = "BLENDER_EEVEE_NEXT"
    s.eevee.taa_render_samples = SAMPLES
    s.render.resolution_x, s.render.resolution_y = RES
    s.render.film_transparent = False
    s.render.image_settings.file_format = "PNG"
    return s


def load(path):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path)
    return [o for o in bpy.data.objects if o not in before and o.type == "MESH"]


def bbox(objs):
    mins, maxs = Vector((1e18,) * 3), Vector((-1e18,) * 3)
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                mins[i], maxs[i] = min(mins[i], w[i]), max(maxs[i], w[i])
    return mins, maxs


# The FRAMING IS COMPUTED ONCE, from variant A, and reused verbatim for B. Framing
# each variant to its own bounding box would silently zoom them differently, and
# then any difference in the pictures could be the framing rather than the mesh.
# That is the single easiest way to make a comparison render worthless.
frame = {}


def build(path, tag, zoom):
    scene = fresh()
    objs = load(path)
    faces = sum(len(o.data.polygons) for o in objs)
    if not frame:
        mins, maxs = bbox(objs)
        frame["centre"] = (mins + maxs) / 2
        frame["scale"] = TARGET / max((maxs - mins)[i] for i in range(3))
        frame["ext"] = (maxs - mins) * frame["scale"]

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    root = bpy.context.active_object
    for o in objs:
        o.parent = root
        o.matrix_parent_inverse = root.matrix_world.inverted()
    s = frame["scale"]
    root.scale = (s, s, s)
    bpy.context.view_layer.update()
    root.location = -(root.matrix_world.to_3x3() @ frame["centre"])
    bpy.context.view_layer.update()

    # A matte, single colour surface. Emission would hide exactly what we are
    # looking for: a hole or a thinned process reads as shape, and shape needs
    # shading. Low roughness is wrong for submerged tissue, so this is the
    # playbook's underwater look, IOR 1.04, not a glossy plastic.
    mat = bpy.data.materials.new("m_cmp")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.38, 0.62, 0.88, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.55
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = 1.04
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(mat)

    world = bpy.data.worlds.new("w")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.06, 0.08, 1)
    for loc, e in (((6, -8, 6), 900.0), ((-7, -5, 2), 400.0), ((0, 7, -3), 250.0)):
        bpy.ops.object.light_add(type="AREA", location=loc)
        L = bpy.context.active_object
        L.data.energy = e
        L.data.size = 8
        L.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

    ext = frame["ext"]
    fov = 2 * math.atan(SENSOR / (2 * LENS))
    dist = 1.15 * max(ext.x / 2, ext.z / 2) / math.tan(fov / 2) * zoom
    bpy.ops.object.camera_add(location=(0, dist, 0))
    cam = bpy.context.active_object
    cam.data.lens = LENS
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.sensor_width = SENSOR
    cam.rotation_euler = (math.pi / 2, 0, math.pi)
    scene.camera = cam

    scene.render.filepath = f"{OUT}_{tag}"
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[c] {tag:<8} {faces:>10,} faces -> {scene.render.filepath}.png "
          f"({time.time()-t:.0f}s)", flush=True)


for tag, path, z in (("a_wide", PATH_A, 1.0), ("b_wide", PATH_B, 1.0),
                     ("a_zoom", PATH_A, ZOOM), ("b_zoom", PATH_B, ZOOM)):
    build(path, tag, z)
print("[c] DONE", flush=True)
