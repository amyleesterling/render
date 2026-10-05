"""First look at a BANC cast in Blender, reusing the CA3 look.

  blender --background --python banc_render.py -- shot=shotB still=1 [res=] [samples=]

Imports the OBJs, scales the population into frame, applies the house materials
(submerged, IOR 1.04, no gloss) and renders one still. Nothing is animated yet:
this exists to answer "what does it look like and what scale is it".

OBJ AXIS NOTE, from the CA3 playbook: Blender's importer maps file (x,y,z) to
(x,-z,y) and stores that in the OBJECT ROTATION, not in the vertices. So never
mix o.data.vertices with matrix_world. Everything here goes through matrix_world.
"""
import json
import os
import sys
import time

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)

SHOT = opts.get("shot", "shotB")
ROOT = r"D:\Meshes\banc"
SRC = os.path.join(ROOT, SHOT)
TARGET_SIZE = 10.0

# ---- the house look ----------------------------------------------------------
PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__
hexcol, emissive_material = g["hexcol"], g["emissive_material"]
g["RESOLUTION"] = tuple(int(x) for x in opts.get("res", "1920x1080").split("x"))
g["SAMPLES"] = int(opts.get("samples", 64))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---- who is who --------------------------------------------------------------
if SHOT == "shotB":
    cast = json.load(open(os.path.join(ROOT, "cast.json")))
    HERO = {int(cast["shotB_descending_neuron"])}
    bp = json.load(open(os.path.join(ROOT, "shotB_bodyparts.json")))
    PART = {int(k): v for k, v in bp["part"].items()}
    # The descending neuron keeps ONE constant colour throughout, because it is
    # the through-line. Every target takes the colour of the body part it
    # innervates, read from its own annotation, so the palette carries a
    # measurement rather than decorating. 41 T1, 40 T3, 32 T2, 8 neck, 3 wing.
    ROLE = lambda i: "dn" if i in HERO else PART.get(i, "other")
    COLOURS = {"dn":   hexcol("#FF7A2F"),   # the constant, warm against every target
               "t1":   hexcol("#2E8BE0"),   # front leg, the house blue
               "t2":   hexcol("#17A06B"),   # middle leg, emerald
               "t3":   hexcol("#B84DD8"),   # hind leg, magenta-purple
               "neck": hexcol("#E8A93A"),   # the house gold
               "wing": hexcol("#FF4FA3"),   # pink
               "other": hexcol("#46536B")}  # unlabelled, deliberately quiet
else:
    grp = json.load(open(os.path.join(ROOT, "shotA_groups.json")))
    S, M, I = set(grp["sensory"]), set(grp["motor"]), set(grp["interneurons"])
    ROLE = lambda i: "sensory" if i in S else "motor" if i in M else "inter"
    COLOURS = {"sensory": hexcol("#E8A93A"), "motor": hexcol("#2E8BE0"),
               "inter": hexcol("#17A06B")}

files = sorted(f for f in os.listdir(SRC)
               if f.endswith(".obj") and not f.endswith(".tmp.obj"))
print(f"[banc] {SHOT}: {len(files)} meshes", flush=True)

t0 = time.time()
objs = {}
for n, fn in enumerate(files, 1):
    rid = int(fn[:-4])
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=os.path.join(SRC, fn))
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    for o in new:
        o.name = f"{ROLE(rid)}_{rid}"
    objs.setdefault(ROLE(rid), []).extend(new)
    if n % 25 == 0 or n == len(files):
        print(f"[banc] imported {n}/{len(files)}  {time.time()-t0:.0f}s", flush=True)
bpy.context.view_layer.update()          # matrix_world reads stale without this

faces = sum(len(o.data.polygons) for v in objs.values() for o in v)
print(f"[banc] {faces/1e6:.1f}M faces in {time.time()-t0:.0f}s", flush=True)
for k, v in objs.items():
    print(f"[banc]   {k}: {len(v)} objects", flush=True)

# ---- fit the population into frame -------------------------------------------
all_objs = [o for v in objs.values() for o in v]
mins = Vector((1e18,) * 3)
maxs = Vector((-1e18,) * 3)
for o in all_objs:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mins[i] = min(mins[i], w[i])
            maxs[i] = max(maxs[i], w[i])
centre = (mins + maxs) / 2
span = max((maxs - mins)[i] for i in range(3))
s = TARGET_SIZE / span
print(f"[banc] bbox span {span:.0f} nm -> scale {s:.3e}", flush=True)

bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
root = bpy.context.active_object
root.name = "BANC_ROOT"
for o in all_objs:
    o.parent = root
    o.matrix_parent_inverse = root.matrix_world.inverted()
root.scale = (s, s, s)
# BANC y increases posteriorly: the DN soma sits at y=63,328, the neck connective
# at 92,500-121,000, the T1 leg sensory endings at 134,000-163,000. The OBJ import
# maps file y to Blender z, so raw import puts the BRAIN AT THE BOTTOM and a
# descending neuron appears to ascend. Rotate 180 degrees about X to put the brain
# at the top. This is a rotation, not a mirror, so the anatomy stays honest.
FLIP = opts.get("flip", "1") not in ("0", "false", "no")
if FLIP:
    import math as _m
    root.rotation_euler = (_m.pi, 0.0, 0.0)
    print("[banc] flipped 180 about X: brain at top, descent reads downward", flush=True)
bpy.context.view_layer.update()
# centre AFTER rotation, or the offset is applied in the unrotated frame
root.location = -(root.matrix_world.to_3x3() @ centre)
bpy.context.view_layer.update()

for role, v in objs.items():
    mat = emissive_material(f"mat_{role}", COLOURS[role], 1.0)
    for o in v:
        o.data.materials.clear()
        o.data.materials.append(mat)

# ---- camera, lights, world ---------------------------------------------------
g["build_world"](scene)
g["build_lights"](scene, TARGET_SIZE, root)
# Camera distance is COMPUTED from the bounding box and the lens, not guessed.
# The first attempt put it at 2x TARGET_SIZE with a 55mm lens, which fits 8.7
# units of a 10 unit subject and cut the animal off at both ends.
import math

LENS = float(opts.get("lens", 55.0))
SENSOR = 36.0
RES_W, RES_H = g["RESOLUTION"]
ext = (maxs - mins) * s                       # extent in Blender units after scaling
half_w, half_h = ext.x / 2, ext.z / 2         # after the OBJ axis flip, file z is up
fov_w = 2 * math.atan(SENSOR / (2 * LENS))
fov_h = 2 * math.atan((SENSOR * RES_H / RES_W) / (2 * LENS))
MARGIN = float(opts.get("margin", 1.12))
dist = MARGIN * max(half_w / math.tan(fov_w / 2), half_h / math.tan(fov_h / 2))
print(f"[banc] extent {ext.x:.1f} x {ext.y:.1f} x {ext.z:.1f} units, "
      f"lens {LENS:.0f}mm -> camera distance {dist:.1f}", flush=True)

bpy.ops.object.camera_add(location=(0, -dist, 0))
cam = bpy.context.active_object
cam.data.lens = LENS
# Pin the sensor to the WIDTH. Blender's default AUTO fit maps sensor_width to
# whichever image dimension is larger, so on a portrait render it silently
# becomes the vertical field of view and the distance maths above comes out
# transposed. That framed a 10 unit subject as if it were 4.5 and cut it off on
# all four sides.
cam.data.sensor_fit = "HORIZONTAL"
cam.data.sensor_width = SENSOR
tc = cam.constraints.new(type="TRACK_TO")
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
tgt = bpy.context.active_object
tc.target = tgt
tc.track_axis = "TRACK_NEGATIVE_Z"
tc.up_axis = "UP_Y"
scene.camera = cam
g["apply_render_settings"](scene)

out = opts.get("out", rf"D:\Meshes\renders\banc_{SHOT}_look.png")
scene.render.filepath = out
scene.render.image_settings.file_format = "PNG"
t0 = time.time()
bpy.ops.render.render(write_still=True)
print(f"[banc] rendered {out} in {time.time()-t0:.0f}s", flush=True)
