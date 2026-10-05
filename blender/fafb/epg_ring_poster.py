"""Render the 54 FAFB EPG compass neurons, frontal view, transparent background.

Same treatment as the BANC panel layers: transparent film, straight alpha, house
shading (IOR 1.04, submerged tissue, never glossy), Standard view transform,
1600x1200.

Colour is not arbitrary. EPGs tile the ellipsoid body, and the 54 cells here spread
evenly around the full 360 degrees of it, so each cell is coloured by its angular
position around the EB. That is what produces a rainbow that runs around the ring
rather than a random scatter of hues.

Camera is solved from the geometry rather than guessed: frontal view down the
anterior-posterior axis, -y up so the somata sit above the ring, framed to a
target height fill using percentile bounds so a few stray vertices cannot blow the
framing out.

  blender --background --python epg_ring_poster.py -- dryrun
  blender --background --python epg_ring_poster.py -- test
  blender --background --python epg_ring_poster.py -- hueoffset=320 huedir=1
  blender --background --python epg_ring_poster.py -- samples=256
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

MESH_DIR = opts.get("meshes", r"C:\Users\amyle\meshparty\EPG")
ANGLES = r"D:\Meshes\banc\epg_angles.json"
OUT = opts.get("out", r"D:\Meshes\renders\epg\epg-ring.png")

RES = (400, 300) if TEST else (1600, 1200)
if "res" in opts:
    RES = tuple(int(v) for v in opts["res"].lower().split("x"))
SAMPLES = int(opts.get("samples", 48 if TEST else 256))
DEVICE = opts.get("device", "GPU").upper()
NM_TO_UM = 0.001

# Colour dials. Anchored on the reference: magenta at the top of the ring, warm
# golds swinging round to the left. Tunable because the right answer is the one
# that looks right in the render, not in a picker.
HUE_OFFSET = float(opts.get("hueoffset", 320.0))
HUE_DIR = float(opts.get("huedir", 1.0))
SAT = float(opts.get("sat", 1.0))   # saturation multiplier on the palette
VAL = float(opts.get("val", 1.0))   # value multiplier on the palette

LIGHT = float(opts.get("light", 0.071))   # measured: lum 186, 2.0% clipped
EMIT = float(opts.get("emit", 0.15))      # luminous, to match the reference
FILL = float(opts.get("fill", 0.92))
BASE_SAT = float(opts.get("basesat", 0.22))   # the dim, desaturated base
BASE_VAL = float(opts.get("baseval", 0.40))          # target height fill
FOVY = math.radians(45.0)

t0 = time.time()
ang_cfg = json.load(open(ANGLES))
angle_of = {c["id"]: c["angle"] for c in ang_cfg["cells"]}

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hsv_to_rgb(h, s, v):
    h = (h % 360) / 60.0
    i = int(h) % 6
    f = h - int(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    return [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]


# Explicit cyclic stops read off the reference, positioned by angle CCW from the
# top of the ring. Interpolated in sRGB, not HSV: a hue sweep walks through
# yellow-green on the way from gold to teal, which the reference does not do.
PALETTE_STOPS = [
    (0,   "#FF4DA6"),   # top: hot pink
    (55,  "#FF8A5C"),   # upper left: coral
    (105, "#FFC24A"),   # left: gold
    (150, "#7FD9A0"),   # lower left: soft green
    (190, "#3FC9C9"),   # lower left/bottom: teal
    (235, "#4C9BE8"),   # bottom: blue
    (280, "#8A6FE0"),   # lower right: indigo
    (320, "#C45CD6"),   # right: violet
    (360, "#FF4DA6"),   # back to top
]


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def palette_rgb(t_deg, sat_mul=1.0, val_mul=1.0):
    """Colour at t degrees counter-clockwise from the top of the ring."""
    t = t_deg % 360
    for i in range(len(PALETTE_STOPS) - 1):
        a, ca = PALETTE_STOPS[i]
        b, cb = PALETTE_STOPS[i + 1]
        if a <= t <= b:
            f = (t - a) / (b - a) if b > a else 0.0
            ra, rb = hex_rgb(ca), hex_rgb(cb)
            rgb = tuple(ra[k] + (rb[k] - ra[k]) * f for k in range(3))
            mx = max(rgb)
            if mx > 0:                       # apply sat/val trims about the hue
                rgb = tuple(mx - (mx - c) * sat_mul for c in rgb)
                rgb = tuple(min(1.0, c * val_mul) for c in rgb)
            return rgb
    return hex_rgb(PALETTE_STOPS[0][1])


def make_mat(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    lin = tuple(srgb_to_linear(c) for c in rgb)
    b.inputs["Base Color"].default_value = (*lin, 1.0)
    b.inputs["Roughness"].default_value = 0.62
    b.inputs["IOR"].default_value = 1.04          # tissue in water, NOT 1.38
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = 0.22
        b.inputs["Subsurface Radius"].default_value = (6.0, 3.0, 2.4)
        if "Subsurface Scale" in b.inputs:
            b.inputs["Subsurface Scale"].default_value = 3.0
    b.inputs["Emission Color"].default_value = (*lin, 1.0)
    b.inputs["Emission Strength"].default_value = EMIT
    return mat


EXCLUDE = set(filter(None, opts.get("exclude", "").split(",")))
files = sorted(glob.glob(os.path.join(MESH_DIR, "*-meshlab.obj")))
if not files:
    raise SystemExit(f"no *-meshlab.obj in {MESH_DIR}")

verts_all = []
faces = 0
for p in files:
    sid = os.path.basename(p).replace("-meshlab.obj", "")
    if sid in EXCLUDE:
        print(f"[epg] EXCLUDED {sid}")
        continue
    ang = angle_of.get(sid)
    if ang is None:
        print(f"[epg] SKIP {sid}: no EB angle")
        continue
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=p, forward_axis="Y", up_axis="Z")
    t = HUE_DIR * ((ang - 90.0) % 360.0)
    mat = make_mat(f"epg_{sid}", palette_rgb(t, SAT, VAL))
    for o in set(bpy.data.objects) - before:
        assert max(abs(a) for a in o.rotation_euler) < 1e-6, \
            f"{sid}: importer put a rotation on the object"
        o.scale = (NM_TO_UM,) * 3
        o.data.materials.clear()
        o.data.materials.append(mat)
        for poly in o.data.polygons:
            poly.use_smooth = True
        faces += len(o.data.polygons)
        # bpy collections do not accept a step slice, so index explicitly
        vs = o.data.vertices
        verts_all.extend([(vs[i].co.x * NM_TO_UM, vs[i].co.y * NM_TO_UM,
                           vs[i].co.z * NM_TO_UM) for i in range(0, len(vs), 7)])

n_cells = len([o for o in bpy.data.objects if o.type == "MESH"])
print(f"[epg] imported {n_cells} cells, {faces/1e6:.1f}M faces")
assert n_cells == 54 - len(EXCLUDE), f"expected {54-len(EXCLUDE)} cells, got {n_cells}"

# ---------------------------------------------------------------- camera
# Frontal: look down +z (anterior to posterior), -y up so somata sit above the ring.
FORWARD = Vector((0.0, 0.0, float(opts.get("zdir", 1.0))))
UP = Vector((0.0, float(opts.get("ydir", -1.0)), 0.0))
back = (-FORWARD).normalized()
right = UP.cross(back).normalized()
true_up = back.cross(right).normalized()

import numpy as np  # Blender ships numpy

V = np.array(verts_all)
# Percentile bounds, not min/max: stray vertices wreck auto-framing.
cx = np.array([np.dot(v, np.array(right)) for v in V])
cy = np.array([np.dot(v, np.array(true_up)) for v in V])
cz = np.array([np.dot(v, np.array(back)) for v in V])
# Percentile bounds guard against stray vertices, but here the "strays" are the
# real tips of the long lateral arms: at 0.5/99.5 they fell outside the frame and
# clipped. Take the union of the percentile box and the true extent, so genuine
# structure is kept while a far-flung fragment still cannot dominate.
lo, hi = 0.5, 99.5
px0, px1 = np.percentile(cx, lo), np.percentile(cx, hi)
py0, py1 = np.percentile(cy, lo), np.percentile(cy, hi)
span_x, span_y = px1 - px0, py1 - py0
x0 = max(cx.min(), px0 - 0.25 * span_x)
x1 = min(cx.max(), px1 + 0.25 * span_x)
y0 = max(cy.min(), py0 - 0.25 * span_y)
y1 = min(cy.max(), py1 + 0.25 * span_y)
print(f"[epg] bounds: percentile {span_x:.0f}x{span_y:.0f} um, "
      f"used {x1-x0:.0f}x{y1-y0:.0f} um, true {cx.max()-cx.min():.0f}x{cy.max()-cy.min():.0f} um")
w, h = x1 - x0, y1 - y0
aspect = RES[0] / RES[1]
c_x, c_y = float((x0 + x1) / 2), float((y0 + y1) / 2)
c_back = float(np.percentile(cz, 50))

# Solve the framing per-vertex under PERSPECTIVE, not as if it were orthographic.
# The cast is ~156 um deep, so the lateral arms nearest the lens magnify: fitting
# the flat bounding box at the centre depth still clipped them at both edges.
# For a point at depth (dist + c_back - cz_i), staying inside the frame needs
#   |cx_i - c_x| / depth <= FILL * tan(fovy/2) * aspect
# which rearranges to a lower bound on dist. Take the binding vertex.
t = math.tan(FOVY / 2)
fx, fy = FILL * t * aspect, FILL * t
inside = (cx >= x0) & (cx <= x1) & (cy >= y0) & (cy <= y1)
need_w = np.abs(cx[inside] - c_x) / fx + cz[inside] - c_back
need_h = np.abs(cy[inside] - c_y) / fy + cz[inside] - c_back
d_w, d_h = float(need_w.max()), float(need_h.max())
dist = max(d_h, d_w)
centre = right * c_x + true_up * c_y + back * c_back
cam_loc = centre + back * dist

cam_data = bpy.data.cameras.new("epg_cam")
cam_data.type = "PERSP"
cam_data.sensor_fit = "VERTICAL"      # AUTO fits the WIDER axis on a 4:3 frame
cam_data.angle_y = FOVY
cam_data.clip_start = 1.0
cam_data.clip_end = dist * 4
cam = bpy.data.objects.new("epg_cam", cam_data)
scene.collection.objects.link(cam)
m = Matrix()
for i in range(3):
    m[i][0], m[i][1], m[i][2] = right[i], true_up[i], back[i]
    m[i][3] = cam_loc[i]
cam.matrix_world = m
scene.camera = cam
bpy.context.view_layer.update()
print(f"[epg] content {w:.0f} x {h:.0f} um, camera {dist:.0f} um back, "
      f"binding axis {'height' if d_h >= d_w else 'width'}")
CAM_OUT = "D:/Meshes/banc/epg_camera.json"   # forward slashes: a backslash-b does not survive a heredoc
if opts.get("savecam", "1") == "1":
    os.makedirs(os.path.dirname(CAM_OUT), exist_ok=True)
    json.dump({
        "_note": "Camera solved from the 53-cell EPG set and then LOCKED, so every "
                 "per-cell render is pixel aligned with every other and with the "
                 "all-cells frame. Solved under perspective per vertex, not on a "
                 "flat bounding box, because the cast is ~156 um deep.",
        "resolution": list(RES),
        "lens": {"type": "PERSP", "sensor_fit": "VERTICAL", "angle_y_deg": 45.0},
        "matrix_world": [[float(cam.matrix_world[r][c]) for c in range(4)] for r in range(4)],
        "content_um": [float(w), float(h)],
        "distance_um": float(dist),
    }, open(CAM_OUT, "w"), indent=1)
    print(f"[epg] camera saved -> {CAM_OUT}")
print(f"[epg] camera at {tuple(round(v,1) for v in cam.matrix_world.translation)} um")

# ---------------------------------------------------------------- lights
SPAN = max(w, h)


def add_light(name, direction, energy, size):
    d = bpy.data.lights.new(name, type="AREA")
    d.energy = energy * LIGHT
    d.size = size
    d.color = (1.0, 0.98, 0.96)
    o = bpy.data.objects.new(name, d)
    scene.collection.objects.link(o)
    pos = centre + direction.normalized() * SPAN * 1.6
    o.location = pos
    o.rotation_euler = (centre - pos).to_track_quat("-Z", "Y").to_euler()


# Energies scale with distance squared, so the BANC dial transfers across scenes.
K = (dist / 1459.293) ** 2
add_light("key", back * 0.7 + right * 0.8 + true_up * 0.5, 5.0e8 * K, SPAN * 0.9)
add_light("fill", back * 0.6 - right * 0.9 + true_up * 0.1, 1.6e8 * K, SPAN * 1.2)
add_light("rim", -back * 0.5 - true_up * 0.8, 2.4e8 * K, SPAN * 1.0)

world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.06, 0.09, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
scene.world = world

# ---------------------------------------------------------------- render
scene.render.engine = "CYCLES"
scene.cycles.samples = SAMPLES
# Denoising is off by default for the layer masters: the OptiX denoiser filters
# across the alpha boundary and smears colour into transparent pixels, which is
# exactly the fringe a straight-alpha overlay must not have. Pay for it in samples.
scene.cycles.use_denoising = opts.get("denoise", "0") == "1"
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
    print(f"[epg] device fell back to CPU: {e}")
    scene.cycles.device = "CPU"

scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.color_depth = "8"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.render.use_compositing = False           # no Alpha Over black plate
scene.render.dither_intensity = 0.0

out = OUT.replace(".png", "_test.png") if TEST else OUT
os.makedirs(os.path.dirname(out), exist_ok=True)
scene.render.filepath = out
print(f"[epg] {RES[0]}x{RES[1]} {SAMPLES} samples on {scene.cycles.device} -> {out}")
if DRYRUN:
    print(f"[epg] DRYRUN ok in {(time.time()-t0)/60:.1f} min, nothing rendered")
    raise SystemExit(0)

# Several palettes from ONE import: re-importing 54 meshes per candidate is what
# makes people skip the comparison, and the comparison is the whole point.
if "sweep" in opts:
    base_energy = {o.name: o.data.energy for o in bpy.data.objects if o.type == "LIGHT"}
    for combo in opts["sweep"].split(","):
        parts = [float(x) for x in combo.split(":")]
        s, v = parts[0], parts[1]
        em = parts[2] if len(parts) > 2 else EMIT
        lm = parts[3] if len(parts) > 3 else 1.0
        for o in bpy.data.objects:
            if o.type == "LIGHT":
                o.data.energy = base_energy[o.name] * lm
        for o in bpy.data.objects:
            if o.type != "MESH":
                continue
            sid = o.data.materials[0].name.replace("epg_", "")
            ang = angle_of[sid]
            t = HUE_DIR * ((ang - 90.0) % 360.0)
            rgb = tuple(srgb_to_linear(c) for c in palette_rgb(t, s, v))
            b = o.data.materials[0].node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (*rgb, 1.0)
            b.inputs["Emission Color"].default_value = (*rgb, 1.0)
            b.inputs["Emission Strength"].default_value = em
        p = out.replace(".png", f"_s{s:.2f}_v{v:.2f}_e{em:.2f}_L{lm:.1f}.png")
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        print(f"[epg] sweep sat={s:.2f} val={v:.2f} -> {p}")
    print(f"[epg] SWEEP DONE in {(time.time()-t0)/60:.1f} min")
    raise SystemExit(0)

if "headings" in argv:
    # Base plus 16 directional bump overlays, all from this one import so every
    # frame shares the locked camera exactly.
    #
    # The bump is applied as COLOUR, not as mesh alpha. Semi-transparent geometry
    # would compound where a tube's front and back walls overlap (0.45 becomes
    # 0.70) and would lose correct occlusion between neighbouring cells. Instead
    # each lit cell stays opaque and its colour is lerped from the dim base colour
    # to its full palette colour by the bump weight, which is what "brightness"
    # means once the overlay is composited over the base.
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    sector_of, tof = {}, {}
    for o in meshes:
        sid = o.data.materials[0].name.replace("epg_", "")
        t = HUE_DIR * ((angle_of[sid] - 90.0) % 360.0)
        tof[sid] = t
        sector_of[sid] = int(t // 22.5) % 16
    outdir = os.path.dirname(out)
    os.makedirs(outdir, exist_ok=True)

    def paint(weight_of):
        for o in meshes:
            sid = o.data.materials[0].name.replace("epg_", "")
            wgt = weight_of(sid)
            o.hide_render = wgt is None
            if wgt is None:
                continue
            sm = BASE_SAT + (SAT - BASE_SAT) * wgt
            vm = BASE_VAL + (VAL - BASE_VAL) * wgt
            rgb = tuple(srgb_to_linear(c) for c in palette_rgb(tof[sid], sm, vm))
            b = o.data.materials[0].node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (*rgb, 1.0)
            b.inputs["Emission Color"].default_value = (*rgb, 1.0)
            b.inputs["Emission Strength"].default_value = EMIT * (0.35 + 0.65 * wgt)

    paint(lambda sid: 0.0)
    scene.render.filepath = os.path.join(outdir, "epg-base.png")
    bpy.ops.render.render(write_still=True)
    print(f"[epg] base (all {len(meshes)} cells dim, desaturated) -> {scene.render.filepath}", flush=True)

    WEIGHTS = {0: 1.0, 1: 0.45, 2: 0.15}
    for k in range(16):
        def w_of(sid, k=k):
            d = abs(sector_of[sid] - k)
            d = min(d, 16 - d)
            return WEIGHTS.get(d)
        paint(w_of)
        lit = sum(1 for o in meshes if not o.hide_render)
        scene.render.filepath = os.path.join(outdir, f"epg-heading-{k:02d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[epg] heading {k:02d}: {lit} cells lit -> {scene.render.filepath}", flush=True)

    for o in meshes:
        o.hide_render = False
    json.dump({sid: {"sector": sector_of[sid], "t_deg": tof[sid]} for sid in sector_of},
              open("D:/Meshes/banc/epg_sectors.json", "w"), indent=1)
    print(f"[epg] HEADINGS DONE in {(time.time()-t0)/60:.1f} min")
    raise SystemExit(0)

if "percell" in argv:
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    cell_dir = os.path.join(os.path.dirname(out), "cells")
    os.makedirs(cell_dir, exist_ok=True)
    scene.render.filepath = os.path.join(os.path.dirname(out), "epg-all.png")
    bpy.ops.render.render(write_still=True)
    print(f"[epg] all-cells reference -> {scene.render.filepath}")
    for i, target in enumerate(meshes, 1):
        for o in meshes:
            o.hide_render = (o is not target)
        sid = target.data.materials[0].name.replace("epg_", "")
        scene.render.filepath = os.path.join(cell_dir, f"epg-cell-{sid}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[epg] {i}/{len(meshes)} {sid} -> {scene.render.filepath}", flush=True)
    for o in meshes:
        o.hide_render = False
    print(f"[epg] PER-CELL DONE: {len(meshes)} cells in {(time.time()-t0)/60:.1f} min")
    raise SystemExit(0)

bpy.ops.render.render(write_still=True)
print(f"[epg] DONE in {(time.time()-t0)/60:.1f} min, exists={os.path.exists(out)} "
      f"size={os.path.getsize(out)/1e6 if os.path.exists(out) else 0:.2f} MB")
