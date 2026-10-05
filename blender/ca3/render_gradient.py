"""
The proximodistal convergence gradient, 304 real cells coloured by MF input count.

  blender --background --python render_gradient.py -- [key=val]

  still=1                 render a single frame (default). 0 renders an orbit.
  frames=300              orbit length when still=0
  res=1920x1080  samples=96
  view=arch|oblique       arch is face on, the view the analysis figure uses
  camdist=1.05            camera distance as a multiple of the fitted radius
  shifty=0.0
  cache=1                 save/reuse gradient_scene.blend
  out=path

WHAT IS BEING SHOWN, AND WHY THESE 304 CELLS. Every cell here has its soma at
z >= 60 um. That restriction is not cosmetic. Proofreading in materialization 671
is graded along z: the mean number of synapses a pyramidal cell receives per
distinct presynaptic segment rises monotonically from 1.15 at z<22 um to 3.5 at
z>80 um, so any connectivity measure taken over the whole block is dominated by
agglomeration state rather than biology. All 304 downloaded cells happen to fall
inside the trustworthy slab, which is why the sample is usable as it stands.

WHAT THE PICTURE SAYS. In the restricted slab the convergence gradient is NOT
monotonic. Median mossy fibre input runs about 50 at one end of the arch, dips to
33 mid arch, then climbs to 72 at the far limb, with the 90th percentile jumping
from about 65 to 160. Both limbs are high and the apex is low. Do not caption
this as a clean proximal to distal ramp, because it is not one.

COLOUR IS LOG SCALED. Input count spans 0 to 235 with a median of 41, so a
linear ramp spends most of its range on a handful of cells and renders the bulk
of the population as one flat shade. log10(n+1) is also what the analysis figure
uses, so the still and the figure agree by construction.
"""
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)

GRAD = Path(r"D:\Meshes\gradient")
CSV = Path(r"D:\Meshes\renders\gradient_sample.csv")
CACHE = Path(r"D:\Meshes\gradient_scene.blend")
Z_MIN_UM = 60.0

# Cool at low convergence, warm at high, which keeps the page's one-warm-accent
# rule and reads as "hotter cell receives more".
COL_LO = "#2F58A8"
COL_HI = "#FFC24A"

# ---- the house module, for materials, lighting and render settings -------------------
HOUSE = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": HOUSE}
exec(compile(open(HOUSE, encoding="utf-8").read(), HOUSE, "exec"), ns)
g = ns["build"].__globals__

hexcol = g["hexcol"]
emissive_material = g["emissive_material"]
build_world = g["build_world"]
build_lights = g["build_lights"]
apply_render_settings = g["apply_render_settings"]
world_bounds = g["world_bounds"]
clear_scene = g["clear_scene"]
TARGET_SIZE = g["TARGET_SIZE"]

if "res" in opts:
    w, h = opts["res"].split("x")
    g["RESOLUTION"] = (int(w), int(h))
g["SAMPLES"] = int(opts.get("samples", 96))

scene = bpy.context.scene


def read_sample():
    """root_id -> mossy fibre input count, for the cells that are on disk.

    Parsed by hand because Blender ships numpy but not pandas.
    """
    rows = CSV.read_text(encoding="utf-8").strip().splitlines()
    head = rows[0].split(",")
    i_id, i_n, i_z = head.index("root_id"), head.index("n_mf"), head.index("soma_z_nm")
    i_arc = head.index("arc_um")
    out = {}
    for r in rows[1:]:
        f = r.split(",")
        seg = f[i_id]
        if float(f[i_z]) / 1000.0 < Z_MIN_UM:
            continue
        if not (GRAD / f"{seg}.obj").exists():
            continue
        out[seg] = (int(float(f[i_n])), float(f[i_arc]))
    return out


def ramp(t):
    """t in [0,1] -> linear RGB, along an explicit three stop ramp.

    NOT interpolated in HSV. Walking hue from blue to gold takes the long way
    round the wheel, through cyan and green, and the first test frame came back a
    green thicket: a rainbow, where green carried no meaning and the low end was
    indistinguishable from the middle. Deep blue to violet to gold instead, lerped
    in sRGB through named stops, which rises monotonically in lightness so the
    ordering survives even where cells overlap, and never touches green.
    """
    stops = ((0.00, (0x1D, 0x35, 0x8F)),   # deep blue, fewest inputs
             (0.50, (0x8E, 0x46, 0xC0)),   # violet, midpoint
             (1.00, (0xFF, 0xC2, 0x4A)))   # warm gold, most inputs
    t = min(max(t, 0.0), 1.0)
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            srgb = [(a + (b - a) * u) / 255.0 for a, b in zip(c0, c1)]
            return tuple(c ** 2.2 for c in srgb)
    return tuple((c / 255.0) ** 2.2 for c in stops[-1][1])


# ---- geometry ------------------------------------------------------------------------
use_cache = opts.get("cache", "1") not in ("0", "false", "no")
cells = read_sample()
print(f"[grad] {len(cells)} cells in the sample and on disk, z >= {Z_MIN_UM} um",
      flush=True)
if not cells:
    raise SystemExit("No cells matched. Check gradient_sample.csv and D:/Meshes/gradient.")

if use_cache and CACHE.exists():
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=str(CACHE))
    scene = bpy.context.scene
    print(f"[grad] opened cache in {time.time() - t0:.0f}s", flush=True)
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
else:
    clear_scene()
    scene = bpy.context.scene
    coll = bpy.data.collections.new("GRADIENT")
    scene.collection.children.link(coll)
    t0 = time.time()
    objs, stripped = [], 0
    for i, seg in enumerate(sorted(cells)):
        before = set(bpy.data.objects)
        bpy.ops.wm.obj_import(filepath=str(GRAD / f"{seg}.obj"))
        new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        for o in new:
            o.name = f"grad_{seg}"
            for c in list(o.users_collection):
                c.objects.unlink(o)
            coll.objects.link(o)
        # stray faces are long thin triangles the mesher leaves behind, and they
        # render as spikes shooting off the arbor. Cheap to remove, ugly to keep.
        for o in new:
            stripped += g["strip_stray_faces"](o)
        objs.extend(new)
        if (i + 1) % 50 == 0:
            print(f"[grad]   imported {i + 1}/{len(cells)} "
                  f"({time.time() - t0:.0f}s)", flush=True)
    faces = sum(len(o.data.polygons) for o in objs)
    print(f"[grad] {len(objs)} meshes, {faces:,} faces, "
          f"{stripped:,} stray faces stripped, in {time.time() - t0:.0f}s", flush=True)

    # ---- normalise: centre on the population and scale to TARGET_SIZE ---------------
    # A root empty carries the transform so the meshes keep their own coordinates,
    # and matrix_parent_inverse stays identity so the root's scale is not cancelled.
    lo, hi = world_bounds(objs)
    centre = (np.asarray(lo) + np.asarray(hi)) / 2.0
    span = float(max((np.asarray(hi) - np.asarray(lo))[i] for i in range(3)))
    root = bpy.data.objects.new("GRAD_ROOT", None)
    scene.collection.objects.link(root)
    for o in objs:
        o.parent = root
        o.matrix_parent_inverse.identity()
        o.location = tuple(np.asarray(o.location) - centre)
    root.scale = (TARGET_SIZE / span,) * 3
    print(f"[grad] span {span:,.0f} -> {TARGET_SIZE}, centred", flush=True)

    for o in objs:
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.shade_smooth()

    if use_cache:
        bpy.ops.wm.save_as_mainfile(filepath=str(CACHE))
        print(f"[grad] cached to {CACHE}", flush=True)

# ---- colour by convergence -----------------------------------------------------------
nmax = max(v[0] for v in cells.values())
denom = np.log10(nmax + 1.0)
for m in list(bpy.data.materials):
    if m.name.startswith("mat_grad"):
        bpy.data.materials.remove(m)
for o in objs:
    seg = o.name.replace("grad_", "")
    n, _arc = cells.get(seg, (0, 0.0))
    t = float(np.log10(n + 1.0) / denom)
    o.data.materials.clear()
    o.data.materials.append(emissive_material(f"mat_grad_{seg}", ramp(t), 1.0))
print(f"[grad] coloured by log10(n+1), n from 0 to {nmax}", flush=True)

# ---- camera ---------------------------------------------------------------------------
# The arch lies in the data x-y plane. Blender's OBJ importer maps data (x,y,z) to
# world (x,-z,y), so the arch ends up in the world x-z plane and viewing it face on
# means looking along world +Y. This is the same view as the middle panel of the
# analysis figure, which is the one that shows the gradient.
for o in list(bpy.data.objects):
    if o.type in {"LIGHT", "CAMERA"}:
        bpy.data.objects.remove(o, do_unlink=True)

lo, hi = world_bounds(objs)
lo, hi = np.asarray(lo), np.asarray(hi)
centre = Vector(((lo + hi) / 2.0).tolist())
radius = float(np.linalg.norm(hi - lo)) / 2.0

cam_data = bpy.data.cameras.new("CAM")
cam_data.lens = g["CAM_LENS_MM"]
cam = bpy.data.objects.new("CAM", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

dist = radius * float(opts.get("camdist", 1.05)) / np.tan(np.radians(22.0))
view = opts.get("view", "arch")
if view == "oblique":
    off = Vector((-dist * 0.42, -dist * 0.82, dist * 0.34))
else:
    off = Vector((0.0, -dist, 0.0))
cam.location = centre + off
cam.data.shift_y = float(opts.get("shifty", 0.0))

# aim it, without needing a constraint or an empty
direction = (centre - cam.location).normalized()
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
print(f"[grad] camera {view}, radius {radius:.2f}, dist {dist:.2f}", flush=True)

build_world(scene)
build_lights(scene, TARGET_SIZE)
apply_render_settings(scene)

out = opts.get("out", r"D:\Meshes\renders\gradient_still.png")
scene.render.filepath = out

if opts.get("still", "1") not in ("0", "false", "no"):
    scene.render.image_settings.file_format = "PNG"
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[grad] still -> {out} in {time.time() - t0:.0f}s", flush=True)
else:
    frames = int(opts.get("frames", 300))
    orbit = bpy.data.objects.new("CAM_ORBIT", None)
    scene.collection.objects.link(orbit)
    orbit.location = centre
    cam.parent = orbit
    cam.matrix_parent_inverse.identity()
    cam.location = off
    scene.frame_start, scene.frame_end = 1, frames
    scene.render.fps = g["FPS"]
    # a sixth of a turn, so the arch is read rather than spun
    for f, rot in ((1, -np.pi / 12.0), (frames, np.pi / 12.0)):
        orbit.rotation_euler = (0.0, 0.0, float(rot))
        orbit.keyframe_insert(data_path="rotation_euler", frame=f)
    for fc in orbit.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation, kp.easing = "SINE", "EASE_IN_OUT"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    el = time.time() - t0
    print(f"[grad] {frames} frames in {el / 60:.1f} min "
          f"({el / frames:.1f}s per frame) -> {out}", flush=True)
print("[grad] DONE", flush=True)
