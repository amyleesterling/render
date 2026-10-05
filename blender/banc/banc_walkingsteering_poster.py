"""Render the BANC walking+steering poster: 81 neurons, transparent background.

For the right-hand panel of amyleesterling.github.io/banc-explorer.

Spec: 1600x1200 WebP, transparent background, straight alpha with no black matte,
sRGB, 52 descending (#ff1493) + 29 ascending (#089c39). This script writes the
RGBA PNG master; banc_walkingsteering_webp.py does the WebP encode and audits the
alpha.

Camera comes from banc/walking_steering_camera.json, which was reconstructed from
the live Neuroglancer viewer and checked to 0.0001 px by
banc_walkingsteering_camera.py. Do not hand-tune it: the whole point is that the
poster keeps the framing of the interactive scene it replaces.

  blender --background --python banc_walkingsteering_poster.py -- dryrun
  blender --background --python banc_walkingsteering_poster.py -- test
  blender --background --python banc_walkingsteering_poster.py -- samples=256
  blender --background --python banc_walkingsteering_poster.py -- device=CPU

`dryrun` builds the whole scene and runs every assert but never renders, so a typo
cannot surface for the first time on a long GPU job.
"""
import glob
import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(kv.split("=", 1) for kv in argv if "=" in kv)
TEST = "test" in argv
DRYRUN = "dryrun" in argv

MESH_DIR = opts.get("meshes", r"D:\Meshes\banc\walking_steering_dec")
IDS_JSON = r"D:\Meshes\banc\walking_steering_ids.json"
CAM_JSON = r"D:\Meshes\banc\walking_steering_camera.json"
LAYERS_JSON = r"D:\Meshes\banc\walking_steering_layers.json"
LAYER = opts.get("layer")     # context-base | forward | turn-left | turn-right
OUT = opts.get("out", r"D:\Meshes\renders\banc_walking_steering_poster.png")
if LAYER and "out" not in opts:
    OUT = os.path.join(r"D:\Meshes\renders\layers", f"{LAYER}.png")

RES = (400, 300) if TEST else (1600, 1200)
if "res" in opts:                       # res=800x600, keeps the 4:3 framing honest
    RES = tuple(int(v) for v in opts["res"].lower().split("x"))
    assert abs(RES[0] / RES[1] - 4 / 3) < 1e-6, f"{RES} is not 4:3, framing would change"
SAMPLES = int(opts.get("samples", 48 if TEST else 256))
DEVICE = opts.get("device", "GPU").upper()
NM_TO_UM = 0.001
# The first rig guess blew 99.7% of lit pixels to 255. These two are the dials.
# Set by measuring clipping and saturation across a 4 value sweep, then looking at
# the tiled sheet, not by eye alone:
#   light  0.010 -> lum 96, 0.0% clipped   (dim)
#   light  0.022 -> lum 122, 0.1% clipped
#   light  0.038 -> lum 149, 0.8% clipped  <- chosen, bright with detail intact
#   light  0.050 -> lum 165, 1.8% clipped  (brain arbor starts blowing out)
LIGHT = float(opts.get("light", 0.038))
EMIT = float(opts.get("emit", 0.03))

# ---- pulse mode -------------------------------------------------------------
# An explanatory travelling pulse along the cell, for the walking-speed overlay.
# It lives in THIS file rather than a fork so the camera, lighting and alpha
# handling stay a single source of truth: a copy would drift and the layers would
# stop registering pixel for pixel, which is the one thing that must never happen.
#
# NOT recorded activity. There is no conduction model here; the speed is chosen so
# it can be watched. Say so wherever this is published.
PULSE = "pulse" in argv or opts.get("pulse", "0") not in ("0", "false", "no")
PULSE_FRAMES = int(opts.get("frames", 16))
# Brain to VNC is +Y, measured not assumed: the long axis of the DNg100 pair spans
# 862 um in Y, and 51% of their vertices sit in the lowest fifth of it, which is
# the dendritic arbor in the brain. The axon runs up through the neck to the VNC.
PULSE_AXIS = opts.get("pulse_axis", "Y").upper()
PULSE_WIDTH = float(opts.get("pulse_width", 0.16))   # fraction of the cell's length
PULSE_GLOW = float(opts.get("pulse_glow", 14.0))     # emission at the crest
PULSE_BASE_ALPHA = float(opts.get("pulse_base", 0.16))  # the mesh, faintly, beneath

MAGENTA = (1.0, 0x14 / 255, 0x93 / 255)      # #ff1493 descending
GREEN = (0x08 / 255, 0x9c / 255, 0x39 / 255)  # #089c39 ascending

t0 = time.time()
cfg = json.load(open(IDS_JSON))
colors = {k: v.lower() for k, v in cfg["segmentColors"].items()}
cam_cfg = json.load(open(CAM_JSON))

# A layer is a subset of the same 81 cells rendered with the same camera, so the
# outputs stack pixel for pixel. Nothing about the camera or the canvas changes.
wanted = set(colors)
if LAYER:
    spec = json.load(open(LAYERS_JSON))["layers"][LAYER]
    if spec["ids"] != "ALL":
        wanted = {row[0] for row in spec["ids"]}
        colors = {row[0]: row[2].lower() for row in spec["ids"]}
    if spec["color"] != "scene":
        colors = {k: spec["color"].lower() for k in wanted}
    print(f"[poster] layer '{LAYER}': {len(wanted)} cells, colour {spec['color']} "
          f"-- {spec['description']}")

# ---------------------------------------------------------------- empty scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- materials
def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_mat(name, rgb):
    """Submerged tissue, not plastic. IOR 1.04 and let subsurface carry it."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    lin = tuple(srgb_to_linear(c) for c in rgb)
    b.inputs["Base Color"].default_value = (*lin, 1.0)
    b.inputs["Roughness"].default_value = 0.62
    b.inputs["IOR"].default_value = 1.04          # tissue in water, NOT 1.38
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = 0.22
        b.inputs["Subsurface Radius"].default_value = (6.0, 3.0, 2.4)  # um
        if "Subsurface Scale" in b.inputs:
            b.inputs["Subsurface Scale"].default_value = 3.0
    b.inputs["Emission Color"].default_value = (*lin, 1.0)
    b.inputs["Emission Strength"].default_value = EMIT   # lift only, the rig lights it
    return mat


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def make_pulse_mat(name, rgb):
    """One travelling band of light along the cell, with the mesh faint beneath.

    Position is read in WORLD space, not object space. Every cell is a separate
    object, so object coordinates would give each its own origin and the two
    DNg100s would pulse independently instead of together. World space is the one
    frame they share.

    The crest is a triangular window around a moving centre `p`, which is keyframed
    from before the brain end to past the VNC end so the pulse enters and leaves
    cleanly rather than appearing and vanishing mid-cell.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "BLEND"
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    lin = tuple(srgb_to_linear(c) for c in rgb)
    b.inputs["Base Color"].default_value = (*lin, 1.0)
    b.inputs["Roughness"].default_value = 0.62
    b.inputs["IOR"].default_value = 1.04
    b.inputs["Emission Color"].default_value = (*lin, 1.0)

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])

    # normalise the chosen axis to 0..1 across the cells' own extent
    norm = nt.nodes.new("ShaderNodeMapRange")
    norm.inputs["From Min"].default_value = PULSE_LO
    norm.inputs["From Max"].default_value = PULSE_HI
    nt.links.new(sep.outputs[PULSE_AXIS], norm.inputs["Value"])

    centre = nt.nodes.new("ShaderNodeValue")     # keyframed below; this is `p`
    centre.name = "pulse_centre"
    centre.label = "pulse_centre"

    diff = nt.nodes.new("ShaderNodeMath"); diff.operation = "SUBTRACT"
    nt.links.new(norm.outputs["Result"], diff.inputs[0])
    nt.links.new(centre.outputs["Value"], diff.inputs[1])
    dist = nt.nodes.new("ShaderNodeMath"); dist.operation = "ABSOLUTE"
    nt.links.new(diff.outputs["Value"], dist.inputs[0])

    band = nt.nodes.new("ShaderNodeMapRange")    # 1 at the crest, 0 past the width
    band.inputs["From Min"].default_value = 0.0
    band.inputs["From Max"].default_value = PULSE_WIDTH
    band.inputs["To Min"].default_value = 1.0
    band.inputs["To Max"].default_value = 0.0
    band.clamp = True
    nt.links.new(dist.outputs["Value"], band.inputs["Value"])
    # square it so the crest reads as a pulse rather than a soft gradient
    sharp = nt.nodes.new("ShaderNodeMath"); sharp.operation = "POWER"
    sharp.inputs[1].default_value = 2.0
    nt.links.new(band.outputs["Result"], sharp.inputs[0])

    glow = nt.nodes.new("ShaderNodeMath"); glow.operation = "MULTIPLY"
    glow.inputs[1].default_value = PULSE_GLOW
    nt.links.new(sharp.outputs["Value"], glow.inputs[0])
    nt.links.new(glow.outputs["Value"], b.inputs["Emission Strength"])

    # alpha: the faint mesh always, opaque at the crest
    a = nt.nodes.new("ShaderNodeMapRange")
    a.inputs["From Min"].default_value = 0.0
    a.inputs["From Max"].default_value = 1.0
    a.inputs["To Min"].default_value = PULSE_BASE_ALPHA
    a.inputs["To Max"].default_value = 1.0
    a.clamp = True
    nt.links.new(sharp.outputs["Value"], a.inputs["Value"])
    nt.links.new(a.outputs["Result"], b.inputs["Alpha"])
    return mat


# PULSE_LO/HI are the cells' own extent along the pulse axis, in the same units
# the shader sees. Objects are scaled nm -> um, so world position is micrometres.
PULSE_LO = PULSE_HI = 0.0

# Build one material per colour actually in use, so a layer can override to gray.
if PULSE:
    mats = {}          # deferred: the extent has to be measured after import
else:
    mats = {h: make_mat(f"mat_{h.lstrip('#')}", hex_to_rgb(h)) for h in sorted(set(colors.values()))}

# ---------------------------------------------------------------- import
files = sorted(glob.glob(os.path.join(MESH_DIR, "*.obj")))
if not files:
    raise SystemExit(f"no meshes in {MESH_DIR} - run the download and decimate steps first")

n_by_color = {h: 0 for h in sorted(set(colors.values()))}
faces = 0
imported = []          # pulse mode only: (object, colour) awaiting a material
for p in files:
    sid = os.path.splitext(os.path.basename(p))[0]
    col = colors.get(sid) if sid in wanted else None
    if col is None:
        continue
    before = set(bpy.data.objects)
    # forward Y / up Z leaves the vertices alone instead of hiding a 90 deg X
    # rotation on the object, which is the trap in playbook section 5.
    bpy.ops.wm.obj_import(filepath=p, forward_axis="Y", up_axis="Z")
    for o in set(bpy.data.objects) - before:
        assert max(abs(a) for a in o.rotation_euler) < 1e-6, \
            f"{sid}: importer put a rotation on the object, coordinate spaces disagree"
        o.scale = (NM_TO_UM,) * 3                 # nanometres -> micrometres
        o.data.materials.clear()
        if PULSE:
            imported.append((o, col))             # material waits for the extent
        else:
            o.data.materials.append(mats[col])
        for poly in o.data.polygons:
            poly.use_smooth = True
        faces += len(o.data.polygons)
        n_by_color[col] += 1

breakdown = ", ".join(f"{n} x {h}" for h, n in sorted(n_by_color.items()) if n)
print(f"[poster] imported {sum(n_by_color.values())} neurons ({breakdown}), "
      f"{faces/1e6:.1f}M faces")
assert sum(n_by_color.values()) > 0, "nothing imported"

# A 2 second frame where 30 is normal means the scene is empty. Say the count out
# loud so a fast render cannot be mistaken for a good one.
if sum(n_by_color.values()) != len(wanted):
    raise SystemExit(f"[poster] expected {len(wanted)} neurons, got "
                     f"{sum(n_by_color.values())}: a mesh is missing from {MESH_DIR}")

# ---------------------------------------------------------------- pulse rig
if PULSE:
    bpy.context.view_layer.update()               # world matrices read stale otherwise
    ai = "XYZ".index(PULSE_AXIS)
    # PERCENTILES OF REAL VERTICES, not the bounding box. The box corners reach
    # past where the cell actually has surface, so a crest driven to the box
    # maximum lands in empty space: the last lit frame showed no pulse at all and
    # the crest position jumped backwards, because the brightest pixels fell back
    # to the terminal arbor. Trimming to the 1st and 99th percentile keeps both
    # ends of the travel on geometry that exists.
    import numpy as _np
    coords = []
    for o, _ in imported:
        mw = o.matrix_world
        vs = _np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", vs)
        vs = vs.reshape(-1, 3)
        # apply the object transform without building a Vector per vertex
        m = _np.array(mw.to_4x4()).reshape(4, 4)
        world = vs @ m[:3, :3].T + m[:3, 3]
        coords.append(world[:, ai])
    allc = _np.concatenate(coords)
    lo, hi = float(_np.percentile(allc, 1)), float(_np.percentile(allc, 99))
    PULSE_LO, PULSE_HI = lo, hi
    print(f"[pulse] {PULSE_AXIS} p1..p99 {lo:.1f} to {hi:.1f} um "
          f"({hi-lo:.0f} um of cell), brain at the low end; "
          f"bbox would have been {float(allc.min()):.1f} to {float(allc.max()):.1f}")

    pm = {}
    for o, col in imported:
        if col not in pm:
            pm[col] = make_pulse_mat(f"pulse_{col.lstrip('#')}", hex_to_rgb(col))
        o.data.materials.append(pm[col])

    # Frames 1..N-2 in Blender carry the pulse. The first and last output frames
    # are written as fully transparent PNGs afterwards rather than rendered: the
    # spec asks for them to be transparent, and synthesising them guarantees that
    # exactly instead of trusting an alpha ramp to reach zero.
    N_LIT = PULSE_FRAMES - 2
    for mat in pm.values():
        nt = mat.node_tree
        node = nt.nodes["pulse_centre"]
        for f in range(1, N_LIT + 1):
            t = (f - 1) / max(1, N_LIT - 1)
            # Travel the cell END TO END, brain to VNC, not from off one end to off
            # the other. The first version overshot by a pulse width at each end so
            # the crest would "enter and leave cleanly", but with only 14 lit frames
            # that put frames 01 and 14 entirely off the cell: they rendered as the
            # bare faint mesh and were indistinguishable from each other, wasting
            # two of fourteen. The transparent bookends already give the sequence
            # its clean start and stop, so the lit frames should all carry a pulse.
            node.outputs[0].default_value = t
            nt.keyframe_insert(
                data_path='nodes["pulse_centre"].outputs[0].default_value', frame=f)
        for fc in nt.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"        # constant speed down the axon
    print(f"[pulse] {N_LIT} lit frames + 2 transparent = {PULSE_FRAMES}, "
          f"width {PULSE_WIDTH:.2f} of the cell, glow {PULSE_GLOW}, "
          f"base alpha {PULSE_BASE_ALPHA}")

# ---------------------------------------------------------------- camera
cam_data = bpy.data.cameras.new("poster_cam")
cam_data.type = "PERSP"
cam_data.sensor_fit = "VERTICAL"          # AUTO would fit the WIDER axis on 4:3
cam_data.angle_y = math.radians(cam_cfg["lens"]["angle_y_deg"])
cam_data.clip_start = cam_cfg["clip"]["start_um"]
cam_data.clip_end = cam_cfg["clip"]["end_um"]
cam = bpy.data.objects.new("poster_cam", cam_data)
scene.collection.objects.link(cam)
cam.matrix_world = Matrix(cam_cfg["matrix_world"])
scene.camera = cam
bpy.context.view_layer.update()           # matrix_world reads stale without this

loc = cam.matrix_world.translation
want = Vector(cam_cfg["location_um"])
assert (loc - want).length < 1e-3, f"camera landed at {loc}, expected {want}"
print(f"[poster] camera at {tuple(round(v,1) for v in loc)} um, "
      f"looking at {tuple(round(v,1) for v in cam_cfg['look_at_um'])}")

# ---------------------------------------------------------------- lights
# Three-point rig scaled to the subject plus a world colour. Not more emission.
target = Vector(cam_cfg["look_at_um"])
back = (Vector(cam_cfg["location_um"]) - target).normalized()
up = Vector((0, 0, 1))
right = back.cross(up).normalized()
true_up = right.cross(back).normalized()
SPAN = 900.0    # the cast is about 780 um tall

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
    return o

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
scene.cycles.use_denoising = True
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    if DEVICE == "GPU":
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type in {"OPTIX", "CUDA"}
        scene.cycles.device = "GPU"
    else:
        scene.cycles.device = "CPU"
except Exception as e:
    print(f"[poster] device setup fell back to CPU: {e}")
    scene.cycles.device = "CPU"

scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.resolution_percentage = 100
scene.render.film_transparent = True                  # the whole point
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"       # or the alpha is thrown away
scene.render.image_settings.color_depth = "8"
scene.render.image_settings.compression = 15
scene.view_settings.view_transform = "Standard"       # NOT AgX, it desaturates
scene.view_settings.look = "None"
scene.render.use_compositing = False                  # no Alpha Over black plate
scene.render.dither_intensity = 0.0

out = OUT.replace(".png", "_test.png") if TEST else OUT
os.makedirs(os.path.dirname(out), exist_ok=True)
scene.render.filepath = out
print(f"[poster] {RES[0]}x{RES[1]} {SAMPLES} samples on {scene.cycles.device}, "
      f"transparent film, -> {out}")

if DRYRUN:
    print(f"[poster] DRYRUN: scene built and all asserts passed in "
          f"{(time.time()-t0)/60:.1f} min, nothing rendered, no GPU touched")
    raise SystemExit(0)

if PULSE:
    seq = os.path.splitext(out)[0]
    os.makedirs(seq, exist_ok=True)
    N_LIT = PULSE_FRAMES - 2
    for f in range(1, N_LIT + 1):
        scene.frame_set(f)
        scene.render.filepath = os.path.join(seq, f"frame-{f:02d}")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[pulse] frame-{f:02d} of {N_LIT} in {time.time()-t:.0f}s", flush=True)
    # the two transparent bookends, written directly so they are exactly empty
    import struct
    import zlib

    def write_blank_png(path, w, h):
        raw = b"".join(b"\x00" + b"\x00\x00\x00\x00" * w for _ in range(h))
        def chunk(tag, data):
            c = tag + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
        png = (b"\x89PNG\r\n\x1a\n"
               + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(raw, 9))
               + chunk(b"IEND", b""))
        open(path, "wb").write(png)

    for name in (f"frame-{0:02d}", f"frame-{PULSE_FRAMES-1:02d}"):
        write_blank_png(os.path.join(seq, name + ".png"), RES[0], RES[1])
    print(f"[pulse] wrote {name} and frame-00 fully transparent")
    print(f"[poster] DONE in {(time.time()-t0)/60:.1f} min -> {seq}")
    n = len([x for x in os.listdir(seq) if x.endswith('.png')])
    print(f"[poster] {n} frames on disk (expected {PULSE_FRAMES})")
    raise SystemExit(0 if n == PULSE_FRAMES else 1)

bpy.ops.render.render(write_still=True)
print(f"[poster] DONE in {(time.time()-t0)/60:.1f} min -> {out}")
print(f"[poster] exists={os.path.exists(out)} "
      f"size={os.path.getsize(out)/1e6 if os.path.exists(out) else 0:.2f} MB")
