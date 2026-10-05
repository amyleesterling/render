"""
A band of light travels the cell layer, so the convergence result is watched, not asserted.

  blender --background --python gradient_sweep.py -- [key=val]

  frames=300  res=1920x1080  samples=64
  camdist=1.52  shifty=-0.045
  band=90                 half width of the travelling band, in um of arc
  peak=2.6                emission strength at the centre of the band
  png=1                   write a PNG sequence instead of an mp4, for the post pass
  out=path

WHY THIS SHOT EXISTS. The still says the gradient is not monotonic, but a caption
asserting "50, then 33, then 72" is a claim the viewer has to take on trust. Here
the band walks the arc from one end to the other and lights each cell as it
passes, so the viewer sees for themselves that gold clusters at both limbs and the
apex is mostly blue. The readout is composited afterwards by sweep_readout.py,
which recomputes the median from the same CSV, so the number on screen and the
cells lit under it cannot drift apart.

WHAT THE BAND DOES NOT ENCODE. Emission peak is the SAME for every cell,
deliberately. Brightness is position along the arc only. Convergence is carried by
hue alone, exactly as in the still, so nothing is double encoded and a bright cell
never reads as a high count cell.

NOTE ON DUPLICATION. read_sample and ramp are copied from render_gradient.py
rather than shared, because that file is inside a running overnight queue and
editing it mid flight risks the job that has not started yet. Factor them into a
gradient_common.py once the GPU is idle.
"""
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)

GRAD = Path(r"D:\Meshes\gradient")
CSV = Path(r"D:\Meshes\renders\gradient_sample.csv")
CACHE = Path(r"D:\Meshes\gradient_scene.blend")
Z_MIN_UM = 60.0
COL_LO, COL_MID, COL_HI = (0x1D, 0x35, 0x8F), (0x8E, 0x46, 0xC0), (0xFF, 0xC2, 0x4A)

HOUSE = r"D:\Meshes\ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": HOUSE}
exec(compile(open(HOUSE, encoding="utf-8").read(), HOUSE, "exec"), ns)
g = ns["build"].__globals__

emissive_material = g["emissive_material"]
build_world = g["build_world"]
build_lights = g["build_lights"]
apply_render_settings = g["apply_render_settings"]
world_bounds = g["world_bounds"]
TARGET_SIZE = g["TARGET_SIZE"]

if "res" in opts:
    w, h = opts["res"].split("x")
    g["RESOLUTION"] = (int(w), int(h))
g["SAMPLES"] = int(opts.get("samples", 64))

FRAMES = int(opts.get("frames", 300))
BAND = float(opts.get("band", 90.0))
PEAK = float(opts.get("peak", 0.45))
# how dark a cell sits when the band is nowhere near it. Not zero: the arch has to
# stay legible as a whole shape, or the shot becomes a light crawling through a void
# and the viewer loses the context the result depends on.
DIM = float(opts.get("dim", 0.12))


def read_sample():
    rows = CSV.read_text(encoding="utf-8").strip().splitlines()
    head = rows[0].split(",")
    i_id, i_n = head.index("root_id"), head.index("n_mf")
    i_z, i_arc = head.index("soma_z_nm"), head.index("arc_um")
    out = {}
    for r in rows[1:]:
        f = r.split(",")
        if float(f[i_z]) / 1000.0 < Z_MIN_UM:
            continue
        if not (GRAD / f"{f[i_id]}.obj").exists():
            continue
        out[f[i_id]] = (int(float(f[i_n])), float(f[i_arc]))
    return out


def ramp(t):
    """Three explicit stops lerped in sRGB. Never HSV: see RENDERING_NEURONS.md 2."""
    stops = ((0.0, COL_LO), (0.5, COL_MID), (1.0, COL_HI))
    t = min(max(t, 0.0), 1.0)
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            return tuple(((a + (b - a) * u) / 255.0) ** 2.2 for a, b in zip(c0, c1))
    return tuple((c / 255.0) ** 2.2 for c in stops[-1][1])


cells = read_sample()
if not cells:
    raise SystemExit("No cells matched. Check gradient_sample.csv and D:/Meshes/gradient.")
if not CACHE.exists():
    raise SystemExit(f"{CACHE} is missing. Run render_gradient.py once to build it.")

t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=str(CACHE))
scene = bpy.context.scene
objs = [o for o in bpy.data.objects if o.type == "MESH"]
print(f"[sweep] cache opened in {time.time() - t0:.0f}s, {len(objs)} meshes, "
      f"{len(cells)} in the sample", flush=True)

arcs = np.array([v[1] for v in cells.values()])
ARC_LO, ARC_HI = float(arcs.min()), float(arcs.max())
# The band starts and ends fully outside the arc, so the first and last cells get a
# complete pass instead of opening or closing halfway through their own rise.
SWEEP_LO, SWEEP_HI = ARC_LO - BAND, ARC_HI + BAND
print(f"[sweep] arc {ARC_LO:.0f} to {ARC_HI:.0f} um, band half width {BAND:.0f}",
      flush=True)


def frame_at(arc_pos):
    """Which frame the band centre sits at a given arc position."""
    u = (arc_pos - SWEEP_LO) / (SWEEP_HI - SWEEP_LO)
    return 1 + u * (FRAMES - 1)


nmax = max(v[0] for v in cells.values())
denom = np.log10(nmax + 1.0)
for m in list(bpy.data.materials):
    if m.name.startswith("mat_"):
        bpy.data.materials.remove(m)

lit = 0
for o in objs:
    seg = o.name.replace("grad_", "")
    if seg not in cells:
        continue
    n, arc = cells[seg]
    col = ramp(float(np.log10(n + 1.0) / denom))
    mat = emissive_material(f"mat_sweep_{seg}", col, 1.0)
    o.data.materials.clear()
    o.data.materials.append(mat)

    bsdf = mat.node_tree.nodes["Principled BSDF"]
    base_col = bsdf.inputs["Base Color"]

    # The band does NOT add light, it withholds it. Adding emission was the first
    # attempt and it failed for a reason worth recording: pushing a cell brighter
    # drives every channel toward the clip point, so hue washes out exactly inside
    # the band, which is the one place the viewer is looking, and hue is the only
    # thing carrying convergence. Measured at peak 2.6 it blew 23,580 pixels to
    # pure white. Dimming instead means a lit cell is exactly its colour in the
    # still and nothing can ever exceed it.
    dim = tuple(c * DIM for c in col)
    f_in = frame_at(arc - BAND)
    f_mid = frame_at(arc)
    f_out = frame_at(arc + BAND)
    for f, v in ((f_in, dim), (f_mid, col), (f_out, dim)):
        base_col.default_value = (*v, 1.0)
        base_col.keyframe_insert("default_value", frame=int(round(f)))

    # a small emission bump on top, so a passing cell reads as lit rather than
    # merely less dark. Kept low deliberately: this is an accent, not the signal.
    strength = bsdf.inputs.get("Emission Strength")
    if strength is not None:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*col, 1.0)
        rest = float(strength.default_value)
        for f, v in ((f_in, rest), (f_mid, rest + PEAK), (f_out, rest)):
            strength.default_value = v
            strength.keyframe_insert("default_value", frame=int(round(f)))

    for fc in mat.node_tree.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation, kp.easing = "SINE", "EASE_IN_OUT"
    lit += 1

print(f"[sweep] {lit} cells keyframed, peak +{PEAK}", flush=True)

# ---- camera, held still: the band moves, not the viewer -------------------------------
for o in list(bpy.data.objects):
    if o.type in {"LIGHT", "CAMERA"} or o.name == "CAM_ORBIT":
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
dist = radius * float(opts.get("camdist", 1.52)) / np.tan(np.radians(22.0))
cam.location = centre + Vector((0.0, -dist, 0.0))
cam.data.shift_y = float(opts.get("shifty", -0.045))
cam.rotation_euler = (centre - cam.location).normalized().to_track_quat("-Z", "Y").to_euler()

build_world(scene)
build_lights(scene, TARGET_SIZE)
apply_render_settings(scene)

scene.frame_start, scene.frame_end = 1, FRAMES
scene.render.fps = g["FPS"]

out = opts.get("out", r"D:\Meshes\renders\gradient_sweep.mp4")
scene.render.filepath = out
as_png = opts.get("png", "0") not in ("0", "false", "no")
if as_png:
    scene.render.image_settings.file_format = "PNG"
else:
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"

still = opts.get("still")
if still:
    scene.render.image_settings.file_format = "PNG"
    scene.frame_set(int(still))
    bpy.ops.render.render(write_still=True)
    print(f"[sweep] test frame {still} -> {out}", flush=True)
else:
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    el = time.time() - t0
    print(f"[sweep] {FRAMES} frames in {el / 60:.1f} min "
          f"({el / FRAMES:.1f}s per frame) -> {out}", flush=True)
print("[sweep] DONE", flush=True)
