"""Retina: where each cell puts its dendrites, and why that is the answer.

  blender --background --python retina_strat_anim.py -- mode=strat|sac [frames=240] [stills=1,120]

TWO SHOTS, ONE IDEA. The direction-selectivity film says WHICH cells respond. This
says WHERE they meet. The inner plexiform layer is about forty micrometres thick
and every cell in it commits to a narrow depth band. Depth is not decoration in
the retina: it is close to the whole wiring rule, because two cells can only form
a synapse where they are both present.

  mode=strat  all 202 calcium-imaged cells, turning from face on to edge on
  mode=sac    the 24 starburst amacrine cells alone, the same move

Colour is POSITION, not identity: every vertex is tinted by its own depth through
the layer, on the CA3 convergence ramp (blue, violet, gold). Nothing draws the
bands in. If bands appear it is because that is where the dendrites are, and if
they do not appear then these cells do not stratify and the picture should say so.

WHICH AXIS IS DEPTH is measured, never assumed. The sheet is imported, its
bounding box is taken, and the SHORTEST axis is depth by construction. On this
data that comes out as Blender Y (extent about 0.7 against 9.4 and 10.0), which is
file z negated by the OBJ importer's Y-up to Z-up conversion.

The camera does not move. The subject turns, on a pivot at the world origin. The
root empty carries a scale and an offset that put the geometry at the origin, so
rotating IT would swing the mosaic out of frame; the pivot is a second empty above
it that sits at the origin and owns the rotation alone.
"""
import math
import os
import sys
import time

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)

ROOT = r"D:\Meshes\retina"
MESH = os.path.join(ROOT, "meshes")
MODE = opts.get("mode", "strat")
FRAMES = int(opts.get("frames", 240))
BUILD = opts.get("build", "0") not in ("0", "false", "no")
# The opening hold has to be long enough to lay every arbor in one at a time when
# building, and only long enough to read the finished mosaic when not. Timing is
# declared here rather than beside the camera move because the build keyframes are
# written earlier, while the materials are being made.
HOLD = int(FRAMES * (0.52 if BUILD else 0.17))
TURN = FRAMES - HOLD - int(FRAMES * 0.17)
TARGET = 10.0
LENS = 50.0
SENSOR = 36.0

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__
g["RESOLUTION"] = tuple(int(x) for x in opts.get("res", "1920x1080").split("x"))
g["SAMPLES"] = int(opts.get("samples", 64))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, FRAMES
scene.render.fps = g["FPS"]

# ---- which cells -------------------------------------------------------------
import csv
cells = []
with open(os.path.join(ROOT, "functional_cells.csv"), encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        if row["has_mesh"] not in ("True", "true", "1"):
            continue
        if MODE == "sac" and row["cell_type"] != "SAC":
            continue
        cells.append({"id": int(row["root_id"]), "type": row["cell_type"],
                      "cls": row["cls"]})
print(f"[S] mode={MODE}  {len(cells)} cells", flush=True)

# ---- import ------------------------------------------------------------------
t0 = time.time()
allo = []
for n, c in enumerate(cells, 1):
    p = os.path.join(MESH, f"{c['id']}.obj")
    if not os.path.exists(p):
        continue
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=p)
    for o in bpy.data.objects:
        if o not in before and o.type == "MESH":
            o.name = f"c{c['id']}"
            allo.append(o)
    if n % 40 == 0 or n == len(cells):
        print(f"[S] imported {n}/{len(cells)}  {time.time()-t0:.0f}s", flush=True)
bpy.context.view_layer.update()
faces = sum(len(o.data.polygons) for o in allo)
print(f"[S] {len(allo)} objects, {faces/1e6:.1f}M faces, {time.time()-t0:.0f}s", flush=True)

mins, maxs = Vector((1e18,) * 3), Vector((-1e18,) * 3)
for o in allo:
    for cn in o.bound_box:
        w = o.matrix_world @ Vector(cn)
        for i in range(3):
            mins[i], maxs[i] = min(mins[i], w[i]), max(maxs[i], w[i])
centre = (mins + maxs) / 2
span = maxs - mins
s = TARGET / max(span[i] for i in range(3))

# DEPTH IS MEASURED. The thinnest axis of the imported sheet is the depth axis.
DEPTH = min(range(3), key=lambda i: span[i])
print(f"[S] extent {span.x:.0f} x {span.y:.0f} x {span.z:.0f} (file units); "
      f"depth axis = {'XYZ'[DEPTH]}", flush=True)

# PIVOT owns the rotation and sits at the world origin. ROOT owns the scale and
# the recentring offset. Merging them would rotate about the offset instead.
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
pivot = bpy.context.active_object
pivot.name = "PIVOT"
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
root = bpy.context.active_object
root.name = "RETINA_ROOT"
root.parent = pivot
for o in allo:
    o.parent = root
    o.matrix_parent_inverse = root.matrix_world.inverted()
root.scale = (s, s, s)
bpy.context.view_layer.update()
root.location = -(root.matrix_world.to_3x3() @ centre)
bpy.context.view_layer.update()
ext = span * s
print(f"[S] scaled extent {ext.x:.1f} x {ext.y:.1f} x {ext.z:.1f}", flush=True)

# ---- colour ------------------------------------------------------------------
# Two schemes, because the two shots are asking different questions.
#
#   colour=depth  every vertex tinted by its own depth. Right for the whole
#                 population, where the depth range is genuinely occupied.
#   colour=cell   one flat colour per cell. Right for the starburst mosaic, where
#                 depth colouring is self defeating: those cells all sit at the
#                 SAME depth, so a depth ramp paints them one uniform blue and the
#                 tiling, which is the thing worth seeing, disappears into a mat.
#
# The CA3 ramp is used LINEARLY for depth and CYCLICALLY for cell identity. Depth
# is not an angle so its map must not wrap; cell index has no meaning at all, so a
# wrapping map is the honest choice there, since it cannot imply an ordering.
SCHEME = opts.get("colour", "cell" if MODE == "sac" else "depth")
STOPS = [(0.00, "#2E8BE0"), (0.50, "#8B5CE0"), (1.00, "#E8A93A")]
# DISCRETE, never interpolated. Blending the four house colours around a circle
# passes through salmon on the way from violet to gold and through chartreuse on
# the way from gold to green, and twenty four arbors painted that way read as the
# rainbow the palette was chosen to replace. These eight are the four CA3 anchors
# and one lighter tint of each, so every cell lands inside the house family.
WHEEL = ["#2E8BE0", "#8B5CE0", "#E8A93A", "#17A06B",
         "#7FC4F5", "#B79BEE", "#F2CE86", "#5FCFA4"]
GLOW = float(opts.get("glow", 1.15))


def _hex(h):
    h = h.lstrip("#")
    return tuple((int(h[i:i + 2], 16) / 255.0) ** 2.2 for i in (0, 2, 4)) + (1.0,)


def emissive(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    for nd in list(t.nodes):
        t.nodes.remove(nd)
    o = t.nodes.new("ShaderNodeOutputMaterial")
    e = t.nodes.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = GLOW
    t.links.new(e.outputs["Emission"], o.inputs["Surface"])
    return m, t, e


if SCHEME == "depth":
    mat, nt, em = emissive("m_depth")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    rng = nt.nodes.new("ShaderNodeMapRange")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    tex = nt.nodes.new("ShaderNodeTexCoord")
    # Object coordinates are per object, so two hundred meshes would each get
    # their own origin and the ramp would mean nothing across cells. Pointing the
    # node at the ROOT empty puts every cell in ONE shared space, which is what
    # makes a depth comparison between two different cells legitimate.
    tex.object = root
    nt.links.new(tex.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["XYZ"[DEPTH]], rng.inputs["Value"])
    # Object space here is the file's own units, centred by ROOT, so the layer
    # runs from -span/2 to +span/2 along the depth axis.
    rng.inputs["From Min"].default_value = -span[DEPTH] / 2.0
    rng.inputs["From Max"].default_value = span[DEPTH] / 2.0
    nt.links.new(rng.outputs["Result"], ramp.inputs["Fac"])
    while len(ramp.color_ramp.elements) > 1:
        ramp.color_ramp.elements.remove(ramp.color_ramp.elements[-1])
    ramp.color_ramp.elements[0].position = STOPS[0][0]
    ramp.color_ramp.elements[0].color = _hex(STOPS[0][1])
    for pos, hx in STOPS[1:]:
        e = ramp.color_ramp.elements.new(pos)
        e.color = _hex(hx)
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    for o in allo:
        o.data.materials.clear()
        o.data.materials.append(mat)
else:
    # Neighbouring cells must not land on the same colour, and cell order in the
    # table is arbitrary, so the palette is stepped by a stride coprime with its
    # length rather than walked in sequence. Eight colours and a stride of 3 means
    # a colour repeats only every eighth cell.
    ids = [c["id"] for c in cells]
    cell_mat = {}
    for k, cid in enumerate(ids):
        m, mt, e = emissive(f"m{cid}")
        e.inputs["Color"].default_value = _hex(WHEEL[(k * 3) % len(WHEEL)])
        cell_mat[cid] = (m, mt, e)
        for o in allo:
            if o.name == f"c{cid}":
                o.data.materials.clear()
                o.data.materials.append(m)
print(f"[S] colour scheme = {SCHEME}", flush=True)

# ---- the build, if asked for --------------------------------------------------
# A mosaic is a claim about COVERAGE: these cells are not scattered, they divide
# the sheet between them with very little overlap and very few gaps. One frame of
# the finished tiling cannot make that claim, because a dense tangle looks the
# same whether it is a tiling or a pile. Laying the arbors in one at a time does
# make it, since you watch each new cell drop into the space the others left.
#
# Order is by position across the sheet, not by table order, so the mosaic fills
# like a wave instead of flickering on at random.
if BUILD and SCHEME != "depth":
    lat_axes = [i for i in range(3) if i != DEPTH]
    pos = {}
    for cid in cell_mat:
        pts = [o.matrix_world @ Vector(cn) for o in allo if o.name == f"c{cid}"
               for cn in o.bound_box]
        if pts:
            pos[cid] = sum(p[lat_axes[0]] for p in pts) / len(pts)
    order = sorted(cell_mat, key=lambda c: pos.get(c, 0.0))
    # Every cell must be fully lit by the time the turn starts, so the build owns
    # the opening hold only. A cell still fading up while the sheet rotates would
    # read as a response to the rotation.
    last_on = max(1, int(HOLD * 0.94))
    step = last_on / max(1, len(order))
    for k, cid in enumerate(order):
        _, mt, _ = cell_mat[cid]
        dp = 'nodes["Emission"].inputs[1].default_value'
        for fr, v in ((1, 0.0), (1 + k * step, 0.0),
                      (1 + k * step + step * 2.6, GLOW * 1.9),
                      (1 + k * step + step * 5.5, GLOW)):
            mt.nodes["Emission"].inputs["Strength"].default_value = v
            mt.keyframe_insert(data_path=dp, frame=int(min(fr, last_on + step * 6)))
        for fc in mt.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "SINE"
                kp.easing = "EASE_IN_OUT"
    print(f"[S] build: {len(order)} cells laid in over {last_on} frames", flush=True)

# ---- the move: face on, turn, edge on ----------------------------------------
# Rotating about world X carries the depth axis from "into the screen" to "up the
# screen", so the layer that was a flat mosaic becomes a cross section. Held at
# both ends, because the two stills ARE the two facts and a shot that never stops
# lets a viewer see neither.
for fr, ang in ((1, 0.0), (HOLD, 0.0), (HOLD + TURN, math.pi / 2), (FRAMES, math.pi / 2)):
    pivot.rotation_euler = (ang, 0, 0)
    pivot.keyframe_insert(data_path="rotation_euler", frame=int(fr))
g["set_interp"](pivot, "BEZIER", "EASE_IN_OUT")

# ---- camera ------------------------------------------------------------------
fov_w = 2 * math.atan(SENSOR / (2 * LENS))
RW, RH = g["RESOLUTION"]
fov_h = 2 * math.atan((SENSOR * RH / RW) / (2 * LENS))
# Framed for the FACE ON pose, which is the widest the subject ever gets: the
# edge on pose is the same width and much shorter, so a frame that holds the
# mosaic holds the cross section too.
half = [ext.x / 2, ext.y / 2, ext.z / 2]
lat = [half[i] for i in range(3) if i != DEPTH]
dist = 1.16 * max(lat[0] / math.tan(fov_w / 2), lat[1] / math.tan(fov_h / 2))
bpy.ops.object.camera_add(location=(0, dist, 0))
cam = bpy.context.active_object
cam.data.lens = LENS
cam.data.sensor_fit = "HORIZONTAL"      # AUTO transposes the FOV on a non 16:9 frame
cam.data.sensor_width = SENSOR
cam.rotation_euler = (math.pi / 2, 0, math.pi)
scene.camera = cam

# The push in. Edge on, the subject is the same width but a small fraction of the
# height, so a frame that fits the mosaic leaves the cross section as a thread in
# a black field. Coming closer as it turns keeps the band readable. This crops the
# lateral extent at the end, which is the correct thing to lose: by then the shot
# is about depth, and the width has already been established by the opening hold.
PUSH = float(opts.get("push", 0.62))
for fr, d in ((1, dist), (HOLD, dist), (HOLD + TURN, dist * PUSH), (FRAMES, dist * PUSH)):
    cam.location = (0, d, 0)
    cam.keyframe_insert(data_path="location", frame=int(fr))
g["set_interp"](cam, "BEZIER", "EASE_IN_OUT")
print(f"[S] camera {dist:.1f} -> {dist*PUSH:.1f} on +Y", flush=True)

g["build_world"](scene)
g["build_lights"](scene, TARGET, root)
g["apply_render_settings"](scene)
scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.10

# ---- render ------------------------------------------------------------------
out_path = opts.get("out", rf"D:\Meshes\renders\retina_{MODE}.mp4")
stills = opts.get("stills") or opts.get("still")
if stills:
    scene.render.image_settings.file_format = "PNG"
    base = out_path[:-4] if out_path.lower().endswith(".mp4") else out_path
    for fr in [int(x) for x in str(stills).split(",")]:
        scene.frame_set(fr)
        scene.render.filepath = f"{base}_{fr:04d}.png"
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[S] beat {fr} -> {scene.render.filepath} in {time.time()-t:.0f}s", flush=True)
else:
    seq = os.path.splitext(out_path)[0] + "_frames"
    os.makedirs(seq, exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    done = {int(f[1:6]) for f in os.listdir(seq)
            if f.startswith("f") and f.endswith(".png") and f[1:6].isdigit()}
    t0 = time.time()
    n_new = 0
    for fr in range(1, FRAMES + 1):
        if fr in done:
            continue
        scene.frame_set(fr)
        scene.render.filepath = os.path.join(seq, f"f{fr:05d}")
        bpy.ops.render.render(write_still=True)
        n_new += 1
        el = time.time() - t0
        print(f"Fra:{fr} of {FRAMES} | {el/60:.1f} min | {el/n_new:.1f}s/frame", flush=True)
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(g["FPS"]),
                    "-i", os.path.join(seq, "f%05d.png"), "-c:v", "libx264",
                    "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", out_path], check=False)
    if os.path.exists(out_path):
        print(f"[S] wrote {out_path} ({os.path.getsize(out_path)/1e6:.1f} MB)", flush=True)
print("[S] DONE", flush=True)
