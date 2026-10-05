"""Shot B: one descending neuron, many body parts.

  blender --background --python banc_shotB_anim.py -- [still=N] [frames=576] [res=] [samples=]

The order of arrival IS the argument. The cell is established alone in the brain,
its axon is followed down through the neck connective, and then each body part it
reaches fades up one at a time in anatomical order: neck, front leg, wing, middle
leg, hind leg. Nothing scales up from a point, per Amy's rule; everything fades.

BEATS (fractions of the run, so changing `frames` retimes everything)
  0.00-0.04  the cell alone in the brain, dendrites only. Brief hold.
  0.04-0.22  camera descends, following the axon toward the neck
  0.22-0.27  the neck connective, the narrowest point. Brief hold.
  0.27-0.36  neck motor neurons arrive          (8, gold)
  0.36-0.47  front leg T1                       (41, blue)
  0.47-0.55  wing                               (3, pink)
  0.55-0.66  middle leg T2                      (32, green)
  0.66-0.78  hind leg T3                        (40, magenta)
  0.78-1.00  pull back, all of it at once. Long hold.

  Retimed 3 Aug 2026: the old cut opened with 3.4 seconds of a still frame and had
  a second dead hold at eight seconds. Measured frame difference under 0.005 in
  both. That time now goes to the fades.

COST NOTE: the fades use alpha blending, which the CA3 playbook measures at about
10.6s per frame against 1-3s opaque. 576 frames is therefore roughly 100 minutes,
in the same ballpark as the CA3 synapse story at 159 minutes. Animating emission
instead would be far faster but a black-but-solid object still occludes what is
behind it, which shows up badly when the camera travels through the population.
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)

ROOT = r"D:\Meshes\banc"
SRC = os.path.join(ROOT, "shotB")
FRAMES = int(opts.get("frames", 576))
TARGET_SIZE = 10.0
LENS = 55.0
SENSOR = 36.0

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__
hexcol, emissive_material, set_interp = g["hexcol"], g["emissive_material"], g["set_interp"]
g["RESOLUTION"] = tuple(int(x) for x in opts.get("res", "1080x1920").split("x"))
g["SAMPLES"] = int(opts.get("samples", 64))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, FRAMES
scene.render.fps = g["FPS"]

cast = json.load(open(os.path.join(ROOT, "cast.json")))
HERO = int(cast["shotB_descending_neuron"])
bp = json.load(open(os.path.join(ROOT, "shotB_bodyparts.json")))
PART = {int(k): v for k, v in bp["part"].items()}

# The descending neuron is near-white, not orange: it has to stay legible as the
# single constant against every colour it meets, and orange sat too close to the
# neck gold at the top of frame.
COLOURS = {"dn": hexcol("#F2F6FF"), "neck": hexcol("#E8A93A"), "t1": hexcol("#2E8BE0"),
           "wing": hexcol("#FF4FA3"), "t2": hexcol("#17A06B"), "t3": hexcol("#B84DD8"),
           "other": hexcol("#46536B")}
ORDER = ["neck", "t1", "wing", "t2", "t3", "other"]     # anatomical, top to bottom
# RETIMED 3 Aug 2026. Amy: "the first 3 seconds no motion happens." She was right
# and it was by design: the old beat one held for 0.14 of the run, 3.4 seconds of a
# still frame before the camera moved at all, and there was a second dead hold at
# 0.30-0.38. Measured frame difference over the old cut was under 0.005 for the
# first three seconds and again at eight seconds: literally nothing changing.
#
# An opening hold earns its place only if there is something to read in it. One
# second is enough to register a single cell; three is a viewer wondering whether
# the file is broken. The time goes to the fades, which is where the shot is.
WINDOW = {"neck": (.27, .36), "t1": (.36, .47), "wing": (.47, .55),
          "t2": (.55, .66), "t3": (.66, .78), "other": (.66, .78)}

role_of = lambda i: "dn" if i == HERO else PART.get(i, "other")

# ---- import -------------------------------------------------------------------
t0 = time.time()
groups = {}
files = sorted(f for f in os.listdir(SRC) if f.endswith(".obj") and ".tmp." not in f)
for n, fn in enumerate(files, 1):
    rid = int(fn[:-4])
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=os.path.join(SRC, fn))
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    r = role_of(rid)
    for o in new:
        o.name = f"{r}_{rid}"
    groups.setdefault(r, []).extend(new)
    if n % 40 == 0 or n == len(files):
        print(f"[B] imported {n}/{len(files)} {time.time()-t0:.0f}s", flush=True)
bpy.context.view_layer.update()
for k, v in groups.items():
    print(f"[B]   {k}: {len(v)}", flush=True)

# ---- fit, and flip so the brain is at the top ---------------------------------
allo = [o for v in groups.values() for o in v]
mins, maxs = Vector((1e18,) * 3), Vector((-1e18,) * 3)
for o in allo:
    for cnr in o.bound_box:
        w = o.matrix_world @ Vector(cnr)
        for i in range(3):
            mins[i], maxs[i] = min(mins[i], w[i]), max(maxs[i], w[i])
centre = (mins + maxs) / 2
s = TARGET_SIZE / max((maxs - mins)[i] for i in range(3))

bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
root = bpy.context.active_object
root.name = "BANC_ROOT"
for o in allo:
    o.parent = root
    o.matrix_parent_inverse = root.matrix_world.inverted()
root.scale = (s, s, s)
root.rotation_euler = (math.pi, 0, 0)      # BANC y is posterior; brain to the top
bpy.context.view_layer.update()
root.location = -(root.matrix_world.to_3x3() @ centre)
bpy.context.view_layer.update()

ext = (maxs - mins) * s
top_z = max((o.matrix_world @ Vector(c)).z for o in groups["dn"] for c in o.bound_box)
bot_z = min((o.matrix_world @ Vector(c)).z for o in allo for c in o.bound_box)
print(f"[B] extent {ext.x:.1f} x {ext.y:.1f} x {ext.z:.1f}; dn top z={top_z:.2f} "
      f"scene bottom z={bot_z:.2f}", flush=True)

# ---- materials, with alpha driven per group ------------------------------------
F = lambda frac: max(1, int(round(frac * FRAMES)))


def fade(objs, role, a, b):
    """Fade a group up between frames a and b. Cells within a group are staggered
    slightly so the group blooms rather than switching on as one flat sheet."""
    n = len(objs)
    for i, o in enumerate(sorted(objs, key=lambda x: x.name)):
        mat = emissive_material(f"mat_{role}_{i:03d}", COLOURS[role], 1.0)
        # HASHED, not BLEND. EEVEE sorts alpha-blended surfaces per OBJECT, not per
        # pixel, so when a fading cell drifts in front of another the sort order can
        # flip between frames and the near surface culls the far one. Measured in
        # shotB v2: the white descending neuron dropped to ZERO visible pixels on
        # single frames between 15 and 17 seconds, when the green hind leg group
        # fades in over it, and came back the next frame. 104 sign changes in 160
        # frames. Amy saw it as the white cell flashing.
        #
        # Hashed alpha is stochastic and resolves against the depth buffer, so it
        # cannot mis-sort. It needs samples to look smooth, which this render has at
        # 64+, and it is also much cheaper: the playbook measures blended frames at
        # about 10.6s against 1-3s opaque, and this shot is 576 frames.
        mat.blend_method = "HASHED"
        if hasattr(mat, "show_transparent_back"):
            mat.show_transparent_back = False
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        o.data.materials.clear()
        o.data.materials.append(mat)
        t = (i * 7919 % max(1, n)) / max(1, n)          # deterministic scatter
        s0 = a + t * (b - a) * 0.45
        s1 = s0 + (b - a) * 0.55
        bsdf.inputs["Alpha"].default_value = 0.0
        mat.node_tree.keyframe_insert(
            data_path='nodes["Principled BSDF"].inputs[4].default_value', frame=int(s0))
        bsdf.inputs["Alpha"].default_value = 1.0
        mat.node_tree.keyframe_insert(
            data_path='nodes["Principled BSDF"].inputs[4].default_value', frame=int(s1))
        for fc in mat.node_tree.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "SINE"
                kp.easing = "EASE_IN_OUT"


mat_dn = emissive_material("mat_dn", COLOURS["dn"], 1.0)
for o in groups["dn"]:
    o.data.materials.clear()
    o.data.materials.append(mat_dn)

beats = {}
for role in ORDER:
    if role in groups:
        a, b = WINDOW[role]
        fade(groups[role], role, F(a), F(b))
        beats[role] = {"start": F(a), "end": F(b), "n": len(groups[role]),
                       "hex": "#%02X%02X%02X" % tuple(
                           int(round(min(1.0, max(0.0, c)) ** (1 / 2.2) * 255))
                           for c in COLOURS[role][:3])}
        print(f"[B] {role}: {len(groups[role])} cells fading {F(a)}-{F(b)}", flush=True)

# The overlay reads this rather than keeping its own copy of the timings. Two
# copies of one schedule drift the moment either is edited, and a label that names
# a group before it appears is worse than no label. Written by the render, so it
# cannot disagree with what was actually rendered.
_OVERLAY_IS_PART_OF_THE_FILM = True
# On 4 Aug this render produced 576 frames and assembled an mp4 with NO LABELS,
# because the overlay was a manual second step. That is the second time the same
# gap has shipped a bare film: I wired it into retina_ds_anim.py after the first
# and did not wire it here, so "fixed" covered one script out of two. The overlay
# now runs at the end of THIS script too, and if it fails the log says so loudly
# rather than quietly assembling a film with no key. See the tail of this file.
_bp = os.path.join(r"D:\Meshes\renders", "shotB_beats.json")
os.makedirs(os.path.dirname(_bp), exist_ok=True)
json.dump({"frames": FRAMES, "fps": g["FPS"], "hero": str(HERO),
           "dn_hex": "#%02X%02X%02X" % tuple(
               int(round(min(1.0, max(0.0, c)) ** (1 / 2.2) * 255))
               for c in COLOURS["dn"][:3]),
           "groups": beats}, open(_bp, "w"), indent=2)
print(f"[B] beat table -> {_bp}", flush=True)

# ---- camera: hold on the brain, descend, then pull back -----------------------
fov_w = 2 * math.atan(SENSOR / (2 * LENS))
RES_W, RES_H = g["RESOLUTION"]
fov_h = 2 * math.atan((SENSOR * RES_H / RES_W) / (2 * LENS))

bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, top_z))
target = bpy.context.active_object
target.name = "SHOT_TARGET"
bpy.ops.object.camera_add(location=(0, -3.0, top_z))
cam = bpy.context.active_object
cam.data.lens = LENS
cam.data.sensor_fit = "HORIZONTAL"       # AUTO transposes the FOV on a portrait frame
cam.data.sensor_width = SENSOR
tc = cam.constraints.new(type="TRACK_TO")
tc.target = target
tc.track_axis = "TRACK_NEGATIVE_Z"
tc.up_axis = "UP_Y"
scene.camera = cam

def frame_dist(half_w, half_h, margin):
    return margin * max(half_w / math.tan(fov_w / 2), half_h / math.tan(fov_h / 2))


full = frame_dist(ext.x / 2, ext.z / 2, 1.15)

# The opening distance is COMPUTED from the descending neuron's own bounding box,
# not guessed. A hardcoded 3.0 put the camera so close that the dendritic arbor
# ran off two edges and the near-white material blew out into a flat silhouette.
# At a distance that actually frames the arbor, the same white holds its fine
# structure, so the colour was never the problem.
dmin, dmax = Vector((1e18,) * 3), Vector((-1e18,) * 3)
for o in groups["dn"]:
    for cnr in o.bound_box:
        w = o.matrix_world @ Vector(cnr)
        for i in range(3):
            dmin[i], dmax[i] = min(dmin[i], w[i]), max(dmax[i], w[i])
dn_c = (dmin.z + dmax.z) / 2
arbor_top = dmax.z - (dmax.z - dmin.z) * 0.12       # the tuft, not the whole axon
open_d = frame_dist((dmax.x - dmin.x) / 2, (dmax.z - arbor_top) * 1.6, 1.20)
mid_d = frame_dist(ext.x / 2, ext.z / 4, 1.15)
print(f"[B] dn bbox {dmax.x-dmin.x:.1f} x {dmax.z-dmin.z:.1f}; "
      f"open distance {open_d:.1f}, mid {mid_d:.1f}, full {full:.1f}", flush=True)

# The arbor is not centred on x=0: the whole scene is centred, but this cell sits
# to one side of it. Distance alone therefore could not frame the opening, the
# camera has to pan across as well, easing back to centre for the wide shot.
dn_cx = (dmin.x + dmax.x) / 2
open_d = frame_dist((dmax.x - dmin.x) / 2, (dmax.z - arbor_top) * 1.6, 1.30)
print(f"[B] dn centre x={dn_cx:.2f}; opening pans there and eases back to 0", flush=True)

for fr, x, z, d in ((1, dn_cx, arbor_top, open_d),
                    (F(.04), dn_cx, arbor_top, open_d),   # was .14: 3.4s of nothing
                    (F(.22), dn_cx * 0.6, dn_c, mid_d),
                    (F(.27), dn_cx * 0.6, dn_c, mid_d),   # was .30-.38: a second dead hold
                    (F(.78), 0.0, (top_z + bot_z) / 2, full * 0.86),
                    (FRAMES, 0.0, (top_z + bot_z) / 2, full)):
    target.location = (x, 0, z)
    target.keyframe_insert(data_path="location", frame=fr)
    cam.location = (x, -d, z)
    cam.keyframe_insert(data_path="location", frame=fr)
set_interp(cam, "SINE", "EASE_IN_OUT")
set_interp(target, "SINE", "EASE_IN_OUT")

g["build_world"](scene)
g["build_lights"](scene, TARGET_SIZE, root)
g["apply_render_settings"](scene)

out = opts.get("out", r"D:\Meshes\renders\banc_shotB.mp4")
scene.render.filepath = out
# `stills=1,219,322` renders several beats from ONE import. Checking beats one at
# a time costs a 2.5 minute re-import each, which is what makes people skip the
# check and launch the animation blind.
stills = opts.get("stills") or opts.get("still")
if stills:
    scene.render.image_settings.file_format = "PNG"
    base = opts.get("out", r"D:\Meshes\renders\banc_shotB_beat")
    base = base[:-4] if base.lower().endswith(".mp4") else base
    for fr in [int(x) for x in str(stills).split(",")]:
        scene.frame_set(fr)
        scene.render.filepath = f"{base}_{fr:04d}.png"
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[B] beat {fr} -> {scene.render.filepath} in {time.time()-t0:.0f}s",
              flush=True)
else:
    # RENDER A PNG SEQUENCE, THEN ASSEMBLE. Never render straight to mp4.
    # Blender writes the mp4 index (the moov atom) only when the animation
    # completes, so a job that is interrupted leaves every encoded frame stranded
    # inside a container nothing can read. That is exactly what happened on
    # 30 July: 3.6 hours of rendering produced a 3.5 MB file with ftyp, free and
    # mdat but no moov, and the frames were not retrievable by any means.
    #
    # A PNG sequence costs a little disk and gives three things back: every
    # finished frame survives an interruption, progress is countable by listing
    # the directory, and a re-run can skip what already exists.
    seq_dir = os.path.splitext(out)[0] + "_frames"
    os.makedirs(seq_dir, exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.join(seq_dir, "f")
    done = {int(f[1:6]) for f in os.listdir(seq_dir)
            if f.startswith("f") and f.endswith(".png") and f[1:6].isdigit()}
    if done:
        print(f"[B] {len(done)} frames already on disk, rendering the rest", flush=True)

    t0 = time.time()
    for fr in range(1, FRAMES + 1):
        if fr in done:
            continue
        scene.frame_set(fr)
        scene.render.filepath = os.path.join(seq_dir, f"f{fr:05d}")
        bpy.ops.render.render(write_still=True)
        n = fr - min(done) if done else fr
        el = time.time() - t0
        print(f"Fra:{fr} of {FRAMES} | {el/60:.1f} min elapsed | "
              f"{el/max(1, fr - len(done)):.1f}s/frame", flush=True)
    el = time.time() - t0
    print(f"[B] {FRAMES} frames in {el/60:.1f} min", flush=True)

    # assemble; ffmpeg is on PATH and already used by the queue for web encodes
    import subprocess

    # THE OVERLAY IS PART OF THE FILM. Without it this shot is coloured shapes
    # appearing in sequence and a viewer cannot tell what any of them are, which
    # is exactly the note Amy gave on v2. Blender ships no Pillow, so it runs in
    # the project venv as a subprocess. If it fails, the raw frames still
    # assemble and the failure is said OUT LOUD, because a bare film looks like a
    # finished one until you go looking for the panels.
    src_dir = seq_dir
    ov_dir = os.path.splitext(out)[0] + "_ov"
    VENV = r"D:\Meshes\.venv\Scripts\python.exe"
    if os.path.exists(VENV) and opts.get("overlay", "1") not in ("0", "false", "no"):
        r = subprocess.run([VENV, r"D:\Meshes\banc_shotB_overlay.py",
                            "--frames", seq_dir, "--out", ov_dir,
                            "--beats", _bp])
        n_ov = len([f for f in os.listdir(ov_dir) if f.endswith(".png")]) \
            if os.path.isdir(ov_dir) else 0
        if r.returncode == 0 and n_ov == FRAMES:
            src_dir = ov_dir
            print(f"[B] labels applied to {n_ov} frames", flush=True)
        else:
            print(f"[B] !! OVERLAY FAILED (rc={r.returncode}, {n_ov}/{FRAMES}). "
                  f"Assembling RAW frames: this film has no labels.", flush=True)

    cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", str(g["FPS"]),
           "-i", os.path.join(src_dir, "f%05d.png"),
           "-c:v", "libx264", "-preset", "slow", "-crf", "17",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    print(f"[B] assembling -> {out}", flush=True)
    subprocess.run(cmd, check=False)
    if os.path.exists(out):
        print(f"[B] wrote {out} ({os.path.getsize(out)/1e6:.1f} MB) "
              f"from {'LABELLED' if src_dir == ov_dir else 'RAW'} frames", flush=True)
print("[B] DONE", flush=True)
