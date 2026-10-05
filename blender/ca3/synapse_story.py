"""
The synapse story, paced to be watched rather than skimmed.

  1  presynaptic cells FADE in           (not scaled up from a point)
  2  hold, so they can actually be seen
  3  synapses bloom in, bright
  4  hold
  5  postsynaptic partner cells fade in
  6  hold, slow drift

Cells fade by material alpha rather than by scaling from zero. Scaling made them
appear to crawl in from a corner; a fade lets them arrive where they belong.

  blender --background --python synapse_story.py -- [key=val]
    still=N   frames=900   res=1080x1920   samples=64   out=path
"""
import sys
import time

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = {}
for tok in argv:
    if "=" in tok:
        k, v = tok.split("=", 1)
        opts[k] = v

BLEND = r"D:\Meshes\ca3_scene.blend"
t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=BLEND)
print(f"[story] opened cache in {time.time()-t0:.0f}s", flush=True)

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__

FRAMES = int(opts.get("frames", 900))
RES = tuple(int(x) for x in opts.get("res", "1080x1920").split("x"))
g["RESOLUTION"] = RES
g["SAMPLES"] = int(opts.get("samples", 64))
g["FRAME_END"] = FRAMES
g["ORBIT_TURNS"] = float(opts.get("turns", 0.10))
g["ORBIT_START_DEG"] = float(opts.get("start", -18))
g["CAM_DISTANCE_MULT"] = float(opts.get("camdist", 2.9))
g["CAM_SHIFT_Y"] = float(opts.get("shifty", -0.16))

# brighter synapses, closer to the first version Amy liked
g["SYNAPSE_EMISSION"] = float(opts.get("synemit", 3.2))
g["BLOOM_THRESHOLD"] = 0.62
g["BLOOM_STRENGTH"] = 0.85

scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, FRAMES
scene.render.fps = g["FPS"]

PRE = ["CA3_deep", "CA3_superficial"]
POST = ["thorny_pyramidals", "sparsely_thorny"]
ALL = PRE + POST

# ---- beats, in frames. Everything holds long enough to be looked at. ----------------
F = FRAMES / 900.0
PRE_IN = (int(30 * F), int(150 * F))       # cells fade up
SYN_IN = (int(300 * F), int(470 * F))      # synapses bloom
POST_IN = (int(600 * F), int(780 * F))     # partners arrive
print(f"[story] presynaptic fade {PRE_IN}, synapses {SYN_IN}, "
      f"postsynaptic {POST_IN}, end {FRAMES}", flush=True)

present = {c.name for c in scene.collection.children}
for c in scene.collection.children:
    on = c.name in ALL
    for o in c.objects:
        o.hide_render = not on
        o.hide_viewport = not on

hexcol, shade_ramp = g["hexcol"], g["shade_ramp"]
emissive_material, set_interp = g["emissive_material"], g["set_interp"]
GROUPS = g["GROUPS"]

for m in list(bpy.data.materials):
    if m.name.startswith("mat_") and "synapse" not in m.name:
        bpy.data.materials.remove(m)


def dress(group, window):
    """Fresh materials, then fade their alpha up across the window."""
    objs = sorted(bpy.data.collections[group].objects, key=lambda o: o.name)
    spec = GROUPS[group]
    rng = spec.get("per_cell_range")
    shades = shade_ramp(rng[0], rng[1], len(objs)) if rng else None
    a, b = window
    for i, o in enumerate(objs):
        col = shades[i] if shades else spec["color"]
        mat = emissive_material(f"mat_{group}_{i:03d}", col, 1.0)
        # BLEND so alpha is animatable; at alpha 1 it still reads solid
        mat.blend_method = "BLEND"
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        alpha = bsdf.inputs["Alpha"]
        o.data.materials.clear()
        o.data.materials.append(mat)
        o.animation_data_clear()
        o.scale = (1.0, 1.0, 1.0)          # no scale-in: they fade, they do not crawl
        # stagger only slightly, so the group arrives together
        t = i / max(1, len(objs) - 1)
        s = a + t * (b - a) * 0.35
        e = s + (b - a) * 0.65
        alpha.default_value = 0.0
        mat.node_tree.keyframe_insert(
            data_path='nodes["Principled BSDF"].inputs[4].default_value', frame=int(s))
        alpha.default_value = 1.0
        mat.node_tree.keyframe_insert(
            data_path='nodes["Principled BSDF"].inputs[4].default_value', frame=int(e))
        if mat.node_tree.animation_data and mat.node_tree.animation_data.action:
            for fc in mat.node_tree.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "SINE"
                    kp.easing = "EASE_IN_OUT"
    print(f"[story] {group}: {len(objs)} cells fading {window}", flush=True)


for gname in PRE:
    dress(gname, PRE_IN)
for gname in POST:
    dress(gname, POST_IN)

# ---- synapses ------------------------------------------------------------------------
dot = bpy.data.objects.get("synapse_dot")
cloud = bpy.data.objects.get("SYNAPSES")
if cloud and dot:
    cloud.hide_render = cloud.hide_viewport = False
    dot.hide_render = False
    dot.animation_data_clear()
    mat = dot.data.materials[0]
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = g["SYNAPSE_EMISSION"]
    a, b = SYN_IN
    dot.scale = (0, 0, 0)
    dot.keyframe_insert(data_path="scale", frame=a)
    dot.scale = (1, 1, 1)
    dot.keyframe_insert(data_path="scale", frame=b)
    set_interp(dot, "SINE", "EASE_IN_OUT")
    print(f"[story] synapse cloud emission {g['SYNAPSE_EMISSION']}, bloom in {SYN_IN}",
          flush=True)

# ---- rebuild the look --------------------------------------------------------------
for o in list(bpy.data.objects):
    if o.type in {"LIGHT", "CAMERA"} or o.name == "CAM_ORBIT":
        bpy.data.objects.remove(o, do_unlink=True)
root = bpy.data.objects.get("CA3_ROOT")
g["build_world"](scene)
g["build_lights"](scene, g["TARGET_SIZE"], root)
g["build_camera_and_orbit"](scene, root)
g["apply_render_settings"](scene)

out = opts.get("out", r"D:\Meshes\renders\synapse_story.mp4")
scene.render.filepath = out

still = opts.get("still")
if still:
    scene.render.image_settings.file_format = "PNG"
    scene.frame_set(int(still))
    print(f"[story] still frame {still} -> {out}", flush=True)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[story] rendered in {time.time()-t0:.0f}s", flush=True)
else:
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    print(f"[story] {FRAMES} frames -> {out}", flush=True)
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    el = time.time() - t0
    print(f"[story] rendered in {el/60:.1f} min ({el/FRAMES:.1f}s per frame)", flush=True)
print("[story] DONE", flush=True)
