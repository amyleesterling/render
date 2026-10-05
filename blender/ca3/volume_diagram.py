"""A scale diagram of the reconstructed volume.

A wireframe box at the block's real proportions with one pyramidal cell inside it,
so the reader can see how little of the tissue a single neuron occupies. The
labels go on in post, this only makes the picture.
"""
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)

# The paper states about 1 x 1 x 0.1 mm. Measured across 25,723 synapse positions
# the reconstructed span is 661 x 902 x 92 um, so the box is drawn at the paper's
# stated block size and the cell sits inside it at true relative scale.
BOX_UM = np.array([1000.0, 1000.0, 100.0])
HERO = r"D:\Meshes\hero\hero_648518346438632877.obj"

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__
RES = tuple(int(x) for x in opts.get("res", "1800x1200").split("x"))
g["RESOLUTION"] = RES
g["SAMPLES"] = int(opts.get("samples", 64))
hexcol = g["hexcol"]

scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y = RES
scene.frame_start = scene.frame_end = 1
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

SCALE = 10.0 / BOX_UM.max()          # 1000 um across becomes 10 Blender units
# World half extents are (x, z, y), NOT (x, y, z). The cell comes in through
# the OBJ importer, whose flip sends data z to world y, so a box built straight
# from BOX_UM is thin along the wrong axis and the cell stands up out of the
# slab. See RENDERING_NEURONS.md section 5.
_h = BOX_UM * SCALE / 2.0
half = Vector((_h[0], _h[2], _h[1]))

# ---- the block, as edges only ------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
box = bpy.context.active_object
box.name = "VOLUME"
box.scale = half
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.modifier_add(type="WIREFRAME")
box.modifiers["Wireframe"].thickness = 0.022
box.modifiers["Wireframe"].use_replace = True

wire = bpy.data.materials.new("VOL_WIRE")
wire.use_nodes = True
wt = wire.node_tree
wt.nodes.clear()
wo = wt.nodes.new("ShaderNodeOutputMaterial")
we = wt.nodes.new("ShaderNodeEmission")
we.inputs["Color"].default_value = hexcol("#5FA8E8") + (1.0,)
we.inputs["Strength"].default_value = 2.6
wt.links.new(we.outputs["Emission"], wo.inputs["Surface"])
box.data.materials.append(wire)

# ---- one cell, at true relative scale ----------------------------------------------
t0 = time.time()
before = set(bpy.data.objects)
bpy.ops.wm.obj_import(filepath=HERO)
cell = [o for o in bpy.data.objects if o not in before and o.type == "MESH"][0]
cell.name = "SCALE_CELL"
n = len(cell.data.vertices)
co = np.empty(n * 3)
cell.data.vertices.foreach_get("co", co)
co = co.reshape(n, 3)
print(f"[vol] cell {n:,} verts in {time.time()-t0:.0f}s", flush=True)

# EVERYTHING registers to one origin: the centre of the reconstructed region,
# which is the same point pull_em_slice.py crops the EM around. An earlier version
# centred the cell on its OWN centroid while the EM was cropped around the data
# centre, which put the cell 223 um out in x, 45 percent of the box half width,
# so it appeared to sit in tissue it is not actually in.
import json as _json
# Blender ships numpy but not pandas, so the origin is precomputed by
# pull_em_slice.py and read from disk. One source of truth, no drift.
DATA_CENTRE = np.array(_json.load(
    open("D:/Meshes/renders/em_registration.json"))["data_centre_nm"])
print(f"[vol] registering everything to the data centre {DATA_CENTRE.round(0)} nm", flush=True)

# vertices are raw file nanometres; the importer's flip rides on the object rotation
centre_scene = Vector((DATA_CENTRE[0], -DATA_CENTRE[2], DATA_CENTRE[1]))
cell.scale = (SCALE / 1000.0,) * 3        # nm -> um -> Blender units
cell.location = tuple(-centre_scene * (SCALE / 1000.0))
_off = (np.percentile(co, 0.5, axis=0) + np.percentile(co, 99.5, axis=0)) / 2.0 - DATA_CENTRE
print(f"[vol] cell sits {(_off/1000).round(1)} um from the block centre", flush=True)
bpy.context.view_layer.update()

span_um = (co.max(0) - co.min(0)) / 1000.0
print(f"[vol] cell spans {span_um.round(1)} um inside a "
      f"{BOX_UM.astype(int)} um block", flush=True)

# The thin axis of the cell must sit inside the thin axis of the block.
# This is the assertion that would have caught the shipped diagram.
_cell_world_y_um = span_um[2]          # data z becomes world y
assert _cell_world_y_um <= BOX_UM[2] * 1.05, (
    f"cell is {_cell_world_y_um:.0f} um through the slab's thin axis, "
    f"which is only {BOX_UM[2]:.0f} um: the box and the cell disagree "
    "about which way is up")
print(f"[vol] cell occupies {_cell_world_y_um:.0f} um of the "
      f"{BOX_UM[2]:.0f} um slab thickness", flush=True)

mat = bpy.data.materials.new("SCALE_CELL")
mat.use_nodes = True
b = mat.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = hexcol("#2E8BE0") + (1.0,)
b.inputs["Roughness"].default_value = 0.62
b.inputs["IOR"].default_value = 1.04          # submerged, never glossy
b.inputs["Emission Color"].default_value = hexcol("#BFE0FF") + (1.0,)
b.inputs["Emission Strength"].default_value = float(opts.get("cellglow", 1.15))
cell.data.materials.clear()
cell.data.materials.append(mat)

# ---- the tissue itself, as a cross section inside the box ---------------------------
# A real EM slice pulled from the imagery layer at 288 nm/voxel, cropped to the
# same 1000 um footprint the box represents and dropped in at mid depth, so the
# wireframe reads as a boundary drawn around actual tissue rather than an
# abstract volume. The pyramidal layer is the dense arc of somata.
EM = r"D:\Meshes\renders\em_plane.png"
if os.path.exists(EM):
    bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = "EM_SLICE"
    plane.scale = (half.x, half.z, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    # stand the plate into the world XZ plane, the two 1000 um axes, so it lies
    # in the slab instead of cutting across it
    plane.rotation_euler = (math.pi / 2.0, 0.0, 0.0)

    em = bpy.data.materials.new("EM_SLICE")
    em.use_nodes = True
    nt = em.node_tree
    nt.nodes.clear()
    eo = nt.nodes.new("ShaderNodeOutputMaterial")
    ee = nt.nodes.new("ShaderNodeEmission")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(EM)
    tex.extension = "CLIP"
    ee.inputs["Strength"].default_value = float(opts.get("emstrength", 1.25))
    nt.links.new(tex.outputs["Color"], ee.inputs["Color"])
    nt.links.new(ee.outputs["Emission"], eo.inputs["Surface"])
    plane.data.materials.append(em)
    print("[vol] EM cross section placed at mid depth", flush=True)
else:
    print("[vol] no EM plane found, drawing the box empty", flush=True)

# ---- present the slab flat ---------------------------------------------------------
# The box, the plate and the cell are now mutually correct, thin along world Y,
# which is where the importer's flip puts the data's 100 um cutting axis. The
# camera composition, though, was written when the slab was thin along Z, and a
# thin slab viewed along its own thin axis is a line. Rather than re-solve the
# camera, rotate the whole assembly as one rigid body: relative geometry is
# untouched, and which way a diagram calls "up" is a presentation choice, not a
# claim about the tissue.
_root = bpy.data.objects.new("VOL_ROOT", None)
bpy.context.collection.objects.link(_root)
for _o in (box, cell) + ((plane,) if os.path.exists(EM) else ()):
    _o.parent = _root
    _o.matrix_parent_inverse.identity()
_root.rotation_euler = (-math.pi / 2.0, 0.0, 0.0)
bpy.context.view_layer.update()
print("[vol] assembly rotated to present the slab flat", flush=True)

g["build_world"](scene)
target = bpy.data.objects.new("VOL_TARGET", None)
bpy.context.collection.objects.link(target)
target.location = (0, 0, 0)
g["build_lights"](scene, 10.0, target=target)

cam_data = bpy.data.cameras.new("VOL_CAM")
cam = bpy.data.objects.new("VOL_CAM", cam_data)
bpy.context.collection.objects.link(cam)
scene.camera = cam
d = float(opts.get("camdist", 2.05)) * 10.0
th = math.radians(float(opts.get("az", 52.0)))
cam.location = (d * math.cos(th), -d * math.sin(th), d * float(opts.get("elev", 0.42)))
trk = cam.constraints.new("TRACK_TO")
trk.target = target
trk.track_axis, trk.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
cam_data.clip_start, cam_data.clip_end = 0.01, d * 40

g["apply_render_settings"](scene)

# The page ground is near black, so the diagram ships with alpha rather than the
# world's grey. apply_render_settings composites a black plate under the
# transparent film, so that node has to go or the alpha is thrown away last.
nt = scene.node_tree
comp = next(n for n in nt.nodes if n.type == "COMPOSITE")
glare = next((n for n in nt.nodes if n.type == "GLARE"), None)
over = next((n for n in nt.nodes if n.type == "ALPHAOVER"), None)
if over is not None and glare is not None:
    for link in list(nt.links):
        if link.to_node is comp or link.from_node is over:
            nt.links.remove(link)
    nt.links.new(glare.outputs["Image"], comp.inputs["Image"])
    nt.nodes.remove(over)
scene.render.film_transparent = True
scene.render.image_settings.color_mode = "RGBA"
out = opts.get("out", r"D:\Meshes\renders\volume_diagram.png")
scene.render.filepath = out
scene.render.image_settings.file_format = "PNG"
t0 = time.time()
# ---- emit the label anchors, measured not guessed -------------------------------------
# label_volume.py reads these. They must be regenerated whenever the pose changes,
# which is exactly what went wrong: the file on disk was left over from the old
# orientation, so the labels would have been placed against geometry that moved.
from bpy_extras.object_utils import world_to_camera_view as _w2c
bpy.context.view_layer.update()
_scn = bpy.context.scene
_rx = _scn.render.resolution_x * _scn.render.resolution_percentage / 100.0
_ry = _scn.render.resolution_y * _scn.render.resolution_percentage / 100.0


def _px(v):
    c = _w2c(_scn, cam, v)
    return [c.x * _rx, (1.0 - c.y) * _ry]


_bb = [box.matrix_world @ Vector(c) for c in box.bound_box]
_xs = [v.x for v in _bb]; _ys = [v.y for v in _bb]; _zs = [v.z for v in _bb]
_lo = Vector((min(_xs), min(_ys), min(_zs)))
_hi = Vector((max(_xs), max(_ys), max(_zs)))
# the two 1000 um edges along the near, low corner, and one thin vertical edge
_proj = {
    "x": _px(Vector(((_lo.x + _hi.x) / 2, _lo.y, _lo.z))),
    "y": _px(Vector((_hi.x, (_lo.y + _hi.y) / 2, _lo.z))),
    "z": _px(Vector((_lo.x, _lo.y, (_lo.z + _hi.z) / 2))),
    "cell": _px(sum((cell.matrix_world @ Vector(c) for c in cell.bound_box),
                    Vector((0, 0, 0))) / 8.0),
}
_json.dump(_proj, open("D:/Meshes/renders/_vol_proj.json", "w"), indent=1)
print("[vol] label anchors ->", {k: [round(x) for x in v] for k, v in _proj.items()},
      flush=True)

bpy.ops.render.render(write_still=True)
print(f"[vol] rendered in {time.time()-t0:.0f}s -> {out}", flush=True)
print("[vol] DONE", flush=True)
