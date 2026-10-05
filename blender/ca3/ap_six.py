"""Six mossy fibres, two attempts, and only the second one fires the cell.

The single-fibre cut shows a spike arriving and the cell firing. The literature
says that is the less likely outcome by roughly eight to one: a lone mossy fibre
spike discharges its target about 12 percent of the time, while a short burst, or
convergent input, reliably does. So this runs the honest version.

  attempt 1  one fibre fires. The thorn depolarises. It fades. Nothing happens.
  attempt 2  the other five fade in, all six fire, and the cell answers.

  blender --background --python ap_six.py -- [key=val]
    still=N  frames=432  res=1920x1080  samples=64  out=path
"""
import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)

HERO_ID = "648518346438632877"
LEAD = "648518346448994107"          # the fibre that goes first, 53 contacts
HERO_DIR = Path(r"D:\Meshes\hero")
F6 = np.load(r"D:\Meshes\skeletons\ap_fields6.npz")
FIBRES = [str(s) for s in F6["fibre_ids"]]
FRAC = {str(s): float(f) for s, f in zip(F6["fibre_ids"], F6["fibre_syn_frac"])}

FRAMES = int(opts.get("frames", 432))
RES = tuple(int(x) for x in opts.get("res", "1920x1080").split("x"))
TARGET_SIZE = 10.0

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__
g["RESOLUTION"] = RES
g["SAMPLES"] = int(opts.get("samples", 64))
g["FRAME_END"] = FRAMES
g["TARGET_SIZE"] = TARGET_SIZE
hexcol = g["hexcol"]

scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, FRAMES
scene.render.fps = g["FPS"]
scene.render.resolution_x, scene.render.resolution_y = RES

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
root = bpy.data.objects.new("CA3_ROOT", None)
bpy.context.collection.objects.link(root)

# ---- meshes -------------------------------------------------------------------------
t0 = time.time()
objs = {}
for key, seg, fn in ([("cell", HERO_ID, f"hero_{HERO_ID}.obj")] +
                     [(s, s, f"fibre_{s}.obj") for s in FIBRES]):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(HERO_DIR / fn))
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    assert new, f"nothing imported from {fn}"
    o = new[0]
    o.name = f"AP_{key}"
    o.parent = root
    objs[key] = o
print(f"[six] imported {len(objs)} meshes in {time.time()-t0:.0f}s", flush=True)


def local_coords(obj):
    n = len(obj.data.vertices)
    a = np.empty(n * 3, dtype=np.float64)
    obj.data.vertices.foreach_get("co", a)
    return a.reshape(n, 3)


def to_blender(pts):
    """Only for putting things in the scene. The importer leaves vertices in file
    space and carries the flip on the object's rotation, so mesh-space work needs
    no conversion at all."""
    pts = np.atleast_2d(pts)
    return np.column_stack([pts[:, 0], -pts[:, 2], pts[:, 1]])


def nearest_value(verts, nodes, values, chunk=20000, lit_only_within=None):
    """Value of the closest skeleton node, per mesh vertex.

    lit_only_within changes what "closest" means, and it matters. The cell's dark
    nodes sit spatially interleaved with the lit corridor, all over the branches
    and spines, so a plain nearest-node lookup along the dendrite alternates
    between lit and dark and the wavefront breaks into blobs. Searching only the
    lit nodes, and parking anything further away than the given distance, gives a
    continuous corridor instead. The distance is in nanometres.
    """
    if lit_only_within is not None:
        keep = values < values.max() * 0.5      # everything except the parked value
        sub_nodes, sub_vals = nodes[keep], values[keep]
    else:
        sub_nodes, sub_vals = nodes, values

    nn = (sub_nodes ** 2).sum(1)
    out = np.empty(len(verts), dtype=np.float64)
    for i in range(0, len(verts), chunk):
        blk = verts[i:i + chunk]
        d2 = nn[None, :] - 2.0 * (blk @ sub_nodes.T)
        j = d2.argmin(1)
        out[i:i + chunk] = sub_vals[j]
        if lit_only_within is not None:
            # d2 is missing the |blk|^2 term, constant per row, so add it back
            # only here where an absolute distance is actually needed
            true2 = d2[np.arange(len(blk)), j] + (blk ** 2).sum(1)
            out[i:i + chunk][true2 > lit_only_within ** 2] = values.max()
    return out


# ---- paint ---------------------------------------------------------------------------
spans = {}
for key, obj in objs.items():
    tag = f"cell_{HERO_ID}" if key == "cell" else f"fibre_{key}"
    nodes, values = F6[f"{tag}_verts"], F6[f"{tag}_dist"]
    span = float(F6[f"{tag}_span"])
    spans[key] = span
    verts = local_coords(obj)
    # the cell needs the continuous-corridor lookup; the fibres are a single
    # unbroken cable with nothing parked, so a plain nearest node is correct
    corridor = float(opts.get("corridor", 5500.0)) if key == "cell" else None
    tagv = "v2corr" if corridor else "v2"
    cache = Path(rf"D:\Meshes\skeletons\_paint6_{key}_{len(verts)}_{tagv}.npy")
    if cache.exists():
        norm = np.load(cache)
    else:
        t0 = time.time()
        # never clip to 1: dark nodes are parked past the end and must stay there
        d = nearest_value(verts, nodes, values, lit_only_within=corridor)
        norm = np.minimum(d / span, 4.0)
        np.save(cache, norm)
        print(f"[six] {key}: mapped {len(verts):,} verts in {time.time()-t0:.0f}s",
              flush=True)
    me = obj.data
    attr = me.color_attributes.new(name="apdist", type="FLOAT_COLOR", domain="POINT")
    flat = np.empty(len(verts) * 4, dtype=np.float32)
    flat[0::4] = flat[1::4] = flat[2::4] = norm
    flat[3::4] = 1.0
    attr.data.foreach_set("color", flat)


def pulse_material(name, base_hex, glow_hex, width, peak):
    """Returns the material plus the two sockets worth animating: where the
    wavefront is, and how hard it burns. The second one is what lets a pulse die
    out partway instead of always running to the end."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = hexcol(base_hex) + (1.0,)
    bsdf.inputs["Roughness"].default_value = 0.62
    bsdf.inputs["IOR"].default_value = 1.04          # submerged, never glossy
    bsdf.inputs["Emission Color"].default_value = hexcol(glow_hex) + (1.0,)
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "apdist"
    sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"
    absn = nt.nodes.new("ShaderNodeMath"); absn.operation = "ABSOLUTE"
    div = nt.nodes.new("ShaderNodeMath"); div.operation = "DIVIDE"
    div.inputs[1].default_value = width
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0; inv.use_clamp = True
    shp = nt.nodes.new("ShaderNodeMath"); shp.operation = "POWER"
    shp.inputs[1].default_value = 2.0
    amp = nt.nodes.new("ShaderNodeMath"); amp.operation = "MULTIPLY"
    amp.inputs[1].default_value = peak
    for a, b in ((attr.outputs["Color"], sub.inputs[0]), (sub.outputs[0], absn.inputs[0]),
                 (absn.outputs[0], div.inputs[0]), (div.outputs[0], inv.inputs[1]),
                 (inv.outputs[0], shp.inputs[0]), (shp.outputs[0], amp.inputs[0]),
                 (amp.outputs[0], bsdf.inputs["Emission Strength"]),
                 (bsdf.outputs["BSDF"], out.inputs["Surface"])):
        nt.links.new(a, b)
    return mat, sub.inputs[1], amp.inputs[1]


mats = {}
for key, obj in objs.items():
    if key == "cell":
        m, head, amp = pulse_material("AP_cell", "#2E8BE0", "#CFE8FF",
                                      float(opts.get("cwidth", 0.095)),
                                      float(opts.get("cpeak", 40.0)))
    else:
        m, head, amp = pulse_material(f"AP_f_{key}", "#E8A93A", "#FFF0C0",
                                      float(opts.get("fwidth", 0.055)),
                                      float(opts.get("fpeak", 26.0)))
    obj.data.materials.clear()
    obj.data.materials.append(m)
    mats[key] = (m, head, amp)

# ---- the two attempts -----------------------------------------------------------------
F = FRAMES / 432.0


def b(x):
    return max(1, int(x * F))


A1_GO, A1_HIT = b(20), b(104)          # one fibre travels and lands
A1_FADE = b(168)                       # its depolarisation dies away
JOIN = (b(176), b(232))                # the other five appear
A2_GO, A2_HIT = b(244), b(320)         # all six travel and land together
A2_END = b(414)                        # the cell answers
print(f"[six] attempt 1 {A1_GO}->{A1_HIT}, fades by {A1_FADE}; others join {JOIN}; "
      f"attempt 2 {A2_GO}->{A2_HIT}, cell fires to {A2_END}", flush=True)


def key(sock, frames_vals, interp="LINEAR"):
    for fr, v in frames_vals:
        sock.default_value = v
        sock.keyframe_insert("default_value", frame=max(1, int(fr)))


LO = -0.15
for seg in FIBRES:
    _, head, amp = mats[seg]
    f = FRAC[seg]
    over = LO + (f - LO) * (1.0 + 0.45)     # keep running a little past the boutons
    FP = float(opts.get("fpeak", 26.0))
    if seg == LEAD:
        key(head, [(1, LO), (A1_GO, LO), (A1_HIT, f), (A1_FADE, over),
                   (A2_GO, LO), (A2_HIT, f), (A2_END, over)])
        # Between the two attempts the wavefront has to rewind to the start, and
        # if it is still lit while it does that, a second pulse visibly runs
        # BACKWARDS up the fibre. Amy caught exactly that around 8 to 9 seconds.
        # Kill the emission across the rewind and bring it back for attempt two.
        key(amp, [(1, FP), (A1_FADE, FP), (A1_FADE + b(6), 0.0),
                  (A2_GO - b(6), 0.0), (A2_GO, FP), (FRAMES, FP)])
    else:
        # the other five sit dark until they join, then run once
        key(head, [(1, LO), (A2_GO, LO), (A2_HIT, f), (A2_END, over)])
        key(amp, [(1, FP)])

# The five that join arrive one after another rather than all at once.
#
# NOT by scaling from zero. These objects sit at raw file coordinates with the
# centring carried on their location, so scaling toward the object origin drags
# them in from somewhere else entirely, which is the flying-in-from-the-corner
# look Amy has already rejected once. Visibility is keyed instead, staggered so
# five separate arrivals read as fibres converging, and each one gets a brief
# flare along its length as it appears so the cut reads as deliberate.
others = [s for s in FIBRES if s != LEAD]
step = max(1, (JOIN[1] - JOIN[0]) // max(1, len(others)))
for i, seg in enumerate(others):
    o = objs[seg]
    on = JOIN[0] + i * step
    for fr, hidden in ((1, True), (max(1, on - 1), True), (on, False), (FRAMES, False)):
        o.hide_render = o.hide_viewport = hidden
        o.keyframe_insert("hide_render", frame=max(1, int(fr)))
        o.keyframe_insert("hide_viewport", frame=max(1, int(fr)))
    print(f"[six] fibre {seg} appears at frame {on}", flush=True)

# The cell: a first depolarisation that gets partway and dies, then the real one.
_, head_c, amp_c = mats["cell"]
SUB = float(opts.get("sub", 0.13))       # how far the failed attempt spreads
key(head_c, [(1, LO), (A1_HIT, LO), (A1_FADE, SUB),
             (A2_HIT, LO), (A2_END, 1.0)])
CP = float(opts.get("cpeak", 40.0))
key(amp_c, [(1, 0.0), (A1_HIT, 0.0), (A1_HIT + b(10), CP * 0.55),
            (A1_FADE, 0.0), (A2_HIT, 0.0), (A2_HIT + b(8), CP), (A2_END, CP),
            (FRAMES, CP)])

for mat, _, _ in mats.values():
    if mat.node_tree.animation_data:
        for fc in mat.node_tree.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# ---- world, placement, lights, camera ---------------------------------------------------
g["build_world"](scene)
allv = np.vstack([local_coords(o) for o in objs.values()])
lo_b, hi_b = np.percentile(allv, 0.5, axis=0), np.percentile(allv, 99.5, axis=0)
centre = (lo_b + hi_b) / 2.0
span_all = float(np.max(hi_b - lo_b))
factor = TARGET_SIZE / span_all
root.scale = (factor,) * 3
centre_scene = Vector(to_blender(centre)[0])
for o in objs.values():
    o.location = tuple(-centre_scene)
bpy.context.view_layer.update()
print(f"[six] span {span_all:,.0f} nm -> scale {factor:.3e}", flush=True)


def scene_pos(nm):
    return (Vector(to_blender(nm)[0]) - centre_scene) * factor


all_syn = np.vstack([F6[f"fibre_{s}_syn"] for s in FIBRES])
contacts = scene_pos(all_syn.mean(axis=0))
assert max(abs(v) for v in contacts) < TARGET_SIZE, "contacts landed outside the scene"

# flash core, sized to the thorn, plus a light pushed clear of the geometry it lights
core_r = TARGET_SIZE * 0.011
bpy.ops.mesh.primitive_uv_sphere_add(radius=core_r, segments=24, ring_count=16,
                                     location=contacts)
core = bpy.context.active_object
core.name = "AP_CORE"
cmat = bpy.data.materials.new("AP_CORE"); cmat.use_nodes = True
cnt = cmat.node_tree; cnt.nodes.clear()
cout = cnt.nodes.new("ShaderNodeOutputMaterial")
cem = cnt.nodes.new("ShaderNodeEmission")
cem.inputs["Color"].default_value = (1.0, 0.93, 0.72, 1.0)
cnt.links.new(cem.outputs["Emission"], cout.inputs["Surface"])
core.data.materials.append(cmat)

flare_data = bpy.data.lights.new("AP_FLARE", type="POINT")
flare_data.color = (1.0, 0.86, 0.55)
flare_data.shadow_soft_size = TARGET_SIZE * 0.030
flare = bpy.data.objects.new("AP_FLARE", flare_data)
bpy.context.collection.objects.link(flare)
flare.location = contacts + Vector((0.62, -0.78, 0.30)).normalized() * (TARGET_SIZE * 0.055)

PEAK = float(opts.get("flash", 900.0))
# the second arrival is six fibres at once, so it burns harder than the first
CURVE = ((1, 0.0), (A1_HIT - b(4), 0.0), (A1_HIT + b(2), 0.42),
         (A1_HIT + b(14), 0.10), (A1_FADE, 0.0),
         (A2_HIT - b(4), 0.0), (A2_HIT + b(2), 1.0), (A2_HIT + b(10), 0.34),
         (A2_HIT + b(30), 0.08), (A2_END, 0.0), (FRAMES, 0.0))
for fr, k in CURVE:
    fr = max(1, int(fr))
    flare_data.energy = PEAK * k
    flare_data.keyframe_insert("energy", frame=fr)
    cem.inputs["Strength"].default_value = 45.0 * k
    cem.inputs["Strength"].keyframe_insert("default_value", frame=fr)
    core.scale = (1.0,) * 3 if k > 0 else (0.001,) * 3
    core.keyframe_insert("scale", frame=fr)

target = bpy.data.objects.new("AP_TARGET", None)
bpy.context.collection.objects.link(target)
c_nodes, c_dist = F6[f"cell_{HERO_ID}_verts"], F6[f"cell_{HERO_ID}_dist"]
span_c = float(F6[f"cell_{HERO_ID}_span"])
ax = np.isfinite(c_dist) & (c_dist > float(F6["soma_dist"])) & (c_dist < span_c * 2)
ax_mid = scene_pos(np.asarray(c_nodes)[ax].mean(axis=0))
for fr, p in ((1, contacts), (A2_HIT, contacts),
              (int((A2_HIT + A2_END) / 2), (contacts + ax_mid) * 0.5),
              (A2_END, ax_mid), (FRAMES, ax_mid)):
    target.location = p
    target.keyframe_insert("location", frame=max(1, int(fr)))
for fc in target.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "BEZIER"
        kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"

g["build_lights"](scene, TARGET_SIZE, target=target)

cam_data = bpy.data.cameras.new("AP_CAM")
cam = bpy.data.objects.new("AP_CAM", cam_data)
bpy.context.collection.objects.link(cam)
scene.camera = cam
DIST = TARGET_SIZE * float(opts.get("camdist", 1.05))
trk = cam.constraints.new("TRACK_TO")
trk.target = target
trk.track_axis, trk.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
cam_data.clip_start, cam_data.clip_end = 0.01, DIST * 60
ARC = math.radians(float(opts.get("arc", 20.0)))
A0 = math.atan2(-0.78, 0.62)
WIDE = float(opts.get("wide", 2.5))


def cam_at(th, rad):
    r = rad * math.hypot(0.62, 0.78)
    return (r * math.cos(th), r * math.sin(th), rad * 0.30)


# One move, not four. The old path pushed in at 4 s, backed off at 7 s, pulled
# wide at 9.7 s and came back in at 13 s, which reads as pumping. It now stays
# close through the whole mossy fibre section, holding on the fibres as they
# converge, and opens out once only, when the six signals reach the cell.
for fr, th, rad in ((1, A0, DIST * 1.02),
                    (A1_HIT, A0 + ARC * 0.14, DIST * 0.90),
                    (A2_HIT, A0 + ARC * 0.52, DIST * 0.95),
                    (A2_END, A0 + ARC * 0.90, DIST * WIDE),
                    (FRAMES, A0 + ARC, DIST * (WIDE + 0.12))):
    cam.location = cam_at(th, rad)
    cam.keyframe_insert("location", frame=max(1, int(fr)))
for fc in cam.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "BEZIER"
        kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"

if opts.get("dof", "1") not in ("0", "false", "no"):
    cam_data.dof.use_dof = True
    cam_data.dof.focus_object = target
    cam_data.dof.aperture_fstop = float(opts.get("fstop", 2.4))
    cam_data.dof.aperture_blades = 6

g["apply_render_settings"](scene)

out = opts.get("out", r"D:\Meshes\renders\ap_six.mp4")
still = opts.get("still")
scene.render.filepath = out
if still:
    scene.render.image_settings.file_format = "PNG"
    scene.frame_set(int(still))
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[six] still {still} in {time.time()-t0:.0f}s -> {out}", flush=True)
else:
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    el = time.time() - t0
    print(f"[six] {FRAMES} frames in {el/60:.1f} min ({el/FRAMES:.1f}s/frame)", flush=True)
print("[six] DONE", flush=True)
