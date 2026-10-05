"""
Build the full scene once and save it as a .blend.

Every render currently re-parses 13.17 GB of ASCII OBJ, which is the ~9 minute
build. Blender's own format is binary, so loading the saved scene should take
well under a minute. Everything cheap to redo (materials, lights, camera,
keyframes, compositor) is deliberately NOT relied upon here: render_from_cache.py
rebuilds all of that on load, so palette and timing stay editable without ever
touching the OBJ files again.

  blender --background --python build_cache.py -- [out=path.blend] <group>...
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

if groups:
    g["ENABLED"] = groups
g["RENDER"] = False
g["SHOW_SYNAPSES"] = opts.get("synapses", "1") not in ("0", "false", "off", "no")

out = opts.get("out", r"D:\Meshes\ca3_scene.blend")

t0 = time.time()
g["build"]()
print(f"[cache] scene built in {time.time() - t0:.0f}s", flush=True)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
faces = sum(len(o.data.polygons) for o in meshes)
print(f"[cache] {len(meshes):,} mesh objects, {faces:,} faces", flush=True)
print(f"[cache] collections: {[c.name for c in bpy.context.scene.collection.children]}",
      flush=True)

t0 = time.time()
bpy.ops.wm.save_as_mainfile(filepath=out, compress=False)
print(f"[cache] saved {out} in {time.time() - t0:.0f}s", flush=True)
print("[cache] DONE", flush=True)
