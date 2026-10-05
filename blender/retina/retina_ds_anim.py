"""Retina: direction selectivity, measured.

  blender --background --python retina_ds_anim.py -- [stills=1,120] [frames=576] [res=] [samples=]

WHAT IS REAL HERE. Every colour and every brightness change is a measurement from
the Euler lab's OGB-1 calcium recordings, joined to the EM reconstruction:

  hue        = bar_pref_dir, the direction the cell actually responds to most.
               Angle to hue is the one honest use of a colour wheel: the data IS
               an angle.
  brightness = bar_dir_component, the cell's measured response at whichever bar
               direction is currently sweeping. A cell brightens when the bar
               moves the way it likes, and it is its own recording doing it.
  grey cells = bar_ds_pvalue >= 0.05, not significantly direction selective.
               They stay dim on purpose: most of the retina is not DS, and
               hiding that would be a lie.

The bar sweeps the same 8 directions the stimulus used.

SPEED. Emission is animated, not alpha. The CA3 playbook measures alpha-blended
frames at about 10.6s against 1-3s opaque, and rendering shot B straight to mp4
with alpha cost 3.6 hours and produced nothing. Output is a PNG sequence, so an
interruption keeps every finished frame.
"""
import colorsys
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)

ROOT = r"D:\Meshes\retina"
# meshes_clean, NOT meshes. The old staged library was the meshparty downsample,
# which arrives already shattered into thousands of components (largest is 6.5% of
# the cell against 94.9% at full resolution) and sits at about 8 faces per um2,
# roughly a tenth of what a dendrite needs to read as continuous. meshes_clean is
# rebuilt from full resolution, stripped of geometry no ray can reach, and
# decimated on a density budget: 35 faces per um2 for cells that light up, 6 for
# the ghosts. See section 13 of RENDERING_NEURONS.md.
MESH = opts.get("meshdir", os.path.join(ROOT, "meshes_clean"))
FRAMES = int(opts.get("frames", 576))
TARGET = 10.0
LENS = 50.0
SENSOR = 36.0

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__
g["RESOLUTION"] = tuple(int(x) for x in opts.get("res", "1080x1920").split("x"))
g["SAMPLES"] = int(opts.get("samples", 64))
set_interp = g["set_interp"]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, FRAMES
scene.render.fps = g["FPS"]

# ---- the measurements ---------------------------------------------------------
import csv
cells = []
with open(os.path.join(ROOT, "functional_cells.csv"), encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        # Ask the DIRECTORY, not the has_mesh column. That column records which
        # cells were staged when the CSV was written, and it is now wrong: it says
        # 202 while the rebuilt library holds all 364. A cached boolean about the
        # filesystem goes stale the moment the filesystem changes.
        if not os.path.exists(os.path.join(MESH, f"{int(row['root_id'])}.obj")):
            continue
        try:
            tune = json.loads(row["dir_tuning"]) if row["dir_tuning"] else []
        except Exception:
            tune = []
        if not tune:
            continue
        cells.append({
            "id": int(row["root_id"]),
            "field": row["field"],
            "type": row["cell_type"],
            "pref": float(row["pref_dir_deg"]) if row["pref_dir_deg"] else 0.0,
            "ds": row["is_ds"] in ("True", "true", "1"),
            "dsi": float(row["ds_index"]) if row["ds_index"] else 0.0,
            "tune": tune,
        })
NBINS = len(cells[0]["tune"])
print(f"[R] {len(cells)} cells with mesh and tuning, {NBINS} bar directions", flush=True)
print(f"[R] direction selective: {sum(c['ds'] for c in cells)}", flush=True)


# The CA3 palette, used as a CYCLIC ramp so it can still encode an angle.
# Preferred direction is a direction, so the colour map has to wrap: the value
# just below 360 must sit next to the value just above 0. A rainbow hue wheel
# does that automatically, which is why it was the first choice, but it is not
# the house palette. These four anchors are taken from the CA3 page and spaced
# evenly around the circle, so the map still wraps and still means an angle,
# while staying blue, purple, gold and teal-green.
DIR_ANCHORS = [
    (0,   "#2E8BE0"),   # blue        (the CA3 thorny pyramidal blue)
    (90,  "#8B5CE0"),   # purple      (sparsely thorny)
    (180, "#E8A93A"),   # golden      (mossy fibre gold)
    (270, "#17A06B"),   # teal-green  (inhibitory emerald)
    (360, "#2E8BE0"),   # wraps back to blue
]


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def hue_rgb(deg, sat, val):
    """Interpolate the house palette around the circle. sat/val kept for signature
    compatibility; val scales brightness, sat pulls toward grey."""
    d = deg % 360
    for i in range(len(DIR_ANCHORS) - 1):
        a0, c0 = DIR_ANCHORS[i]
        a1, c1 = DIR_ANCHORS[i + 1]
        if a0 <= d <= a1:
            t = (d - a0) / (a1 - a0)
            r0, g0, b0 = _hex(c0)
            r1, g1, b1 = _hex(c1)
            r, gg, b = (r0 + (r1 - r0) * t, g0 + (g1 - g0) * t, b0 + (b1 - b0) * t)
            break
    else:
        r, gg, b = _hex("#2E8BE0")
    grey = (r + gg + b) / 3.0
    r = grey + (r - grey) * sat
    gg = grey + (gg - grey) * sat
    b = grey + (b - grey) * sat
    return ((r * val) ** 2.2, (gg * val) ** 2.2, (b * val) ** 2.2, 1.0)


# ---- import -------------------------------------------------------------------
t0 = time.time()
objs = {}
for n, c in enumerate(cells, 1):
    p = os.path.join(MESH, f"{c['id']}.obj")
    if not os.path.exists(p):
        continue
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=p)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    for o in new:
        o.name = f"c{c['id']}"
    if new:
        objs[c["id"]] = new
    if n % 30 == 0 or n == len(cells):
        print(f"[R] imported {n}/{len(cells)}  {time.time()-t0:.0f}s", flush=True)
bpy.context.view_layer.update()
faces = sum(len(o.data.polygons) for v in objs.values() for o in v)
print(f"[R] {faces/1e6:.1f}M faces in {time.time()-t0:.0f}s", flush=True)

allo = [o for v in objs.values() for o in v]
mins, maxs = Vector((1e18,) * 3), Vector((-1e18,) * 3)
for o in allo:
    for cn in o.bound_box:
        w = o.matrix_world @ Vector(cn)
        for i in range(3):
            mins[i], maxs[i] = min(mins[i], w[i]), max(maxs[i], w[i])
centre = (mins + maxs) / 2
s = TARGET / max((maxs - mins)[i] for i in range(3))

bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
root = bpy.context.active_object
root.name = "RETINA_ROOT"
for o in allo:
    o.parent = root
    o.matrix_parent_inverse = root.matrix_world.inverted()
root.scale = (s, s, s)
bpy.context.view_layer.update()
root.location = -(root.matrix_world.to_3x3() @ centre)
bpy.context.view_layer.update()
ext = (maxs - mins) * s
print(f"[R] extent {ext.x:.1f} x {ext.y:.1f} x {ext.z:.1f}", flush=True)

# ---- materials: hue is preferred direction, brightness is the response ---------
HOLD = int(FRAMES * 0.10)                 # establish the mosaic before it moves
SWEEP = FRAMES - HOLD
per = SWEEP / NBINS

for c in cells:
    if c["id"] not in objs:
        continue
    if c["ds"]:
        base = hue_rgb(c["pref"], 0.88, 1.0)
    else:
        base = (0.055, 0.065, 0.085, 1.0)          # quiet, not invisible
    mat = bpy.data.materials.new(f"m{c['id']}")
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = base
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    for o in objs[c["id"]]:
        o.data.materials.clear()
        o.data.materials.append(mat)

    tune = c["tune"]
    lo, hi = min(tune), max(tune)
    rng = (hi - lo) or 1.0
    st = em.inputs["Strength"]
    cl = em.inputs["Color"]

    def key_s(fr, v):
        st.default_value = v
        nt.keyframe_insert(data_path='nodes["Emission"].inputs[1].default_value',
                           frame=int(fr))

    def key_c(fr, rgba):
        cl.default_value = rgba
        nt.keyframe_insert(data_path='nodes["Emission"].inputs[0].default_value',
                           frame=int(fr))

    # EVERY cell sits as a dim grey wireframe by default and only takes its
    # direction colour while it is actually responding. The previous version kept
    # all 64 direction-selective cells permanently coloured and only varied
    # brightness, so a dozen were always part-lit and you could not tell which
    # ones the current bar was driving. Colour is now the signal, not the label.
    # Raised from 0.030. At the old level the sheet was invisible between pulses,
    # and since some bar directions drive only one or two cells, roughly a third
    # of the film was a near black frame. The ghost is the same wireframe idea,
    # just actually visible: the mosaic stays as faint structure throughout so the
    # lit cells read as part of a population rather than as sparks in the dark.
    GHOST = (0.055, 0.064, 0.082, 1.0)
    # A cell lights at ITS OWN PREFERRED DIRECTION and nowhere else, so each of
    # the 64 direction-selective cells fires exactly once per sweep. Thresholding
    # the normalised tuning instead let 18 to 41 cells light simultaneously,
    # because real direction tuning is broad and most cells clear any reasonable
    # threshold at several directions.
    #
    # WHICH estimate of "preferred" decides the timing has to be the SAME one that
    # decides the hue, and for 29 of the 64 cells it was not. The hue comes from
    # bar_pref_dir, the vector sum of the tuning curve, which is the quantity the
    # recording reports. The timing used to come from argmax of the same curve.
    # Those disagree whenever tuning is broad or one bin is noisy, and they
    # disagreed by more than a whole 45 degree step for 45% of the population, so
    # gold cells lit during the downward sweep while the compass said 270. Binning
    # the reported angle makes the two agree by construction: the worst possible
    # disagreement is now half a bin. Argmax is the weaker estimate anyway, being
    # quantised to 45 degrees and decided by a single sample.
    best = int(round(c["pref"] / (360.0 / NBINS))) % NBINS
    quiet = 0.16 if c["ds"] else 0.11

    key_s(1, quiet); key_c(1, GHOST)
    key_s(HOLD, quiet); key_c(HOLD, GHOST)
    for b in range(NBINS):
        resp = (tune[b] - lo) / rng                 # 0..1, the cell's own curve
        a = HOLD + b * per
        fires = c["ds"] and b == best
        peak_s = quiet + (3.4 * resp if fires else 0.10 * resp)
        peak_c = base if fires else GHOST
        key_s(a + per * 0.12, quiet); key_c(a + per * 0.12, GHOST)
        key_s(a + per * 0.45, peak_s); key_c(a + per * 0.45, peak_c)
        key_s(a + per * 0.88, quiet); key_c(a + per * 0.88, GHOST)
    key_s(FRAMES, quiet); key_c(FRAMES, GHOST)
    for fc in nt.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "SINE"
            kp.easing = "EASE_IN_OUT"

# ---- the bar --------------------------------------------------------------------
# OFF by default. Two attempts at drawing the stimulus produced a bright white
# diagonal slab lying across the mosaic: at 1.4x scene width in front it hid the
# cells, and thinned and moved behind it still read as a scratch rather than a
# moving bar. The sweep is already carried by the cells themselves lighting in
# sequence, each following its own measured tuning curve, so the bar was adding
# nothing and taking attention. Pass bar=1 to bring it back and iterate on it.
SHOW_BAR = opts.get("bar", "0") not in ("0", "false", "no")
if SHOW_BAR:
    bpy.ops.mesh.primitive_plane_add(size=1)
    bar = bpy.context.active_object
    bar.name = "BAR"
    # Thin, and BEHIND the sheet. The first attempt was 1.4x the scene wide and sat in
    # front, so it read as a giant white slab lying across the mosaic and hid the very
    # cells it was meant to explain. Behind the cells it glows through the gaps and
    # reads as a sweep without competing.
    bar.scale = (ext.x * 1.5, ext.z * 0.016, 1)
    bar.rotation_euler = (math.pi / 2, 0, 0)   # lie in the sheet's plane, not across it
    bm = bpy.data.materials.new("m_bar")
    bm.use_nodes = True
    bnt = bm.node_tree
    for nd in list(bnt.nodes):
        bnt.nodes.remove(nd)
    bo = bnt.nodes.new("ShaderNodeOutputMaterial")
    be = bnt.nodes.new("ShaderNodeEmission")
    be.inputs["Color"].default_value = (0.9, 0.93, 1.0, 1)
    be.inputs["Strength"].default_value = 0.0
    bnt.links.new(be.outputs["Emission"], bo.inputs["Surface"])
    bar.data.materials.append(bm)
    bar.location = (0, ext.y * 1.6, 0)      # just in front of the sheet, toward camera

    span = max(ext.x, ext.z) * 0.78
    for b in range(NBINS):
        ang = 2 * math.pi * b / NBINS
        a = HOLD + b * per
        # the stimulus moves within the plane of the retina: Blender X and Z
        d = Vector((math.cos(ang), 0.0, math.sin(ang)))
        for fr, t in ((a + per * 0.10, -1.0), (a + per * 0.90, 1.0)):
            bar.location = (d.x * span * t, ext.y * 1.6, d.z * span * t)
            bar.rotation_euler = (math.pi / 2, -ang, 0)
            bar.keyframe_insert(data_path="location", frame=int(fr))
            bar.keyframe_insert(data_path="rotation_euler", frame=int(fr))
        for fr, v in ((a + per * 0.06, 0.0), (a + per * 0.16, 0.55),
                      (a + per * 0.86, 0.55), (a + per * 0.95, 0.0)):
            be.inputs["Strength"].default_value = v
            bnt.keyframe_insert(data_path='nodes["Emission"].inputs[1].default_value',
                                frame=int(fr))
    set_interp(bar, "LINEAR", "EASE_IN_OUT")

# ---- camera: look down on the retinal sheet ------------------------------------
fov_w = 2 * math.atan(SENSOR / (2 * LENS))
RW, RH = g["RESOLUTION"]
fov_h = 2 * math.atan((SENSOR * RH / RW) / (2 * LENS))
# The retina is a SHEET. After the OBJ axis flip its plane is Blender X-Z and the
# thin axis is Y (measured extent 9.4 x 0.7 x 10.0). Looking down Z therefore sees
# it edge-on, as a 9.4 x 0.7 strip. Look along Y instead, so the mosaic is face on
# and the tiling is visible, which is the whole point.
dist = 1.18 * max((ext.x / 2) / math.tan(fov_w / 2), (ext.z / 2) / math.tan(fov_h / 2))
# SOMAS TOWARD THE VIEWER. Checked against the data rather than by eye: soma
# depths sit at the LOW end of each cell's z range in file coordinates, and the
# OBJ importer maps file z to Blender -y, so low file z becomes HIGH Blender y.
# A camera on -y therefore looks at the arbors from underneath with the somas
# pointing away, which is what the first render did. Sit on +y instead.
bpy.ops.object.camera_add(location=(0, dist, 0))
cam = bpy.context.active_object
cam.data.lens = LENS
cam.data.sensor_fit = "HORIZONTAL"       # AUTO transposes FOV on a portrait frame
cam.data.sensor_width = SENSOR
cam.rotation_euler = (math.pi / 2, 0, math.pi)   # face the sheet, somas to camera
scene.camera = cam
print(f"[R] camera at {dist:.1f} on +Y: somas face the viewer", flush=True)

g["build_world"](scene)
g["build_lights"](scene, TARGET, root)
g["apply_render_settings"](scene)
scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.10

# ---- the anatomy frame --------------------------------------------------------
# Every cell lit at once, no direction colouring: the opening and closing state,
# "here is all of the tissue", before and after the film says which parts of it
# care about direction.
#
# ONE FRAME, not a rendered fade. The camera in this film never moves and no
# geometry moves; only emission changes. So a fade from black to this frame, and a
# dissolve from this frame into the ghost state, are pixel-identical to rendering
# those frames. At 52 s/frame a 200 frame handle would cost three hours to produce
# what a dissolve gives exactly, in seconds. Anything that MOVED would have to be
# rendered; nothing here does.
# ---- the opening stages -------------------------------------------------------
# Amy's sequence, 3 Aug 2026: show the five calcium imaged clusters coloured by
# cluster, recolour to cell type, fade away everything that is not direction
# selective, THEN start the bar.
#
# All three are stills. The camera and geometry never move in this film, so the
# transitions between them are cross-dissolves and are pixel-identical to rendered
# frames at no GPU cost. All three are rendered in ONE import, because the import
# is 25 minutes and the render is one.
#
# SHADED, not emissive. The first anatomy frame was pure emission with no lights,
# so nothing had form and Amy could not find the somas: with flat emission a soma
# is only a denser lump of the same brightness. These use the house surface, tissue
# in water at IOR 1.04, so a soma reads as a solid body.
if opts.get("stages", "0") not in ("0", "false", "no"):
    import csv as _c
    meta = {}
    with open(os.path.join(ROOT, "functional_cells.csv"), encoding="utf-8") as fh:
        for row in _c.DictReader(fh):
            meta[int(row["root_id"])] = (row["field"], row["cell_type"], row["cls"])

    CLUSTER = {"GCL0": "#2E8BE0", "GCL1": "#8B5CE0", "GCL2": "#E8A93A",
               "GCL3": "#17A06B", "GCL4": "#7FC4F5"}
    # 83 distinct type strings is far too many to colour. These are the six most
    # numerous, plus the rest split by class, which keeps a legend readable and
    # still says the thing worth saying: what kind of cell each one is.
    TYPE = {"SAC": "#E8A93A", "WFAC": "#8B5CE0", "A1": "#17A06B",
            "Fmini OFF": "#2E8BE0", "UHD": "#E0559B", "ON OS": "#7FC4F5"}
    # The unnamed remainder has to be DARK. Only 122 of the 364 cells fall into the
    # six named types, so 242 are "other": at the first attempt those were mid
    # greys and 242 of them simply swamped the frame, leaving a pale mass with the
    # named types as confetti on top. The remainder is context, not subject, so it
    # sits well below the named types instead of competing with them.
    OTHER_AC, OTHER_RGC = "#232A33", "#2E3742"

    def _lin(h):
        h = h.lstrip("#")
        return tuple((int(h[i:i + 2], 16) / 255.0) ** 2.2 for i in (0, 2, 4)) + (1.0,)

    def shaded(name, rgba):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = rgba
        b.inputs["Roughness"].default_value = 0.62
        b.inputs["IOR"].default_value = 1.04          # submerged tissue, never glossy
        if "Subsurface Weight" in b.inputs:
            b.inputs["Subsurface Weight"].default_value = 0.20
        b.inputs["Emission Color"].default_value = rgba
        b.inputs["Emission Strength"].default_value = 0.10   # lift, the rig lights it
        return m

    base = opts.get("out", r"D:\Meshes\renders\retina_stage.png")
    base = base[:-4] if base.lower().endswith(".png") else base
    for stage in ("cluster", "type", "dsonly"):
        cache = {}
        for c in cells:
            if c["id"] not in objs:
                continue
            field, ctype, cls = meta.get(c["id"], ("", "", ""))
            if stage == "cluster":
                hexc = CLUSTER.get(field, OTHER_RGC)
            elif stage == "type":
                hexc = TYPE.get(ctype, OTHER_AC if cls == "AC" else OTHER_RGC)
            else:
                # The direction selective cells take THEIR OWN preferred direction
                # hue here, not a flat colour. Flat cyan made this stage 106 cells
                # of one colour, which says only "these are the ones", and then the
                # bar sweeps arrive with a colour scheme the viewer has not seen.
                # Painting them by preferred direction makes this stage the colour
                # key itself: the wheel is introduced on the population before it is
                # used on the animation, and the sweeps then just animate what is
                # already on screen.
                hexc = None if not c["ds"] else "USE_DIR"
            if hexc is None:
                mat = cache.get("__ghost")
                if mat is None:
                    # A dark BASE COLOUR is not enough: the scene is lit, so a dark
                    # surface still catches the key light and 258 of them read as a
                    # solid haze. The first dsonly stage was cyan cells against a
                    # cyan mass. Dropping ALPHA is what actually removes them, since
                    # it removes the surface rather than dimming it.
                    mat = cache["__ghost"] = shaded("s_ghost", (0.018, 0.022, 0.030, 1.0))
                    b = mat.node_tree.nodes["Principled BSDF"]
                    b.inputs["Emission Strength"].default_value = 0.0
                    b.inputs["Alpha"].default_value = 0.10
                    # HASHED, never BLEND: EEVEE sorts blended surfaces per object,
                    # and 258 overlapping transparent cells is exactly the case that
                    # made the BANC descending neuron vanish on single frames.
                    mat.blend_method = "HASHED"
            elif hexc == "USE_DIR":
                # hue_rgb is the SAME function the sweeps use, so the colour a cell
                # takes here is exactly the colour it takes when it fires. Two
                # copies of one colour map would drift and the key would stop
                # matching the animation it is supposed to explain.
                key = f"dir{int(c['pref']) % 360}"
                mat = cache.get(key)
                if mat is None:
                    mat = cache[key] = shaded(f"s_dir_{key}", hue_rgb(c["pref"], 0.88, 1.0))
            else:
                mat = cache.get(hexc)
                if mat is None:
                    mat = cache[hexc] = shaded(f"s_{stage}_{hexc.lstrip('#')}", _lin(hexc))
            for o in objs[c["id"]]:
                if o.data.materials and o.data.materials[0] and o.data.materials[0].node_tree \
                        and o.data.materials[0].node_tree.animation_data:
                    o.data.materials[0].node_tree.animation_data_clear()
                o.data.materials.clear()
                o.data.materials.append(mat)
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = f"{base}_{stage}.png"
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[R] stage {stage} -> {scene.render.filepath} in {time.time()-t:.0f}s "
              f"({len(cache)} materials)", flush=True)
    print("[R] DONE", flush=True)
    raise SystemExit(0)

if opts.get("anatomy", "0") not in ("0", "false", "no"):
    ANAT = (0.42, 0.52, 0.68, 1.0)      # the ghost colour, lit: same cells, brighter
    for c in cells:
        if c["id"] not in objs:
            continue
        for o in objs[c["id"]]:
            for m in o.data.materials:
                if not m or not m.node_tree:
                    continue
                nt2 = m.node_tree
                if nt2.animation_data:
                    nt2.animation_data_clear()      # drop the sweep keyframes
                em2 = nt2.nodes.get("Emission")
                if em2:
                    em2.inputs["Color"].default_value = ANAT
                    em2.inputs["Strength"].default_value = float(opts.get("anat_glow", 1.5))
    scene.render.image_settings.file_format = "PNG"
    ap = opts.get("out", r"D:\Meshes\renders\retina_anatomy.png")
    scene.render.filepath = ap
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[R] anatomy frame -> {ap} in {time.time()-t:.0f}s", flush=True)
    print("[R] DONE", flush=True)
    raise SystemExit(0)

out = opts.get("out", r"D:\Meshes\renders\retina_ds.mp4")
stills = opts.get("stills") or opts.get("still")
if stills:
    scene.render.image_settings.file_format = "PNG"
    base = out[:-4] if out.lower().endswith(".mp4") else out
    for fr in [int(x) for x in str(stills).split(",")]:
        scene.frame_set(fr)
        scene.render.filepath = f"{base}_{fr:04d}.png"
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[R] beat {fr} -> {scene.render.filepath} in {time.time()-t:.0f}s", flush=True)
else:
    seq = os.path.splitext(out)[0] + "_frames"
    os.makedirs(seq, exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    done = {int(f[1:6]) for f in os.listdir(seq)
            if f.startswith("f") and f.endswith(".png") and f[1:6].isdigit()}
    t0 = time.time()
    for fr in range(1, FRAMES + 1):
        if fr in done:
            continue
        scene.frame_set(fr)
        scene.render.filepath = os.path.join(seq, f"f{fr:05d}")
        bpy.ops.render.render(write_still=True)
        el = time.time() - t0
        print(f"Fra:{fr} of {FRAMES} | {el/60:.1f} min | "
              f"{el/max(1,fr-len(done)):.1f}s/frame", flush=True)
    import subprocess

    # THE OVERLAY IS PART OF THE FILM, NOT A SEPARATE ERRAND.
    #
    # It used to be a manual second step, and on 2 August the nightly queue
    # rendered all 576 frames of the 364 cell version and assembled an mp4 with no
    # colour key, no compass and no readout. That file was sent out before anyone
    # noticed, because a bare render looks like a finished one until you go
    # looking for the panels. The queue's contract is that a job produces its
    # output, so the job has to do this itself.
    #
    # Blender ships no Pillow, so the overlay runs in the project venv as a
    # subprocess rather than being imported here. If it fails the raw frames are
    # still on disk and the mp4 is still assembled from them, with the failure
    # said out loud rather than silently producing a film with no key.
    src = seq
    ov = os.path.splitext(out)[0] + "_overlay"
    VENV = r"D:\Meshes\.venv\Scripts\python.exe"
    if os.path.exists(VENV) and opts.get("overlay", "1") not in ("0", "false", "no"):
        r = subprocess.run([VENV, r"D:\Meshes\retina_overlay.py",
                            "--frames", seq, "--out", ov, "--total", str(FRAMES)])
        n_ov = len([f for f in os.listdir(ov) if f.endswith(".png")]) if os.path.isdir(ov) else 0
        if r.returncode == 0 and n_ov == FRAMES:
            src = ov
            print(f"[R] overlay applied to {n_ov} frames", flush=True)
        else:
            print(f"[R] !! OVERLAY FAILED (rc={r.returncode}, {n_ov}/{FRAMES} frames). "
                  f"Assembling the RAW frames: this film has no colour key.", flush=True)

    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(g["FPS"]),
                    "-i", os.path.join(src, "f%05d.png"), "-c:v", "libx264",
                    "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", out], check=False)
    if os.path.exists(out):
        print(f"[R] wrote {out} ({os.path.getsize(out)/1e6:.1f} MB) "
              f"from {'OVERLAID' if src == ov else 'RAW'} frames", flush=True)
print("[R] DONE", flush=True)
