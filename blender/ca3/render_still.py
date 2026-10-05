"""Render one frame of the CA3 scene.

  blender --background --python render_still.py -- <frame> <out.png> [key=val] <group>...

Optional key=val tokens:
  zoom=2.5      camera distance divisor (higher = closer)
  lens=110      camera focal length in mm
  res=2560x1440 resolution
  samples=128
"""
import sys
import time

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
frame = int(argv[0])
out_png = argv[1]
rest = argv[2:]

opts = {}
groups = []
for tok in rest:
    if "=" in tok:
        k, v = tok.split("=", 1)
        opts[k] = v
    else:
        groups.append(tok)

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)

g = ns["build"].__globals__
g["ENABLED"] = groups
g["RENDER"] = False
if "lens" in opts:
    g["CAM_LENS_MM"] = float(opts["lens"])
if "res" in opts:
    w, h = opts["res"].split("x")
    g["RESOLUTION"] = (int(w), int(h))
if "samples" in opts:
    g["SAMPLES"] = int(opts["samples"])
if "rt" in opts:
    g["USE_RAYTRACING"] = opts["rt"] not in ("0", "false", "off", "no")
if "shadows" in opts:
    g["USE_SHADOWS"] = opts["shadows"] not in ("0", "false", "off", "no")
if "softness" in opts:
    g["SHADOW_SOFTNESS"] = float(opts["softness"])
if "swapcolors" in opts:
    # swapcolors=groupA,groupB exchanges their colour and per-cell ramp, so two
    # palette variants can be rendered from one config with no file edits.
    a, b = opts["swapcolors"].split(",")
    ga, gb = g["GROUPS"][a], g["GROUPS"][b]
    for key in ("color", "per_cell_range"):
        va, vb = ga.get(key), gb.get(key)
        if va is None and vb is None:
            continue
        ga[key], gb[key] = vb, va
        if ga[key] is None:
            del ga[key]
        if gb[key] is None:
            del gb[key]
    print(f"[render] swapped colours: {a} <-> {b}", flush=True)

t0 = time.time()
g["build"]()
print(f"[render] scene built in {time.time() - t0:.0f}s", flush=True)

scene = bpy.context.scene
scene.frame_set(frame)

if "zoom" in opts:
    z = float(opts["zoom"])
    cam = scene.camera
    cam.location = tuple(c / z for c in cam.location)
    print(f"[render] zoom {z}x, camera at {tuple(round(c, 2) for c in cam.location)}",
          flush=True)

scene.render.filepath = out_png
scene.render.image_settings.file_format = "PNG"
print(f"[render] engine={scene.render.engine} frame={frame} "
      f"{scene.render.resolution_x}x{scene.render.resolution_y} -> {out_png}", flush=True)

# report what the materials actually are, so transparency bugs cannot hide
for mat in bpy.data.materials:
    if not mat.use_nodes or "Principled BSDF" not in mat.node_tree.nodes:
        continue
    b = mat.node_tree.nodes["Principled BSDF"]
    print(f"[mat] {mat.name:<28} alpha={b.inputs['Alpha'].default_value:.2f} "
          f"blend={mat.blend_method} "
          f"emission={b.inputs['Emission Strength'].default_value:.2f} "
          f"rough={b.inputs['Roughness'].default_value:.2f}", flush=True)

t0 = time.time()
bpy.ops.render.render(write_still=True)
print(f"[render] rendered in {time.time() - t0:.0f}s", flush=True)

import numpy as np

img = bpy.data.images.load(out_png)
px = np.array(img.pixels[:]).reshape(-1, 4)
lum = px[:, :3].mean(axis=1)
print(f"[verify] luminance mean={lum.mean():.4f} max={lum.max():.4f}", flush=True)
print(f"[verify] pixels above 5% brightness: {(lum > 0.05).mean() * 100:.2f}%", flush=True)
print("[verify] image has visible content" if lum.max() > 0.02 else "[verify] WARNING black",
      flush=True)
