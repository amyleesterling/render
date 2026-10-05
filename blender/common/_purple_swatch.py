"""Colour check for the partner purple.

Builds a tiny scene of dendrite-like tubes using the project's own
emissive_material, build_world, build_lights and apply_render_settings, so
what comes out has the same IOR 1.04, the same subsurface, the same HDRI, the
same Standard view transform and the same bloom as the real shot. Two
reference tubes carry the hero blue and the mossy-fibre gold; the rest are the
purple candidates.

  blender --background --python _purple_swatch.py -- out=path
"""
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__
g["RESOLUTION"] = (1600, 900)
g["SAMPLES"] = 64

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

SWATCHES = [
    ("hero blue", "#39A0FF"),
    ("MF gold", "#E2AF5E"),
    ("sparsely thorny", "#8B5CE0"),
    ("imperial", "#6A0DAD"),
    ("P1", "#7B2CB5"),
    ("P2", "#8837B8"),
    ("P3", "#9141C4"),
    ("A", "#A651C2"),
]

n = len(SWATCHES)
for i, (name, hexv) in enumerate(SWATCHES):
    x = (i - (n - 1) / 2.0) * 1.5
    # dendrite-thin, not a slab: a fat cylinder catches far more of the key
    # light than a 1um process does and every colour reads several stops
    # brighter than it will in the shot
    bpy.ops.mesh.primitive_cylinder_add(radius=0.10, depth=5.0,
                                        location=(x, 0, 0))
    o = bpy.context.active_object
    o.name = name
    bpy.ops.object.shade_smooth()
    o.data.materials.clear()
    o.data.materials.append(
        g["emissive_material"](f"sw_{i}", g["hexcol"](hexv), 1.0))
    # a sphere too: the somata are the big rounded forms and colour reads
    # differently on a curved mass than on a thin tube
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.62, location=(x, 0, 3.6))
    s = bpy.context.active_object
    s.name = name + "_soma"
    bpy.ops.object.shade_smooth()
    s.data.materials.clear()
    s.data.materials.append(bpy.data.materials[f"sw_{i}"])

bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0.8))
tgt = bpy.context.active_object
tgt.name = "SW_TARGET"

bpy.ops.object.camera_add(location=(0, -16.0, 2.0))
cam = bpy.context.active_object
cam.data.lens = 55
tc = cam.constraints.new(type="TRACK_TO")
tc.target = tgt
tc.track_axis = "TRACK_NEGATIVE_Z"
tc.up_axis = "UP_Y"
scene = bpy.context.scene
scene.camera = cam

g["build_world"](scene)
g["build_lights"](scene, 10.0, tgt)
g["apply_render_settings"](scene)

out = opts.get("out", r"D:\Meshes\renders\_purple_swatch.png")
scene.render.filepath = out
scene.render.image_settings.file_format = "PNG"
print("[sw] " + "  ".join(f"{i+1}:{n} {h}" for i, (n, h) in enumerate(SWATCHES)),
      flush=True)
bpy.ops.render.render(write_still=True)
print(f"[sw] wrote {out}", flush=True)
