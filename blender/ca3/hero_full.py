"""
The hero shot, but it actually pulls back to the whole population.

The first version built its own scene from D:\\Meshes\\hero\\ alone, so there was
nothing to zoom out to. This opens the full scene cache, drops the native-
resolution hero cell and its 6 mossy fibres in on top, hides the decimated copy
of that same cell, and lets the camera travel from the thorns all the way out to
every cell in the volume.

  blender --background --python hero_full.py -- [key=val]
    scope=all|cell|partners|inhibition  still=N  frames=900  res=1080x1920
    samples=64  out=path  far=  farcell=  cellact=  purple=#A651C2

scope=inhibition is the selective feedforward inhibition shot, 432 frames at
24 fps in 7 beats, storyboarded in STORYBOARD_inhibition.md and built in
inhibition_shot.py. It opens the same full scene cache and needs no extra
geometry: the interneuron already in that cache is the 3.06M face copy, and so
are its 7 mossy fibres, so there is nothing to import and nothing to hide.

scope=partners is the 8 second cell shot extended to 14 seconds: the first 192
frames are the cut Amy already has, then the camera keeps pulling back while
the 56 cells that the hero's own 6 mossy fibres also contact fade up in a
gentle imperial purple. It opens ca3_scene_partners.blend (built once by
build_partner_cache.py) instead of ca3_scene.blend.
"""
import math
import os
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = {}
for tok in argv:
    if "=" in tok:
        k, v = tok.split("=", 1)
        opts[k] = v

HERO_ID = "648518346438632877"
# scope=cell     -> pull back only as far as the whole cell and its 6 fibres.
#                   No population fades, so every frame stays opaque and cheap.
# scope=partners -> scope=cell, then keep pulling back while the 56 cells that
#                   the hero's own 6 fibres ALSO contact fade up in purple.
# scope=all      -> keep going out to all 688 fibres and every cell.
# scope=inhibition -> the 7 beat feedforward inhibition shot, which shares this
#                   file's scene cache, config plumbing and render tail but has
#                   its own beats, palette and camera in inhibition_shot.py.
SCOPE = opts.get("scope", "all")
PARTNERS = SCOPE == "partners"
INHIB = SCOPE == "inhibition"
HERO_DIR = Path(r"D:\Meshes\hero")
# partners_lite is the same 56 cells re-decimated to 5 faces/um2, the density
# the rest of the populations use. The original partners/ folder kept 40% of
# its faces because download_partners.py's keep-floor beat the density target,
# which made it 21M faces for background context and cost ~2 min a frame.
PARTNER_DIR = (Path(r"D:\Meshes\partners_lite")
               if Path(r"D:\Meshes\partners_lite").exists()
               else Path(r"D:\Meshes\partners"))
# Second scene cache with the native hero and all 56 partners already imported.
# Built by build_partner_cache.py. Saves the 63s OBJ import on every run.
PARTNER_CACHE = Path(r"D:\Meshes\ca3_scene_partners.blend")

# Gentle imperial purple: #5D2E8C, hue 268 / sat 0.79 / val 0.55.
#
# This is the dark end of imperial purple as named, and it is deliberately NOT
# a lightened, desaturated version of it, which is the obvious reading of
# "gentle" and which was tried first and looked wrong. Two measured reasons:
#
# 1. The light rig lifts everything hard. KEY_ENERGY is 5200 W and the view
#    transform is Standard, not AgX, so nothing rolls off. A hex picked to
#    LOOK gentle as a swatch, e.g. #A651C2 at sat 0.58 / val 0.76, renders as
#    a hot electric orchid on a lit dendrite. Push the desaturation further,
#    to #9B7FC4 at sat 0.35, and it goes pale lilac, which is the washed-out
#    look Amy has rejected repeatedly. #5D2E8C comes out of this rig as a
#    medium, soft violet. Gentle is what it renders as, not what the hex
#    number looks like in a colour picker.
# 2. There are 56 partners and one hero. Anything brighter buries the blue
#    cell that the whole shot is about; checked by looking at frame 336 at
#    #8837B8, #6E2E9E, #6B3A9E and #5D2E8C.
#
# Against the palette in ca3_animation.py's GROUPS: 7 degrees off
# sparsely_thorny's #8B5CE0 in hue but far deeper, sat 0.79 vs 0.59 and val
# 0.55 vs 0.88, so the two never read as one population; 55 degrees off the
# deep-layer pink #C43F92; 59 degrees off the hero blue. In this shot only the
# blue cell and the gold fibres are ever on screen anyway.
#
# _purple_swatch.py renders candidates through the project's own material,
# HDRI, light rig and view transform if this ever needs revisiting.
PARTNER_HEX = opts.get("purple", "#5D2E8C")
# The partners are context, not the subject. At full opacity 56 cells wrap
# right around the hero and bury both it and the gold fibres; ca3_animation.py
# already carries the same idea as POST_ALPHA = 0.55 for the postsynaptic set,
# and this landed on the same number independently. Solid enough to read as
# cells, thin enough that the blue shows through the near ones.
PARTNER_ALPHA = float(opts.get("partneralpha", 0.55))

src = (str(PARTNER_CACHE) if PARTNERS and PARTNER_CACHE.exists()
       else r"D:\Meshes\ca3_scene.blend")
t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=src)
print(f"[full] opened {Path(src).name} in {time.time()-t0:.0f}s", flush=True)

PATH = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": PATH}
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
g = ns["build"].__globals__

# 384 frames = 16s at 24fps: the original 8s cell act frame for frame, then 8
# more seconds, 6.2 of them for 56 cells to arrive in a staggered fade and
# 1.7 to hold on the finished picture. Amy asks for long holds and time to
# "see, process, discover and contemplate", and 56 cells arriving inside 3
# seconds is a blur.
FRAMES = int(opts.get("frames", 432 if INHIB else 384 if PARTNERS else 900))
RES = tuple(int(x) for x in opts.get(
    "res", "1920x1080" if INHIB else "1080x1920").split("x"))
g["RESOLUTION"] = RES
g["SAMPLES"] = int(opts.get("samples", 64))
g["FRAME_END"] = FRAMES
if "shadows" in opts:
    g["USE_SHADOWS"] = opts["shadows"] not in ("0","false","off","no")
if "lights" in opts:
    g["LIGHT_COUNT"] = int(opts["lights"])

scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, FRAMES
scene.render.fps = g["FPS"]

if INHIB:
    # Everything below this point is the hero cell shot and none of it applies:
    # no native import, no partner cache, no thorn aim point. The inhibition
    # shot builds its own beats, palette and camera and then uses the same
    # render tail, so the branch stays here rather than threading conditionals
    # through the rest of the file.
    INH = r"D:\Meshes\inhibition_shot.py"
    ins = {"__name__": "inhibition_module", "__file__": INH}
    exec(compile(open(INH, encoding="utf-8").read(), INH, "exec"), ins)
    info = ins["build"](opts, g, scene)

    out = opts.get("out", r"D:\Meshes\renders\inhibition.mp4")
    stem, _ = os.path.splitext(out)
    if opts.get("at"):
        # explicit frame numbers, so the wide beats can be checked at the frame
        # they actually settle on rather than at their midpoint
        scene.render.image_settings.file_format = "PNG"
        for fr in [int(x) for x in opts["at"].split(",")]:
            scene.frame_set(fr)
            scene.render.filepath = f"{stem}_f{fr}.png"
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"[inh] frame {fr} in {time.time()-t0:.0f}s -> {stem}_f{fr}.png",
                  flush=True)
    elif opts.get("beats"):
        # One frame from the middle of each named beat, all from a single scene
        # build. Looking at a frame per beat before launching the animation is
        # the one process rule this project has paid for most often.
        scene.render.image_settings.file_format = "PNG"
        for n in [int(x) for x in opts["beats"].split(",")]:
            a, bfr = info["beats"][n - 1]
            fr = int(round((a + bfr) / 2))
            scene.frame_set(fr)
            scene.render.filepath = f"{stem}_b{n}.png"
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"[inh] beat {n} frame {fr} in {time.time()-t0:.0f}s -> "
                  f"{stem}_b{n}.png", flush=True)
    elif opts.get("still"):
        scene.render.image_settings.file_format = "PNG"
        scene.frame_set(int(opts["still"]))
        scene.render.filepath = out
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[inh] still {opts['still']} in {time.time()-t0:.0f}s -> {out}",
              flush=True)
    else:
        scene.render.filepath = out
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "HIGH"
        print(f"[inh] {FRAMES} frames -> {out}", flush=True)
        t0 = time.time()
        bpy.ops.render.render(animation=True)
        el = time.time() - t0
        print(f"[inh] rendered in {el/60:.1f} min ({el/FRAMES:.1f}s per frame)",
              flush=True)
    print("[inh] DONE", flush=True)
    raise SystemExit(0)

hexcol, shade_ramp = g["hexcol"], g["shade_ramp"]
emissive_material, set_interp = g["emissive_material"], g["set_interp"]
GROUPS = g["GROUPS"]
root = bpy.data.objects.get("CA3_ROOT")
pivot = bpy.data.objects.get("pivot_thorny_pyramidals")

# ---- hide the decimated copy of the hero cell, it is about to be replaced -----------
for o in bpy.data.objects:
    if (HERO_ID in o.name and o.type == "MESH"
            and not o.name.startswith(("NATIVE_", "PARTNER_"))):
        o.hide_render = o.hide_viewport = True
        print(f"[full] hiding decimated {o.name}", flush=True)

# ---- bring in the native-resolution hero set ---------------------------------------
# The partner cache already holds these, imported and shaded the same way, so
# only import when they are not in the file yet.
def import_set(paths, prefix):
    got = []
    for p in paths:
        if p.name.endswith((".raw.obj", ".tmp.obj")):
            continue
        before = set(bpy.data.objects)
        bpy.ops.wm.obj_import(filepath=str(p))
        new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        for o in new:
            o.name = prefix + p.stem
            o.parent = pivot
            o.matrix_parent_inverse = Matrix.Identity(4)
        got.extend(new)
    return got


t0 = time.time()
preloaded = [o for o in bpy.data.objects if o.name.startswith("NATIVE_")]
if preloaded:
    hero_objs = [o for o in preloaded if "hero_" in o.name]
    fibre_objs = [o for o in preloaded if "fibre_" in o.name]
    fresh = []
else:
    fresh = import_set(sorted(HERO_DIR.glob("*.obj")), "NATIVE_")
    hero_objs = [o for o in fresh if "hero_" in o.name]
    fibre_objs = [o for o in fresh if "fibre_" in o.name]

partner_objs = []
if PARTNERS:
    partner_objs = [o for o in bpy.data.objects if o.name.startswith("PARTNER_")]
    if not partner_objs:
        partner_objs = import_set(sorted(PARTNER_DIR.glob("*.obj")), "PARTNER_")
        fresh += partner_objs

bpy.context.view_layer.update()      # matrix_world reads stale until this runs
print(f"[full] native hero: {len(hero_objs)} cell + {len(fibre_objs)} fibres"
      + (f" + {len(partner_objs)} partners" if PARTNERS else "")
      + f" in {time.time()-t0:.0f}s"
      + (" (from cache, no import)" if not fresh else ""), flush=True)

for o in fresh:
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.shade_smooth()

mat_hero = emissive_material("mat_native_hero", hexcol("#39A0FF"), 1.0)
# house gold, matching GROUPS["mossy_fibers"] now that the two have been
# reconciled; this used to be #E2AF5E, the value GROUPS carried
mat_fib = emissive_material("mat_native_fibre", hexcol("#E8A93A"), 1.0)
for o in hero_objs:
    o.data.materials.clear(); o.data.materials.append(mat_hero)
for o in fibre_objs:
    o.data.materials.clear(); o.data.materials.append(mat_fib)


def smooth_path(obj, data_path=None):
    """Continuous velocity through intermediate keyframes.

    Easing every key makes the object stop at each one. Auto-clamped bezier
    handles fit a single smooth curve through all of them, so speed carries
    across the joins and only the ends settle.
    """
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    for fc in ad.action.fcurves:
        if data_path and fc.data_path != data_path:
            continue
        kps = fc.keyframe_points
        for i, kp in enumerate(kps):
            kp.interpolation = "BEZIER"
            if i == 0 or i == len(kps) - 1:
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
                kp.easing = "EASE_IN_OUT"
            else:
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
        fc.update()


# ---- beats --------------------------------------------------------------------------
# Timed against a 480-frame / 20s cut. The opening used to sit on the thorns
# for nearly 6 seconds before anything happened; the fibres now start at 3s and
# the pull-back is compressed so the whole thing lands in 20 seconds.
#
# scope=partners keeps the 8s cell act EXACTLY as it was cut (192 frames, hold
# to 24, fibres 28..66) and appends the partner act on the end, rather than
# stretching the original beats over the longer running time. So the first 8
# seconds of the 14s version are the 8s version.
if PARTNERS:
    CELL_ACT = int(opts.get("cellact", 192))   # where the old shot used to end
    F = CELL_ACT / 480.0
else:
    CELL_ACT = FRAMES
    F = FRAMES / 480.0
HOLD_END = int(60 * F)                     # brief hold on the thorns
FIB_IN = (int(72 * F), int(165 * F))       # its own 6 fibres, from 3s
MF_IN = (int(195 * F), int(305 * F))       # all 688 mossy fibres
CELLS_IN = (int(265 * F), int(400 * F))    # every pyramidal cell and interneuron
# The first partner arrives at CELL_ACT, the exact frame the 8s cut used to
# end on, so nothing before that changes at all. The last fibre landed at
# frame 66, five seconds earlier, which is what Amy asked for: partners after
# the mossy fibres, not on top of them. PART_HOLD frames of stillness at the
# end so the finished picture is not cut off mid-arrival.
PART_HOLD = int(opts.get("parthold", 40))
PART_IN = (CELL_ACT, max(CELL_ACT + 24, FRAMES - PART_HOLD))
print(f"[full] hold to {HOLD_END}, own fibres {FIB_IN}, all MF {MF_IN}, "
      f"cells {CELLS_IN}"
      + (f", cell act ends {CELL_ACT}, partners {PART_IN}" if PARTNERS else ""),
      flush=True)


def fade_group(name, window, order_seed=0):
    objs = sorted(bpy.data.collections[name].objects, key=lambda o: o.name)
    objs = [o for o in objs if HERO_ID not in o.name]
    spec = GROUPS[name]
    rng = spec.get("per_cell_range")
    shades = shade_ramp(rng[0], rng[1], len(objs)) if rng else None
    a, b = window
    for i, o in enumerate(objs):
        col = shades[i] if shades else spec["color"]
        mat = emissive_material(f"mat_{name}_{i:04d}", col, 1.0)
        mat.blend_method = "OPAQUE"      # opaque frames render ~50x faster
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        o.data.materials.clear(); o.data.materials.append(mat)
        o.animation_data_clear()
        o.scale = (1, 1, 1)
        o.hide_render = o.hide_viewport = False
        t = ((i * 7919 + order_seed) % max(1, len(objs))) / max(1, len(objs))
        s = a + t * (b - a) * 0.55
        e = s + (b - a) * 0.45

        # Fade by brightness rather than transparency: drive Base Color and
        # Emission from black up to the cell's colour. Against a black
        # background this reads the same as an alpha fade, but every material
        # stays opaque so EEVEE never runs the blend path.
        black = (0.0, 0.0, 0.0, 1.0)
        full = (*col, 1.0)
        for socket, dark, lit in (("Base Color", black, full),
                                  ("Emission Color", black, full)):
            if socket not in bsdf.inputs:
                continue
            idx = list(bsdf.inputs).index(bsdf.inputs[socket])
            dp = f'nodes["Principled BSDF"].inputs[{idx}].default_value'
            bsdf.inputs[socket].default_value = dark
            mat.node_tree.keyframe_insert(data_path=dp, frame=int(s))
            bsdf.inputs[socket].default_value = lit
            mat.node_tree.keyframe_insert(data_path=dp, frame=int(e))
        for fc in mat.node_tree.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "SINE"; kp.easing = "EASE_IN_OUT"
    print(f"[full] {name}: {len(objs)} cells fading {window}", flush=True)


for c in scene.collection.children:
    for o in c.objects:
        o.hide_render = o.hide_viewport = True

# The native hero landed in one of those collections on import, so the blanket
# hide above caught it too and the opening frames came out black. Put it back.
for o in hero_objs + fibre_objs:
    o.hide_render = o.hide_viewport = False

if SCOPE == "all":
    fade_group("mossy_fibers", MF_IN, 11)
    for i, nm in enumerate(("thorny_pyramidals", "sparsely_thorny", "inhibitory")):
        fade_group(nm, CELLS_IN, 101 * (i + 1))
else:
    print(f"[full] scope={SCOPE}: population stays hidden, frames stay opaque",
          flush=True)
for o in bpy.data.objects:
    if HERO_ID in o.name and not o.name.startswith(("NATIVE_", "PARTNER_")):
        o.hide_render = o.hide_viewport = True

cloud = bpy.data.objects.get("SYNAPSES")
if cloud:
    cloud.hide_render = cloud.hide_viewport = True

# Order the fibres by how close their contacts sit to the thorn cluster, so the
# first one to arrive is the one already in frame. Alphabetical order put the
# most distant fibre (46.7um away, off screen) first.
_order = open('D:/Meshes/renders/fibre_order.txt').read().strip().split(',')
_rank = {sid: i for i, sid in enumerate(_order)}
fibre_objs.sort(key=lambda o: _rank.get(
    next((t for t in _order if t in o.name), ""), 99))
print("[full] fibre arrival order: "
      + ", ".join(o.name.replace("NATIVE_fibre_", "")[-6:] for o in fibre_objs),
      flush=True)

for i, o in enumerate(fibre_objs):
    t = i / max(1, len(fibre_objs) - 1)
    a, b = FIB_IN
    s = a + t * (b - a) * 0.5
    o.scale = (0, 0, 0); o.keyframe_insert(data_path="scale", frame=int(s))
    o.scale = (1, 1, 1); o.keyframe_insert(data_path="scale", frame=int(s + (b - a) * 0.5))
    set_interp(o, "CUBIC", "EASE_OUT")

# ---- camera: thorns to the whole volume ---------------------------------------------
SYN = np.load(os.path.join(r"D:\Meshes", "renders", "hero_synapses.npy"))
m0 = np.array(hero_objs[0].matrix_world)
aim = (SYN @ m0[:3, :3].T + m0[:3, 3]).mean(axis=0)
thorns = Vector((float(aim[0]), float(aim[1]), float(aim[2])))
print(f"[full] thorn cluster at {tuple(round(float(x),2) for x in aim)}", flush=True)


# ---- the 56 partner cells -----------------------------------------------------------
def fade_partners(objs, window, hex_colour):
    """Bring the partners up out of nothing, nearest to the thorns first.

    NOT the black-Base-Color trick fade_group uses. That works for the wide
    population shot because everything there fades together against empty
    space, but these 56 cells are interleaved with the hero: a "black" cell is
    still solid geometry that occludes the blue dendrites behind it, still
    catches a rim off the key light through its subsurface, and still casts
    shadows. Rendered that way, frame 120 came out as a wall of dark tissue
    with the hero buried in it. Verified by looking at the frame.

    So this animates Alpha under EEVEE Next's DITHERED surface render method.
    Dithered is stochastic alpha, not sorted blending: it runs on the opaque
    pipeline and the 64 TAA samples resolve the dither, so it costs far less
    than BLENDED while alpha 0 genuinely means "not there". hide_render is
    keyed off as well, on CONSTANT interpolation, so each cell is not even
    rasterised or shadow-mapped until its own moment.

    Arrival order is by distance from the thorn cluster rather than by segment
    id, for the same reason the fibres are ordered that way: alphabetical order
    starts with whichever cell happens to sort first, which is usually one that
    is not even on screen yet.
    """
    col = hexcol(hex_colour)          # 3 floats; the sockets want 4
    ranked = []
    for o in objs:
        n = len(o.data.vertices)
        co = np.empty(n * 3, dtype=np.float64)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        if n > 3000:
            co = co[np.linspace(0, n - 1, 3000).astype(int)]
        # o.data.vertices is raw OBJ file space; matrix_world carries the
        # importer's 90 deg X rotation AND the root scale. Go through the
        # matrix, never convert by hand.
        m = np.array(o.matrix_world)
        w = np.median(co @ m[:3, :3].T + m[:3, 3], axis=0)
        ranked.append((float(np.linalg.norm(w - np.array(thorns))), o))
    ranked.sort(key=lambda t: t[0])

    a, b = window
    for i, (dist, o) in enumerate(ranked):
        mat = emissive_material(f"mat_partner_{i:03d}", col, 1.0)
        # In 4.4 EEVEE Next, Material.blend_method still exists but does
        # nothing; the live control is surface_render_method, DITHERED or
        # BLENDED. DITHERED is stochastic alpha on the opaque pipeline, which
        # is what makes this fade cheap. Set both, guarded, so the file keeps
        # working if it is ever opened under legacy EEVEE.
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
        if hasattr(mat, "use_transparent_shadow"):
            mat.use_transparent_shadow = True
        mat.blend_method = "HASHED"
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        o.data.materials.clear(); o.data.materials.append(mat)
        o.animation_data_clear()
        o.scale = (1, 1, 1)

        t = i / max(1, len(ranked) - 1)
        s = int(a + t * (b - a) * 0.55)
        e = int(s + (b - a) * 0.45)

        idx = list(bsdf.inputs).index(bsdf.inputs["Alpha"])
        dp = f'nodes["Principled BSDF"].inputs[{idx}].default_value'
        bsdf.inputs["Alpha"].default_value = 0.0
        mat.node_tree.keyframe_insert(data_path=dp, frame=s)
        bsdf.inputs["Alpha"].default_value = PARTNER_ALPHA
        mat.node_tree.keyframe_insert(data_path=dp, frame=e)
        for fc in mat.node_tree.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "SINE"; kp.easing = "EASE_IN_OUT"

        # Absent, not merely transparent, until its own moment. Booleans have
        # to be CONSTANT or Blender interpolates them into a half-hidden state.
        o.hide_render = o.hide_viewport = True
        o.keyframe_insert(data_path="hide_render", frame=1)
        o.keyframe_insert(data_path="hide_viewport", frame=1)
        o.hide_render = o.hide_viewport = False
        o.keyframe_insert(data_path="hide_render", frame=s)
        o.keyframe_insert(data_path="hide_viewport", frame=s)
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    print(f"[full] partners: {len(ranked)} cells in {hex_colour}, fading "
          f"{window}, nearest {ranked[0][0]:.2f} to farthest "
          f"{ranked[-1][0]:.2f} units from the thorns", flush=True)


if PARTNERS:
    if not partner_objs:
        raise SystemExit("scope=partners but no PARTNER_ meshes were loaded")
    fade_partners(partner_objs, PART_IN, PARTNER_HEX)

for o in list(bpy.data.objects):
    if o.type in {"LIGHT", "CAMERA"} or o.name in {"CAM_ORBIT", "HERO_ORBIT", "HERO_TARGET"}:
        bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.object.empty_add(type="PLAIN_AXES", location=thorns)
target = bpy.context.active_object; target.name = "SHOT_TARGET"
bpy.ops.object.empty_add(type="PLAIN_AXES", location=thorns)
orbit = bpy.context.active_object; orbit.name = "SHOT_ORBIT"

NEAR = 0.55
# 34 frames the whole volume; 7.5 frames just this cell and its fibres.
# 10.5 frames the cell plus all 56 partners. The partner set measures 4.6 x
# 1.1 x 4.4 blender units and reaches about 3.2 units from the aim point, so
# on paper a 55mm lens wants 13 to 15. Rendered and looked at, 13 leaves a
# third of a portrait frame empty top and bottom and shrinks the hero to
# nothing; 10.5 fills the frame and loses only a couple of outer tips, which
# this project already does with the hero itself.
FAR = float(opts.get("far", 34.0 if SCOPE == "all"
                     else 10.5 if PARTNERS else 7.5))
# Where the original 8s cut ended. Holding this as an intermediate key means
# the first 8 seconds still land on exactly the framing Amy signed off on, and
# the extra 6 seconds are a continuation rather than a re-time.
FAR_CELL = float(opts.get("farcell", 7.5))
bpy.ops.object.camera_add(location=(0.0, -NEAR, NEAR * 0.15))
cam = bpy.context.active_object; cam.name = "SHOT_CAM"
cam.data.lens = 55
cam.parent = orbit
tc = cam.constraints.new(type="TRACK_TO")
tc.target = target; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"
scene.camera = cam

# Three keys, not four. Each extra key is another place the curve can kink,
# and the pull-back reads better as one continuous acceleration outward.
# scope=partners adds one more, at the old end frame, and smooth_path's
# auto-clamped handles keep the velocity continuous through it.
keys = [(1, (0.0, -NEAR, NEAR * 0.15)),
        (HOLD_END, (0.0, -NEAR * 1.30, NEAR * 0.20))]
if PARTNERS and CELL_ACT < FRAMES:
    keys.append((CELL_ACT, (0.0, -FAR_CELL, FAR_CELL * 0.20)))
keys.append((FRAMES, (0.0, -FAR, FAR * 0.20)))
for fr, loc in keys:
    cam.location = loc
    cam.keyframe_insert(data_path="location", frame=fr)
smooth_path(cam, "location")
print("[full] camera keys: "
      + ", ".join(f"f{fr}@{-loc[1]:.2f}" for fr, loc in keys), flush=True)

orbit.rotation_euler = (0, 0, math.radians(-10))
orbit.keyframe_insert(data_path="rotation_euler", frame=1)
if PARTNERS and CELL_ACT < FRAMES:
    # keep the same -10 to +14 drift across the original 8s, then let it carry
    # on to 22 so the partners get some parallax as they arrive
    orbit.rotation_euler = (0, 0, math.radians(14))
    orbit.keyframe_insert(data_path="rotation_euler", frame=CELL_ACT)
    orbit.rotation_euler = (0, 0, math.radians(22))
else:
    orbit.rotation_euler = (0, 0, math.radians(14))
orbit.keyframe_insert(data_path="rotation_euler", frame=FRAMES)
smooth_path(orbit, "rotation_euler")

# the aim drifts from the thorns out to the centre of the whole volume
target.location = thorns
target.keyframe_insert(data_path="location", frame=1)
target.location = thorns
target.keyframe_insert(data_path="location", frame=int(FRAMES * 0.4))
target.location = (Vector((0.0, 0.0, 0.0)) if SCOPE == "all" else thorns)
target.keyframe_insert(data_path="location", frame=FRAMES)
smooth_path(target, "location")

g["build_world"](scene)
g["build_lights"](scene, g["TARGET_SIZE"], root)
g["apply_render_settings"](scene)

# transparent=1 keeps the alpha channel instead of laying black behind, so the
# still can sit on a page with no box around it. apply_render_settings normally
# composites a black plate under the transparent film; drop that node and wire
# the glare straight to the output.
if opts.get("transparent") in ("1", "true", "yes"):
    nt = scene.node_tree
    comp = next(n for n in nt.nodes if n.type == "COMPOSITE")
    glare = next((n for n in nt.nodes if n.type == "GLARE"), None)
    over = next((n for n in nt.nodes if n.type == "ALPHAOVER"), None)
    if over is not None:
        for link in list(nt.links):
            if link.to_node is comp or link.from_node is over:
                nt.links.remove(link)
        nt.links.new(glare.outputs["Image"], comp.inputs["Image"])
        nt.nodes.remove(over)
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    print("[full] transparent output: alpha kept, no black plate", flush=True)

out = opts.get("out", r"D:\Meshes\renders\hero_full.mp4")
scene.render.filepath = out
still = opts.get("still")
if still:
    scene.render.image_settings.file_format = "PNG"
    scene.frame_set(int(still))
    print(f"[full] still {still} -> {out}", flush=True)
    t0 = time.time(); bpy.ops.render.render(write_still=True)
    print(f"[full] rendered in {time.time()-t0:.0f}s", flush=True)
else:
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    print(f"[full] {FRAMES} frames -> {out}", flush=True)
    t0 = time.time(); bpy.ops.render.render(animation=True)
    el = time.time() - t0
    print(f"[full] rendered in {el/60:.1f} min ({el/FRAMES:.1f}s per frame)", flush=True)
print("[full] DONE", flush=True)
