"""Hairy brain, 360 degree turntable.

A FreeSurfer pial surface covered in short hair strands, each strand coloured by
its own direction with the diffusion-MRI convention (red left-right, green
front-back, blue up-down). Rendered in Cycles on a white studio floor.

    blender --background --python hairy_brain_360.py -- stills=1,180 res=960x540
    blender --background --python hairy_brain_360.py -- frames=360 out=D:\Meshes\renders\hairy_brain_360.mp4

Arguments (key=value after "--"):
    stills    comma list of frames to render as PNG beats, from one build
    frames    turntable length (default 360, one degree per frame, 24 fps)
    res       WxH (default 1920x1080)
    samples   Cycles samples (default 128)
    strands   hair strands PER HEMISPHERE (default 1_200_000)
    length    strand length in scene units, 1 unit = 100 mm (default 0.020)
    radius    strand radius at the root (default 0.0006)
    out       mp4 path; PNG frames go next to it in <name>_frames
    device    GPU (default) or CPU
    debug     print what the depsgraph exposes before rendering
    views     comma list of coronal,sagittal,axial: straight-on stills, no turntable

The mesh is in RAS millimetres (x right, y anterior, z superior). It is imported
with forward=Y, up=Z so RAS maps straight onto Blender axes with NO rotation on
the object, then scaled by 0.01 so the brain is about 1.4 units wide. Bounds are
asserted after import, not assumed.

The fur lives on its own Curves object. A geometry-nodes curves component left
inside a mesh object's modifier output was never picked up by Cycles here (the
render log listed only the two pial meshes and the floor), while a Curves object
is synced as hair every time.
"""
import math
import os
import subprocess
import sys
import time

import bpy
from pathlib import Path
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(kv.split("=", 1) for kv in argv if "=" in kv)

SUB = r"C:\Users\amyle\Downloads\human brain subcortical_obj\subcortical_obj"
MESHES = [
    # FreeSurfer pial surfaces are cerebral cortex only ("our brain is missing
    # cerebellum", Amy 4 Sept 2026). The aseg-derived cerebellum and brainstem
    # meshes in the same download share the RAS mm space: measured cerebellum
    # z -63..-5, y -98..-32, tucked under the occipital pole at y -100.
    (r"C:\Users\amyle\Downloads\pial_Full_obj\pial_Full_obj\human brain lh.pial.obj", "pial_lh"),
    (r"C:\Users\amyle\Downloads\pial_Full_obj\pial_Full_obj\human bran rh.pial.obj", "pial_rh"),
    (SUB + r"\Left-Cerebellum-Cortex.obj", "cbm_lh"),
    (SUB + r"\Right-Cerebellum-Cortex.obj", "cbm_rh"),
    (SUB + r"\Brain-Stem.obj", "brainstem"),
]
SCALE = 0.01                                  # mm -> units, 1 unit = 100 mm
FRAMES = int(opts.get("frames", 360))
FPS = 24
RES = tuple(int(v) for v in opts.get("res", "1920x1080").split("x"))
SAMPLES = int(opts.get("samples", 128))
STRANDS = int(opts.get("strands", 1_200_000))
LENGTH = float(opts.get("length", 0.010))
RADIUS = float(opts.get("radius", 0.0006))
DEVICE = opts.get("device", "GPU").upper()
OUT = opts.get("out", r"D:\Meshes\renders\hairy_brain_360.mp4")
ELEVATION_DEG = 14.0
CAMH = opts.get("camh")                       # 0..100, % of brain height; None = old 14 deg elevation
CAMDIST = float(opts.get("camdist", "1.0"))   # multiplier on the solved distance
SEED = 7

t_start = time.time()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS


def log(msg):
    print(f"[hair] {msg}", flush=True)


def sock(node, name, output=False):
    """First ENABLED socket with this name. Random Value and Store Named
    Attribute carry one hidden socket per data type under the same name."""
    coll = node.outputs if output else node.inputs
    for s in coll:
        if s.name == name and s.enabled:
            return s
    raise KeyError(f"{node.name} has no enabled socket {name!r}")


# ---------------------------------------------------------------- meshes
def import_pial(path):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path, forward_axis="Y", up_axis="Z")
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    assert len(new) == 1, f"expected one mesh from {path}, got {len(new)}"
    obj = new[0]
    # The playbook's trap: the OBJ importer may express its axis flip as an
    # object ROTATION. With forward=Y up=Z there should be none. Check it.
    assert all(abs(r) < 1e-6 for r in obj.rotation_euler), \
        f"importer put a rotation on {obj.name}: {tuple(obj.rotation_euler)}"
    obj.scale = (SCALE, SCALE, SCALE)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)
    return obj


hemis = []
for path, tag in MESHES:
    o = import_pial(path)
    o.name = tag
    hemis.append(o)

# world-space bounds, measured
allv = [o.matrix_world @ Vector(c) for o in hemis for c in o.bound_box]
lo = Vector((min(v.x for v in allv), min(v.y for v in allv), min(v.z for v in allv)))
hi = Vector((max(v.x for v in allv), max(v.y for v in allv), max(v.z for v in allv)))
ext = hi - lo
center = (lo + hi) / 2
log(f"bounds lo={tuple(round(c, 3) for c in lo)} hi={tuple(round(c, 3) for c in hi)} "
    f"extent={tuple(round(c, 3) for c in ext)}")
# RAS in mm: width ~139, length ~170, height ~119 -> scaled 1.39 / 1.70 / 1.19
assert 1.2 < ext.x < 1.6, f"width {ext.x:.2f}: axis mapping is wrong"
assert 1.5 < ext.y < 1.9, f"length {ext.y:.2f}: axis mapping is wrong"
assert 1.0 < ext.z < 1.5, f"height {ext.z:.2f}: axis mapping is wrong"
# left hemisphere must sit at negative x, right at positive x
lx = (hemis[0].matrix_world @ Vector(hemis[0].bound_box[0])).x
rx = (hemis[1].matrix_world @ Vector(hemis[1].bound_box[6])).x
assert lx < -0.5 and rx > 0.5, f"hemispheres swapped or mirrored: lh min x {lx:.2f}, rh max x {rx:.2f}"

def store_peakness(obj, iterations=int(opts.get("peakiters", 60))):
    """Gyral crown vs sulcal fundus, per vertex, from geometry alone.

    Laplacian-smooth a copy of the vertices; where the real surface sits
    OUTSIDE the smoothed one (along the normal) it is a crown, where it sits
    inside it is a fundus. Normalised by percentiles to 0..1 and stored as the
    float attribute "peak". Ambient occlusion could not do this on dense fur:
    neighbouring strands shade every point equally.
    """
    import numpy as np
    me = obj.data
    n = len(me.vertices)
    P = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", P)
    P = P.reshape(n, 3)
    N = np.empty(n * 3, dtype=np.float64)
    me.vertex_normals.foreach_get("vector", N)
    N = N.reshape(n, 3)
    E = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", E)
    E = E.reshape(-1, 2)
    deg = np.bincount(E.ravel(), minlength=n).astype(np.float64)
    deg[deg == 0] = 1.0
    S = P.copy()
    for _ in range(iterations):
        acc = np.zeros_like(S)
        np.add.at(acc, E[:, 0], S[E[:, 1]])
        np.add.at(acc, E[:, 1], S[E[:, 0]])
        S = 0.5 * S + 0.5 * acc / deg[:, None]
    d = np.einsum("ij,ij->i", P - S, N)
    lo_, hi_ = np.percentile(d, 5), np.percentile(d, 95)
    peak = np.clip((d - lo_) / max(hi_ - lo_, 1e-9), 0.0, 1.0)
    attr = me.attributes.new("peak", "FLOAT", "POINT")
    attr.data.foreach_set("value", peak.astype(np.float32))
    log(f"{obj.name}: peak from {iterations} smoothing passes, crown offset "
        f"{lo_ * 100:.1f}..{hi_ * 100:.1f} mm, {100 * (peak > 0.65).mean():.0f}% of vertices above 0.65")


for o in hemis:
    store_peakness(o)

area = sum(sum(p.area for p in o.data.polygons) for o in hemis)
log(f"{sum(len(o.data.polygons) for o in hemis):,} faces, surface area {area:.2f} units^2 "
    f"({area * 1e4 / 100:.0f} cm^2)")
density = (STRANDS * 2) / area           # strands per unit^2, both hemispheres
log(f"{STRANDS:,} strands per hemisphere -> density {density:,.0f} per unit^2")


# ---------------------------------------------------------------- materials
math_pi_2 = math.pi / 2
math_pi = math.pi

# Amy's palette, 4 Sept 2026: lean purple, hot pink, all the blues, teal,
# turquoise, blue-green, golden yellow. Less green. Nothing near red, which
# reads as blood. So direction no longer maps straight to RGB; it drives a
# position along this ramp instead.
# First pass had blue over 40% of the ramp and a strong vertical pull, and the
# lateral view came out almost entirely blue. Ramp rebalanced, pull weakened.
PALETTE = [
    (0.00, (1.00, 0.22, 0.60)),   # hot pink
    (0.25, (0.60, 0.20, 0.90)),   # purple
    (0.50, (0.15, 0.38, 0.98)),   # blue: vertical strands are pulled here
    (0.72, (0.10, 0.75, 0.92)),   # turquoise
    (0.86, (0.05, 0.62, 0.56)),   # teal
    (1.00, (0.15, 0.38, 0.98)),   # blue again next to gold, so the thin blend is grey not olive
]
GOLD = tuple(float(v) for v in opts.get("gold", "1.00,0.86,0.42").split(","))  # golden yellow, own channel
GOLD_MAX = float(opts.get("goldmax", "1.0"))   # how far a gold strand goes to pure gold
BLUE_T = 0.5                      # ramp position vertical strands are pulled to


MODE = opts.get("palette", "vivid")       # vivid | monsters | bluegold | blue | september | pastel | rainbow | amy
# Monsters Inc (Amy 6 Sept: "mostly blue, BRIGHT blue, and purple and yellow").
# Same mechanism as amy/bluegold: this ramp, plus yellow as its own channel
# on the gyral crowns. Blue at 0.5 so the vertical pull lands on blue.
MONSTERS = [
    # first pass was mostly yellow with pale blue: blues now saturated, and the
    # yellow threshold sits at the very top of the crown range
    (0.00, (0.08, 0.55, 1.00)),   # bright blue
    (0.22, (0.48, 0.18, 0.95)),   # purple
    (0.38, (0.15, 0.65, 1.00)),   # bright blue, lighter
    (0.50, (0.05, 0.45, 1.00)),   # bright blue
    (0.66, (0.58, 0.35, 1.00)),   # violet
    (0.80, (0.10, 0.60, 1.00)),   # bright blue
    (1.00, (0.05, 0.40, 1.00)),   # deep bright blue, next to the yellow
]
# Amy 4 Sept 2026, from the amy-palette fur: "replace the pink with yellow:
# purples, blues (many blues, especially light bright blues), teal, golden
# yellows". Cyclic. Yellow sits between two light blues so its blends are a
# short grey, never green or olive.
BLUEGOLD = [
    # the ramp for the amy mechanism: NO gold in here, gold is its own channel
    # (see GOLD below), so it never blends into khaki. Blue at both ends,
    # because that is what sits next to the gold.
    (0.00, (0.45, 0.80, 1.00)),   # light bright blue (where the pink was)
    (0.20, (0.42, 0.15, 0.75)),   # deep purple
    (0.38, (0.15, 0.28, 0.95)),   # royal blue
    (0.55, (0.55, 0.85, 1.00)),   # sky blue
    (0.72, (0.05, 0.62, 0.60)),   # teal
    (0.86, (0.68, 0.55, 0.95)),   # light purple
    (1.00, (0.10, 0.45, 0.98)),   # cobalt, next to the gold
]
STYLE = opts.get("style", "fur")           # fur | crystal | holo_dots | holo_blue | holo_amber | holo_wire | holo_points
HOLOCOL = opts.get("holocol", "blue")      # blue | amber, for holo_dots
HOLO = STYLE.startswith("holo")
# all shades of blue (Amy 4 Sept 2026), cyclic
BLUE = [
    # first pass read as one flat royal blue: stops now alternate dark and
    # light so neighbouring gyri differ
    (0.00, (0.04, 0.08, 0.42)),   # navy
    (0.18, (0.08, 0.46, 0.96)),   # cobalt
    (0.35, (0.74, 0.90, 1.00)),   # ice
    (0.50, (0.42, 0.74, 1.00)),   # sky
    (0.65, (0.12, 0.24, 0.85)),   # royal
    (0.82, (0.55, 0.65, 1.00)),   # powder
    (1.00, (0.04, 0.08, 0.42)),   # navy again
]
# "early morning sun in September" (Amy, 4 Sept 2026): low amber sun, honey
# and pale gold where the light lands, dawn-sky blue and lavender haze in the
# shadow side, a dusky rose in the turn. Cyclic; no salmon or peach.
SEPTEMBER = [
    # second reading ("far too fleshy, think of it from a different angle"):
    # the SHADOW side of a September dawn. Body in cool blues and lavender;
    # the sun is not a ramp stop at all, it is a thin gold catch applied only
    # where a strand faces the low sun (SUN_DIR, below).
    (0.00, (0.18, 0.20, 0.58)),   # indigo, the sky straight up
    (0.22, (0.40, 0.48, 0.96)),   # periwinkle
    (0.45, (0.50, 0.76, 1.00)),   # sky blue
    (0.65, (0.78, 0.88, 0.98)),   # silver, mist
    (0.84, (0.62, 0.52, 0.92)),   # cold lavender
    (1.00, (0.18, 0.20, 0.58)),   # indigo again
]
SUN_DIR = Vector((0.70, -0.60, 0.32)).normalized()   # low, front right
SUN_GOLD = (1.00, 0.82, 0.38)
# Amy 4 Sept 2026, after the pastels: "hot pink, orange, warm yellow,
# teal-green, turquoise, sky blue, rich blue, royal blue, light purple, deep
# purple". In that order it is a hue circle with red and grass green cut out,
# so it runs as a cyclic ramp. Short bands where it must cross red-orange and
# yellow-green.
VIVID = [
    (0.00, (1.00, 0.18, 0.62)),   # hot pink
    (0.09, (1.00, 0.50, 0.10)),   # orange
    (0.18, (1.00, 0.82, 0.15)),   # warm yellow
    (0.30, (0.08, 0.68, 0.50)),   # teal-green
    (0.40, (0.10, 0.82, 0.85)),   # turquoise
    (0.50, (0.35, 0.72, 1.00)),   # sky blue
    (0.60, (0.12, 0.40, 0.95)),   # rich blue
    (0.70, (0.18, 0.20, 0.85)),   # royal blue
    (0.80, (0.66, 0.50, 0.95)),   # light purple
    (0.90, (0.40, 0.10, 0.70)),   # deep purple
    (1.00, (1.00, 0.18, 0.62)),   # hot pink again
]
# Pastels, Amy 4 Sept 2026 ("EWWW too pink, like rotting tissue. how about
# pastels?"). Cyclic: last stop equals the first. No peach or salmon anywhere,
# those are the flesh tones. Pink is a cool pink, kept short.
PASTEL = [
    (0.00, (0.70, 0.58, 0.98)),   # lavender
    (0.22, (0.50, 0.78, 1.00)),   # baby blue
    (0.44, (0.50, 0.95, 0.76)),   # mint
    (0.64, (1.00, 0.94, 0.45)),   # lemon
    (0.82, (0.98, 0.64, 0.90)),   # cool pink
    (1.00, (0.70, 0.58, 0.98)),   # lavender again
]
HUE_TILT = float(opts.get("huetilt", "0.3"))
SAT = float(opts.get("sat", "0.65"))
LIGHT = float(opts.get("light", "0.80" if opts.get("palette") in ("bluegold", "monsters") else "0.60"))
# Studio HDRI instead of the four area lights (Amy 4 Sept: "the lighting
# doesn't look good, studio light"). The map lights the scene; the camera still
# sees the flat grey backdrop through the Is Camera Ray mix.
HDRI = opts.get("hdri", "")
HDRI_STRENGTH = float(opts.get("hdristrength", "1.0"))
HDRI_ROT = float(opts.get("hdrirot", "0"))   # multiplier on the whole rig; 1.0 was overlit (Amy 4 Sept)


def direction_colour(nt, vec_socket):
    """Direction -> colour. Two modes.

    rainbow (default, Amy 4 Sept 2026 "just make it full rainbow"): hue runs
    once round the wheel with the compass bearing the strand faces, so each
    side of the brain gets its own hue and a turntable cycles the whole
    spectrum. Strands pointing straight up or down lose saturation and go
    pastel, which lifts the gyral crowns.

    amy: the curated ramp (pink, purple, blue, turquoise, teal, gold).
    """
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(vec_socket, sep.inputs["Vector"])

    def math(op, a, b=None, const=None):
        m = nt.nodes.new("ShaderNodeMath")
        m.operation = op
        nt.links.new(a, m.inputs[0])
        if b is not None:
            nt.links.new(b, m.inputs[1])
        elif const is not None:
            m.inputs[1].default_value = const
        return m.outputs[0]

    def smoothstep(v, lo, hi):
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.interpolation_type = "SMOOTHSTEP"
        mr.inputs["From Min"].default_value = lo
        mr.inputs["From Max"].default_value = hi
        nt.links.new(v, mr.inputs["Value"])
        return mr.outputs["Result"]

    az_abs = math("ABSOLUTE", sep.outputs["Z"])

    if MODE in ("rainbow", "pastel", "vivid", "september", "blue"):
        # signed bearing -pi..pi -> 0..1 hue
        bearing = math("ARCTAN2", sep.outputs["Y"], sep.outputs["X"])
        hue = math("ADD", math("DIVIDE", bearing, const=2 * math_pi), const=0.5)
        # tilt shifts the hue too (up to +-HUE_TILT of a turn), so crowns and
        # flanks of one gyrus differ instead of a whole side being one gradient
        hue = math("ADD", hue, math("MULTIPLY", sep.outputs["Z"], const=HUE_TILT))
        hue = math("FRACT", hue)
        if MODE in ("pastel", "vivid", "september", "blue"):
            stops = {"pastel": PASTEL, "vivid": VIVID, "september": SEPTEMBER, "blue": BLUE}[MODE]
            pr = nt.nodes.new("ShaderNodeValToRGB")
            pcr = pr.color_ramp
            pcr.interpolation = "LINEAR"
            while len(pcr.elements) > 1:
                pcr.elements.remove(pcr.elements[-1])
            pcr.elements[0].position = stops[0][0]
            pcr.elements[0].color = (*stops[0][1], 1.0)
            for pos, col in stops[1:]:
                e = pcr.elements.new(pos)
                e.color = (*col, 1.0)
            nt.links.new(hue, pr.inputs["Fac"])
            if MODE != "september":
                return pr.outputs["Color"]
            # sun catch: dot(normal, sun) through a steep smoothstep
            dot = nt.nodes.new("ShaderNodeVectorMath")
            dot.operation = "DOT_PRODUCT"
            nt.links.new(vec_socket, dot.inputs[0])
            dot.inputs[1].default_value = tuple(SUN_DIR)
            catch = smoothstep(dot.outputs["Value"], 0.70, 0.96)
            gm = nt.nodes.new("ShaderNodeMixRGB")
            nt.links.new(catch, gm.inputs["Fac"])
            nt.links.new(pr.outputs["Color"], gm.inputs["Color1"])
            gm.inputs["Color2"].default_value = (*SUN_GOLD, 1.0)
            return gm.outputs["Color"]
        # base saturation SAT, and vertical strands go a little more pastel:
        # S = SAT - 0.3 * SAT * |z|^2   ("giving Lisa Frank" at 0.95, Amy 4 Sept)
        sat = math("SUBTRACT", math("MULTIPLY", math("POWER", az_abs, const=2.0), const=-0.3 * SAT), const=-SAT)
        hsv = nt.nodes.new("ShaderNodeCombineHSV")
        nt.links.new(hue, hsv.inputs["H"])
        nt.links.new(sat, hsv.inputs["S"])
        hsv.inputs["V"].default_value = 0.92
        return hsv.outputs["Color"]

    ax, ay = (nt.nodes.new("ShaderNodeMath") for _ in range(2))
    for m, src in ((ax, "X"), (ay, "Y")):
        m.operation = "ABSOLUTE"
        nt.links.new(sep.outputs[src], m.inputs[0])
    # azimuth folded into one octant: 0 = left-right facing, 1 = front-back facing
    azimuth = math("DIVIDE", math("ARCTAN2", ay.outputs[0], ax.outputs[0]), const=math_pi_2)
    # vertical strands pulled towards blue
    pull = math("POWER", az_abs, const=2.5)
    mixf = nt.nodes.new("ShaderNodeMix")
    mixf.data_type = "FLOAT"
    nt.links.new(pull, sock(mixf, "Factor"))
    nt.links.new(azimuth, sock(mixf, "A"))
    sock(mixf, "B").default_value = BLUE_T
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "LINEAR"
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    stops = {"bluegold": BLUEGOLD, "monsters": MONSTERS}.get(MODE, PALETTE)
    cr.elements[0].position = stops[0][0]
    cr.elements[0].color = (*stops[0][1], 1.0)
    for pos, col in stops[1:]:
        e = cr.elements.new(pos)
        e.color = (*col, 1.0)
    nt.links.new(sock(mixf, "Result", output=True), ramp.inputs["Fac"])

    # gold channel: front/back facing AND not vertical, both steep
    # bluegold wants real golden patches, not rims: wider gold coverage
    front = smoothstep(azimuth, 0.70, 0.88) if MODE == "bluegold" else smoothstep(azimuth, 0.80, 0.93)
    flat = math("ADD", math("MULTIPLY", math("POWER", az_abs, const=2.0), const=-1.0), const=1.0)
    gold_f = smoothstep(math("MULTIPLY", front, flat), 0.35, 0.65) if MODE in ("bluegold", "monsters") else         smoothstep(math("MULTIPLY", front, flat), 0.45, 0.75)
    if MODE in ("bluegold", "monsters") and opts.get("goldmode", "peaks") == "peaks":
        # Amy: "yellow should be at the peaks/top". A crown is open to the
        # sky, a sulcus is enclosed: short-range ambient occlusion finds the
        # ridge tops regardless of which way they face.
        pk = nt.nodes.new("ShaderNodeAttribute")
        pk.attribute_name = "peak"
        pk.attribute_type = "GEOMETRY"
        gold_f = smoothstep(pk.outputs["Fac"], float(opts.get("peaklo", 0.86)), float(opts.get("peakhi", 0.97)))
    gold_f = math("MULTIPLY", gold_f, const=GOLD_MAX)
    gold_mix = nt.nodes.new("ShaderNodeMixRGB")
    gold_mix.blend_type = "MIX"
    nt.links.new(gold_f, gold_mix.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], gold_mix.inputs["Color1"])
    gold_mix.inputs["Color2"].default_value = (*GOLD, 1.0)
    return gold_mix.outputs["Color"]


def fur_material():
    mat = bpy.data.materials.new("Fur")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "nrm"
    attr.attribute_type = "GEOMETRY"
    col = direction_colour(nt, attr.outputs["Vector"])
    # darker towards the root so the sulci read as depth, brighter at the tips
    hi_ = nt.nodes.new("ShaderNodeHairInfo")
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.0
    ramp.inputs["From Max"].default_value = 1.0
    ramp.inputs["To Min"].default_value = 0.75
    ramp.inputs["To Max"].default_value = 1.0
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
    col = direction_colour(nt, geo.outputs["Normal"])
    dark = nt.nodes.new("ShaderNodeMixRGB")
    dark.blend_type = "MULTIPLY"
    dark.inputs["Fac"].default_value = 1.0
    # with very short hair the surface shows between strands: keep it matte and
    # close to the strand colour so gaps read as fur, not plastic
    dark.inputs["Color2"].default_value = (0.45, 0.45, 0.45, 1.0) if MODE == "pastel" else         tuple([float(opts.get("surfdark", "0.25"))] * 3 + [1.0])
    nt.links.new(col, dark.inputs["Color1"])
    nt.links.new(dark.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.95
    bsdf.inputs["Specular IOR Level"].default_value = 0.1
    return mat


def crystal_material():
    """Clear crystal with a cold tint. Cycles caustics are off below, so this
    relies on transmission bounces rather than light-through-glass patterns."""
    mat = bpy.data.materials.new("Crystal")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.90, 0.98, 1.00, 1.0)
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.10
    bsdf.inputs["IOR"].default_value = 1.55
    # a gem, not window glass: absorption makes the thick parts go turquoise
    # and the thin gyral crowns stay bright
    vol = nt.nodes.new("ShaderNodeVolumeAbsorption")
    vol.inputs["Color"].default_value = (0.35, 0.80, 1.00, 1.0)
    vol.inputs["Density"].default_value = 3.5
    nt.links.new(vol.outputs["Volume"], nt.nodes["Material Output"].inputs["Volume"])
    return mat


def tissue_material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.62
    bsdf.inputs["IOR"].default_value = 1.04
    bsdf.inputs["Subsurface Weight"].default_value = 0.35
    bsdf.inputs["Subsurface Scale"].default_value = 0.012
    return mat


HOLO_CYAN = (0.25, 0.85, 1.00)
HOLO_DEEP = (0.05, 0.25, 0.90)


def scanlines(nt):
    """0.55..1 stripe pattern down world Z, the classic projected-hologram tell."""
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 520.0
    nt.links.new(sep.outputs["Z"], mul.inputs[0])
    sin = nt.nodes.new("ShaderNodeMath")
    sin.operation = "SINE"
    nt.links.new(mul.outputs[0], sin.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1.0
    mr.inputs["From Max"].default_value = 1.0
    mr.inputs["To Min"].default_value = 0.55
    mr.inputs["To Max"].default_value = 1.0
    nt.links.new(sin.outputs[0], mr.inputs["Value"])
    return mr.outputs["Result"]


def holo_surface_material():
    """Mostly transparent, glowing at the rim (facing ratio), with scanlines."""
    mat = bpy.data.materials.new("HoloSurface")
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    emis = nt.nodes.new("ShaderNodeEmission")
    emis.inputs["Color"].default_value = (*HOLO_CYAN, 1.0)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.65
    strength = nt.nodes.new("ShaderNodeMath")
    strength.operation = "MULTIPLY"
    strength.inputs[1].default_value = 0.6
    nt.links.new(lw.outputs["Facing"], strength.inputs[0])
    sl = nt.nodes.new("ShaderNodeMath")
    sl.operation = "MULTIPLY"
    nt.links.new(strength.outputs[0], sl.inputs[0])
    nt.links.new(scanlines(nt), sl.inputs[1])
    nt.links.new(sl.outputs[0], emis.inputs["Strength"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    fac = nt.nodes.new("ShaderNodeMath")
    fac.operation = "MULTIPLY"
    fac.inputs[1].default_value = 0.9
    nt.links.new(lw.outputs["Facing"], fac.inputs[0])
    nt.links.new(fac.outputs[0], mix.inputs["Fac"])
    nt.links.new(trans.outputs["BSDF"], mix.inputs[1])
    nt.links.new(emis.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def holo_wire_material():
    mat = bpy.data.materials.new("HoloWire")
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emis = nt.nodes.new("ShaderNodeEmission")
    emis.inputs["Color"].default_value = (*HOLO_CYAN, 1.0)
    st = nt.nodes.new("ShaderNodeMath")
    st.operation = "MULTIPLY"
    st.inputs[0].default_value = 2.4
    nt.links.new(scanlines(nt), st.inputs[1])
    nt.links.new(st.outputs[0], emis.inputs["Strength"])
    nt.links.new(emis.outputs["Emission"], out.inputs["Surface"])
    return mat


def holo_points_material():
    """Emissive strands graded deep blue at the base to cyan at the crown."""
    mat = bpy.data.materials.new("HoloPoints")
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emis = nt.nodes.new("ShaderNodeEmission")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.65
    mr.inputs["From Max"].default_value = 0.60
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*HOLO_DEEP, 1.0)
    ramp.color_ramp.elements[1].color = (*HOLO_CYAN, 1.0)
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emis.inputs["Color"])
    st = nt.nodes.new("ShaderNodeMath")
    st.operation = "MULTIPLY"
    st.inputs[0].default_value = 3.0
    nt.links.new(scanlines(nt), st.inputs[1])
    nt.links.new(st.outputs[0], emis.inputs["Strength"])
    nt.links.new(emis.outputs["Emission"], out.inputs["Surface"])
    return mat


HOLO_COLOURS = {
    "holo_blue":  ((0.30, 0.80, 1.00), (0.75, 0.95, 1.00)),   # body, hot core
    "holo_amber": ((1.00, 0.55, 0.10), (1.00, 0.86, 0.50)),
    "holo_warm":  ((1.00, 0.80, 0.56), (1.00, 0.96, 0.88)),   # warm white light (Amy prefers over blue)
    "holo_gold":  ((1.00, 0.68, 0.28), (1.00, 0.90, 0.62)),   # "almost golden" (Amy)
}
DRESSED = ("holo_blue", "holo_amber", "holo_dots")   # dark floor, haze, motes, bloom


def hologram_material(body, core, hexgrid=False):
    """A hologram is light, not a surface.

    Surface: mostly transparent, emitting by facing ratio (rim-dominant), so
    faces stack additively and the interior shows through. Volume: emission
    inside the closed mesh, so thick regions glow more than thin ones. Both are
    modulated by fine scanlines, slow brightness bands and a fade away from the
    projector on the floor. Bloom and dispersion are added in the compositor.
    """
    mat = bpy.data.materials.new("Hologram")
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")

    def m(op, a, b=None, const=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        if isinstance(a, (int, float)):
            n.inputs[0].default_value = a
        else:
            nt.links.new(a, n.inputs[0])
        if b is not None:
            nt.links.new(b, n.inputs[1])
        elif const is not None:
            n.inputs[1].default_value = const
        return n.outputs[0]

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])
    z = sep.outputs["Z"]
    # interference: fine scanlines (0.6..1) x slow bands (0.75..1) x fade up
    fine = m("ADD", m("MULTIPLY", m("SINE", m("MULTIPLY", z, const=700.0)), const=0.2), const=0.8)
    bands = m("ADD", m("MULTIPLY", m("SINE", m("MULTIPLY", z, const=23.0)), const=0.125), const=0.875)
    fade = nt.nodes.new("ShaderNodeMapRange")
    fade.inputs["From Min"].default_value = -0.65
    fade.inputs["From Max"].default_value = 0.60
    fade.inputs["To Min"].default_value = 1.0
    fade.inputs["To Max"].default_value = 0.55
    nt.links.new(z, fade.inputs["Value"])
    pattern = m("MULTIPLY", m("MULTIPLY", fine, bands), fade.outputs["Result"])
    if hexgrid:
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.feature = "DISTANCE_TO_EDGE"
        vor.inputs["Scale"].default_value = 28.0
        nt.links.new(geo.outputs["Position"], vor.inputs["Vector"])
        edge = m("LESS_THAN", vor.outputs["Distance"], const=0.004)
        pattern = m("MULTIPLY", pattern, m("ADD", m("MULTIPLY", edge, const=1.5), const=1.0))

    # surface: transparent + rim emission
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.6
    facing = lw.outputs["Facing"]
    rim = m("POWER", facing, const=1.6)
    surf_strength = m("MULTIPLY", m("ADD", m("MULTIPLY", rim, const=0.85), const=0.02), pattern)
    # colour: body colour, pushed to the hot core on the strongest rims
    col = nt.nodes.new("ShaderNodeMixRGB")
    col.inputs["Color1"].default_value = (*body, 1.0)
    col.inputs["Color2"].default_value = (*core, 1.0)
    nt.links.new(m("POWER", facing, const=3.0), col.inputs["Fac"])
    emis = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(col.outputs["Color"], emis.inputs["Color"])
    nt.links.new(surf_strength, emis.inputs["Strength"])
    trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(trans.outputs["BSDF"], add.inputs[0])
    nt.links.new(emis.outputs["Emission"], add.inputs[1])
    nt.links.new(add.outputs["Shader"], out.inputs["Surface"])

    # volume: the body of light inside the closed mesh
    vem = nt.nodes.new("ShaderNodeEmission")
    vem.inputs["Color"].default_value = (*body, 1.0)
    nt.links.new(m("MULTIPLY", pattern, const=0.07), vem.inputs["Strength"])
    nt.links.new(vem.outputs["Emission"], out.inputs["Volume"])
    mat.cycles.emission_sampling = "NONE"
    return mat


def projector_disc():
    """Faint glowing disc on the floor under the brain: the projector."""
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=1.05, fill_type="NGON",
                                      location=(center.x, center.y, lo.z - 0.015))
    disc = bpy.context.active_object
    disc.name = "Projector"
    mat = bpy.data.materials.new("ProjectorDisc")
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    grad = nt.nodes.new("ShaderNodeTexGradient")
    grad.gradient_type = "SPHERICAL"
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Location"].default_value = (-0.5, -0.5, 0.0)
    nt.links.new(tc.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], grad.inputs["Vector"])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 2.5
    nt.links.new(grad.outputs["Fac"], pw.inputs[0])
    st = nt.nodes.new("ShaderNodeMath")
    st.operation = "MULTIPLY"
    st.inputs[1].default_value = 0.18
    nt.links.new(pw.outputs[0], st.inputs[0])
    emis = nt.nodes.new("ShaderNodeEmission")
    emis.inputs["Color"].default_value = (*HOLO_COLOURS.get(STYLE, HOLO_COLOURS["holo_" + HOLOCOL])[0], 1.0)
    nt.links.new(st.outputs[0], emis.inputs["Strength"])
    trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(trans.outputs["BSDF"], add.inputs[0])
    nt.links.new(emis.outputs["Emission"], add.inputs[1])
    nt.links.new(add.outputs["Shader"], out.inputs["Surface"])
    disc.data.materials.append(mat)
    return disc


def holo_dots_material(body, core):
    """Each tiny strand is a point of light. Emission only, no transparency:
    the dark cortex underneath occludes, so the dots define the surface.
    Colour sits between body and hot core by a per-strand random ("tw"), the
    same random drives a twinkle in strength, and the scanline / band / fade
    pattern of the projected-hologram look runs across the whole field."""
    mat = bpy.data.materials.new("HoloDots")
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")

    def m(op, a, b=None, const=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        if isinstance(a, (int, float)):
            n.inputs[0].default_value = a
        else:
            nt.links.new(a, n.inputs[0])
        if b is not None:
            nt.links.new(b, n.inputs[1])
        elif const is not None:
            n.inputs[1].default_value = const
        return n.outputs[0]

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])
    z = sep.outputs["Z"]
    fine = m("ADD", m("MULTIPLY", m("SINE", m("MULTIPLY", z, const=700.0)), const=0.25), const=0.75)
    bands = m("ADD", m("MULTIPLY", m("SINE", m("MULTIPLY", z, const=23.0)), const=0.15), const=0.85)
    fade = nt.nodes.new("ShaderNodeMapRange")
    fade.inputs["From Min"].default_value = -0.65
    fade.inputs["From Max"].default_value = 0.60
    fade.inputs["To Min"].default_value = 1.0
    fade.inputs["To Max"].default_value = 0.7
    nt.links.new(z, fade.inputs["Value"])
    pattern = m("MULTIPLY", m("MULTIPLY", fine, bands), fade.outputs["Result"])

    tw = nt.nodes.new("ShaderNodeAttribute")
    tw.attribute_name = "tw"
    tw.attribute_type = "GEOMETRY"
    twf = tw.outputs["Fac"]
    # twinkle: most dots middling, a few hot (tw^4 picks the few)
    hot = m("POWER", twf, const=4.0)
    strength = m("MULTIPLY", m("ADD", m("MULTIPLY", hot, const=6.0), const=1.2), pattern)
    col = nt.nodes.new("ShaderNodeMixRGB")
    col.inputs["Color1"].default_value = (*body, 1.0)
    col.inputs["Color2"].default_value = (*core, 1.0)
    nt.links.new(hot, col.inputs["Fac"])
    emis = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(col.outputs["Color"], emis.inputs["Color"])
    nt.links.new(m("MULTIPLY", strength, const=float(opts.get("dotglow", 1.0))), emis.inputs["Strength"])
    nt.links.new(emis.outputs["Emission"], out.inputs["Surface"])
    # Millions of tiny emitters must NOT be sampled as lights: with 4M strands
    # Cycles built a light tree over all of them and estimated 3 h per frame.
    # Camera rays still see the glow.
    mat.cycles.emission_sampling = "NONE"
    return mat


def dark_cortex_material(body=None):
    """Opaque near-black cortex under the dots. With a body colour it also
    emits at grazing angles only (facing ratio cubed), so folds and the
    silhouette glow the way the translucent hologram did, without any
    see-through: the surface stays solid."""
    mat = bpy.data.materials.new("DarkCortex")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.006, 0.008, 0.014, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.55
    bsdf.inputs["Specular IOR Level"].default_value = 0.2
    if body is not None:
        lw = nt.nodes.new("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.55
        pw = nt.nodes.new("ShaderNodeMath")
        pw.operation = "POWER"
        pw.inputs[1].default_value = 3.0
        nt.links.new(lw.outputs["Facing"], pw.inputs[0])
        st = nt.nodes.new("ShaderNodeMath")
        st.operation = "MULTIPLY"
        st.inputs[1].default_value = float(opts.get("rimglow", 1.2))
        nt.links.new(pw.outputs[0], st.inputs[0])
        bsdf.inputs["Emission Color"].default_value = (*body, 1.0)
        nt.links.new(st.outputs[0], bsdf.inputs["Emission Strength"])
        mat.cycles.emission_sampling = "NONE"
    return mat


if STYLE == "holo_dots":
    mat_fur = holo_dots_material(*HOLO_COLOURS["holo_" + HOLOCOL])
elif STYLE == "holo_points":
    mat_fur = holo_points_material()
else:
    mat_fur = fur_material()
if STYLE == "crystal":
    mat_surf = crystal_material()
elif STYLE == "holo_dots":
    mat_surf = dark_cortex_material(HOLO_COLOURS["holo_" + HOLOCOL][0])
elif STYLE in HOLO_COLOURS:
    mat_surf = hologram_material(*HOLO_COLOURS[STYLE], hexgrid=(STYLE == "holo_amber"))
elif HOLO:
    mat_surf = holo_surface_material()
else:
    mat_surf = surface_material()
for o in hemis:
    o.data.materials.clear()
    o.data.materials.append(mat_surf)

if STYLE == "crystal" and opts.get("interior") == "1":
    # the deep structures, both sides, one palette colour each, seen through
    # the crystal cortex
    SUB = r"C:\Users\amyle\Downloads\human brain subcortical_obj\subcortical_obj"
    C = {"hot pink": (1.00, 0.18, 0.62), "orange": (1.00, 0.40, 0.04),
         "warm yellow": (1.00, 0.82, 0.15), "teal-green": (0.08, 0.68, 0.50),
         "turquoise": (0.10, 0.82, 0.85), "sky blue": (0.35, 0.72, 1.00),
         "rich blue": (0.12, 0.40, 0.95), "royal blue": (0.18, 0.20, 0.85),
         "light purple": (0.66, 0.50, 0.95), "deep purple": (0.40, 0.10, 0.70)}
    DEEP = [("Thalamus-Proper", "rich blue"), ("Caudate", "turquoise"),
            ("Putamen", "orange"), ("Pallidum", "warm yellow"),
            ("Hippocampus", "hot pink"), ("Amygdala", "deep purple"),
            ("Accumbens-area", "light purple"), ("VentralDC", "royal blue"),
            ("Lateral-Ventricle", "sky blue")]
    for side in ("Left", "Right"):
        for nm, cn in DEEP:
            o = import_pial(SUB + "\\" + f"{side}-{nm}.obj")
            o.name = f"{side}-{nm}"
            o.data.materials.clear()
            o.data.materials.append(tissue_material(o.name, C[cn]))
    for nm in ("CC_Anterior", "CC_Mid_Anterior", "CC_Central", "CC_Mid_Posterior", "CC_Posterior"):
        o = import_pial(SUB + "\\" + f"{nm}.obj")
        o.name = nm
        o.data.materials.clear()
        o.data.materials.append(tissue_material(nm, C["teal-green"]))

if STYLE == "holo_wire":
    for o in list(hemis):
        w = o.copy()
        w.data = o.data.copy()
        w.name = o.name + "_wire"
        scene.collection.objects.link(w)
        w.data.materials.clear()
        w.data.materials.append(holo_wire_material())
        # 290k faces of wire read as a solid; a 4% decimate leaves a mesh the
        # eye can see through
        dm = w.modifiers.new("Dec", "DECIMATE")
        dm.ratio = float(opts.get("wire", "0.04"))
        wm = w.modifiers.new("Wire", "WIREFRAME")
        wm.thickness = 0.0008
        wm.use_replace = True


# ---------------------------------------------------------------- fur
def fur_node_group():
    """Curves object modifier: scatter strands over both pial meshes."""
    ng = bpy.data.node_groups.new("BrainFur", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = ng.nodes
    L = ng.links
    n.new("NodeGroupInput")                   # unused: the Curves object is empty
    gout = n.new("NodeGroupOutput")

    join_src = n.new("GeometryNodeJoinGeometry")
    for o in hemis:
        oi = n.new("GeometryNodeObjectInfo")
        oi.transform_space = "RELATIVE"
        sock(oi, "Object").default_value = o
        L.new(oi.outputs["Geometry"], join_src.inputs["Geometry"])

    dist = n.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "RANDOM"
    sock(dist, "Density").default_value = density
    sock(dist, "Seed").default_value = SEED
    L.new(join_src.outputs["Geometry"], sock(dist, "Mesh"))

    # strand direction = surface normal + a little random tilt
    jit = n.new("FunctionNodeRandomValue")
    jit.data_type = "FLOAT_VECTOR"
    sock(jit, "Min").default_value = (-0.35, -0.35, -0.35)
    sock(jit, "Max").default_value = (0.35, 0.35, 0.35)
    sock(jit, "Seed").default_value = SEED + 1
    add = n.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    L.new(dist.outputs["Normal"], add.inputs[0])
    L.new(sock(jit, "Value", output=True), add.inputs[1])
    norm = n.new("ShaderNodeVectorMath")
    norm.operation = "NORMALIZE"
    L.new(add.outputs["Vector"], norm.inputs[0])

    # keep that direction as a point attribute; it rides through the instances
    # to the realized curves and the shader colours by it (verified in debug:
    # the evaluated geometry carries "dir" on every strand point)
    store = n.new("GeometryNodeStoreNamedAttribute")
    store.data_type = "FLOAT_VECTOR"
    store.domain = "POINT"
    sock(store, "Name").default_value = "dir"
    L.new(dist.outputs["Points"], sock(store, "Geometry"))
    L.new(norm.outputs["Vector"], sock(store, "Value"))
    # the clean surface normal as well: colour comes from this, so the random
    # tilt does not scatter neighbouring strands across a palette boundary
    store2 = n.new("GeometryNodeStoreNamedAttribute")
    store2.data_type = "FLOAT_VECTOR"
    store2.domain = "POINT"
    sock(store2, "Name").default_value = "nrm"
    L.new(store.outputs["Geometry"], sock(store2, "Geometry"))
    L.new(dist.outputs["Normal"], sock(store2, "Value"))
    # a random float per strand, for twinkle in the emissive dot shader
    twr = n.new("FunctionNodeRandomValue")
    twr.data_type = "FLOAT"
    sock(twr, "Min").default_value = 0.0
    sock(twr, "Max").default_value = 1.0
    sock(twr, "Seed").default_value = SEED + 3
    store3 = n.new("GeometryNodeStoreNamedAttribute")
    store3.data_type = "FLOAT"
    store3.domain = "POINT"
    sock(store3, "Name").default_value = "tw"
    L.new(store2.outputs["Geometry"], sock(store3, "Geometry"))
    L.new(sock(twr, "Value", output=True), sock(store3, "Value"))
    # crown measure, sampled from the mesh under each strand root
    pk_in = n.new("GeometryNodeInputNamedAttribute")
    pk_in.data_type = "FLOAT"
    sock(pk_in, "Name").default_value = "peak"
    samp = n.new("GeometryNodeSampleNearestSurface")
    samp.data_type = "FLOAT"
    L.new(join_src.outputs["Geometry"], sock(samp, "Mesh"))
    L.new(sock(pk_in, "Attribute", output=True), sock(samp, "Value"))
    pos = n.new("GeometryNodeInputPosition")
    L.new(pos.outputs["Position"], sock(samp, "Sample Position"))
    store4 = n.new("GeometryNodeStoreNamedAttribute")
    store4.data_type = "FLOAT"
    store4.domain = "POINT"
    sock(store4, "Name").default_value = "peak"
    L.new(store3.outputs["Geometry"], sock(store4, "Geometry"))
    L.new(sock(samp, "Value", output=True), sock(store4, "Value"))

    line = n.new("GeometryNodeCurvePrimitiveLine")
    line.mode = "POINTS"
    sock(line, "Start").default_value = (0, 0, 0)
    sock(line, "End").default_value = (0, 0, LENGTH)
    resample = n.new("GeometryNodeResampleCurve")
    resample.mode = "COUNT"
    # straight sub-millimetre bristles need 2 points, not 4: with 8M strands
    # the extra points and the curve subdivision pushed the OptiX BVH build
    # out of GPU memory
    sock(resample, "Count").default_value = int(opts.get("curvepts", 4))
    L.new(line.outputs["Curve"], sock(resample, "Curve"))

    align = n.new("FunctionNodeAlignRotationToVector")
    align.axis = "Z"
    align.pivot_axis = "AUTO"
    L.new(norm.outputs["Vector"], sock(align, "Vector"))

    lenr = n.new("FunctionNodeRandomValue")
    lenr.data_type = "FLOAT"
    sock(lenr, "Min").default_value = 0.55
    sock(lenr, "Max").default_value = 1.0
    sock(lenr, "Seed").default_value = SEED + 2

    inst = n.new("GeometryNodeInstanceOnPoints")
    L.new(store4.outputs["Geometry"], sock(inst, "Points"))
    L.new(resample.outputs["Curve"], sock(inst, "Instance"))
    L.new(align.outputs["Rotation"], sock(inst, "Rotation"))
    L.new(sock(lenr, "Value", output=True), sock(inst, "Scale"))

    real = n.new("GeometryNodeRealizeInstances")
    L.new(inst.outputs["Instances"], sock(real, "Geometry"))

    # taper: full radius at the root, a third at the tip
    param = n.new("GeometryNodeSplineParameter")
    taper = n.new("ShaderNodeMapRange")
    taper.inputs["From Min"].default_value = 0.0
    taper.inputs["From Max"].default_value = 1.0
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


if STYLE == "holo_points":
    density *= 0.012
    LENGTH *= 1.2
    RADIUS *= 2.6
if STYLE == "holo_dots":
    # dots, not hairs: strand about as long as it is wide
    LENGTH = float(opts.get("length", 0.0035))
    RADIUS = float(opts.get("radius", 0.0011))
fur_obj = None
if STYLE in ("fur", "holo_points", "holo_dots"):
    fur_data = bpy.data.hair_curves.new("BrainFur")
    fur_data.materials.append(mat_fur)
    fur_obj = bpy.data.objects.new("BrainFur", fur_data)
    scene.collection.objects.link(fur_obj)
    fur_mod = fur_obj.modifiers.new("Fur", "NODES")
    fur_mod.node_group = fur_node_group()


# ---------------------------------------------------------------- studio
def studio_world():
    world = bpy.data.worlds.new("Studio")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    # what the camera sees: a flat light-grey backdrop
    cam_bg = nt.nodes.new("ShaderNodeBackground")
    cam_bg.inputs["Color"].default_value = (0.004, 0.007, 0.016, 1.0) if HOLO else (0.86, 0.86, 0.87, 1.0)
    cam_bg.inputs["Strength"].default_value = 1.0
    # what lights the scene: the HDRI if given, else a soft white environment
    env_bg = nt.nodes.new("ShaderNodeBackground")
    env_bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    env_bg.inputs["Strength"].default_value = (0.08 if HOLO else 0.30) * LIGHT
    if HDRI:
        assert Path(HDRI).exists(), f"HDRI not found: {HDRI}"
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(HDRI, check_existing=True)
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Rotation"].default_value[2] = math.radians(HDRI_ROT)
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["Generated"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
        nt.links.new(env.outputs["Color"], env_bg.inputs["Color"])
        env_bg.inputs["Strength"].default_value = HDRI_STRENGTH
        log(f"HDRI {Path(HDRI).name} strength {HDRI_STRENGTH} rot {HDRI_ROT}")
    if HOLO:
        env_bg.inputs["Color"].default_value = (0.5, 0.7, 1.0, 1.0)
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(env_bg.outputs["Background"], mix.inputs[1])
    nt.links.new(cam_bg.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    # haze lives in a bounded box (see haze_box), not the world: a world volume
    # marched through 4M hair curves ran at 40 s per SAMPLE at 960x540.


studio_world()

# floor: a shadow catcher, so the backdrop stays seamless and only the soft
# contact shadow appears under the brain
bpy.ops.mesh.primitive_plane_add(size=40, location=(center.x, center.y, lo.z - 0.02))
floor = bpy.context.active_object
floor.name = "Floor"
if STYLE in DRESSED:
    fm = bpy.data.materials.new("HoloFloor")
    fm.use_nodes = True
    fb = fm.node_tree.nodes["Principled BSDF"]
    fb.inputs["Base Color"].default_value = (0.015, 0.02, 0.035, 1.0)
    fb.inputs["Roughness"].default_value = 0.16
    fb.inputs["Specular IOR Level"].default_value = 0.6
    floor.data.materials.append(fm)
    projector_disc()
    # dust motes in the beam: tiny emissive spheres scattered in a box around
    # the brain, realized to a mesh so Cycles sees them
    motes_me = bpy.data.meshes.new("Motes")
    motes = bpy.data.objects.new("Motes", motes_me)
    scene.collection.objects.link(motes)
    mm = bpy.data.materials.new("Mote")
    mm.use_nodes = True
    mt = mm.node_tree
    for nd in list(mt.nodes):
        mt.nodes.remove(nd)
    mo = mt.nodes.new("ShaderNodeOutputMaterial")
    me_ = mt.nodes.new("ShaderNodeEmission")
    me_.inputs["Color"].default_value = (*HOLO_COLOURS.get(STYLE, HOLO_COLOURS["holo_" + HOLOCOL])[1], 1.0)
    me_.inputs["Strength"].default_value = 1.3
    mt.links.new(me_.outputs["Emission"], mo.inputs["Surface"])
    mm.cycles.emission_sampling = "NONE"
    ng = bpy.data.node_groups.new("Motes", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, L = ng.nodes, ng.links
    n.new("NodeGroupInput")
    gout = n.new("NodeGroupOutput")
    pts = n.new("GeometryNodePoints")
    sock(pts, "Count").default_value = int(opts.get("motes", 220))
    rnd = n.new("FunctionNodeRandomValue")
    rnd.data_type = "FLOAT_VECTOR"
    sock(rnd, "Min").default_value = (center.x - 0.8, center.y - 0.9, lo.z + 0.02)
    sock(rnd, "Max").default_value = (center.x + 0.8, center.y + 0.8, hi.z + 0.15)
    sock(rnd, "Seed").default_value = 11
    setp = n.new("GeometryNodeSetPosition")
    L.new(pts.outputs["Points"], sock(setp, "Geometry"))
    L.new(sock(rnd, "Value", output=True), sock(setp, "Position"))
    ico = n.new("GeometryNodeMeshIcoSphere")
    sock(ico, "Radius").default_value = 0.0025
    sock(ico, "Subdivisions").default_value = 1
    sz = n.new("FunctionNodeRandomValue")
    sz.data_type = "FLOAT"
    sock(sz, "Min").default_value = 0.25
    sock(sz, "Max").default_value = 1.0
    sock(sz, "Seed").default_value = 12
    inst = n.new("GeometryNodeInstanceOnPoints")
    L.new(setp.outputs["Geometry"], sock(inst, "Points"))
    L.new(ico.outputs["Mesh"], sock(inst, "Instance"))
    L.new(sock(sz, "Value", output=True), sock(inst, "Scale"))
    real = n.new("GeometryNodeRealizeInstances")
    L.new(inst.outputs["Instances"], sock(real, "Geometry"))
    sm = n.new("GeometryNodeSetMaterial")
    sock(sm, "Material").default_value = mm
    L.new(real.outputs["Geometry"], sock(sm, "Geometry"))
    L.new(sm.outputs["Geometry"], gout.inputs["Geometry"])
    motes.modifiers.new("Motes", "NODES").node_group = ng
    hz = float(opts.get("haze", 0.03))
    if hz > 0:
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(center.x, center.y, center.z + 0.2))
        box = bpy.context.active_object
        box.name = "HazeBox"
        # big enough that its edges never enter frame: at eye level and 1.4x
        # back the old 3.2-unit box showed as a pale rectangle behind the brain
        # (golden dots turntable, 6 Sept)
        box.scale = (14.0, 14.0, 6.0)
        box.location.z = lo.z + 3.0
        hm = bpy.data.materials.new("Haze")
        hm.use_nodes = True
        ht = hm.node_tree
        for nd in list(ht.nodes):
            ht.nodes.remove(nd)
        ho = ht.nodes.new("ShaderNodeOutputMaterial")
        sc = ht.nodes.new("ShaderNodeVolumeScatter")
        sc.inputs["Color"].default_value = (0.6, 0.8, 1.0, 1.0)
        sc.inputs["Density"].default_value = hz
        sc.inputs["Anisotropy"].default_value = 0.45
        ht.links.new(sc.outputs["Volume"], ho.inputs["Volume"])
        box.data.materials.append(hm)
        box.visible_shadow = False
else:
    floor.is_shadow_catcher = True

# target for the lights and the camera rig
bpy.ops.object.empty_add(location=center)
root = bpy.context.active_object
root.name = "BrainRoot"

size = max(ext)
# The first test still at 900/350/500/400 W was badly overexposed: the surface
# material at 25% value came out pastel. Cut to about 40%.
LIGHTS = [
    ("KEY",  ( 1.4, -1.3,  1.6), 380.0, 2.2, (1.00, 0.97, 0.93)),
    ("FILL", (-1.8, -0.9,  0.6), 140.0, 3.0, (0.96, 0.96, 1.00)),
] if MODE != "september" else [
    # the sun itself, low and warm, along SUN_DIR; cool sky fill opposite
    ("KEY",  tuple(SUN_DIR * 2.2), 360.0, 1.2, (1.00, 0.84, 0.60)),
    ("FILL", (-1.8, -0.9,  0.8), 170.0, 3.0, (0.72, 0.82, 1.00)),
    ("RIM",  (-0.4,  1.8,  1.2), 220.0, 2.0, (0.92, 0.95, 1.00)),
    ("TOP",  ( 0.1,  0.2,  2.4), 150.0, 2.6, (1.00, 1.00, 1.00)),
]
if MODE == "september":
    LIGHTS = LIGHTS + [
        ("RIM",  (-0.4,  1.8,  1.2), 160.0, 2.0, (0.80, 0.88, 1.00)),
        ("TOP",  ( 0.1,  0.2,  2.4),  90.0, 2.6, (0.85, 0.90, 1.00)),
    ]
for name, dirv, energy, lsize, colour in ([] if HDRI else LIGHTS):
    bpy.ops.object.light_add(type="AREA", location=tuple(center[i] + d * size for i, d in enumerate(dirv)))
    lt = bpy.context.active_object
    lt.name = name
    lt.data.energy = energy * LIGHT * (0.25 if HOLO else 1.0)
    # area lights reflect in the glossy hologram floor as pale rectangles
    # (seen behind the brain on the golden dots turntable, 6 Sept)
    lt.visible_glossy = False
    lt.data.size = lsize
    lt.data.color = colour
    con = lt.constraints.new(type="TRACK_TO")
    con.target = root
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    if opts.get("lightfollow") == "1":
        # Amy 5 Sept: "light traveling with the camera". The rig is parented
        # to the same empty the camera orbits on, so key, fill, rim and top
        # keep their relation to the lens for the whole turn.
        lt.parent = root
        lt.matrix_parent_inverse = root.matrix_world.inverted()


# ---------------------------------------------------------------- camera
# Solve the distance from the measured bounds, not by eye: the brain's largest
# half-extent must fit inside the vertical field of view with a margin.
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 60.0 * float(opts.get("camdist", "1.0"))   # farther back keeps the framing: longer lens
cam_data.sensor_width = 36.0
cam_data.sensor_fit = "HORIZONTAL"
cam = bpy.data.objects.new("Camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

half_diag = max(ext) * 0.5 * 1.1                # widest silhouette, any angle
tan_h = (cam_data.sensor_width / 2) / cam_data.lens
tan_v = tan_h * RES[1] / RES[0]
dist_cam = half_diag / min(tan_h, tan_v) * 1.12  # 12% breathing room
elev = math.radians(ELEVATION_DEG)
cam.parent = root
# CAMDIST is already in the lens, and the distance is solved from the lens, so
# the camera moves back by itself; multiplying here again doubled it
if CAMH is None:
    cam.location = (0.0, -dist_cam * math.cos(elev), dist_cam * math.sin(elev))
    cam.rotation_euler = (math.pi / 2 - elev, 0.0, 0.0)
else:
    # camera at a given height above the floor, aimed at the brain centre
    cz = lo.z + float(CAMH) / 100.0 * ext.z - center.z
    horiz = math.sqrt(max(dist_cam ** 2 - cz ** 2, 0.1))
    cam.location = (0.0, -horiz, cz)
    trk = cam.constraints.new(type="TRACK_TO")
    trk.target = root
    trk.track_axis = "TRACK_NEGATIVE_Z"
    trk.up_axis = "UP_Y"
    log(f"camera height {CAMH}% of brain ({lo.z + float(CAMH) / 100.0 * ext.z:.2f} u), "
        f"distance x{CAMDIST}")
cam_data.dof.use_dof = True
cam_data.dof.focus_object = root
cam_data.dof.aperture_fstop = 5.6
log(f"camera {dist_cam:.2f} units from centre, elevation {ELEVATION_DEG} deg, lens {cam_data.lens} mm")

# turntable: one full turn over FRAMES, linear, so frame FRAMES+1 == frame 1
root.rotation_euler = (0.0, 0.0, 0.0)
root.keyframe_insert("rotation_euler", index=2, frame=1)
root.rotation_euler = (0.0, 0.0, math.radians(360.0))
root.keyframe_insert("rotation_euler", index=2, frame=FRAMES + 1)
for fc in root.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"
scene.frame_start, scene.frame_end = 1, FRAMES


# ---------------------------------------------------------------- render
scene.render.engine = "CYCLES"
scene.cycles.samples = SAMPLES
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.02
scene.cycles.use_denoising = True
scene.cycles.denoiser = "OPTIX"
if STYLE == "crystal":
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.cycles.max_bounces = 24
    scene.cycles.transmission_bounces = 24
    scene.cycles.transparent_max_bounces = 24
if HOLO:
    scene.cycles.transparent_max_bounces = 64
    scene.cycles.volume_bounces = 2
    scene.cycles.volume_step_rate = 0.5
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    if DEVICE == "GPU":
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for dv in prefs.devices:
            dv.use = dv.type != "CPU"
        scene.cycles.device = "GPU"
    else:
        scene.cycles.device = "CPU"
except Exception as e:  # noqa: BLE001
    log(f"device fell back to CPU: {e}")
    scene.cycles.device = "CPU"

if hasattr(scene.render, "hair_type"):
    scene.render.hair_type = "STRIP"
    scene.render.hair_subdiv = int(opts.get("hairsubdiv", 2))

# MOTION BLUR OFF. Standing instruction.
scene.render.use_motion_blur = False
for vl in scene.view_layers:
    if hasattr(vl, "use_pass_vector"):
        vl.use_pass_vector = False

scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.color_depth = "8"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.render.use_compositing = STYLE in DRESSED
if STYLE in DRESSED:
    scene.use_nodes = True
    ct = scene.node_tree
    for nd in list(ct.nodes):
        ct.nodes.remove(nd)
    rl = ct.nodes.new("CompositorNodeRLayers")
    glare = ct.nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.threshold = 1.0
    glare.size = 8
    glare.mix = 0.0
    lens = ct.nodes.new("CompositorNodeLensdist")
    lens.use_projector = False
    lens.inputs["Distortion"].default_value = 0.0
    lens.inputs["Dispersion"].default_value = 0.018
    comp = ct.nodes.new("CompositorNodeComposite")
    ct.links.new(rl.outputs["Image"], glare.inputs["Image"])
    ct.links.new(glare.outputs["Image"], lens.inputs["Image"])
    ell = ct.nodes.new("CompositorNodeEllipseMask")
    ell.width = 1.05
    ell.height = 1.05
    blur = ct.nodes.new("CompositorNodeBlur")
    blur.filter_type = "FAST_GAUSS"
    blur.size_x = 420
    blur.size_y = 420
    ct.links.new(ell.outputs["Mask"], blur.inputs["Image"])
    vig = ct.nodes.new("CompositorNodeMixRGB")
    vig.blend_type = "MULTIPLY"
    vig.inputs["Fac"].default_value = 0.55
    ct.links.new(lens.outputs["Image"], vig.inputs[1])
    ct.links.new(blur.outputs["Image"], vig.inputs[2])
    ct.links.new(vig.outputs["Image"], comp.inputs["Image"])
scene.render.dither_intensity = 0.0

log(f"built in {time.time() - t_start:.0f}s: {RES[0]}x{RES[1]} {SAMPLES} samples on "
    f"{scene.cycles.device}, {FRAMES} frames -> {OUT}")

if opts.get("debug"):
    dg = bpy.context.evaluated_depsgraph_get()
    kinds = {}
    for inst in dg.object_instances:
        owner = inst.parent.name if inst.is_instance and inst.parent else inst.object.name
        key = (inst.object.type, inst.is_instance, owner)
        kinds[key] = kinds.get(key, 0) + 1
    for k, v in kinds.items():
        log(f"depsgraph: type={k[0]} is_instance={k[1]} owner={k[2]} x{v}")
    fe = fur_obj.evaluated_get(dg).data
    log(f"BrainFur evaluated: curves={len(fe.curves):,} points={len(fe.points):,} "
        f"attrs={list(fe.attributes.keys())}")

views = opts.get("views")
stills = opts.get("stills") or opts.get("still")
sweep = opts.get("sweep")
if sweep:
    # camera heights as % of brain height above the floor, from the hero
    # bearing, farther back by CAMDIST, always aimed at the brain centre
    cam.parent = None
    for c in list(cam.constraints):
        cam.constraints.remove(c)
    root.rotation_euler = (0, 0, 0)
    root.animation_data_clear()
    bearing = Vector((-1.0, -0.55, 0.0)).normalized()
    base = OUT[:-4] if OUT.lower().endswith(".mp4") else OUT
    os.makedirs(os.path.dirname(base), exist_ok=True)
    for pct in [float(v) for v in sweep.split(",")]:
        cz = lo.z + pct / 100.0 * ext.z
        dz = cz - center.z
        horiz = math.sqrt(max(dist_cam ** 2 - dz ** 2, 0.1))
        cam.location = center + bearing * horiz + Vector((0, 0, dz))
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{base}_h{int(pct):03d}.png"
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        log(f"height {pct:.0f}% -> {scene.render.filepath} in {time.time() - t0:.0f}s")
elif views:
    # Anatomical planes, straight on. The camera leaves the turntable rig and is
    # placed from the measured bounds so each view fills the frame the same way.
    #   coronal  : from the front (anterior, +Y), sees width x height
    #   sagittal : from the left (-X), sees length x height
    #   axial    : from above (+Z), anterior at the top of frame, sees width x length
    VIEWS = {
        "coronal":  ((0, 1, 0),  (math.pi / 2, 0, math.pi),      (ext.x, ext.z)),
        "sagittal": ((-1, 0, 0), (math.pi / 2, 0, -math.pi / 2), (ext.y, ext.z)),
        "axial":    ((0, 0, 1),  (0, 0, 0),                      (ext.x, ext.y)),
        "threequarter": (tuple(Vector((-1.0, -0.45, 0.42)).normalized()), None, (max(ext), max(ext) * 0.8)),
        "hero": (tuple(Vector((-1.0, -0.55, 0.20)).normalized()), None, (max(ext) * 0.92, max(ext) * 0.72)),
    }
    cam.parent = None
    root.rotation_euler = (0, 0, 0)
    root.animation_data_clear()
    base = OUT[:-4] if OUT.lower().endswith(".mp4") else OUT
    os.makedirs(os.path.dirname(base), exist_ok=True)
    for name in [v.strip() for v in views.split(",")]:
        axis, rot, (w, h) = VIEWS[name]
        d = max((w / 2) / tan_h, (h / 2) / tan_v) * 1.10 * 1.18
        cam.location = tuple(center[i] + axis[i] * d for i in range(3))
        cam.rotation_euler = rot if rot is not None else \
            (-Vector(axis)).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{base}_{name}.png"
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        log(f"{name} view from {tuple(round(c, 2) for c in cam.location)} -> "
            f"{scene.render.filepath} in {time.time() - t0:.0f}s")
elif stills:
    base = OUT[:-4] if OUT.lower().endswith(".mp4") else OUT
    os.makedirs(os.path.dirname(base), exist_ok=True)
    for fr in [int(x) for x in str(stills).split(",")]:
        scene.frame_set(fr)
        scene.render.filepath = f"{base}_beat_{fr:04d}.png"
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        log(f"beat {fr} -> {scene.render.filepath} in {time.time() - t0:.0f}s")
else:
    # PNG sequence, then assemble. Never straight to mp4: an interrupted mp4 has
    # no moov atom and every frame in it is lost.
    seq_dir = os.path.splitext(OUT)[0] + "_frames"
    os.makedirs(seq_dir, exist_ok=True)
    done = {int(f[1:6]) for f in os.listdir(seq_dir)
            if f.startswith("f") and f.endswith(".png") and f[1:6].isdigit()}
    if done:
        log(f"{len(done)} frames already on disk, rendering the rest")
    t0 = time.time()
    n_new = 0
    for fr in range(1, FRAMES + 1):
        if fr in done:
            continue
        scene.frame_set(fr)
        scene.render.filepath = os.path.join(seq_dir, f"f{fr:05d}")
        bpy.ops.render.render(write_still=True)
        n_new += 1
        el = time.time() - t0
        print(f"Fra:{fr} of {FRAMES} | {el / 60:.1f} min elapsed | {el / n_new:.1f}s/frame", flush=True)
    log(f"{FRAMES} frames in {(time.time() - t0) / 60:.1f} min")
    cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
           "-i", os.path.join(seq_dir, "f%05d.png"),
           "-c:v", "libx264", "-preset", "slow", "-crf", "17",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT]
    log(f"assembling -> {OUT}")
    subprocess.run(cmd, check=False)
    if os.path.exists(OUT):
        log(f"wrote {OUT} ({os.path.getsize(OUT) / 1e6:.1f} MB)")
log("DONE")
