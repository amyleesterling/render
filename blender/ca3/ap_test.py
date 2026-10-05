"""An action potential travelling real cable.

One mossy fibre and the pyramidal cell it contacts. The pulse is not a decorative
sweep across the screen: every mesh vertex carries its own path distance, measured
along the skeleton, so the wavefront follows the branching of the actual arbor.

  fibre : distance from the fibre's far end, so the spike runs toward the boutons
  cell  : distance outward from the 53 synapses themselves, so the depolarisation
          leaves the thorn and spreads through the dendrites to the soma

  blender --background --python ap_test.py -- [key=val]
    still=N  frames=192  res=1920x1080  samples=64  out=path
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
FIBRE_ID = "648518346448994107"
HERO_DIR = Path(r"D:\Meshes\hero")
FIELDS = np.load(r"D:\Meshes\skeletons\ap_fields.npz")

FRAMES = int(opts.get("frames", 192))
RES = tuple(int(x) for x in opts.get("res", "1920x1080").split("x"))
TARGET_SIZE = 10.0

# ---- helpers from the main animation module, so lighting and look match ------------
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

# ---- empty the default scene -------------------------------------------------------
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

root = bpy.data.objects.new("CA3_ROOT", None)
bpy.context.collection.objects.link(root)

# ---- import just these two meshes --------------------------------------------------
t0 = time.time()
objs = {}
for key, seg in (("cell", HERO_ID), ("fibre", FIBRE_ID)):
    path = HERO_DIR / (f"hero_{seg}.obj" if key == "cell" else f"fibre_{seg}.obj")
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    assert new, f"nothing imported from {path.name}"
    o = new[0]
    o.name = f"AP_{key}"
    o.parent = root
    objs[key] = o
    print(f"[ap] {key}: {len(o.data.vertices):,} verts from {path.name}", flush=True)
print(f"[ap] imported in {time.time()-t0:.0f}s", flush=True)


def local_coords(obj):
    """Vertex positions in the object's own space, which is OBJ space axis-converted."""
    n = len(obj.data.vertices)
    a = np.empty(n * 3, dtype=np.float64)
    obj.data.vertices.foreach_get("co", a)
    return a.reshape(n, 3)


def to_blender(pts):
    """Blender's OBJ importer maps file (x, y, z) onto (x, -z, y).

    It does NOT bake that into the vertices. It leaves them in file order and
    puts a 90 degree X rotation on the object, verified by reading back
    rotation_euler and comparing a mesh bounding box against its skeleton. So
    mesh-space work needs no conversion at all, and only positions that have to
    land in the rendered scene get turned through here.
    """
    pts = np.atleast_2d(pts)
    return np.column_stack([pts[:, 0], -pts[:, 2], pts[:, 1]])


def nearest_value(verts, nodes, values, chunk=20000):
    """Value of the closest skeleton node, per mesh vertex.

    Brute force in chunks rather than a KD tree, since Blender ships numpy but
    not scipy. Distances come from the expansion |a-b|^2 = |a|^2 - 2a.b + |b|^2
    rather than a 3D broadcast: the broadcast would allocate chunk x nodes x 3
    doubles, over a gigabyte a chunk, while this is a plain matmul that BLAS
    threads for us and holds only chunk x nodes.
    """
    nn = (nodes ** 2).sum(1)
    out = np.empty(len(verts), dtype=np.float64)
    for i in range(0, len(verts), chunk):
        blk = verts[i:i + chunk]
        d2 = nn[None, :] - 2.0 * (blk @ nodes.T)       # |a|^2 is constant per row
        out[i:i + chunk] = values[d2.argmin(1)]
    return out


# ---- paint each mesh with its own distance field ------------------------------------
spans = {}
for key, seg in (("cell", HERO_ID), ("fibre", FIBRE_ID)):
    obj = objs[key]
    # both sides stay in raw file space here, which is what the vertices are in
    nodes = FIELDS[f"{key}_{seg}_verts"]
    values = FIELDS[f"{key}_{seg}_dist"]
    verts = local_coords(obj)
    # Take the span the field was built with, never values.max(). Dark nodes are
    # parked at ten times the span, so max() normalises them to exactly 1.0 and
    # every one of them lights on the last frame of the sweep.
    span = float(FIELDS[f"{key}_{seg}_span"])
    spans[key] = span
    # equal when nothing is parked, as on the fibre, which has no dark nodes
    assert span <= values.max() + 1e-6, "stored span exceeds the field it came from"

    # 2.3M vertices against 3.2k nodes costs a minute and a half, and nothing
    # about it changes between renders, so keep it. The vertex count guards the
    # cache: if the mesh is ever reimported differently the mapping is redone.
    cache = Path(rf"D:\Meshes\skeletons\_paint_{seg}_{len(verts)}.npy")
    if cache.exists():
        norm = np.load(cache)
        print(f"[ap] {key}: reused cached mapping, 0 to {span:.1f} um", flush=True)
    else:
        t0 = time.time()
        d = nearest_value(verts, nodes, values)
        # Clamping to 1 would drag every deliberately dark node to the end of the
        # sweep and light it last. They are parked far past the end instead, so
        # the band never reaches them and the dendrites the signal does not enter
        # stay dark for the whole shot.
        norm = np.minimum(d / span, 4.0)
        np.save(cache, norm)
        print(f"[ap] {key}: mapped {len(verts):,} verts in {time.time()-t0:.0f}s, "
              f"0 to {span:.1f} um", flush=True)

    me = obj.data
    attr = me.color_attributes.new(name="apdist", type="FLOAT_COLOR", domain="POINT")
    flat = np.empty(len(verts) * 4, dtype=np.float32)
    flat[0::4] = norm
    flat[1::4] = norm
    flat[2::4] = norm
    flat[3::4] = 1.0
    attr.data.foreach_set("color", flat)


# ---- a material whose emission is a band sliding along that field -------------------
def pulse_material(name, base_hex, glow_hex, width, peak):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = hexcol(base_hex) + (1.0,)
    bsdf.inputs["Roughness"].default_value = 0.62
    # submerged tissue, not glass: index matched to water so it never reads wet
    bsdf.inputs["IOR"].default_value = 1.04
    bsdf.inputs["Emission Color"].default_value = hexcol(glow_hex) + (1.0,)

    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "apdist"

    # debug=lo-hi lights everything whose distance falls in that normalised band
    # and nothing else, which is how you check a classification instead of
    # squinting at a moving wavefront and hoping.
    if opts.get("debug"):
        d_lo, d_hi = (float(x) for x in opts["debug"].split("-"))
        gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"
        gt.inputs[1].default_value = d_lo
        lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"
        lt.inputs[1].default_value = d_hi
        mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
        amp2 = nt.nodes.new("ShaderNodeMath"); amp2.operation = "MULTIPLY"
        amp2.inputs[1].default_value = 12.0
        nt.links.new(attr.outputs["Color"], gt.inputs[0])
        nt.links.new(attr.outputs["Color"], lt.inputs[0])
        nt.links.new(gt.outputs[0], mul.inputs[0])
        nt.links.new(lt.outputs[0], mul.inputs[1])
        nt.links.new(mul.outputs[0], amp2.inputs[0])
        nt.links.new(amp2.outputs[0], bsdf.inputs["Emission Strength"])
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        # hand back a socket wired to nothing, so the sweep keyframes land
        # somewhere harmless. Returning the amplitude input meant the sweep drove
        # it to -0.15 on frame 1 and the debug render came out unlit.
        dummy = nt.nodes.new("ShaderNodeMath")
        return mat, dummy.inputs[0]

    # band = (1 - |d - t| / width) ** 2, clamped, so a soft crest rides the field
    sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"
    absn = nt.nodes.new("ShaderNodeMath"); absn.operation = "ABSOLUTE"
    div = nt.nodes.new("ShaderNodeMath"); div.operation = "DIVIDE"
    div.inputs[1].default_value = width
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    inv.use_clamp = True
    shp = nt.nodes.new("ShaderNodeMath"); shp.operation = "POWER"
    shp.inputs[1].default_value = 2.0
    amp = nt.nodes.new("ShaderNodeMath"); amp.operation = "MULTIPLY"
    amp.inputs[1].default_value = peak

    nt.links.new(attr.outputs["Color"], sub.inputs[0])
    nt.links.new(sub.outputs[0], absn.inputs[0])
    nt.links.new(absn.outputs[0], div.inputs[0])
    nt.links.new(div.outputs[0], inv.inputs[1])
    nt.links.new(inv.outputs[0], shp.inputs[0])
    nt.links.new(shp.outputs[0], amp.inputs[0])
    nt.links.new(amp.outputs[0], bsdf.inputs["Emission Strength"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat, sub.inputs[1]        # the socket that carries the wavefront


# palette matches the rest of the project: fibres gold, thorny pyramidal blue
# The cell's band is wider and much hotter than the fibre's. The axon is thin,
# and the camera pulls back from it, so at the end of the shot it is only a few
# pixels across. Bloom is the only thing keeping it legible out there.
mat_f, head_f = pulse_material("AP_fibre", "#E8A93A", "#FFF0C0",
                               float(opts.get("fwidth", 0.055)),
                               float(opts.get("fpeak", 26.0)))
mat_c, head_c = pulse_material("AP_cell", "#2E8BE0", "#CFE8FF",
                               float(opts.get("cwidth", 0.095)),
                               float(opts.get("cpeak", 40.0)))
objs["fibre"].data.materials.clear(); objs["fibre"].data.materials.append(mat_f)
objs["cell"].data.materials.clear(); objs["cell"].data.materials.append(mat_c)

# ---- timing -------------------------------------------------------------------------
# The spike runs the fibre, reaches the boutons, and only then does the cell
# light, because that is the order it happens in. Beats are fractions of the
# running time so the shot can be recut to any length without redoing them.
#
# The pause between arrival and spread is deliberate. It is the one moment the
# viewer needs to register, and it is also true: transmission takes time.
def beat(a, b):
    return int(a * FRAMES), int(b * FRAMES)


SPIKE = beat(0.10, 0.49)      # down the fibre to the boutons
CELL = beat(0.55, 0.95)       # in at the thorn, through the soma, out the axon

arc = FIELDS["arc_at_syn"]
syn_frac = float(np.median(arc) / spans["fibre"])
arrive = SPIKE[0] + (SPIKE[1] - SPIKE[0]) * syn_frac
soma_frac = float(FIELDS["soma_dist"]) / spans["cell"]
soma_lit = CELL[0] + (CELL[1] - CELL[0]) * soma_frac
print(f"[ap] spike {SPIKE}, boutons reached at frame {arrive:.0f}", flush=True)
print(f"[ap] cell {CELL}, soma lights at frame {soma_lit:.0f}", flush=True)


def sweep(socket, a, b, lo=-0.15, hi=1.15):
    """Drive the wavefront from before the near end to past the far end, so the
    band enters and leaves cleanly instead of popping on at full width."""
    socket.default_value = lo
    socket.keyframe_insert("default_value", frame=1)
    socket.keyframe_insert("default_value", frame=a)
    socket.default_value = hi
    socket.keyframe_insert("default_value", frame=b)
    socket.keyframe_insert("default_value", frame=FRAMES)


sweep(head_f, *SPIKE)
# the cell's sweep stops right at the far end rather than overshooting, so the
# wave is still on the axon as the shot ends instead of leaving it dark
sweep(head_c, *CELL, hi=1.0)
for mat in (mat_f, mat_c):
    for fc in mat.node_tree.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"      # constant conduction velocity

# ---- world, lights, camera ----------------------------------------------------------
g["build_world"](scene)

allv = np.vstack([local_coords(objs["cell"]), local_coords(objs["fibre"])])
lo, hi = np.percentile(allv, 0.5, axis=0), np.percentile(allv, 99.5, axis=0)
centre = (lo + hi) / 2.0                      # raw file space
span = float(np.max(hi - lo))
factor = TARGET_SIZE / span
root.scale = (factor, factor, factor)
# the object's own rotation runs before its location, so the offset that lands
# the centre on the origin has to be expressed after that turn, not before it
centre_scene = Vector(to_blender(centre)[0])
for o in objs.values():
    o.location = tuple(-centre_scene)
bpy.context.view_layer.update()
print(f"[ap] span {span:,.0f} nm -> scale {factor:.3e}", flush=True)

def scene_pos(nm):
    """A point in raw OBJ nanometres, placed where it lands in the rendered scene."""
    return (Vector(to_blender(nm)[0]) - centre_scene) * factor


contacts = scene_pos(FIELDS["syn_nm"].mean(axis=0))
assert max(abs(v) for v in contacts) < TARGET_SIZE, (
    f"contacts landed at {tuple(round(v, 2) for v in contacts)}, outside a scene "
    f"only {TARGET_SIZE} across, so the coordinate spaces do not agree")

# ---- the flash where the fibre actually touches the cell ---------------------------
# 53 synapses inside a 5 micrometre box: one bouton wrapped round one thorn. It
# earns a real light rather than a painted glow, so it throws illumination onto
# the dendrites around it.
FLASH_PEAK = float(opts.get("flash", 900.0))
_arrive = int(round(arrive))
# energies through the beat: dark, then a hard rise, a fast initial decay and a
# longer tail, which is roughly the shape of the event and reads better than a
# symmetric bump
CURVE = ((1, 0.0), (_arrive - 4, 0.0), (_arrive + 1, 1.0), (_arrive + 6, 0.34),
         (_arrive + 16, 0.10), (_arrive + 34, 0.0), (FRAMES, 0.0))

# The contacts sit at the centroid of 53 synapses wrapped around a thorn, which
# is INSIDE the dendrite. A point light there is sealed in and lights nothing,
# which is exactly what went wrong the first time. So the beat is carried by an
# emissive core that the bloom can catch, plus a light pushed out along the line
# to the camera so it is clear of the geometry it is meant to illuminate.
core_r = TARGET_SIZE * 0.011
bpy.ops.mesh.primitive_uv_sphere_add(radius=core_r, segments=24, ring_count=16,
                                     location=contacts)
core = bpy.context.active_object
core.name = "AP_CORE"
cmat = bpy.data.materials.new("AP_CORE")
cmat.use_nodes = True
cnt = cmat.node_tree
cnt.nodes.clear()
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
_out = Vector((0.62, -0.78, 0.30)).normalized() * (TARGET_SIZE * 0.055)
flare.location = contacts + _out

for f, k in CURVE:
    fr = max(1, int(f))
    flare_data.energy = FLASH_PEAK * k
    flare_data.keyframe_insert("energy", frame=fr)
    cem.inputs["Strength"].default_value = 45.0 * k
    cem.inputs["Strength"].keyframe_insert("default_value", frame=fr)
    core.scale = (1.0,) * 3 if k > 0 else (0.001,) * 3
    core.keyframe_insert("scale", frame=fr)

target = bpy.data.objects.new("AP_TARGET", None)
bpy.context.collection.objects.link(target)
target.location = contacts
bpy.context.view_layer.update()
print(f"[ap] contacts at {tuple(round(v, 2) for v in target.location)}", flush=True)
print(f"[ap] synapse flash peaks at frame {_arrive + 1}", flush=True)

# ---- where the camera looks --------------------------------------------------------
# aim=follow   walks the target along the fibre and then out through the cell,
#              using the same distance fields the emission uses, so the lens is
#              always on the wavefront.
# aim=synapse  holds the thorn. Tight, and the arbor is meant to run off frame.
# aim=cell     holds the middle, so the whole cell stays in shot.
AIM = opts.get("aim", "follow" if opts.get("follow", "1") not in ("0", "false", "no")
               else "cell")
if AIM == "follow":
    f_nodes = FIELDS[f"fibre_{FIBRE_ID}_verts"]
    f_dist = FIELDS[f"fibre_{FIBRE_ID}_dist"]
    c_nodes = FIELDS[f"cell_{HERO_ID}_verts"]
    c_dist = FIELDS[f"cell_{HERO_ID}_dist"]

    def front_raw(nodes, dist, span, frac, k=140):
        """Where the wavefront is: the mean of the k nodes nearest that distance.
        Averaging keeps the target gliding instead of hopping between branches
        whenever the arbor splits."""
        want = np.clip(frac, 0.0, 1.0) * span
        idx = np.argsort(np.abs(dist - want))[:k]
        return scene_pos(np.asarray(nodes)[idx].mean(axis=0))

    keys = []
    for fr in range(1, FRAMES + 1, 4):
        if fr <= SPIKE[0]:
            p = front_raw(f_nodes, f_dist, spans["fibre"], 0.0)
        elif fr <= SPIKE[1]:
            p = front_raw(f_nodes, f_dist, spans["fibre"],
                          (fr - SPIKE[0]) / (SPIKE[1] - SPIKE[0]))
        elif fr <= CELL[0]:
            p = contacts
        elif fr <= CELL[1]:
            p = front_raw(c_nodes, c_dist, spans["cell"],
                          (fr - CELL[0]) / (CELL[1] - CELL[0]))
        else:
            p = front_raw(c_nodes, c_dist, spans["cell"], 1.0)
        keys.append((fr, p))
    for fr, p in keys:
        target.location = p
        target.keyframe_insert("location", frame=fr)
    for fc in target.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
    print(f"[ap] camera target follows the pulse, {len(keys)} keys", flush=True)
elif AIM == "reveal":
    # Amy's cut: hold tight on the thorn for the whole arrival, then once the
    # signal is inside the cell, ease the frame open so the axon has somewhere to
    # run to. The target drifts from the contacts down to the middle of the
    # descending arbor, and the pull-back is keyed to match.
    c_nodes = FIELDS[f"cell_{HERO_ID}_verts"]
    c_dist = FIELDS[f"cell_{HERO_ID}_dist"]
    span_c = float(opts.get("_span_c", 0)) or float(FIELDS["cell_span"])
    ax_mask = np.isfinite(c_dist) & (c_dist > float(FIELDS["soma_dist"])) \
        & (c_dist < span_c * 2)
    ax_mid = scene_pos(np.asarray(c_nodes)[ax_mask].mean(axis=0))
    for fr, p in ((1, contacts), (CELL[0], contacts),
                  (int((CELL[0] + CELL[1]) / 2), (contacts + ax_mid) * 0.5),
                  (CELL[1], ax_mid), (FRAMES, ax_mid)):
        target.location = p
        target.keyframe_insert("location", frame=max(1, int(fr)))
    for fc in target.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
    print(f"[ap] hold on the thorn, then open out to the axon from frame {CELL[0]}",
          flush=True)
elif AIM == "synapse":
    target.location = contacts
    print("[ap] camera static on the thorn", flush=True)
else:
    # The contacts sit high on the apical dendrite, so aiming there hangs the
    # basal arbor off the bottom. The objects are already centred on the origin,
    # so that is the point that holds the whole cell.
    target.location = (0.0, 0.0, 0.0)
    print("[ap] camera static on the cell centre", flush=True)

g["build_lights"](scene, TARGET_SIZE, target=target)

cam_data = bpy.data.cameras.new("AP_CAM")
cam = bpy.data.objects.new("AP_CAM", cam_data)
bpy.context.collection.objects.link(cam)
scene.camera = cam
DIST = TARGET_SIZE * float(opts.get("camdist", 1.9))
trk = cam.constraints.new("TRACK_TO")
trk.target = target
trk.track_axis, trk.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
cam_data.clip_start, cam_data.clip_end = 0.01, DIST * 40

# A slow arc rather than a locked tripod. Sixteen degrees across the whole shot
# is barely perceptible frame to frame, but it gives the arbor parallax, which
# is what stops a still-looking 3D render from reading as a flat picture. The
# lens also eases in a little as the spike arrives and drifts back out as the
# depolarisation spreads, so the framing breathes with the event.
ARC = math.radians(float(opts.get("arc", 16.0)))
A0 = math.atan2(-0.78, 0.62)
ELEV = 0.30


def cam_at(theta, radius):
    r = radius * math.hypot(0.62, 0.78)
    return (r * math.cos(theta), r * math.sin(theta), radius * ELEV)


PUSH = float(opts.get("push", 0.86))         # closest point, as a fraction of DIST
if AIM == "reveal":
    # tight through the arrival, then open right out to take in the axon
    WIDE = float(opts.get("wide", 3.4))
    keys = ((1,           A0,              DIST * 1.02),
            (SPIKE[0],    A0 + ARC * 0.10, DIST * 1.00),
            (int(arrive), A0 + ARC * 0.40, DIST * 0.88),
            (CELL[0],     A0 + ARC * 0.50, DIST * 0.94),
            (CELL[1],     A0 + ARC * 0.86, DIST * WIDE),
            (FRAMES,      A0 + ARC,        DIST * (WIDE + 0.12)))
else:
    keys = ((1,           A0,              DIST * 1.06),
            (SPIKE[0],    A0 + ARC * 0.10, DIST * 1.03),
            (int(arrive), A0 + ARC * 0.44, DIST * PUSH),
            (CELL[0],     A0 + ARC * 0.56, DIST * (PUSH + 0.02)),
            (CELL[1],     A0 + ARC * 0.88, DIST * 1.02),
            (FRAMES,      A0 + ARC,        DIST * 1.08))
for fr, th, rad in keys:
    cam.location = cam_at(th, rad)
    cam.keyframe_insert("location", frame=max(1, int(fr)))
for fc in cam.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "BEZIER"
        kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"

# Focus rides the same target the lens tracks, so whatever the pulse is doing is
# the sharp thing in frame and the rest of the arbor falls off softly.
if opts.get("dof", "1") not in ("0", "false", "no"):
    cam_data.dof.use_dof = True
    cam_data.dof.focus_object = target
    cam_data.dof.aperture_fstop = float(opts.get("fstop", 2.4))
    cam_data.dof.aperture_blades = 6
    print(f"[ap] depth of field on, f/{cam_data.dof.aperture_fstop}", flush=True)

g["apply_render_settings"](scene)

# ---- go ------------------------------------------------------------------------------
out = opts.get("out", r"D:\Meshes\renders\ap_test.mp4")
still = opts.get("still")
if still:
    scene.render.filepath = out
    scene.render.image_settings.file_format = "PNG"
    scene.frame_set(int(still))
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[ap] still {still} in {time.time()-t0:.0f}s -> {out}", flush=True)
else:
    scene.render.filepath = out
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    el = time.time() - t0
    print(f"[ap] {FRAMES} frames in {el/60:.1f} min ({el/FRAMES:.1f}s/frame)", flush=True)
print("[ap] DONE", flush=True)
