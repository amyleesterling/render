"""
Render from the saved .blend instead of re-parsing 13 GB of OBJ.

Geometry comes from the cache; everything cheap is rebuilt fresh on load, so the
palette, lighting, camera, timing and reveal order all stay editable. Only the
mesh import is skipped, and that was the entire 9 minute cost.

  blender --background --python render_from_cache.py -- [key=val] [group...]

  blend=path        default D:\\Meshes\\ca3_scene.blend
  frames=480  res=1080x1920  samples=64
  turns=0.2  start=-36  camdist=3.4
  reveal=1          honour the per-group reveal windows
  synapses=1        show the synapse cloud (must exist in the cache)
  only=a,b,c        render only these collections, hide the rest
  out=path.mp4
"""
import sys
import time

import bpy
from mathutils import Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts, extra = {}, []
for tok in argv:
    if "=" in tok:
        k, v = tok.split("=", 1)
        opts[k] = v
    else:
        extra.append(tok)

BLEND = opts.get("blend", r"D:\Meshes\ca3_scene.blend")
t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=BLEND)
print(f"[cache] opened {BLEND} in {time.time() - t0:.0f}s", flush=True)

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__

frames = int(opts.get("frames", 480))
g["FRAME_END"] = frames
g["ORBIT_TURNS"] = float(opts.get("turns", 0.2))
g["ORBIT_START_DEG"] = float(opts.get("start", -36.0))
if "res" in opts:
    w, h = opts["res"].split("x")
    g["RESOLUTION"] = (int(w), int(h))
if "samples" in opts:
    g["SAMPLES"] = int(opts["samples"])
if "camdist" in opts:
    g["CAM_DISTANCE_MULT"] = float(opts["camdist"])
if "shifty" in opts:
    g["CAM_SHIFT_Y"] = float(opts["shifty"])

scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, frames
scene.render.fps = g["FPS"]

hexcol = g["hexcol"]
shade_ramp = g["shade_ramp"]
emissive_material = g["emissive_material"]
set_interp = g["set_interp"]
GROUPS = g["GROUPS"]

# ---- which collections are in play -------------------------------------------------
present = {c.name for c in scene.collection.children}
wanted = set(opts["only"].split(",")) if "only" in opts else (set(extra) or present)
for c in scene.collection.children:
    on = c.name in wanted
    for o in c.objects:
        o.hide_render = not on
        o.hide_viewport = not on
print(f"[cache] rendering collections: {sorted(wanted & present)}", flush=True)

# ---- fresh materials, so the palette is never stale ---------------------------------
for m in list(bpy.data.materials):
    if m.name.startswith("mat_") and not m.name.startswith("mat_synapse"):
        bpy.data.materials.remove(m)

for name in sorted(wanted & present):
    spec = GROUPS.get(name)
    if not spec:
        continue
    objs = sorted(bpy.data.collections[name].objects, key=lambda o: o.name)
    rng = spec.get("per_cell_range")
    shades = shade_ramp(rng[0], rng[1], len(objs)) if rng else None
    alpha = spec.get("alpha", 1.0)
    flat = None if shades else emissive_material(f"mat_{name}", spec["color"], alpha)
    for i, o in enumerate(objs):
        o.data.materials.clear()
        o.data.materials.append(
            emissive_material(f"mat_{name}_{i:03d}", shades[i], alpha) if shades else flat)
    print(f"[cache] {name}: {len(objs)} cells recoloured", flush=True)

# ---- reveal keyframes --------------------------------------------------------------
use_reveal = opts.get("reveal", "1") not in ("0", "false", "off", "no")
for name in sorted(wanted & present):
    spec = GROUPS.get(name)
    if not spec:
        continue
    objs = sorted(bpy.data.collections[name].objects, key=lambda o: o.name)
    for o in objs:
        o.animation_data_clear()
    if not use_reveal:
        for o in objs:
            o.scale = (1.0, 1.0, 1.0)
        continue
    a, b = spec["reveal"]
    last = max(a, b - g["REVEAL_LEN"])
    n = len(objs)
    for i, o in enumerate(objs):
        t = i / max(1, n - 1)
        s = a + t * (last - a)
        o.scale = (0.0, 0.0, 0.0)
        o.keyframe_insert(data_path="scale", frame=int(s))
        o.scale = (1.0, 1.0, 1.0)
        o.keyframe_insert(data_path="scale", frame=int(s + g["REVEAL_LEN"]))
        set_interp(o, "CUBIC", "EASE_OUT")

# ---- synapse cloud visibility and timing -------------------------------------------
dot = bpy.data.objects.get("synapse_dot")
cloud = bpy.data.objects.get("SYNAPSES")
show_syn = opts.get("synapses", "0") not in ("0", "false", "off", "no")
if cloud and dot:
    cloud.hide_render = not show_syn
    cloud.hide_viewport = not show_syn
    dot.hide_render = not show_syn
    dot.animation_data_clear()
    if show_syn:
        a, b = (int(x) for x in opts.get("synreveal", "1-60").split("-"))
        dot.scale = (0, 0, 0)
        dot.keyframe_insert(data_path="scale", frame=a)
        dot.scale = (1, 1, 1)
        dot.keyframe_insert(data_path="scale", frame=b)
        set_interp(dot, "CUBIC", "EASE_OUT")
    print(f"[cache] synapse cloud: {'on' if show_syn else 'off'}", flush=True)

# ---- rebuild everything else from scratch ------------------------------------------
for o in list(bpy.data.objects):
    if o.type in {"LIGHT", "CAMERA"} or o.name == "CAM_ORBIT":
        bpy.data.objects.remove(o, do_unlink=True)

root = bpy.data.objects.get("CA3_ROOT")
g["build_world"](scene)
g["build_lights"](scene, g["TARGET_SIZE"])
g["build_camera_and_orbit"](scene, root)
g["apply_render_settings"](scene)

out = opts.get("out", r"D:\Meshes\renders\from_cache.mp4")
scene.render.filepath = out
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "HIGH"
scene.render.ffmpeg.ffmpeg_preset = "GOOD"

still = opts.get("still")
if still:
    # single frame, for dialling in framing without paying for 480
    scene.render.image_settings.file_format = "PNG"
    scene.frame_set(int(still))
    scene.render.filepath = out
    print(f"[cache] still frame {still} -> {out}", flush=True)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[cache] rendered in {time.time() - t0:.0f}s", flush=True)
    print("[cache] DONE", flush=True)
else:
    print(f"[cache] {frames} frames, {scene.render.resolution_x}x"
          f"{scene.render.resolution_y}, {scene.eevee.taa_render_samples} samples -> {out}",
          flush=True)
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    el = time.time() - t0
    print(f"[cache] rendered in {el/60:.1f} min ({el/frames:.1f}s per frame)", flush=True)
    print("[cache] DONE", flush=True)
