"""
A core through cortex: proofread MICrONS neurons coloured by cortical depth.

  blender --background --python microns_column.py -- [key=val]

  res=3840x2160  samples=128
  camdist=1.35  shifty=0.0
  view=side|front
  out=path

WHAT THIS IS. Every fully proofread neuron on disk from the MICrONS mouse visual
cortex volume, 38 cells, shown side on with the pia at the top. Colour is not a
measurement of the cell, it is the cell's own position: every vertex is tinted by
its depth below the pia, so a single pyramidal neuron reads gold where its apical
tuft reaches the surface and blue where its soma and basal dendrites sit deep.
Cortical lamination is not drawn on; it emerges from where the somata gather.

WHY PER VERTEX AND NOT PER CELL. One colour per cell would need a soma
coordinate, and what is on disk is meshes, not a soma table. The honest quantity
available at every point is the point's own depth, and colouring by it says
something true about the whole arbor rather than reducing a 500 um cell to a
single number. It also makes the picture: the apical dendrite becomes a visible
gradient climbing through the layers.

DEPTH IS THE DATA'S y AXIS, and it increases downward from the pia. Blender's OBJ
importer maps (x, y, z) to world (x, -z, y), so data y arrives as world z, which
puts deep cells HIGH. The whole assembly is therefore rotated 180 degrees about X
so that down on screen is down in the cortex. Getting this backwards renders an
upside down brain that still looks entirely plausible.

COLOUR RAMP: gold at the pia through violet to deep blue, three explicit stops
lerped in sRGB. Never interpolate a ramp in HSV; blue to gold takes the long way
round through green and invents a colour neither stop contains. See
RENDERING_NEURONS.md section 2. These are the same three stops the CA3
convergence gradient uses, reversed, so the two datasets read as one visual
language even though the axis being encoded is different. Say that in the caption.
"""
import sys
import glob
import time
import os

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)

SRC = opts.get("src", r"D:\Meshes\microns")
CACHE = r"D:\Meshes\microns_scene.blend"

# gold at the pia, deep blue at the white matter
STOPS = ((0.00, (0xFF, 0xC2, 0x4A)),
         (0.50, (0x8E, 0x46, 0xC0)),
         (1.00, (0x1D, 0x35, 0x8F)))

HOUSE = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": HOUSE}
exec(compile(open(HOUSE, encoding="utf-8").read(), HOUSE, "exec"), ns)
g = ns["build"].__globals__
build_world = g["build_world"]
build_lights = g["build_lights"]
apply_render_settings = g["apply_render_settings"]
world_bounds = g["world_bounds"]
clear_scene = g["clear_scene"]
TARGET_SIZE = g["TARGET_SIZE"]

if "res" in opts:
    w, h = opts["res"].split("x")
    g["RESOLUTION"] = (int(w), int(h))
g["SAMPLES"] = int(opts.get("samples", 128))


def cell_jitter(seg):
    """A small, fixed, per cell offset: (hue degrees, lightness multiplier).

    OFF BY DEFAULT. Amy tried it and does not want it: "no jitter, I don't like
    jitter." Both amounts default to zero, so this returns a no-op and the ramp is
    exactly the depth ramp. The code stays because the underlying want is still
    real, telling one cell from its neighbour, but jitter is not the answer to it.
    Pass huejit and litjit to switch it back on.
    """
    h = 0
    for ch in str(seg):
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    hue = ((h & 0xFFFF) / 65535.0 - 0.5) * 2.0 * float(opts.get("huejit", 0.0))
    lit = 1.0 + (((h >> 16) & 0xFFFF) / 65535.0 - 0.5) * 2.0 * float(opts.get("litjit", 0.0))
    return hue, lit


def apply_jitter(rgb_lin, hue_deg, lit_mul):
    """Rotate hue and scale lightness on a linear RGB triple, via HSV.

    The ramp itself is never interpolated in HSV, for the reason in
    RENDERING_NEURONS.md section 2. Rotating a single already chosen colour is a
    different operation and is safe: there is no path between two hues to take
    the long way round.
    """
    import colorsys
    srgb = [max(0.0, min(1.0, c)) ** (1.0 / 2.2) for c in rgb_lin]
    h, sv, v = colorsys.rgb_to_hsv(*srgb)
    h = (h + hue_deg / 360.0) % 1.0
    v = max(0.0, min(1.0, v * lit_mul))
    r, g_, b = colorsys.hsv_to_rgb(h, sv, v)
    return tuple(c ** 2.2 for c in (r, g_, b))


def ramp(t):
    t = float(min(max(t, 0.0), 1.0))
    for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            return tuple(((a + (b - a) * u) / 255.0) ** 2.2 for a, b in zip(c0, c1))
    return tuple((c / 255.0) ** 2.2 for c in STOPS[-1][1])


scene = bpy.context.scene
files = sorted(glob.glob(os.path.join(SRC, "*.obj")))
if not files:
    raise SystemExit(f"No decimated cells in {SRC}. Run decimate_microns.py first.")
print(f"[mic] {len(files)} cells", flush=True)

clear_scene()
scene = bpy.context.scene
coll = bpy.data.collections.new("MICRONS")
scene.collection.children.link(coll)

t0 = time.time()
objs = []
for i, f in enumerate(files):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=f)
    for o in [x for x in bpy.data.objects if x not in before and x.type == "MESH"]:
        o.name = "mic_" + os.path.splitext(os.path.basename(f))[0]
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        objs.append(o)
    if (i + 1) % 10 == 0:
        print(f"[mic]   {i+1}/{len(files)} ({time.time()-t0:.0f}s)", flush=True)
faces = sum(len(o.data.polygons) for o in objs)
print(f"[mic] {len(objs)} meshes, {faces:,} faces in {time.time()-t0:.0f}s", flush=True)

# ---- depth range across the whole population, in data micrometres ---------------------
# vertices are file nanometres; data y is depth. Percentile bounds, not min/max, so a
# single stray fragment does not set the scale for everything else.
dep = []
for o in objs:
    n = len(o.data.vertices)
    co = np.empty(n * 3)
    o.data.vertices.foreach_get("co", co)
    dep.append(co.reshape(n, 3)[:, 1])
alld = np.concatenate(dep)
D_LO, D_HI = (np.percentile(alld, 0.2) / 1000.0, np.percentile(alld, 99.8) / 1000.0)
print(f"[mic] depth {D_LO:.0f} to {D_HI:.0f} um below pia, "
      f"{D_HI - D_LO:.0f} um of cortex", flush=True)

# ---- colour ---------------------------------------------------------------------------
# Two schemes. `colour=depth` tints every vertex by its own depth below the pia and
# is the original. `colour=type` gives each cell one flat colour from its predicted
# cell type. Amy chose type on 31 July 2026, after saying of the depth version that
# "the cells are all still the same color".
#
# WHAT TYPE COLOURING DOES AND DOES NOT FIX. It separates a layer 4 pyramid from a
# layer 5 one, and it makes the Martinotti cell and the oligodendrocyte instantly
# findable. It does NOT separate a cell from a same-type neighbour, and 11 of these
# 38 are 23P, so eleven cells still share one colour. If the requirement is that
# every individual cell be distinguishable, this is not sufficient on its own.
#
# The layering survives the change, which is the interesting part: colour is now
# identity rather than position, and the bands still appear, because that is where
# each type lives. That is a stronger version of the page's claim than the depth
# ramp made, since the ramp could only ever show what it was told.
SCHEME = opts.get("colour", "type")

# Types resolved through the chunked graph first: 9 of the 38 mesh ids had gone
# stale, and a stale id looked up in a current table returns nothing, which reads
# as "no cell type" rather than as an error. Built by the lookup that writes
# microns_celltypes.csv; regenerate that if the mesh set changes.
TYPE_COLOUR = {
    "23P":   "#2E8BE0",   # layer 2/3 pyramidal      blue
    "4P":    "#8B5CE0",   # layer 4 pyramidal        violet
    "5P-IT": "#E8A93A",   # layer 5 intratelencephalic gold
    "5P-ET": "#17A06B",   # layer 5 extratelencephalic emerald
    "6P-IT": "#7FC4F5",   # layer 6 intratelencephalic pale blue
    "MC":    "#E0559B",   # Martinotti, INHIBITORY    rose, deliberately off-palette
    "oligo": "#8A94A6",   # oligodendrocyte, NOT A NEURON  grey
}
UNKNOWN = "#4A5568"       # no type call; grey-blue, visibly not a claim


def _hex_lin(h):
    h = h.lstrip("#")
    return tuple((int(h[i:i + 2], 16) / 255.0) ** 2.2 for i in (0, 2, 4))


CELLTYPE = {}
_tp = r"D:\Meshes\renders\microns_celltypes.csv"
if SCHEME == "type":
    if not os.path.exists(_tp):
        raise SystemExit(f"colour=type needs {_tp}. Run the cell type lookup first.")
    # imported here, not at the top: the file's other csv import is further down,
    # after this block, so relying on it would raise NameError at render time.
    import csv as _csv_mod
    with open(_tp, encoding="utf-8") as fh:
        for r in _csv_mod.DictReader(fh):
            if r.get("cell_type"):
                CELLTYPE[r["mesh_id"]] = r["cell_type"]
    seen = {}
    for o in objs:
        seen[CELLTYPE.get(o.name.replace("mic_", ""), "unknown")] = 1
    print(f"[mic] colour = cell type; {len(CELLTYPE)} of {len(objs)} cells typed; "
          f"types present: {', '.join(sorted(seen))}", flush=True)
else:
    print("[mic] colour = depth ramp", flush=True)

for o, dy in zip(objs, dep):
    me = o.data
    at = me.color_attributes.get("depth") or me.color_attributes.new(
        name="depth", type="FLOAT_COLOR", domain="POINT")
    n = len(me.vertices)
    cols = np.empty((n, 4), dtype=np.float64)
    if SCHEME == "type":
        ct = CELLTYPE.get(o.name.replace("mic_", ""))
        cols[:, :3] = _hex_lin(TYPE_COLOUR.get(ct, UNKNOWN))
    else:
        t = np.clip((dy / 1000.0 - D_LO) / max(1e-6, D_HI - D_LO), 0.0, 1.0)
        _hue, _lit = cell_jitter(o.name.replace("mic_", ""))
        # one lookup table per cell rather than per vertex: the ramp is smooth, so
        # 256 steps is indistinguishable and it turns millions of colorsys calls
        # into 256
        _lut = np.array([apply_jitter(ramp(i / 255.0), _hue, _lit) for i in range(256)])
        cols[:, :3] = _lut[(t * 255).astype(np.int32)]
    cols[:, 3] = 1.0
    at.data.foreach_set("color", cols.ravel())
    me.update()

mat = bpy.data.materials.new("mat_depth")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
attr = nt.nodes.new("ShaderNodeVertexColor")
attr.layer_name = "depth"
nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
# submerged tissue, never glossy. Same rule as every other render in this project.
bsdf.inputs["Roughness"].default_value = g["SURFACE_ROUGHNESS"]
bsdf.inputs["IOR"].default_value = g["TISSUE_IOR_IN_WATER"]
if "Specular IOR Level" in bsdf.inputs:
    bsdf.inputs["Specular IOR Level"].default_value = g["SPECULAR_LEVEL"]
if "Emission Color" in bsdf.inputs:
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = float(opts.get("glow", 0.28))
for o in objs:
    o.data.materials.clear()
    o.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.shade_smooth()
print("[mic] painted by depth and shaded", flush=True)

# ---- real somata, from the CAVE nucleus table ------------------------------------------
# Amy's correction: a vertex centroid is noise inside the soma, and the exact
# locations are queryable. nucleus_detection_v0 on minnie65_phase3_v1, positions
# in 4/4/40 nm voxels, converted to nanometres here and put through the same axis
# flip the meshes get, then parented to the same root so they inherit everything.
# 9 of the 38 mesh ids had gone stale since download and were resolved forward
# through the chunkedgraph; 34 of 38 have a nucleus.
import csv as _csv
_soma_w = []
_sp = 'D:/Meshes/renders/microns_somas.csv'
if os.path.exists(_sp):
    with open(_sp) as fh:
        for r in _csv.DictReader(fh):
            x = float(r['x_um']) * 1000.0
            y = float(r['depth_um']) * 1000.0
            z = float(r['z_um']) * 1000.0
            _soma_w.append((Vector((x/1000.0, -z/1000.0, y/1000.0)), float(r['depth_um'])))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=4.2, segments=20, ring_count=12)
    _dot = bpy.context.active_object
    _dot.name = 'SOMA_PROTO'
    bpy.ops.object.shade_smooth()
    _sm = bpy.data.materials.new('mat_soma')
    _sm.use_nodes = True
    _st = _sm.node_tree
    _st.nodes.clear()
    _so = _st.nodes.new('ShaderNodeOutputMaterial')
    _se = _st.nodes.new('ShaderNodeEmission')
    _se.inputs['Color'].default_value = (1.0, 0.97, 0.90, 1.0)
    _se.inputs['Strength'].default_value = 3.4
    _st.links.new(_se.outputs['Emission'], _so.inputs['Surface'])
    _dot.data.materials.append(_sm)
    _me = bpy.data.meshes.new('SOMA_CLOUD')
    _me.from_pydata([tuple(v) for v, d in _soma_w], [], [])
    _me.update()
    _cl = bpy.data.objects.new('SOMAS', _me)
    scene.collection.objects.link(_cl)
    _cl.instance_type = 'VERTS'
    _dot.parent = _cl
    objs.append(_cl)
    _d = [d for v, d in _soma_w]
    print('[mic] %d real somata, depth %.0f to %.0f um, median %.0f' %
          (len(_d), min(_d), max(_d), sorted(_d)[len(_d)//2]), flush=True)
else:
    print('[mic] no soma csv, skipping markers', flush=True)

# ---- orient: pia at the top ------------------------------------------------------------
lo, hi = world_bounds(objs)
lo, hi = np.asarray(lo), np.asarray(hi)
centre = Vector(((lo + hi) / 2.0).tolist())
root = bpy.data.objects.new("MIC_ROOT", None)
scene.collection.objects.link(root)
for o in objs:
    o.parent = root
    o.matrix_parent_inverse.identity()
for _o in objs:
    _o.scale = (0.001,) * 3          # nanometre vertices into micrometres
root.location = tuple(-centre * 0.001)
# data y arrives as world z, so deep cells sit HIGH. Turn the whole thing over.
root.rotation_euler = (np.pi, 0.0, 0.0)
bpy.context.view_layer.update()

bpy.context.view_layer.update()
lo, hi = world_bounds(objs)
span = float(max(np.asarray(hi) - np.asarray(lo)))
print(f"[mic] span {span:,.0f} um, one unit is one micrometre, pia up", flush=True)

# ---- camera ------------------------------------------------------------------------------
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
dist = radius * float(opts.get("camdist", 1.35)) / np.tan(np.radians(22.0))
view = opts.get("view", "side")
off = Vector((0.0, -dist, 0.0)) if view == "side" else \
      Vector((-dist * 0.55, -dist * 0.78, 0.0))
cam.location = centre + off
cam.data.shift_y = float(opts.get("shifty", 0.0))
cam_data.clip_start = max(dist * 0.002, 0.01)
cam_data.clip_end = dist * 12.0
cam.rotation_euler = (centre - cam.location).normalized().to_track_quat(
    "-Z", "Y").to_euler()
print(f"[mic] camera {view}, radius {radius:.2f}, dist {dist:.2f}", flush=True)

build_world(scene)
build_lights(scene, span)
apply_render_settings(scene)

out = opts.get("out", r"D:\Meshes\renders\microns_column.png")
scene.render.filepath = out
FRAMES = int(opts.get("frames", 0))
if FRAMES <= 1:
    scene.render.image_settings.file_format = "PNG"
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[mic] still -> {out} in {time.time()-t0:.0f}s", flush=True)
else:
    AZ0 = np.radians(float(opts.get("az0", -38)))
    AZ1 = np.radians(float(opts.get("az1", 34)))
    EL0 = np.radians(float(opts.get("el0", 4)))
    # Amy: at the end it is too low, she would want to be looking higher up. So the
    # camera finishes tilted UP rather than down, and the aim below stops descending
    # short of the basal layer.
    EL1 = np.radians(float(opts.get("el1", 9)))
    R0 = radius * float(opts.get("camdist", 1.32))
    R1 = radius * float(opts.get("camnear", 0.86))
    # The aim descends, but only far enough to carry the eye down the layers.
    # At a 0.20 span drop the last frame held nothing but basal dendrites.
    top = Vector((centre.x, centre.y, centre.z + span * 0.14))
    bot = Vector((centre.x, centre.y, centre.z + span * 0.02))

    def smooth(u):
        return u * u * (3.0 - 2.0 * u)

    for f in range(1, FRAMES + 1):
        u = smooth((f - 1) / max(1, FRAMES - 1))
        az = AZ0 + (AZ1 - AZ0) * u
        el = EL0 + (EL1 - EL0) * u
        r = float(np.exp(np.log(R0) + (np.log(R1) - np.log(R0)) * u))
        aim = top.lerp(bot, u)
        dist = r / np.tan(np.radians(22.0))
        off = Vector((dist * np.cos(el) * np.sin(az),
                      -dist * np.cos(el) * np.cos(az),
                      dist * np.sin(el)))
        cam.location = aim + off
        cam.rotation_euler = (aim - cam.location).normalized().to_track_quat(
            "-Z", "Y").to_euler()
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        cam_data.clip_start = max(dist * 0.002, 0.01)
        cam_data.clip_end = dist * 12.0
        cam_data.keyframe_insert("clip_start", frame=f)
        cam_data.keyframe_insert("clip_end", frame=f)
    for act in (cam.animation_data.action, cam_data.animation_data.action):
        for fc in act.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    scene.frame_start, scene.frame_end = 1, FRAMES
    scene.render.fps = g["FPS"]
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    print(f"[mic] orbit {np.degrees(AZ0):.0f} to {np.degrees(AZ1):.0f} deg, "
          f"radius {R0:.0f} to {R1:.0f} um, {FRAMES} frames", flush=True)
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    _el = time.time() - t0
    print(f"[mic] {FRAMES} frames in {_el/60:.1f} min "
          f"({_el/FRAMES:.1f}s per frame) -> {out}", flush=True)
print("[mic] DONE", flush=True)
