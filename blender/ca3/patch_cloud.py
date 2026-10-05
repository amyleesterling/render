"""Rebuild just the synapse cloud inside the existing .blend.

The first cloud was built from raw CAVE coordinates while every cell had come
through Blender's OBJ importer, which converts (x, y, z) to (x, -z, y). The
cloud therefore landed in a different part of the scene. This replaces it with
the axis-corrected version without re-importing 13 GB of meshes.
"""
import time

import bpy
import numpy as np
from mathutils import Vector

BLEND = r"D:\Meshes\ca3_scene.blend"
t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=BLEND)
print(f"[patch] opened in {time.time()-t0:.0f}s", flush=True)

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__

for name in ("SYNAPSES", "synapse_dot"):
    o = bpy.data.objects.get(name)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)
        print(f"[patch] removed old {name}", flush=True)

pivot = bpy.data.objects.get("pivot_synapses")
root = bpy.data.objects.get("CA3_ROOT")
factor = root.scale[0]
g["build_synapse_cloud"](pivot, factor)

cloud = bpy.data.objects["SYNAPSES"]
lo = Vector((float("inf"),) * 3)
hi = Vector((float("-inf"),) * 3)
for c in cloud.bound_box:
    p = cloud.matrix_world @ Vector(c)
    lo = Vector((min(lo[i], p[i]) for i in range(3)))
    hi = Vector((max(hi[i], p[i]) for i in range(3)))
cc = (lo + hi) / 2
print(f"[patch] cloud centre now ({cc.x:.2f}, {cc.y:.2f}, {cc.z:.2f}) "
      f"span ({(hi-lo).x:.2f}, {(hi-lo).y:.2f}, {(hi-lo).z:.2f})", flush=True)

cells = bpy.data.collections["thorny_pyramidals"].objects
lo2 = Vector((float("inf"),) * 3)
hi2 = Vector((float("-inf"),) * 3)
for o in cells:
    for c in o.bound_box:
        p = o.matrix_world @ Vector(c)
        lo2 = Vector((min(lo2[i], p[i]) for i in range(3)))
        hi2 = Vector((max(hi2[i], p[i]) for i in range(3)))
c2 = (lo2 + hi2) / 2
print(f"[patch] thorny centre  ({c2.x:.2f}, {c2.y:.2f}, {c2.z:.2f}) "
      f"span ({(hi2-lo2).x:.2f}, {(hi2-lo2).y:.2f}, {(hi2-lo2).z:.2f})", flush=True)
print(f"[patch] centre offset: {(cc - c2).length:.2f} units", flush=True)

t0 = time.time()
bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=False)
print(f"[patch] saved in {time.time()-t0:.0f}s", flush=True)
print("[patch] DONE", flush=True)
