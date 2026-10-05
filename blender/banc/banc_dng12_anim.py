"""16-frame explanatory signal sequence for the BANC DNg12 population.

24 fps, non-looping, transparent RGBA straight alpha, on the unchanged
walking_steering_camera.json so it registers with every existing BANC layer.

The pulse is NOT a y-axis sweep. It travels along each cell's own CAVE skeleton by
geodesic path distance, starting from that cell's input-dominant region, which was
located from real synapse polarity (see banc_dng12_polarity.py). Branches light up
according to their path distance, so the signal forks where the arbor forks.

Visual contract from the brief:
  full mesh faintly visible at 10-15% coloured opacity
  skeleton visible at low opacity
  bright soft-edged pulse about 8-10% of normalised path length
  a short trailing glow behind the front
  frames 00 and 15 fully transparent

  blender --background --python banc_dng12_anim.py -- device=GPU
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(kv.split("=", 1) for kv in argv if "=" in kv)

POP = "D:/Meshes/banc/dng12_population.json"
POLARITY = "D:/Meshes/banc/dng12_polarity.npz"
MESH_DIR = "D:/Meshes/banc/walking_steering_dec"
CAM_JSON = "D:/Meshes/banc/walking_steering_camera.json"
OUTDIR = opts.get("outdir", "D:/Meshes/renders/layers/groom-head-dng12")

RES = (1600, 1200)
SAMPLES = int(opts.get("samples", 200))
DEVICE = opts.get("device", "GPU").upper()
NM_TO_UM = 0.001
N_FRAMES, FPS = 16, 24

BASE = (0xC7 / 255, 0xA6 / 255, 0xF3 / 255)   # #C7A6F3
CORE = (0xF2 / 255, 0xE6 / 255, 0xFF / 255)   # bright soft core
REST_ALPHA = float(opts.get("rest", 0.13))    # 10-15% resting mesh opacity
SKEL_ALPHA = float(opts.get("skelalpha", 0.22))
SKEL_RADIUS_UM = float(opts.get("skelr", 0.45))
SIGMA = float(opts.get("sigma", 0.045))       # ~10% of path length at FWHM
TAIL = float(opts.get("tail", 2.4))           # trailing glow is this much longer

# frames 1..14 carry the pulse; 00 and 15 are empty by contract
POS = [None] + list(np.linspace(0.02, 1.00, N_FRAMES - 2)) + [None]
AMP = [0.0, 0.35, 0.70] + [1.0] * 10 + [0.72, 0.34, 0.0]   # 3 + 10 + 3 = 16
assert len(POS) == N_FRAMES and len(AMP) == N_FRAMES

t0 = time.time()
cells = json.load(open(POP))
pol = np.load(POLARITY)
cam_cfg = json.load(open(CAM_JSON))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def nearest_t(verts_nm, skel_nm, t_nodes):
    """Path-distance value for every mesh vertex, from its nearest skeleton node.

    Chunked brute force: Blender ships numpy but not scipy, so no cKDTree here.
    Skeletons are only a few hundred nodes, so this is cheap.
    """
    out = np.empty(len(verts_nm), dtype=np.float32)
    step = 20000
    for i in range(0, len(verts_nm), step):
        chunk = verts_nm[i:i + step]
        d = ((chunk[:, None, 0] - skel_nm[None, :, 0]) ** 2
             + (chunk[:, None, 1] - skel_nm[None, :, 1]) ** 2
             + (chunk[:, None, 2] - skel_nm[None, :, 2]) ** 2)
        out[i:i + step] = t_nodes[d.argmin(1)]
    return out


mesh_objs, skel_objs = [], []
faces = 0
for sid in cells:
    key = f"{sid}|"
    if key + "skel_v" not in pol:
        print(f"[groom] SKIP {sid}: no polarity data")
        continue
    skel_v = pol[key + "skel_v"].astype(np.float64)
    skel_e = pol[key + "skel_e"].astype(int)
    t_nodes = pol[key + "t"].astype(np.float32)

    p = os.path.join(MESH_DIR, f"{sid}.obj")
    if not os.path.exists(p):
        print(f"[groom] SKIP {sid}: no mesh")
        continue
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=p, forward_axis="Y", up_axis="Z")
    obj = list(set(bpy.data.objects) - before)[0]
    assert max(abs(a) for a in obj.rotation_euler) < 1e-6, f"{sid}: importer rotation"
    obj.scale = (NM_TO_UM,) * 3
    me = obj.data
    for poly in me.polygons:
        poly.use_smooth = True
    faces += len(me.polygons)

    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)                        # still nanometres
    tv = nearest_t(co, skel_v, t_nodes)
    me.attributes.new(name="pathT", type="FLOAT", domain="POINT").data.foreach_set(
        "value", tv.astype(np.float32))
    me.color_attributes.new(name="pulse", type="FLOAT_COLOR", domain="POINT")
    mesh_objs.append((obj, tv))

    # --- skeleton as thin tubes, one 2-point spline per edge -----------------
    cu = bpy.data.curves.new(f"skel_{sid}", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = SKEL_RADIUS_UM / NM_TO_UM      # curve lives in nm before scaling
    cu.bevel_resolution = 1
    for a, b in skel_e:
        sp = cu.splines.new("POLY")
        sp.points.add(1)
        sp.points[0].co = (*skel_v[a], 1.0)
        sp.points[1].co = (*skel_v[b], 1.0)
    so = bpy.data.objects.new(f"skel_{sid}", cu)
    scene.collection.objects.link(so)
    so.scale = (NM_TO_UM,) * 3
    skel_objs.append(so)

print(f"[groom] {len(mesh_objs)} cells, {faces/1e6:.1f}M faces, {len(skel_objs)} skeletons")
assert len(mesh_objs) == 28, f"expected 28 DNg12 cells, got {len(mesh_objs)}"

# --- materials ---------------------------------------------------------------
mesh_mat = bpy.data.materials.new("dng12_mesh")
mesh_mat.use_nodes = True
nt = mesh_mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
vc = nt.nodes.new("ShaderNodeVertexColor")
vc.layer_name = "pulse"
nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(vc.outputs["Color"], bsdf.inputs["Emission Color"])
nt.links.new(vc.outputs["Alpha"], bsdf.inputs["Alpha"])
bsdf.inputs["Roughness"].default_value = 0.62
bsdf.inputs["IOR"].default_value = 1.04
bsdf.inputs["Emission Strength"].default_value = 0.55
for obj, _ in mesh_objs:
    obj.data.materials.clear()
    obj.data.materials.append(mesh_mat)

skel_mat = bpy.data.materials.new("dng12_skel")
skel_mat.use_nodes = True
sb = skel_mat.node_tree.nodes["Principled BSDF"]
lin = tuple(srgb_to_linear(c) for c in BASE)
sb.inputs["Base Color"].default_value = (*lin, 1.0)
sb.inputs["Emission Color"].default_value = (*lin, 1.0)
sb.inputs["Emission Strength"].default_value = 0.35
sb.inputs["Roughness"].default_value = 0.62
sb.inputs["IOR"].default_value = 1.04
sb.inputs["Alpha"].default_value = SKEL_ALPHA
for so in skel_objs:
    so.data.materials.append(skel_mat)

# --- camera, unchanged --------------------------------------------------------
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

target = Vector(cam_cfg["look_at_um"])
back = (Vector(cam_cfg["location_um"]) - target).normalized()
right = back.cross(Vector((0, 0, 1))).normalized()
true_up = right.cross(back).normalized()
SPAN, LIGHT = 900.0, 0.038


def add_light(name, d, energy, size):
    L = bpy.data.lights.new(name, type="AREA")
    L.energy = energy * LIGHT
    L.size = size
    L.color = (1.0, 0.98, 0.96)
    o = bpy.data.objects.new(name, L)
    scene.collection.objects.link(o)
    pos = target + d.normalized() * SPAN * 1.6
    o.location = pos
    o.rotation_euler = (target - pos).to_track_quat("-Z", "Y").to_euler()


add_light("key", back * 0.7 + right * 0.8 + true_up * 0.5, 5.0e8, SPAN * 0.9)
add_light("fill", back * 0.6 - right * 0.9 + true_up * 0.1, 1.6e8, SPAN * 1.2)
add_light("rim", -back * 0.5 - true_up * 0.8, 2.4e8, SPAN * 1.0)
w = bpy.data.worlds.new("w")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.06, 0.09, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.6
scene.world = w

scene.render.engine = "CYCLES"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = False          # never filter across the alpha boundary
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
    print(f"[groom] device fell back to CPU: {e}")
    scene.cycles.device = "CPU"

scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.color_depth = "8"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.render.use_compositing = False
scene.render.dither_intensity = 0.0
scene.render.fps = FPS

lin_base = np.array([srgb_to_linear(c) for c in BASE], dtype=np.float32)
lin_core = np.array([srgb_to_linear(c) for c in CORE], dtype=np.float32)
os.makedirs(OUTDIR, exist_ok=True)

for f in range(N_FRAMES):
    amp = AMP[f]
    if amp <= 0.0:
        for obj, _ in mesh_objs:
            obj.hide_render = True
        for so in skel_objs:
            so.hide_render = True
        note = "fully transparent"
    else:
        for obj, _ in mesh_objs:
            obj.hide_render = False
        for so in skel_objs:
            so.hide_render = False
        p = POS[f]
        for obj, tv in mesh_objs:
            dt = tv - p
            # asymmetric: a short bright front, a longer trailing glow behind it
            s = np.where(dt >= 0, SIGMA, SIGMA * TAIL)
            g = np.exp(-((dt / s) ** 2)).astype(np.float32) * amp
            col = lin_base[None, :] + (lin_core - lin_base)[None, :] * g[:, None]
            a = REST_ALPHA + (1.0 - REST_ALPHA) * g
            rgba = np.empty((len(tv), 4), dtype=np.float32)
            rgba[:, :3] = col
            rgba[:, 3] = a
            obj.data.color_attributes["pulse"].data.foreach_set("color", rgba.ravel())
            obj.data.update()
        sb.inputs["Alpha"].default_value = SKEL_ALPHA * min(1.0, amp * 1.4)
        note = f"pulse at {p:.3f} amp {amp:.2f}"
    scene.render.filepath = os.path.join(OUTDIR, f"frame-{f:02d}.png")
    bpy.ops.render.render(write_still=True)
    print(f"[groom] frame {f:02d}  {note}", flush=True)

print(f"[groom] DONE {N_FRAMES} frames at {FPS} fps ({1000*N_FRAMES/FPS:.0f} ms) "
      f"in {(time.time()-t0)/60:.1f} min -> {OUTDIR}")
