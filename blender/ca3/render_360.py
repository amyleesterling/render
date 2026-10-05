"""
Render the full 360 orbit as an mp4.

  blender --background --python render_360.py -- [key=val] <group>...

  frames=240        length of the orbit
  res=1920x1080
  samples=64
  reveal=0          everything visible from frame 1 (default for a pure turntable)
  out=<path.mp4>

Scene build is paid once; every frame after that reuses the geometry.
"""
import sys
import time

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts, groups = {}, []
for tok in argv:
    if "=" in tok:
        k, v = tok.split("=", 1)
        opts[k] = v
    else:
        groups.append(tok)

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__

frames = int(opts.get("frames", 240))
g["ENABLED"] = groups
g["RENDER"] = False
g["FRAME_END"] = frames
g["ORBIT_TURNS"] = float(opts.get("turns", 1.0))
g["ORBIT_START_DEG"] = float(opts.get("start", 0.0))
if "camdist" in opts:
    g["CAM_DISTANCE_MULT"] = float(opts["camdist"])
if "synapses" in opts:
    g["SHOW_SYNAPSES"] = opts["synapses"] not in ("0", "false", "off", "no")
if "synreveal" in opts:
    a2, b2 = opts["synreveal"].split("-")
    g["SYNAPSE_REVEAL"] = (int(a2), int(b2))
if "synradius" in opts:
    g["SYNAPSE_RADIUS_NM"] = float(opts["synradius"])
if "res" in opts:
    w, h = opts["res"].split("x")
    g["RESOLUTION"] = (int(w), int(h))
if "samples" in opts:
    g["SAMPLES"] = int(opts["samples"])

# For a turntable we want every cell present in every frame, so collapse the
# staged reveal windows rather than letting cells grow in.
if opts.get("reveal", "0") in ("0", "false", "no", "off"):
    for spec in g["GROUPS"].values():
        spec["reveal"] = (1, 1)
    g["REVEAL_LEN"] = 0
    print("[360] staged reveal disabled, all cells visible throughout", flush=True)

t0 = time.time()
g["build"]()
print(f"[360] scene built in {time.time() - t0:.0f}s", flush=True)

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = frames

out = opts.get("out", r"D:\Meshes\renders\ca3_360.mp4")
scene.render.filepath = out
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "HIGH"
scene.render.ffmpeg.ffmpeg_preset = "GOOD"

print(f"[360] {frames} frames @ {scene.render.fps}fps, "
      f"{scene.render.resolution_x}x{scene.render.resolution_y}, "
      f"{scene.eevee.taa_render_samples} samples -> {out}", flush=True)

t0 = time.time()
bpy.ops.render.render(animation=True)
el = time.time() - t0
print(f"[360] rendered {frames} frames in {el/60:.1f} min "
      f"({el/frames:.1f}s per frame)", flush=True)
print("[360] DONE", flush=True)
