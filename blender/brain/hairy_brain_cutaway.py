"""Hairy brain, cutaway: the left cortex lifted off to show what sits under it.

Right hemisphere, both cerebellar hemispheres and the brainstem keep the fur
from hairy_brain_360.py. The left pial surface is removed and the left deep
structures from the same FreeSurfer segmentation are shown as smooth tissue,
one palette colour per structure. Same subject, same RAS mm space, so nothing
is placed by hand.

    blender --background --python hairy_brain_cutaway.py -- res=960x540 samples=64
    blender --background --python hairy_brain_cutaway.py -- out=D:\Meshes\renders\hairy_brain_cutaway.png

Data: Anderson Winkler, Brain for Blender (brainder.org), FreeSurfer 5.2,
CC BY-SA 3.0. Limits: one subject's automatic segmentation; structure
boundaries are aseg labels, not histology; the ventricles are shown as solid
bodies.
"""
import math
import os
import sys
import time

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(kv.split("=", 1) for kv in argv if "=" in kv)

PIAL = r"C:\Users\amyle\Downloads\pial_Full_obj\pial_Full_obj"
SUB = r"C:\Users\amyle\Downloads\human brain subcortical_obj\subcortical_obj"
SCALE = 0.01
RES = tuple(int(v) for v in opts.get("res", "1920x1080").split("x"))
SAMPLES = int(opts.get("samples", 128))
STRANDS = int(opts.get("strands", 1_200_000))
LENGTH = float(opts.get("length", 0.020))
RADIUS = float(opts.get("radius", 0.0006))
LIGHT = float(opts.get("light", "0.60"))
HUE_TILT = float(opts.get("huetilt", "0.3"))
OUT = opts.get("out", r"D:\Meshes\renders\hairy_brain_cutaway.png")
SEED = 7

# Amy's palette, 4 Sept 2026
C = {
    "hot pink":     (1.00, 0.18, 0.62),
    "orange":       (1.00, 0.40, 0.04),
    "warm yellow":  (1.00, 0.82, 0.15),
    "teal-green":   (0.08, 0.68, 0.50),
    "turquoise":    (0.10, 0.82, 0.85),
    "sky blue":     (0.35, 0.72, 1.00),
    "rich blue":    (0.12, 0.40, 0.95),
    "royal blue":   (0.18, 0.20, 0.85),
    "light purple": (0.66, 0.50, 0.95),
    "deep purple":  (0.40, 0.10, 0.70),
}
VIVID = [(0.00, C["hot pink"]), (0.09, C["orange"]), (0.18, C["warm yellow"]),
         (0.30, C["teal-green"]), (0.40, C["turquoise"]), (0.50, C["sky blue"]),
         (0.60, C["rich blue"]), (0.70, C["royal blue"]), (0.80, C["light purple"]),
         (0.90, C["deep purple"]), (1.00, C["hot pink"])]

FURRED = [
    (PIAL + r"\human bran rh.pial.obj", "pial_rh"),
    (SUB + r"\Left-Cerebellum-Cortex.obj", "cbm_lh"),
    (SUB + r"\Right-Cerebellum-Cortex.obj", "cbm_rh"),
    (SUB + r"\Brain-Stem.obj", "brainstem"),
]
# left deep structures, one colour each
DEEP = [
    ("Left-Thalamus-Proper", "rich blue"),
    ("Left-Caudate", "turquoise"),
    ("Left-Putamen", "orange"),
    ("Left-Pallidum", "warm yellow"),
    ("Left-Hippocampus", "hot pink"),
    ("Left-Amygdala", "deep purple"),
    ("Left-Accumbens-area", "light purple"),
    ("Left-VentralDC", "royal blue"),
    ("Left-Lateral-Ventricle", "sky blue"),
    ("Left-Inf-Lat-Vent", "sky blue"),
    ("3rd-Ventricle", "sky blue"),
    ("CC_Anterior", "teal-green"),
    ("CC_Mid_Anterior", "teal-green"),
    ("CC_Central", "teal-green"),
    ("CC_Mid_Posterior", "teal-green"),
    ("CC_Posterior", "teal-green"),
]

t_start = time.time()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def log(msg):
    print(f"[cut] {msg}", flush=True)


def sock(node, name, output=False):
    for s in (node.outputs if output else node.inputs):
        if s.name == name and s.enabled:
            return s
    raise KeyError(f"{node.name} has no enabled socket {name!r}")


def import_obj(path, name):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path, forward_axis="Y", up_axis="Z")
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    assert len(new) == 1, path
    obj = new[0]
    assert all(abs(r) < 1e-6 for r in obj.rotation_euler), f"rotation on {name}"
    obj.name = name
    obj.scale = (SCALE,) * 3
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)
    obj.data.materials.clear()
    return obj


furred = [import_obj(p, n) for p, n in FURRED]
deep = [(import_obj(SUB + f"\\{n}.obj", n), c) for n, c in DEEP]
everything = furred + [o for o, _ in deep]

allv = [o.matrix_world @ Vector(c) for o in everything for c in o.bound_box]
lo = Vector(tuple(min(v[i] for v in allv) for i in range(3)))
hi = Vector(tuple(max(v[i] for v in allv) for i in range(3)))
# the removed left hemisphere still defines the composition: use the full
# brain's centre so the cutaway sits where the whole brain would
full_lo = Vector((-0.697, -0.999, -0.638))
full_hi = Vector((0.689, 0.702, 0.603))
center = (full_lo + full_hi) / 2
ext = full_hi - full_lo
log(f"furred {sum(len(o.data.polygons) for o in furred):,} faces, "
    f"{len(deep)} deep structures, bounds z {lo.z:.2f}..{hi.z:.2f}")
assert lo.z < -0.6 and hi.z > 0.55, "bounds off: check axis mapping"

area = sum(sum(p.area for p in o.data.polygons) for o in furred)
density = STRANDS * 1.4 / area


# ------------------------------------------------------------ colour
def vivid_colour(nt, vec_socket):
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(vec_socket, sep.inputs["Vector"])

    def m(op, a, b=None, const=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        nt.links.new(a, n.inputs[0])
        if b is not None:
            nt.links.new(b, n.inputs[1])
        elif const is not None:
            n.inputs[1].default_value = const
        return n.outputs[0]

    bearing = m("ARCTAN2", sep.outputs["Y"], sep.outputs["X"])
    hue = m("ADD", m("DIVIDE", bearing, const=2 * math.pi), const=0.5)
    hue = m("FRACT", m("ADD", hue, m("MULTIPLY", sep.outputs["Z"], const=HUE_TILT)))
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position = VIVID[0][0]
    cr.elements[0].color = (*VIVID[0][1], 1.0)
    for pos, col in VIVID[1:]:
        cr.elements.new(pos).color = (*col, 1.0)
    nt.links.new(hue, ramp.inputs["Fac"])
    return ramp.outputs["Color"]


def fur_material():
    mat = bpy.data.materials.new("Fur")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "nrm"
    col = vivid_colour(nt, attr.outputs["Vector"])
    hi_ = nt.nodes.new("ShaderNodeHairInfo")
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = 0.75
    nt.links.new(hi_.outputs["Intercept"], ramp.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMixRGB")
    mul.blend_type = "MULTIPLY"
    mul.inputs["Fac"].default_value = 1.0
    nt.links.new(col, mul.inputs["Color1"])
    nt.links.new(ramp.outputs["Result"], mul.inputs["Color2"])
    nt.links.new(mul.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.55
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    return mat


def surface_material():
    mat = bpy.data.materials.new("PialSurface")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    col = vivid_colour(nt, geo.outputs["Normal"])
    dark = nt.nodes.new("ShaderNodeMixRGB")
    dark.blend_type = "MULTIPLY"
    dark.inputs["Fac"].default_value = 1.0
    dark.inputs["Color2"].default_value = (0.25, 0.25, 0.25, 1.0)
    nt.links.new(col, dark.inputs["Color1"])
    nt.links.new(dark.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.7
    return mat


def tissue_material(name, rgb):
    """Deep structures: submerged tissue per the playbook. IOR 1.04, soft,
    subsurface carrying the translucency, no glossy highlight."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.62
    bsdf.inputs["IOR"].default_value = 1.04
    bsdf.inputs["Subsurface Weight"].default_value = 0.35
    bsdf.inputs["Subsurface Radius"].default_value = (0.02, 0.015, 0.012)
    bsdf.inputs["Subsurface Scale"].default_value = 0.012
    return mat


mat_fur = fur_material()
mat_surf = surface_material()
for o in furred:
    o.data.materials.append(mat_surf)
for o, cname in deep:
    o.data.materials.append(tissue_material(o.name, C[cname]))


# ------------------------------------------------------------ fur
def fur_node_group():
    ng = bpy.data.node_groups.new("BrainFur", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, L = ng.nodes, ng.links
    n.new("NodeGroupInput")
    gout = n.new("NodeGroupOutput")
    join = n.new("GeometryNodeJoinGeometry")
    for o in furred:
        oi = n.new("GeometryNodeObjectInfo")
        sock(oi, "Object").default_value = o
        L.new(oi.outputs["Geometry"], join.inputs["Geometry"])
    dist = n.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "RANDOM"
    sock(dist, "Density").default_value = density
    sock(dist, "Seed").default_value = SEED
    L.new(join.outputs["Geometry"], sock(dist, "Mesh"))
    jit = n.new("FunctionNodeRandomValue")
    jit.data_type = "FLOAT_VECTOR"
    sock(jit, "Min").default_value = (-0.35,) * 3
    sock(jit, "Max").default_value = (0.35,) * 3
    sock(jit, "Seed").default_value = SEED + 1
    add = n.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    L.new(dist.outputs["Normal"], add.inputs[0])
    L.new(sock(jit, "Value", output=True), add.inputs[1])
    norm = n.new("ShaderNodeVectorMath")
    norm.operation = "NORMALIZE"
    L.new(add.outputs["Vector"], norm.inputs[0])
    store = n.new("GeometryNodeStoreNamedAttribute")
    store.data_type = "FLOAT_VECTOR"
    store.domain = "POINT"
    sock(store, "Name").default_value = "nrm"
    L.new(dist.outputs["Points"], sock(store, "Geometry"))
    L.new(dist.outputs["Normal"], sock(store, "Value"))
    line = n.new("GeometryNodeCurvePrimitiveLine")
    sock(line, "End").default_value = (0, 0, LENGTH)
    res = n.new("GeometryNodeResampleCurve")
    res.mode = "COUNT"
    sock(res, "Count").default_value = 4
    L.new(line.outputs["Curve"], sock(res, "Curve"))
    align = n.new("FunctionNodeAlignRotationToVector")
    align.axis = "Z"
    L.new(norm.outputs["Vector"], sock(align, "Vector"))
    lenr = n.new("FunctionNodeRandomValue")
    lenr.data_type = "FLOAT"
    sock(lenr, "Min").default_value = 0.55
    sock(lenr, "Max").default_value = 1.0
    sock(lenr, "Seed").default_value = SEED + 2
    inst = n.new("GeometryNodeInstanceOnPoints")
    L.new(store.outputs["Geometry"], sock(inst, "Points"))
    L.new(res.outputs["Curve"], sock(inst, "Instance"))
    L.new(align.outputs["Rotation"], sock(inst, "Rotation"))
    L.new(sock(lenr, "Value", output=True), sock(inst, "Scale"))
    real = n.new("GeometryNodeRealizeInstances")
    L.new(inst.outputs["Instances"], sock(real, "Geometry"))
    param = n.new("GeometryNodeSplineParameter")
    taper = n.new("ShaderNodeMapRange")
    taper.inputs["To Min"].default_value = RADIUS
    taper.inputs["To Max"].default_value = RADIUS * 0.33
    L.new(param.outputs["Factor"], taper.inputs["Value"])
    rad = n.new("GeometryNodeSetCurveRadius")
    L.new(real.outputs["Geometry"], sock(rad, "Curve"))
    L.new(taper.outputs["Result"], sock(rad, "Radius"))
    setmat = n.new("GeometryNodeSetMaterial")
    sock(setmat, "Material").default_value = mat_fur
    L.new(rad.outputs["Curve"], sock(setmat, "Geometry"))
    L.new(setmat.outputs["Geometry"], gout.inputs["Geometry"])
    return ng


fur_data = bpy.data.hair_curves.new("BrainFur")
fur_data.materials.append(mat_fur)
fur_obj = bpy.data.objects.new("BrainFur", fur_data)
scene.collection.objects.link(fur_obj)
fur_obj.modifiers.new("Fur", "NODES").node_group = fur_node_group()


# ------------------------------------------------------------ studio
world = bpy.data.worlds.new("Studio")
scene.world = world
world.use_nodes = True
nt = world.node_tree
for nd in list(nt.nodes):
    nt.nodes.remove(nd)
out = nt.nodes.new("ShaderNodeOutputWorld")
lp = nt.nodes.new("ShaderNodeLightPath")
mix = nt.nodes.new("ShaderNodeMixShader")
cam_bg = nt.nodes.new("ShaderNodeBackground")
cam_bg.inputs["Color"].default_value = (0.86, 0.86, 0.87, 1.0)
env_bg = nt.nodes.new("ShaderNodeBackground")
env_bg.inputs["Strength"].default_value = 0.30 * LIGHT
nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
nt.links.new(env_bg.outputs["Background"], mix.inputs[1])
nt.links.new(cam_bg.outputs["Background"], mix.inputs[2])
nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])

bpy.ops.mesh.primitive_plane_add(size=40, location=(center.x, center.y, lo.z - 0.02))
bpy.context.active_object.is_shadow_catcher = True
bpy.ops.object.empty_add(location=center)
root = bpy.context.active_object
size = max(ext)
# key light moved to the cut side so the deep structures are lit, not in shadow
for name, dirv, energy, lsize, colour in [
    ("KEY",  (-1.5, -1.1,  1.5), 380.0, 2.2, (1.00, 0.97, 0.93)),
    ("FILL", ( 1.8, -0.9,  0.6), 140.0, 3.0, (0.96, 0.96, 1.00)),
    ("RIM",  ( 0.4,  1.8,  1.2), 220.0, 2.0, (0.92, 0.95, 1.00)),
    ("TOP",  ( 0.1,  0.2,  2.4), 150.0, 2.6, (1.00, 1.00, 1.00)),
]:
    bpy.ops.object.light_add(type="AREA", location=tuple(center[i] + d * size for i, d in enumerate(dirv)))
    lt = bpy.context.active_object
    lt.data.energy = energy * LIGHT
    lt.data.size = lsize
    lt.data.color = colour
    con = lt.constraints.new(type="TRACK_TO")
    con.target = root
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

# camera: from the left, a little forward and above, looking at the centre
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 60.0
cam = bpy.data.objects.new("Camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
tan_h = 18.0 / cam_data.lens
tan_v = tan_h * RES[1] / RES[0]
dist = (max(ext) * 0.5 * 1.1) / min(tan_h, tan_v) * 1.02
direction = Vector((-1.0, -0.45, 0.42)).normalized()
cam.location = center + direction * dist
cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
cam_data.dof.use_dof = True
cam_data.dof.focus_object = root
cam_data.dof.aperture_fstop = 5.6

# ------------------------------------------------------------ render
scene.render.engine = "CYCLES"
scene.cycles.samples = SAMPLES
scene.cycles.use_adaptive_sampling = True
scene.cycles.use_denoising = True
scene.cycles.denoiser = "OPTIX"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for dv in prefs.devices:
    dv.use = dv.type != "CPU"
scene.cycles.device = "GPU"
if hasattr(scene.render, "hair_type"):
    scene.render.hair_type = "STRIP"
    scene.render.hair_subdiv = 2
scene.render.use_motion_blur = False
scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.render.dither_intensity = 0.0

os.makedirs(os.path.dirname(OUT), exist_ok=True)
scene.render.filepath = OUT
t0 = time.time()
bpy.ops.render.render(write_still=True)
log(f"{RES[0]}x{RES[1]} {SAMPLES} samples -> {OUT} in {time.time() - t0:.0f}s "
    f"(build {t0 - t_start:.0f}s)")
log("DONE")
