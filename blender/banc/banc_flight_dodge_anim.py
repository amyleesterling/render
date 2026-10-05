"""12-frame quick-dodge pulse for DNp03, one sequence per anatomical hemisphere.

24 fps, 500 ms, non-looping, transparent RGBA with straight alpha, rendered on the
UNCHANGED walking_steering_camera.json so every frame registers exactly with the
existing BANC layers.

What the animation does and does not claim
-----------------------------------------
This is a **head-to-tail luminance sweep along the neuron's own anterior-posterior
extent**, not branch-specific conduction. No skeleton was used and none is implied.
BANC y increases posteriorly and both DNp03 cells run from y~154,000 nm in the brain
to y~790,000 nm in the nerve cord, crossing the neck connective, so "brain end" and
"nerve cord end" are measured facts about these meshes. The travelling glow is
explanatory animation, not measured neural activity.

Intensity is baked per vertex each frame rather than built from shader math, so the
wavefront is exactly what this file says it is.

  blender --background --python banc_flight_dodge_anim.py -- side=left
  blender --background --python banc_flight_dodge_anim.py -- side=right
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(kv.split("=", 1) for kv in argv if "=" in kv)

SIDE = opts.get("side", "left")
CELL = {"left": "720575941539809997", "right": "720575941558607396"}[SIDE]
MESH_DIR = "D:/Meshes/banc/walking_steering_dec"
CAM_JSON = "D:/Meshes/banc/walking_steering_camera.json"
OUTDIR = opts.get("outdir", f"D:/Meshes/renders/layers/flight-dodge/anatomical-{SIDE}")

RES = (1600, 1200)
SAMPLES = int(opts.get("samples", 256))
DEVICE = opts.get("device", "GPU").upper()
NM_TO_UM = 0.001
FPS, N_FRAMES = 24, 12

PULSE = (0xFF / 255, 0x8F / 255, 0xA8 / 255)   # #FF8FA8 quick-dodge pulse
CORE = (0xFF / 255, 0xD2 / 255, 0xDC / 255)    # #FFD2DC peak core

# Per-frame wavefront position along the neuron (0 = brain end, 1 = nerve cord end),
# global amplitude, and wavefront width. Frame 00 and frame 11 are fully transparent
# so the sequence starts and ends clean: it is a one-shot, not a loop.
#            frame: 0     1     2     3     4     5     6     7     8     9    10    11
POS = [None, 0.03, 0.07, 0.13, 0.25, 0.39, 0.53, 0.67, 0.80, 0.90, 0.96, None]
AMP = [0.00, 0.35, 0.70, 0.92, 0.95, 0.95, 0.95, 0.95, 1.00, 1.00, 0.42, 0.00]
SIG = [None, 0.16, 0.16, 0.17, 0.17, 0.17, 0.17, 0.17, 0.19, 0.21, 0.26, None]

t0 = time.time()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
cam_cfg = json.load(open(CAM_JSON))

path = os.path.join(MESH_DIR, f"{CELL}.obj")
if not os.path.exists(path):
    raise SystemExit(f"missing mesh {path}")
bpy.ops.wm.obj_import(filepath=path, forward_axis="Y", up_axis="Z")
obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
assert max(abs(a) for a in obj.rotation_euler) < 1e-6, "importer added a rotation"
obj.scale = (NM_TO_UM,) * 3
for poly in obj.data.polygons:
    poly.use_smooth = True

me = obj.data
ys = [v.co.y for v in me.vertices]
y0, y1 = min(ys), max(ys)
print(f"[dodge] {SIDE} {CELL}: {len(me.vertices)} verts, {len(me.polygons)} faces, "
      f"y {y0*NM_TO_UM:.1f} to {y1*NM_TO_UM:.1f} um (brain end -> nerve cord end)")

attr = me.color_attributes.new(name="pulse", type="FLOAT_COLOR", domain="POINT")

mat = bpy.data.materials.new("dodge")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
vc = nt.nodes.new("ShaderNodeVertexColor")
vc.layer_name = "pulse"
nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(vc.outputs["Color"], bsdf.inputs["Emission Color"])
bsdf.inputs["Roughness"].default_value = 0.62
bsdf.inputs["IOR"].default_value = 1.04
if "Subsurface Weight" in bsdf.inputs:
    bsdf.inputs["Subsurface Weight"].default_value = 0.22
    bsdf.inputs["Subsurface Radius"].default_value = (6.0, 3.0, 2.4)
me.materials.clear()
me.materials.append(mat)


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def bake(pos, sigma):
    """Colour every vertex by its distance from the wavefront."""
    span = max(y1 - y0, 1e-9)
    data = attr.data
    for i, v in enumerate(me.vertices):
        t = (v.co.y - y0) / span
        g = math.exp(-(((t - pos) / sigma) ** 2))
        rgb = [PULSE[k] + (CORE[k] - PULSE[k]) * g for k in range(3)]
        lin = [srgb_to_linear(c) for c in rgb]
        data[i].color = (lin[0], lin[1], lin[2], 1.0)
    return None


# ---------------------------------------------------------------- camera, unchanged
cd = bpy.data.cameras.new("cam")
cd.type = "PERSP"
cd.sensor_fit = "VERTICAL"
cd.angle_y = math.radians(cam_cfg["lens"]["angle_y_deg"])
cd.clip_start = cam_cfg["clip"]["start_um"]
cd.clip_end = cam_cfg["clip"]["end_um"]
cam = bpy.data.objects.new("cam", cd)
scene.collection.objects.link(cam)
cam.matrix_world = Matrix(cam_cfg["matrix_world"])
scene.camera = cam
bpy.context.view_layer.update()

# ---------------------------------------------------------------- lights
from mathutils import Vector
target = Vector(cam_cfg["look_at_um"])
back = (Vector(cam_cfg["location_um"]) - target).normalized()
right = back.cross(Vector((0, 0, 1))).normalized()
true_up = right.cross(back).normalized()
SPAN, LIGHT = 900.0, 0.038


def add_light(name, direction, energy, size):
    d = bpy.data.lights.new(name, type="AREA")
    d.energy = energy * LIGHT
    d.size = size
    d.color = (1.0, 0.98, 0.96)
    o = bpy.data.objects.new(name, d)
    scene.collection.objects.link(o)
    pos = target + direction.normalized() * SPAN * 1.6
    o.location = pos
    o.rotation_euler = (target - pos).to_track_quat("-Z", "Y").to_euler()


add_light("key", back * 0.7 + right * 0.8 + true_up * 0.5, 5.0e8, SPAN * 0.9)
add_light("fill", back * 0.6 - right * 0.9 + true_up * 0.1, 1.6e8, SPAN * 1.2)
add_light("rim", -back * 0.5 - true_up * 0.8, 2.4e8, SPAN * 1.0)
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.06, 0.09, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
scene.world = world

# ---------------------------------------------------------------- render settings
scene.render.engine = "CYCLES"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = False        # never filter across the alpha boundary
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    if DEVICE == "GPU":
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for dv in prefs.devices:
            dv.use = dv.type in {"OPTIX", "CUDA"}
        scene.cycles.device = "GPU"
    else:
        scene.cycles.device = "CPU"
except Exception as e:
    print(f"[dodge] device fell back to CPU: {e}")
    scene.cycles.device = "CPU"

scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.color_depth = "8"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.render.use_compositing = False
scene.render.dither_intensity = 0.0
scene.render.fps = FPS

os.makedirs(OUTDIR, exist_ok=True)
for f in range(N_FRAMES):
    amp = AMP[f]
    if amp <= 0.0:
        obj.hide_render = True
        note = "fully transparent"
    else:
        obj.hide_render = False
        bake(POS[f], SIG[f])
        me.update()
        bsdf.inputs["Alpha"].default_value = amp
        bsdf.inputs["Emission Strength"].default_value = 0.10 + 0.55 * amp
        note = f"wavefront {POS[f]:.2f} amp {amp:.2f} sigma {SIG[f]:.2f}"
    scene.render.filepath = os.path.join(OUTDIR, f"frame-{f:02d}.png")
    bpy.ops.render.render(write_still=True)
    print(f"[dodge] frame {f:02d}  {note}", flush=True)

print(f"[dodge] {SIDE} DONE: {N_FRAMES} frames at {FPS} fps "
      f"({1000*N_FRAMES/FPS:.0f} ms) in {(time.time()-t0)/60:.1f} min -> {OUTDIR}")
