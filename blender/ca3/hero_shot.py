"""
The hero shot: one thorny pyramidal cell, its mossy fibre boutons, then pull back.

  cell    648518346438632877   165 mossy fibre synapses from 6 distinct fibres
  meshes  D:\\Meshes\\hero\\  native resolution, so the thorny excrescences survive

Camera is one continuous move rather than three cuts: it starts tight on the soma
with the boutons filling the frame, rotates a few degrees while panning slightly
against that rotation, and then dollies out as the fibres and finally the wider
population fade in. Rotation, pan and dolly all ease together so it reads as a
single slow breath outward.

  blender --background --python hero_shot.py -- [key=val]

  still=N          render one frame instead of the sequence (do this first)
  frames=600  res=1080x1920  samples=64
  out=path
"""
import math
import os
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = {}
for tok in argv:
    if "=" in tok:
        k, v = tok.split("=", 1)
        opts[k] = v

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__
hexcol = g["hexcol"]
emissive_material = g["emissive_material"]
set_interp = g["set_interp"]

HERO_DIR = Path(r"D:\Meshes\hero")
FRAMES = int(opts.get("frames", 600))
RES = tuple(int(x) for x in opts.get("res", "1080x1920").split("x"))
SAMPLES = int(opts.get("samples", 64))
OUT = opts.get("out", r"D:\Meshes\renders\hero_shot.mp4")

CELL_COLOR = "#2586F5"      # same blue family as the thorny population
FIBRE_COLOR = "#E2AF5E"     # mossy fibre gold

# --- clean slate ---------------------------------------------------------------------
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for block in (bpy.data.meshes, bpy.data.materials, bpy.data.objects):
    for item in list(block):
        if item.users == 0:
            block.remove(item)

scene = bpy.context.scene
scene.render.fps = g["FPS"]
scene.frame_start, scene.frame_end = 1, FRAMES
g["RESOLUTION"] = RES
g["SAMPLES"] = SAMPLES

# --- import the hero set -------------------------------------------------------------
t0 = time.time()
cell_objs, fibre_objs = [], []
for p in sorted(HERO_DIR.glob("*.obj")):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(p))
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    (cell_objs if p.name.startswith("hero_") else fibre_objs).extend(new)
    for o in new:
        o.name = p.stem
print(f"[hero] imported {len(cell_objs)} cell, {len(fibre_objs)} fibres in "
      f"{time.time()-t0:.0f}s", flush=True)
print(f"[hero] cell faces: {sum(len(o.data.polygons) for o in cell_objs):,}", flush=True)
print(f"[hero] fibre faces: {sum(len(o.data.polygons) for o in fibre_objs):,}", flush=True)

allobjs = cell_objs + fibre_objs
for o in allobjs:
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.shade_smooth()

# --- normalise on the CELL, not the fibres: it is the subject -------------------------
lo, hi = g["world_bounds"](cell_objs)
centre = (lo + hi) / 2.0
span = max((hi - lo)[i] for i in range(3))
TARGET = 10.0
factor = TARGET / span
print(f"[hero] cell span {span:,.0f} nm -> scale {factor:.3e}", flush=True)

bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
root = bpy.context.active_object
root.name = "HERO_ROOT"
root.scale = (factor, factor, factor)

bpy.ops.object.empty_add(type="PLAIN_AXES", location=-centre)
pivot = bpy.context.active_object
pivot.name = "hero_pivot"
pivot.parent = root
pivot.matrix_parent_inverse = Matrix.Identity(4)
for o in allobjs:
    o.parent = pivot
    o.matrix_parent_inverse = Matrix.Identity(4)

# Force the dependency graph to catch up. matrix_world reads STALE straight after
# reparenting, so anything computed from it lands in the pre-parent coordinate
# space. That is what put the soma in the millions instead of in scene units.
bpy.context.view_layer.update()

# --- materials -----------------------------------------------------------------------
mat_cell = emissive_material("mat_hero_cell", hexcol(CELL_COLOR), 1.0)
mat_fib = emissive_material("mat_hero_fibre", hexcol(FIBRE_COLOR), 1.0)
for o in cell_objs:
    o.data.materials.clear()
    o.data.materials.append(mat_cell)
for o in fibre_objs:
    o.data.materials.clear()
    o.data.materials.append(mat_fib)

# --- fibres fade in during the pull-back ----------------------------------------------
FIB_IN, FIB_FULL = int(FRAMES * 0.28), int(FRAMES * 0.52)
for i, o in enumerate(fibre_objs):
    t = i / max(1, len(fibre_objs) - 1)
    s = FIB_IN + t * (FIB_FULL - FIB_IN) * 0.6
    o.scale = (0, 0, 0)
    o.keyframe_insert(data_path="scale", frame=int(s))
    o.scale = (1, 1, 1)
    o.keyframe_insert(data_path="scale", frame=int(s + FRAMES * 0.10))
    set_interp(o, "CUBIC", "EASE_OUT")

# --- the camera move ------------------------------------------------------------------
# soma position drives where we start: tight on it, boutons filling the frame
verts = []
for o in cell_objs:
    n = len(o.data.vertices)
    co = np.empty(n * 3)
    o.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    if n > 400000:
        co = co[np.linspace(0, n - 1, 400000).astype(int)]
    # Work in WORLD space. Blender's OBJ importer puts its axis conversion in the
    # object's rotation rather than baking it into the vertices, so o.data.vertices
    # are still raw file coordinates while matrix_world is what actually places
    # them. Mixing the two put the camera target 50 units off the cell.
    m = np.array(o.matrix_world)
    verts.append(co @ m[:3, :3].T + m[:3, 3])
v = np.vstack(verts)

# Aim at the THORNS, not the soma. The thorny excrescences sit off to one side
# of the cell body, so a camera centred on the soma pushed them out of frame.
# The 165 real synapse coordinates for this cell mark where the mossy fibre
# boutons attach, which is exactly where the thorns are.
SYN = np.load(os.path.join(r"D:\Meshes", "renders", "hero_synapses.npy"))

# These are raw file coordinates, same as the mesh vertices. The importer's
# axis conversion lives in the object's rotation, so pushing the points through
# the same matrix_world puts them exactly where the meshes ended up.
m0 = np.array(cell_objs[0].matrix_world)
aim = (SYN @ m0[:3, :3].T + m0[:3, 3]).mean(axis=0)
soma = Vector((float(aim[0]), float(aim[1]), float(aim[2])))
print(f"[hero] aiming at the thorn cluster, world "
      f"{tuple(round(float(x), 2) for x in aim)} "
      f"(centroid of {len(SYN)} mossy fibre synapses)", flush=True)

bpy.ops.object.empty_add(type="PLAIN_AXES", location=soma)
target = bpy.context.active_object
target.name = "HERO_TARGET"

bpy.ops.object.empty_add(type="PLAIN_AXES", location=soma)
orbit = bpy.context.active_object
orbit.name = "HERO_ORBIT"

# NEAR must clear the soma itself: the cell spans 10 units, so 0.85 put the
# camera inside the geometry and rendered black. 2.2 sits just outside the cell
# body with the thorns filling the frame.
NEAR, FAR = 2.2, 16.0
bpy.ops.object.camera_add(location=(0.0, -NEAR, NEAR * 0.16))
cam = bpy.context.active_object
cam.name = "HERO_CAM"
cam.data.lens = 60
cam.parent = orbit
track = cam.constraints.new(type="TRACK_TO")
track.target = target
track.track_axis = "TRACK_NEGATIVE_Z"
track.up_axis = "UP_Y"
scene.camera = cam

HOLD = int(FRAMES * 0.22)       # slow drift before the pull-back begins
cam.location = (0.0, -NEAR, NEAR * 0.16)
cam.keyframe_insert(data_path="location", frame=1)
cam.location = (0.0, -NEAR * 1.18, NEAR * 0.19)
cam.keyframe_insert(data_path="location", frame=HOLD)
cam.location = (0.0, -FAR, FAR * 0.22)
cam.keyframe_insert(data_path="location", frame=FRAMES)
set_interp(cam, "SINE", "EASE_IN_OUT")

# a few degrees of rotation, plus a slight pan running against it
orbit.rotation_euler = (0.0, 0.0, math.radians(-9))
orbit.keyframe_insert(data_path="rotation_euler", frame=1)
orbit.rotation_euler = (0.0, 0.0, math.radians(11))
orbit.keyframe_insert(data_path="rotation_euler", frame=FRAMES)
set_interp(orbit, "SINE", "EASE_IN_OUT")

pan = soma + Vector((0.35, 0.0, 0.45))
target.location = soma
target.keyframe_insert(data_path="location", frame=1)
target.location = pan
target.keyframe_insert(data_path="location", frame=int(FRAMES * 0.6))
target.location = soma
target.keyframe_insert(data_path="location", frame=FRAMES)
set_interp(target, "SINE", "EASE_IN_OUT")

# --- look and output --------------------------------------------------------------------
g["build_world"](scene)
g["build_lights"](scene, TARGET, target)
g["apply_render_settings"](scene)
scene.render.filepath = OUT

still = opts.get("still")
if still:
    scene.render.image_settings.file_format = "PNG"
    scene.frame_set(int(still))
    print(f"[hero] still frame {still} -> {OUT}", flush=True)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[hero] rendered in {time.time()-t0:.0f}s", flush=True)
else:
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    print(f"[hero] {FRAMES} frames -> {OUT}", flush=True)
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    el = time.time() - t0
    print(f"[hero] rendered in {el/60:.1f} min ({el/FRAMES:.1f}s per frame)", flush=True)
print("[hero] DONE", flush=True)
