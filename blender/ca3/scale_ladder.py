"""
The scale ladder. One block, one cell, one contact, one spike.

  blender --background --python scale_ladder.py -- [key=val]

  stills=1,120,...        render those frames only, to renders/_ladder_<f>.png
  res=1920x1080  samples=64
  rebuild=1               force a rebuild of the geometry cache
  density=1               0 skips the population entirely, for fast camera work
  out=path

FIVE MOVEMENTS, in Amy's order.

  1  THE BLOCK      wireframe outline, the real EM cross section, one pyramidal
                    cell inside it for scale.
  2  IT FILLS       the population arrives, staggered, until the block reads as
                    tissue rather than one lonely neuron.
  3  DOWN TO ONE    the population recedes and the hero pyramidal is the subject.
  4  DOWN TO THE    into the thorny excrescence where mossy fibre ...994107 makes
     CONTACT        its 53 synapses inside a 4.7 x 5.2 x 6.4 um box.
  5  THE SPIKE      one fibre fires and fails, five more join, all six fire and
                    the cell answers. The camera opens out once, and only once,
                    as the cell's own wave leaves the thorn.

WHY HOLDS. A single unbroken push across fifty times of magnification, from a
540 um half frame to an 11 um one, gives the eye nothing to fix on: every frame
is a different scale and none of them is read. The camera stops on each rung to
register what it is looking at, then moves. The stops make it a ladder rather
than a dive. The one direction of travel is inward; the single reversal is at the
very end, when the subject itself grows from a thorn to a whole cell.

UNITS ARE MICROMETRES. One Blender unit is one micrometre, so the block is 1000
units across and the contact rung frames 22. Every number in this file can
be checked against the paper directly. Two things have to follow that scale or
the shot breaks:

  * the camera clip planes, rescaled every frame, or the close rungs render black
  * the light rig, whose distance scales with the framing radius and whose energy
    therefore scales with its SQUARE. A rig calibrated at 540 um is three orders
    of magnitude too dim at 11 um.

COORDINATES, AND THE BUG THAT SHIPPED. Blender's OBJ importer stores its axis
flip as an object ROTATION and leaves the vertices in file nanometres, so a data
point maps to world as (x, y, z) -> (x, -z, y). volume_diagram.py converted the
CELL that way but drew the box and the EM plate straight, in unflipped world
axes, which stood a 233 um cell up out of a 100 um slab. Here the block, the
plate and every mesh go through to_world() exactly once and the assertions below
check the result against the block bounds.

EVERYTHING REGISTERS TO ONE ORIGIN: renders/em_registration.json, the centre of
the reconstructed region, which is the point pull_em_slice.py cropped the EM
around. Do not centre anything on its own centroid. That put the cell 223 um out
of the tissue it is actually in, once already.
"""
import json
import math
import sys
import time
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)


def flag(name, default="1"):
    return opts.get(name, default) not in ("0", "false", "no")


ROOT = Path(r"D:\Meshes")
REG_JSON = ROOT / "renders" / "em_registration.json"
EM_PNG = ROOT / "renders" / "em_plane.png"
HERO_ID = "648518346438632877"
LEAD = "648518346448994107"          # the 53 synapse fibre, the one we descend to
HERO_OBJ = ROOT / "hero" / f"hero_{HERO_ID}.obj"
FIELDS = ROOT / "skeletons" / "ap_fields6.npz"
PAINT_DIR = ROOT / "skeletons"
CACHE = Path(opts.get("cache", str(ROOT / "ladder_scene.blend")))

BOX_UM = np.array([1000.0, 1000.0, 100.0])     # the imaged block, data x, y, z
# em_plane.png is the central 3472 px of the 4306 px em_slice.png, checked by
# cross correlation at 0.994, so it covers exactly 1000 um centred on the origin.
EM_FOOTPRINT_UM = 1000.0

# The population, for movement 2. Chosen for coverage, not for count: pyramidal
# arbors alone leave the stratum lucidum empty, and the mossy fibres are what
# make that band read as tissue.
DENSITY = [
    ("grad",  ROOT / "gradient",                          ("#2352B8", "#5E8FE8")),
    ("mf",    ROOT / "hq" / "MF 700",                     ("#C98C2E", "#F0CE7A")),
    ("thorn", ROOT / "hq" / "thorny pyramidals ca3 250",  ("#5C34B0", "#A87BE8")),
    # the inhibitory population, in the house emerald. Amy asked for them: without
    # them the block is all excitatory and reads as a simpler tissue than it is.
    # hq, NOT the bare folder. Measured, the bare "inhibitory ca3 28" meshes span
    # z -303 to 681 um against a block that is 0 to 100 um thick, so they hang far
    # outside the tissue, and they are coarse enough to read as faceted. The hq
    # copies sit at z 4 to 96, inside the slab, and carry proper surface detail.
    ("inhib", ROOT / "hq" / "inhibitory ca3 28",           ("#0F7A50", "#3FCB92")),
]

# ---- the house module, for world, lights, render settings ------------------------------
HOUSE = ROOT / "ca3_animation.py"
ns = {"__name__": "ca3_module", "__file__": str(HOUSE)}
exec(compile(HOUSE.read_text(encoding="utf-8"), str(HOUSE), "exec"), ns)
g = ns["build"].__globals__
hexcol = g["hexcol"]
shade_ramp = g["shade_ramp"]
emissive_material = g["emissive_material"]

RES = tuple(int(x) for x in opts.get("res", "1920x1080").split("x"))
g["RESOLUTION"] = RES
g["SAMPLES"] = int(opts.get("samples", 64))
# Subsurface scale is quoted in the playbook as 0.012 Blender units at
# TARGET_SIZE 10 over a ~1000 um population, which is 1.2 um of tissue. In a
# world where one unit IS one micrometre that number is simply 1.2.
g["SUBSURFACE_SCALE"] = 1.2

FPS = g["FPS"]

# THE FRAMING RADIUS IS A HALF HEIGHT, so the distance that achieves it depends on
# the VERTICAL half angle, which is not the one a 50 mm lens is usually quoted by.
# Blender's default sensor fit is AUTO, which fits the 36 mm sensor across the
# LARGER output dimension: at 1920x1080 that is the width, and the vertical field
# is only 11.4 degrees against the 19.8 horizontal. Using the horizontal number
# here put the camera twice as close as intended and cropped the block on the
# first test frame.
SENSOR_MM = 36.0
CAM_LENS_MM = g["CAM_LENS_MM"]
_long = SENSOR_MM / 2.0
V_HALF = math.atan((_long * min(1.0, RES[1] / RES[0])) / CAM_LENS_MM)
H_HALF = math.atan((_long * min(1.0, RES[0] / RES[1])) / CAM_LENS_MM)
print(f"[ladder] {RES[0]}x{RES[1]} on a {CAM_LENS_MM} mm lens: half field "
      f"{math.degrees(H_HALF):.1f} deg across, {math.degrees(V_HALF):.1f} deg down",
      flush=True)

# ---- registration -----------------------------------------------------------------------
DATA_CENTRE = np.array(json.load(open(REG_JSON, encoding="utf-8"))["data_centre_nm"])


def to_world(p_nm):
    """data nanometres -> world micrometres, applying the importer's axis flip once."""
    p = np.asarray(p_nm, dtype=float)
    if p.ndim == 1:
        return Vector((p[0] / 1000.0, -p[2] / 1000.0, p[1] / 1000.0))
    return np.column_stack([p[:, 0], -p[:, 2], p[:, 1]]) / 1000.0


ORIGIN_W = to_world(DATA_CENTRE)      # world position the data centre would land at


def dpos(p_nm):
    """world position of a data point in the registered scene."""
    return to_world(p_nm) - ORIGIN_W


HALF_W = Vector((BOX_UM[0] / 2.0, BOX_UM[2] / 2.0, BOX_UM[1] / 2.0))   # x, z, y


def register(o):
    """Put an imported OBJ into the registered micrometre scene.

    The object matrix is T * R * S, so location is applied AFTER the flip: the
    offset has to be given in world axes, not data axes. Getting that backwards
    is the failure mode the module docstring describes.
    """
    r = o.rotation_euler
    assert abs(r.x - math.pi / 2) < 1e-4 and abs(r.y) < 1e-6 and abs(r.z) < 1e-6, \
        f"{o.name}: expected the importer's 90 degree X rotation, got {tuple(r)}"
    o.scale = (0.001,) * 3
    o.location = tuple(-ORIGIN_W)


# ---- geometry ---------------------------------------------------------------------------
def smooth_all(me):
    """shade_smooth without the operator, which is per object and slow at 1200 cells."""
    n = len(me.polygons)
    if n:
        me.polygons.foreach_set("use_smooth", np.ones(n, dtype=bool))
        me.update()


def strip_strays(obj, max_edge_nm=20000.0):
    """Delete the long thin faces the mesher leaves reaching out to stray vertices.

    Same criterion as ca3_animation.strip_stray_faces, but the face walk is in
    numpy instead of Python. Over a thousand cells that is the difference between
    a minute and most of an hour.
    """
    me = obj.data
    npoly, nloop, nvert = len(me.polygons), len(me.loops), len(me.vertices)
    if not npoly:
        return 0
    lv = np.empty(nloop, dtype=np.int32)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(npoly, dtype=np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(npoly, dtype=np.int32)
    me.polygons.foreach_get("loop_total", lt)
    co = np.empty(nvert * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(nvert, 3)

    poly_of_loop = np.repeat(np.arange(npoly, dtype=np.int64), lt)
    idx = np.arange(nloop, dtype=np.int64)
    start = ls[poly_of_loop]
    nxt = start + (idx - start + 1) % lt[poly_of_loop]
    d = co[lv[nxt]] - co[lv[idx]]
    bad = (d * d).sum(1) > max_edge_nm * max_edge_nm
    if not bad.any():
        return 0
    doomed = np.unique(poly_of_loop[bad])
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[int(i)] for i in doomed], context="FACES")
    bm.to_mesh(me)
    me.update()
    bm.free()
    return int(len(doomed))


# how far a density cell may reach past the drawn block before it is cut, in the
# data's own nanometres. 40 um is enough to keep an arbor looking continuous at
# the edge without letting a whole cell body sit outside the wireframe.
CLIP_MARGIN_NM = 40000.0


def clip_to_block(obj):
    """Delete faces whose centre lies outside the drawn block, plus a margin.

    Works in the object's own vertex coordinates, which are the data's raw
    nanometres, so the block bounds can be compared directly without going
    through the axis flip. Returns the number of faces removed.
    """
    import bmesh
    lo = DATA_CENTRE - (BOX_UM * 1000.0) / 2.0 - CLIP_MARGIN_NM
    hi = DATA_CENTRE + (BOX_UM * 1000.0) / 2.0 + CLIP_MARGIN_NM
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    doomed = [f for f in bm.faces
              if any(f.calc_center_median()[i] < lo[i] or f.calc_center_median()[i] > hi[i]
                     for i in range(3))]
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
        bm.to_mesh(obj.data)
        obj.data.update()
    n = len(doomed)
    bm.free()
    return n


def import_obj(path, name, strip, clip=False):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    assert new, f"nothing imported from {path}"
    o = new[0]
    for extra in new[1:]:                      # a couple of files come in as two parts
        bpy.data.objects.remove(extra, do_unlink=True)
    o.name = name
    o.data.name = name
    register(o)
    n = strip_strays(o) if strip else 0
    if clip:
        n += clip_to_block(o)
    smooth_all(o.data)
    return o, n


def paint_ap(obj, tag):
    """Attach the per vertex cable distance field ap_six.py animates against.

    The caches on disk are keyed on vertex count, so the hero and the fibres must
    be imported at native resolution and must NOT have stray faces stripped, or
    the count moves and a 90 second remap runs for nothing.
    """
    f6 = np.load(FIELDS)
    nodes, values = f6[f"{tag}_verts"], f6[f"{tag}_dist"]
    span = float(f6[f"{tag}_span"])
    n = len(obj.data.vertices)
    key = "cell" if tag.startswith("cell") else tag.split("_")[1]
    corridor = 5500.0 if key == "cell" else None
    cache = PAINT_DIR / f"_paint6_{key}_{n}_{'v2corr' if corridor else 'v2'}.npy"
    if cache.exists():
        norm = np.load(cache)
    else:
        verts = np.empty(n * 3, dtype=np.float64)
        obj.data.vertices.foreach_get("co", verts)
        verts = verts.reshape(n, 3)
        t0 = time.time()
        norm = np.minimum(nearest_value(verts, nodes, values, corridor) / span, 4.0)
        np.save(cache, norm)
        print(f"[ladder] painted {key} {n:,} verts in {time.time() - t0:.0f}s", flush=True)
    assert len(norm) == n, f"{tag}: paint cache is {len(norm)} for {n} vertices"
    attr = obj.data.color_attributes.new(name="apdist", type="FLOAT_COLOR",
                                         domain="POINT")
    flat = np.empty(n * 4, dtype=np.float32)
    flat[0::4] = flat[1::4] = flat[2::4] = norm
    flat[3::4] = 1.0
    attr.data.foreach_set("color", flat)
    return span


def nearest_value(verts, nodes, values, lit_only_within=None, chunk=20000):
    """Value of the closest skeleton node per vertex. Verbatim from ap_six.py."""
    if lit_only_within is not None:
        keep = values < values.max() * 0.5
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
            true2 = d2[np.arange(len(blk)), j] + (blk ** 2).sum(1)
            out[i:i + chunk][true2 > lit_only_within ** 2] = values.max()
    return out


def build_block():
    """The wireframe outline, at the block's real proportions in world axes."""
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
    box = bpy.context.active_object
    box.name = box.data.name = "BLOCK"
    box.scale = HALF_W                      # data x, z, y -> world x, y, z
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.modifier_add(type="WIREFRAME")
    box.modifiers["Wireframe"].thickness = 2.2      # 2.2 um, what volume_diagram shipped
    box.modifiers["Wireframe"].use_replace = True
    return box


def build_em_plane():
    """The EM cross section, as four explicit corners rather than a rotated plane.

    The image is a constant data z cut: rows run along data y, columns along data
    x, and row 0 is minimum y. Under the flip that puts it in the world x-z plane
    with its normal along world y. Writing the corners out by hand means the
    mapping is visible and assertable instead of hidden in a rotation.
    """
    c = DATA_CENTRE
    h = EM_FOOTPRINT_UM * 1000.0 / 2.0
    corners_nm = [(c[0] - h, c[1] - h, c[2]),     # image (col 0, row 0) -> uv (0, 1)
                  (c[0] + h, c[1] - h, c[2]),
                  (c[0] + h, c[1] + h, c[2]),
                  (c[0] - h, c[1] + h, c[2])]
    uvs = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]
    verts = [tuple(dpos(p)) for p in corners_nm]
    me = bpy.data.meshes.new("EM_SLICE")
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    for loop in me.polygons[0].loop_indices:
        uv.data[loop].uv = uvs[loop]
    plane = bpy.data.objects.new("EM_SLICE", me)
    bpy.context.scene.collection.objects.link(plane)

    n = me.polygons[0].normal
    assert abs(abs(n.y) - 1.0) < 1e-6, f"EM plate normal is {tuple(n)}, expected world y"
    lo = np.array(verts).min(0)
    hi = np.array(verts).max(0)
    assert abs(hi[1] - lo[1]) < 1e-9, "EM plate is not flat in world y"
    print(f"[ladder] EM plate {hi[0] - lo[0]:.0f} x {hi[2] - lo[2]:.0f} um in the world "
          f"x-z plane at y {lo[1]:+.2f}", flush=True)
    return plane


# Amy: reduce some of the pyramidal cells to buy back polygons and still look full.
# The mossy fibres are what make the lucidum band read as tissue, so they are kept
# whole; the pyramidal arbors overlap heavily and thin out without a visible loss
# of density. Deterministic stride, not a random sample, so the shot is repeatable.
KEEP = {"grad": 0.62, "thorn": 0.62, "mf": 1.0, "inhib": 1.0}


def collect_density():
    """One path per segment id, deduplicated across folders, hero excluded."""
    picked, order = {}, []
    for tag, folder, _ramp in DENSITY:
        if not folder.exists():
            print(f"[ladder] density folder missing: {folder}", flush=True)
            continue
        n = 0
        _all = sorted(folder.glob("*.obj"))
        _k = KEEP.get(tag, 1.0)
        if _k < 1.0:
            _step = 1.0 / _k
            _all = [_all[int(i * _step)] for i in range(int(len(_all) * _k))
                    if int(i * _step) < len(_all)]
        for path in _all:
            if path.name.endswith((".raw.obj", ".tmp.obj")):
                continue
            seg = path.stem.replace("-meshlab", "")
            if seg == HERO_ID or seg in picked:
                continue
            picked[seg] = (tag, path)
            order.append(seg)
            n += 1
        print(f"[ladder] density {tag}: {n} cells from {folder.name}", flush=True)
    cells = [(picked[s][0], s, picked[s][1]) for s in order]
    cap = int(opts.get("maxcells", 0))
    if cap:
        # take an even stride so a capped run still covers all three folders
        cells = cells[::max(1, len(cells) // cap)][:cap]
        print(f"[ladder] capped to {len(cells)} density cells", flush=True)
    return cells


def build_geometry():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    build_block()
    build_em_plane()

    t0 = time.time()
    hero, _ = import_obj(HERO_OBJ, "HERO", strip=False)
    paint_ap(hero, f"cell_{HERO_ID}")
    f6 = np.load(FIELDS)
    for seg in [str(s) for s in f6["fibre_ids"]]:
        o, _ = import_obj(ROOT / "hero" / f"fibre_{seg}.obj", f"FIB_{seg}", strip=False)
        paint_ap(o, f"fibre_{seg}")
    print(f"[ladder] hero and 6 fibres in {time.time() - t0:.0f}s", flush=True)

    if flag("density"):
        t0 = time.time()
        stripped = 0
        cells = collect_density()
        for i, (tag, seg, path) in enumerate(cells):
            o, n = import_obj(path, f"DENS_{tag}_{seg}", strip=True, clip=True)
            stripped += n
            if (i + 1) % 100 == 0:
                print(f"[ladder]   {i + 1}/{len(cells)} ({time.time() - t0:.0f}s)",
                      flush=True)
        objs = [o for o in bpy.data.objects if o.name.startswith("DENS_")]
        print(f"[ladder] {len(objs)} density cells, "
              f"{sum(len(o.data.polygons) for o in objs):,} faces, "
              f"{stripped:,} stray faces stripped, in {time.time() - t0:.0f}s", flush=True)

    bpy.context.view_layer.update()
    return scene


# ---- open or build ----------------------------------------------------------------------
if CACHE.exists() and not flag("rebuild", "0"):
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=str(CACHE))
    print(f"[ladder] opened cache in {time.time() - t0:.0f}s", flush=True)
else:
    build_geometry()
    t0 = time.time()
    bpy.ops.wm.save_as_mainfile(filepath=str(CACHE))
    print(f"[ladder] cached to {CACHE} in {time.time() - t0:.0f}s "
          f"({CACHE.stat().st_size / 1e9:.2f} GB)", flush=True)

scene = bpy.context.scene
for o in list(bpy.data.objects):
    if o.type in {"LIGHT", "CAMERA", "EMPTY"}:
        bpy.data.objects.remove(o, do_unlink=True)

box = bpy.data.objects["BLOCK"]
plane = bpy.data.objects["EM_SLICE"]
hero = bpy.data.objects["HERO"]
f6 = np.load(FIELDS)
FIBRES = [str(s) for s in f6["fibre_ids"]]
FRAC = {str(s): float(f) for s, f in zip(f6["fibre_ids"], f6["fibre_syn_frac"])}
fibs = {s: bpy.data.objects[f"FIB_{s}"] for s in FIBRES}
dens = sorted((o for o in bpy.data.objects if o.name.startswith("DENS_")),
              key=lambda o: o.name)
print(f"[ladder] {len(dens)} density cells, hero {len(hero.data.vertices):,} verts, "
      f"{sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH'):,} "
      f"faces in the scene", flush=True)

# ---- the registration assertions ---------------------------------------------------------
SOMA_NM = np.array(json.load(open(ROOT / "skeletons" / "ap_paths.json",
                                  encoding="utf-8"))["cells"][HERO_ID]["soma_centre_nm"])
BOUT_NM = f6[f"fibre_{LEAD}_syn"]
BOUT_C_NM = BOUT_NM.mean(axis=0)

soma_w = dpos(SOMA_NM)
bout_w = dpos(BOUT_C_NM)
for name, p in (("soma", soma_w), ("bouton centroid", bout_w)):
    assert abs(p.x) < HALF_W.x and abs(p.y) < HALF_W.y and abs(p.z) < HALF_W.z, \
        f"{name} at {tuple(round(v, 1) for v in p)} is outside the block"
    print(f"[ladder] {name:16s} world ({p.x:8.1f},{p.y:7.1f},{p.z:8.1f}) um, "
          f"block half extent ({HALF_W.x:.0f},{HALF_W.y:.0f},{HALF_W.z:.0f})", flush=True)

# and the same check against the mesh itself, through its actual object matrix,
# because a wrong axis on the box would pass the point test above and still stand
# the cell up out of the slab
m = np.array(hero.matrix_world)
nv = len(hero.data.vertices)
co = np.empty(nv * 3, dtype=np.float64)
hero.data.vertices.foreach_get("co", co)
co = co.reshape(nv, 3)[::501]
hw = co @ m[:3, :3].T + m[:3, 3]
lo_h = np.percentile(hw, 0.5, axis=0)
hi_h = np.percentile(hw, 99.5, axis=0)
print(f"[ladder] hero mesh world bbox {lo_h.round(1)} .. {hi_h.round(1)} um", flush=True)
assert np.all(np.abs(lo_h) < np.array(HALF_W) + 1.0) and \
       np.all(np.abs(hi_h) < np.array(HALF_W) + 1.0), \
    "the hero mesh does not fit inside the block: the axis flip disagrees somewhere"
assert abs(hi_h[1] - lo_h[1]) < BOX_UM[2], \
    "the hero is thicker than the slab in world y, so the box is drawn on data axes"

# where the EM plate cuts the cell, which is the check that failed before
d_near = float(np.abs(hw[:, 1] - 0.0).min())
print(f"[ladder] EM plate passes {d_near:.2f} um from the nearest hero vertex, "
      f"cell spans world y {lo_h[1]:.1f} to {hi_h[1]:.1f}", flush=True)
assert lo_h[1] < 0.0 < hi_h[1], "the EM plate does not cut through the cell"

# ---- materials ---------------------------------------------------------------------------
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)

wire = bpy.data.materials.new("BLOCK_WIRE")
wire.use_nodes = True
wt = wire.node_tree
wt.nodes.clear()
wo = wt.nodes.new("ShaderNodeOutputMaterial")
we = wt.nodes.new("ShaderNodeEmission")
we.inputs["Color"].default_value = hexcol("#5FA8E8") + (1.0,)
wt.links.new(we.outputs["Emission"], wo.inputs["Surface"])
box.data.materials.clear()
box.data.materials.append(wire)

em = bpy.data.materials.new("EM_SLICE")
em.use_nodes = True
et = em.node_tree
et.nodes.clear()
eo = et.nodes.new("ShaderNodeOutputMaterial")
ee = et.nodes.new("ShaderNodeEmission")
tex = et.nodes.new("ShaderNodeTexImage")
tex.image = bpy.data.images.load(str(EM_PNG), check_existing=True)
tex.extension = "CLIP"
et.links.new(tex.outputs["Color"], ee.inputs["Color"])
et.links.new(ee.outputs["Emission"], eo.inputs["Surface"])
plane.data.materials.clear()
plane.data.materials.append(em)

by_tag = {}
for o in dens:
    by_tag.setdefault(o.name.split("_")[1], []).append(o)
ramps = {t: r for t, _d, r in DENSITY}
for tag, objs in by_tag.items():
    shades = shade_ramp(ramps[tag][0], ramps[tag][1], len(objs))
    for i, o in enumerate(objs):
        o.data.materials.clear()
        o.data.materials.append(emissive_material(f"mat_{tag}_{i:04d}", shades[i], 1.0))


def pulse_material(name, base_hex, glow_hex, width, peak):
    """From ap_six.py. Returns the material and the two sockets worth animating:
    where the wavefront sits, and how hard it burns."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = hexcol(base_hex) + (1.0,)
    bsdf.inputs["Roughness"].default_value = 0.62
    bsdf.inputs["IOR"].default_value = 1.04           # submerged, never glossy
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
    for a, bq in ((attr.outputs["Color"], sub.inputs[0]), (sub.outputs[0], absn.inputs[0]),
                  (absn.outputs[0], div.inputs[0]), (div.outputs[0], inv.inputs[1]),
                  (inv.outputs[0], shp.inputs[0]), (shp.outputs[0], amp.inputs[0]),
                  (amp.outputs[0], bsdf.inputs["Emission Strength"]),
                  (bsdf.outputs["BSDF"], out.inputs["Surface"])):
        nt.links.new(a, bq)
    return mat, sub.inputs[1], amp.inputs[1]


CWIDTH = float(opts.get("cwidth", 0.095))
CPEAK = float(opts.get("cpeak", 40.0))
FWIDTH = float(opts.get("fwidth", 0.055))
FPEAK = float(opts.get("fpeak", 2.5))

mats = {}
m, head_c, amp_c = pulse_material("AP_cell", "#2E8BE0", "#CFE8FF", CWIDTH, CPEAK)
hero.data.materials.clear()
hero.data.materials.append(m)
mats["cell"] = (m, head_c, amp_c)
for seg in FIBRES:
    m, h, a = pulse_material(f"AP_f_{seg}", "#E8A93A", "#FFF0C0", FWIDTH, FPEAK)
    fibs[seg].data.materials.clear()
    fibs[seg].data.materials.append(m)
    mats[seg] = (m, h, a)

# ---- the 53 synapses, as instanced markers -----------------------------------------------
# Small enough that they stay 53 separate points at the contact rung rather than
# fusing into one blob through the bloom. Measured, not guessed: see the
# component count printed by ladder_measure.py.
SYN_R = float(opts.get("synr", 0.45))
SYN_E = float(opts.get("syne", 6.0))
bpy.ops.mesh.primitive_uv_sphere_add(radius=SYN_R, segments=14, ring_count=10)
dot = bpy.context.active_object
dot.name = "SYN_DOT"
smooth_all(dot.data)
sm = bpy.data.materials.new("mat_syn")
sm.use_nodes = True
st = sm.node_tree
st.nodes.clear()
so = st.nodes.new("ShaderNodeOutputMaterial")
se = st.nodes.new("ShaderNodeEmission")
se.inputs["Color"].default_value = hexcol("#FFF0C4") + (1.0,)
st.links.new(se.outputs["Emission"], so.inputs["Surface"])
dot.data.materials.append(sm)
cloud = bpy.data.meshes.new("SYN_CLOUD")
cloud.from_pydata([tuple(dpos(p)) for p in BOUT_NM], [], [])
cloud.update()
cl = bpy.data.objects.new("SYNAPSES", cloud)
scene.collection.objects.link(cl)
cl.instance_type = "VERTS"
dot.parent = cl
dot.matrix_parent_inverse.identity()
print(f"[ladder] {len(BOUT_NM)} synapse markers at radius {SYN_R} um", flush=True)

# ---- the shot -----------------------------------------------------------------------------
# frame, target, framing radius in micrometres. Every travel is bracketed by a
# hold, so the smoothstep on each segment starts and ends at zero velocity with
# nothing to stutter against.
CELL_C = Vector(((lo_h + hi_h) / 2.0).tolist())
R_BLOCK = float(opts.get("rblock", 540.0))
R_CELL = float(opts.get("rcell", 124.0))
R_CONTACT = float(opts.get("rcontact", 11.0))

# The fourth entry is an aim shift along the camera's own up axis, as a fraction
# of the framing radius. A slab seen from above projects its near edge low in the
# frame, so aiming at the geometric centre wastes the top of the picture and
# clips the bottom; measured at 63 px of 1080 low, which is what the -0.14 is.
BLOCK_SHIFT = float(opts.get("blockshift", -0.14))
CELL_SHIFT = float(opts.get("cellshift", 0.0))
KEYS = [
    (1,   Vector((0, 0, 0)), R_BLOCK,        BLOCK_SHIFT),   # 1  the block
    (48,  Vector((0, 0, 0)), R_BLOCK,        BLOCK_SHIFT),
    (126, Vector((0, 0, 0)), R_BLOCK * 0.97, BLOCK_SHIFT),   # 2  it fills
    (156, Vector((0, 0, 0)), R_BLOCK * 0.97, BLOCK_SHIFT),
    (240, CELL_C,            R_CELL,         CELL_SHIFT),    # 3  down to one cell
    (276, CELL_C,            R_CELL,         CELL_SHIFT),
    (360, bout_w,            R_CONTACT,      0.0),           # 4  down to the contact
    (390, bout_w,            R_CONTACT,      0.0),
    (486, bout_w,            R_CONTACT,      0.0),           # 5  one fibre, and it fails
    (558, CELL_C,            R_CELL,         CELL_SHIFT),    #    the one reversal
    (654, CELL_C,            R_CELL,         CELL_SHIFT),
]
FRAMES = KEYS[-1][0]
# Amy's notes. The fill is slower, so the tissue assembles rather than switching
# on. The EM plate and the wireframe now leave DURING the fill, so one thing hands
# over to the other instead of the block sitting empty between them. And the
# population stays through the descent to the cell, going only as the camera
# closes on the contact, where it would otherwise be in front of the subject.
FILL = (50, 186)               # the population arrives, slower
FADE_BLOCK = (74, 158)         # the EM plate and wireframe leave while it fills
RECEDE = (262, 348)            # the cells hold through the zoom, then go
SYN_ON = (318, 360)

# movement 5, in global frames
A1_GO, A1_HIT = 398, 452       # one fibre travels and lands
A1_FADE = 494                  # its depolarisation dies away
JOIN = (500, 540)              # the other five appear, during the open out
A2_GO, A2_HIT = 560, 604       # all six travel and land together
A2_END = 642                   # the cell answers
print(f"[ladder] {FRAMES} frames at {FPS} fps = {FRAMES / FPS:.1f} s", flush=True)
print(f"[ladder] magnification {R_BLOCK / R_CONTACT:.0f}x, "
      f"rungs {R_BLOCK:.0f} -> {R_CELL:.0f} -> {R_CONTACT:.1f} um", flush=True)


def smooth(u):
    return u * u * (3.0 - 2.0 * u)


def path_state(f):
    """target, framing radius and aim shift at frame f.

    The radius interpolates in LOG space. Linearly, a 660 to 4.6 move spends
    almost every frame already deep in the last decade and the wide rungs blur
    past in a handful.
    """
    for (f0, t0, r0, s0), (f1, t1, r1, s1) in zip(KEYS, KEYS[1:]):
        if f <= f1:
            u = 0.0 if f1 == f0 else smooth((f - f0) / (f1 - f0))
            r = math.exp(math.log(r0) + (math.log(r1) - math.log(r0)) * u)
            return t0.lerp(t1, u), r, s0 + (s1 - s0) * u
    return KEYS[-1][1], KEYS[-1][2], KEYS[-1][3]


# THE SLAB HAS TO LIE FLAT. Its 100 um thickness runs along world Y, because the
# importer's flip sends data z there, while the 1000 x 1000 um face lies in the
# world x-z plane. Blender's to_track_quat always makes world +Z the screen up,
# and world Z is IN the face, so the default aim stands the block up on its edge
# and it reads as a wall rather than a block of tissue. Screen up here is the
# slab NORMAL instead, built by hand.
SLAB_N = Vector((0.0, 1.0, 0.0))          # data z, the sectioning axis
SLAB_U = Vector((1.0, 0.0, 0.0))          # data x
SLAB_V = Vector((0.0, 0.0, 1.0))          # data y

# 18 degrees of travel within the plane, which is parallax without announcing
# itself, and a tilt that starts high enough to read the slab as a slab and
# flattens as we descend into it.
# The opening move is quick and the rest is slow. A single smoothstep across the
# whole shot spends its 18 degrees so evenly that the first seconds read as static,
# which is dead time while the viewer is only looking at a slab and one cell.
# Amy asked for a faster pan through the first second and a half, so the spin is
# piecewise on FRAME: 20 degrees inside the first 36 frames, 12 across the
# remaining 618. The tilt still eases over the whole shot, since that one is
# reading the slab as a slab and should not hurry.
SPIN0, SPIN1 = math.radians(26.0), math.radians(58.0)
TILT0, TILT1 = math.radians(36.0), math.radians(22.0)
# Amy: the rotation stopped dead at 1.5 s. It did, and measurably: two smoothsteps
# joined end to end BOTH have zero derivative at the junction, so the camera came
# to a complete halt at frame 36, going 0.85 deg/frame at frame 20, 0.14 at 35 and
# 0.0001 at 37. The apparent dolly in and out is the parallax settling around that
# stop; the framing radius is monotonic throughout, checked.
#
# An exponential ease out is fast at the start, slows continuously and never
# reaches zero velocity, so there is no junction to stop at. TAU is set so a bit
# over half the travel happens inside the first 36 frames, which is the fast
# opening pan Amy asked for, without the stop she then saw.
SPIN_TAU = 0.067


def spin_at(f):
    u = (f - 1) / max(1, FRAMES - 1)
    return SPIN0 + (SPIN1 - SPIN0) * (1.0 - math.exp(-u / SPIN_TAU))


def cam_basis(radius, p, frame=None):
    """offset from the target, plus the camera's own right/up, at progress p."""
    spin = spin_at(frame) if frame is not None else SPIN0 + (SPIN1 - SPIN0) * smooth(p)
    tilt = TILT0 + (TILT1 - TILT0) * smooth(p)
    d = radius / math.tan(V_HALF)
    back = (SLAB_U * (math.cos(tilt) * math.cos(spin))
            + SLAB_V * (math.cos(tilt) * math.sin(spin))
            + SLAB_N * math.sin(tilt))
    fwd = -back
    right = fwd.cross(SLAB_N)
    right.normalize()
    up = right.cross(fwd).normalized()
    return back * d, d, right, up, fwd


target = bpy.data.objects.new("LADDER_TARGET", None)
scene.collection.objects.link(target)

cam_data = bpy.data.cameras.new("CAM")
cam_data.lens = CAM_LENS_MM
assert abs(cam_data.sensor_width - SENSOR_MM) < 1e-6 and cam_data.sensor_fit == "AUTO", \
    "the field of view above assumes a 36 mm sensor on AUTO fit"
cam = bpy.data.objects.new("CAM", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
# DEPTH OF FIELD IS OFF, and not by taste. Blender's physical camera treats one
# Blender unit as one metre, so in a world where one unit is one micrometre the
# camera sits 54 units from the contact with a 50 mm lens. Hyperfocal at f/2.4 is
# about 35 units, so everything past a third of that distance is already sharp:
# the computed circle of confusion across the whole thorn is 0.05 px. Turning it
# on costs render time and produces literally nothing. It would need the scene
# rebuilt at a smaller unit to work, which is not worth breaking the
# micrometre-per-unit convention for. Pass dof=1 to see for yourself.
if flag("dof", "0"):
    cam_data.dof.use_dof = True
    cam_data.dof.focus_object = target
    cam_data.dof.aperture_fstop = float(opts.get("fstop", 2.4))
    cam_data.dof.aperture_blades = 6

# ---- the light rig, which has to travel with the camera -----------------------------------
# build_lights places a three point rig at a multiple of the subject size and
# leaves the energies fixed, which is correct for a scene that stays one size.
# Here the subject shrinks by 135x, so distance goes with the framing radius and
# energy has to go with its SQUARE to hold irradiance constant.
# The rig is expressed in the CAMERA's frame, not the world's, so it stays a
# three point rig at every rung. build_lights' vectors are written for a camera
# sitting at -Y looking up +Y with Z up, so its x is the camera right, its z is
# the camera up, and minus its y points back toward the camera.
REF = 10.0
SPECS = [("KEY",  (1.15, 0.85, 1.05), g["KEY_ENERGY"],  1.1, (1.00, 0.97, 0.92)),
         ("FILL", (-1.30, 0.10, 0.55), g["FILL_ENERGY"], 1.6, (0.72, 0.82, 1.00)),
         ("RIM",  (-0.35, 0.75, -1.25), g["RIM_ENERGY"],  1.2, (0.85, 0.90, 1.00)),
         ("TOP",  (0.05, 1.60, -0.10), g["TOP_ENERGY"],  1.4, (0.95, 0.95, 1.00))]
lights = []
for name, dirv, energy, lsz, colour in SPECS:
    ld = bpy.data.lights.new(name, type="AREA")
    ld.color = colour
    lo_obj = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(lo_obj)
    con = lo_obj.constraints.new(type="TRACK_TO")
    con.target = target
    con.track_axis, con.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    lights.append((lo_obj, Vector(dirv), energy, lsz))

# NO SINGLE FLASH CORE. ap_six.py puts one emissive sphere at the bouton
# centroid, which is right when the whole cell is in frame and the contact is a
# few dozen pixels across. At this rung the contact is half the picture and that
# sphere is exactly the glowing blob this shot is supposed to avoid: the first
# test frame came back with the bouton blown to white across 84 percent of the
# frame. The arrival is carried by the 53 markers flaring individually instead,
# which is also the more honest picture, because 53 release sites is the fact.
flare_data = bpy.data.lights.new("AP_FLARE", type="POINT")
flare_data.color = (1.0, 0.86, 0.55)
flare = bpy.data.objects.new("AP_FLARE", flare_data)
scene.collection.objects.link(flare)
# Pushed well off the geometry it lights, on the camera's side, so the thorn is
# lit toward the lens rather than rimmed from behind. At 1.9 um it was closer to
# the bouton than the bouton is wide, so the near face took roughly ten times the
# irradiance of the far one and burned out. 6 um is far enough to read as a flash
# rather than a torch pressed against the mesh.
FLARE_D = float(opts.get("flared", 6.0))
_back, _d, _r, _u, _fw = cam_basis(1.0, (452 - 1) / 653.0)
flare.location = bout_w + (_back + _u * 0.35).normalized() * FLARE_D

# ---- bake the move ------------------------------------------------------------------------
scene.frame_start, scene.frame_end = 1, FRAMES
scene.render.fps = FPS

radii = []
for f in range(1, FRAMES + 1):
    tgt, radius, shift = path_state(f)
    radii.append(radius)
    p = (f - 1) / (FRAMES - 1)
    off, dist, right, up, fwd = cam_basis(radius, p, frame=f)
    tgt = tgt + up * (shift * radius)
    target.location = tgt
    target.keyframe_insert("location", frame=f)
    cam.location = tgt + off
    # local +X right, +Y up, -Z forward: the columns of the rotation matrix
    cam.rotation_euler = Matrix(((right.x, up.x, -fwd.x),
                                 (right.y, up.y, -fwd.y),
                                 (right.z, up.z, -fwd.z))).to_euler()
    cam.keyframe_insert("location", frame=f)
    cam.keyframe_insert("rotation_euler", frame=f)
    # clip planes follow the scale, or the close rungs render as nothing.
    # clip_end stays generous so the far side of the cell is never sliced off.
    cam_data.clip_start = max(dist * 0.002, 5e-4)
    cam_data.clip_end = max(dist * 60.0, 2500.0)
    cam_data.keyframe_insert("clip_start", frame=f)
    cam_data.keyframe_insert("clip_end", frame=f)

    s = radius / REF
    for lo_obj, dirv, energy, lsz in lights:
        lo_obj.location = tgt + (right * dirv.x + up * dirv.y - fwd * dirv.z) * radius
        lo_obj.keyframe_insert("location", frame=f)
        lo_obj.data.energy = energy * s * s
        lo_obj.data.size = REF * lsz * s
        lo_obj.data.shadow_soft_size = REF * lsz * s * g["SHADOW_SOFTNESS"]
        lo_obj.data.keyframe_insert("energy", frame=f)
        lo_obj.data.keyframe_insert("size", frame=f)
        lo_obj.data.keyframe_insert("shadow_soft_size", frame=f)

print(f"[ladder] camera distance {radii[0] / math.tan(V_HALF):.0f} um at the block, "
      f"{min(radii) / math.tan(V_HALF):.2f} um at the contact", flush=True)

# Velocity check. Measured in micrometres per frame this is meaningless across a
# 135x zoom: the wide rungs dwarf everything and every close frame reads as a
# near stop. What the eye actually judges is motion relative to the frame, so
# divide by the framing radius. A travel segment should sit well above the holds.
pos = np.array([cam.animation_data.action.fcurves[i].evaluate(f)
                for f in range(1, FRAMES + 1) for i in range(3)]).reshape(FRAMES, 3)
rad = np.array(radii)
vel = np.linalg.norm(np.diff(pos, axis=0), axis=1) / rad[:-1]
travel = np.zeros(FRAMES - 1, dtype=bool)
segs = []
for (f0, t0, r0, _s0), (f1, t1, r1, _s1) in zip(KEYS, KEYS[1:]):
    if t0 != t1 or abs(r0 - r1) > 1e-9:
        travel[f0 - 1:f1 - 1] = True
        segs.append((f0, f1))
print(f"[ladder] frame relative camera speed: travel median "
      f"{np.median(vel[travel]):.4f}, peak {vel.max():.4f}, "
      f"holds median {np.median(vel[~travel]):.4f}", flush=True)
# Every travel starts and ends at zero velocity by design, so counting slow
# frames across a whole segment just counts the ramps. What would be a visible
# stutter is a dip in the MIDDLE of a move, so only the middle 60 percent counts.
for f0, f1 in segs:
    a = f0 + int((f1 - f0) * 0.2)
    b = f0 + int((f1 - f0) * 0.8)
    mid = vel[a - 1:b - 1]
    print(f"[ladder]   travel {f0}-{f1}: mid speed min {mid.min():.4f} against a "
          f"segment peak of {vel[f0 - 1:f1 - 1].max():.4f} "
          f"({mid.min() / vel[f0 - 1:f1 - 1].max() * 100:.0f} percent, "
          f"{'clean' if mid.min() > vel[f0 - 1:f1 - 1].max() * 0.12 else 'STUTTER'})",
          flush=True)

# FRAME THE CONTACT AGAINST THE SUBJECT, NOT AGAINST THE LIT PIXELS. At this rung
# the hero's arbor fills the picture at any distance, so a content bounding box
# reads 100 percent whatever the camera does. What has to be measured is where
# the 53 synapses themselves land, in pixels.
from bpy_extras.object_utils import world_to_camera_view      # noqa: E402

for probe in (390, 452):
    scene.frame_set(probe)
    bpy.context.view_layer.update()
    uv = np.array([world_to_camera_view(scene, cam, Vector(dpos(p))) for p in BOUT_NM])
    px = uv[:, 0] * RES[0]
    py = (1.0 - uv[:, 1]) * RES[1]
    print(f"[ladder] frame {probe}: the 53 synapses span "
          f"{px.max() - px.min():.0f} x {py.max() - py.min():.0f} px "
          f"({(px.max() - px.min()) / RES[0] * 100:.0f} x "
          f"{(py.max() - py.min()) / RES[1] * 100:.0f} percent of the frame), "
          f"centred ({px.mean() / RES[0]:.2f}, {py.mean() / RES[1]:.2f}), "
          f"{int(((px > 0) & (px < RES[0]) & (py > 0) & (py < RES[1])).sum())} in frame",
          flush=True)

# How many of the 53 are actually SEEN. A synapse centre sits in the cleft
# between two opaque membranes, so most of them are inside the apposition and no
# marker can show through. This ray casts each one back to the lens and counts
# the ones nothing occludes, which is the honest number to quote rather than 53.
scene.frame_set(452)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
cam_p = cam.matrix_world.translation
seen = 0
_b, _dd, r_ax, u_ax, _f = cam_basis(R_CONTACT, (452 - 1) / (FRAMES - 1))
for p in BOUT_NM:
    w = Vector(dpos(p))
    # A marker is a sphere, not a point. Testing only its centre says 2 of 53,
    # while a render diff against the same frame with the markers dark shows 25
    # separate patches, because a cap can poke through a gap while the centre is
    # buried. Sample the disc the sphere presents to the lens instead.
    for off in (Vector((0, 0, 0)),
                r_ax * (SYN_R * 0.7), -r_ax * (SYN_R * 0.7),
                u_ax * (SYN_R * 0.7), -u_ax * (SYN_R * 0.7)):
        q = w + off
        v = q - cam_p
        L = v.length
        hit, loc, _n, _i, _o, _m = scene.ray_cast(dg, cam_p, v.normalized(),
                                                  distance=L * 1.2)
        if not hit or (loc - cam_p).length >= L - SYN_R - 0.05:
            seen += 1
            break
print(f"[ladder] {seen} of {len(BOUT_NM)} synapse markers show from the contact rung "
      f"camera; the rest are buried inside the apposition, where a synapse centre "
      f"physically is", flush=True)
scene.frame_set(1)

for act in (cam.animation_data.action, cam_data.animation_data.action,
            target.animation_data.action):
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
for lo_obj, _d, _e, _s in lights:
    for act in (lo_obj.animation_data.action, lo_obj.data.animation_data.action):
        for fc in act.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


# ---- visibility -----------------------------------------------------------------------------
def key_vis(o, events):
    """Keyed hide_render, not a scale from zero and not an alpha fade.

    These meshes carry their centring on location, so scaling toward the object
    origin drags them in from somewhere else entirely and reads as objects flying
    in from a corner. Alpha is roughly fifty times slower per frame and there are
    a thousand of these.
    """
    for fr, hidden in events:
        o.hide_render = o.hide_viewport = bool(hidden)
        o.keyframe_insert("hide_render", frame=max(1, int(fr)))
        o.keyframe_insert("hide_viewport", frame=max(1, int(fr)))
    for fc in o.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


# The population arrives shuffled rather than in file order, so the block fills
# all over at once instead of sweeping across. A thousand cells appearing in
# spatial order reads as a wipe; shuffled, it reads as tissue resolving.
rng = np.random.default_rng(7)
shuffled = [dens[i] for i in rng.permutation(len(dens))]
for i, o in enumerate(shuffled):
    u = i / max(1, len(shuffled) - 1)
    on = int(FILL[0] + (FILL[1] - FILL[0]) * u)
    # first in, first out. Reversing the order here means the last cells to
    # arrive, at frame 126, are also the first to go at 156, so a fifth of the
    # population is on screen for barely a second and the fill looks like it
    # never finished.
    off = int(RECEDE[0] + (RECEDE[1] - RECEDE[0]) * u)
    key_vis(o, [(1, True), (on - 1, True), (on, False), (off, True), (FRAMES, True)])
if dens:
    print(f"[ladder] population fills over frames {FILL[0]}-{FILL[1]} and "
          f"recedes over {RECEDE[0]}-{RECEDE[1]}", flush=True)

key_vis(box, [(1, False), (FADE_BLOCK[1], False), (FADE_BLOCK[1] + 1, True),
              (FRAMES, True)])
key_vis(plane, [(1, False), (FADE_BLOCK[1], False), (FADE_BLOCK[1] + 1, True),
                (FRAMES, True)])
key_vis(fibs[LEAD], [(1, True), (RECEDE[0] - 1, True), (RECEDE[0], False),
                     (FRAMES, False)])
others = [s for s in FIBRES if s != LEAD]
step = max(1, (JOIN[1] - JOIN[0]) // max(1, len(others)))
for i, seg in enumerate(others):
    on = JOIN[0] + i * step
    key_vis(fibs[seg], [(1, True), (on - 1, True), (on, False), (FRAMES, False)])
    print(f"[ladder] fibre {seg} joins at frame {on}", flush=True)


def key(sock, pairs):
    for fr, v in pairs:
        sock.default_value = v
        sock.keyframe_insert("default_value", frame=max(1, int(fr)))


key(we.inputs["Strength"], [(1, 2.6), (FADE_BLOCK[0], 2.6), (FADE_BLOCK[1], 0.0),
                            (FRAMES, 0.0)])
key(ee.inputs["Strength"], [(1, 1.25), (FADE_BLOCK[0], 1.25), (FADE_BLOCK[1], 0.0),
                            (FRAMES, 0.0)])
# The markers come up as the contact resolves, flare individually on each
# arrival, and fade out once the subject is the whole cell again.
SYN_FLASH = float(opts.get("synflash", 22.0))
key(se.inputs["Strength"],
    [(1, 0.0), (SYN_ON[0], 0.0), (SYN_ON[1], SYN_E),
     (A1_HIT - 3, SYN_E), (A1_HIT + 2, SYN_FLASH), (A1_HIT + 20, SYN_E),
     (A1_FADE, SYN_E * 0.6),
     (A2_HIT - 3, SYN_E * 0.6), (A2_HIT + 2, SYN_FLASH), (A2_HIT + 22, SYN_E * 0.6),
     (A2_END, SYN_E * 0.25), (FRAMES, 0.0)])

# ---- movement 5, the two attempts ------------------------------------------------------------
# ap_six.py's story, retold at two scales: the lead fibre fires alone at the
# contact rung and the cell does not answer, which is the likely outcome by about
# eight to one; then the other five join as the camera opens out, all six fire,
# and the cell answers.
LO = -0.15
for seg in FIBRES:
    _mat, head, amp = mats[seg]
    fr_seg = FRAC[seg]
    over = LO + (fr_seg - LO) * 1.45           # keep running a little past the boutons
    if seg == LEAD:
        key(head, [(1, LO), (A1_GO, LO), (A1_HIT, fr_seg), (A1_FADE, over),
                   (A2_GO, LO), (A2_HIT, fr_seg), (A2_END, over)])
        # Across the rewind between the two attempts the wavefront runs from the
        # far end back to the start. Lit, that is a second pulse visibly going
        # BACKWARDS up the fibre. Kill the emission for the rewind.
        key(amp, [(1, FPEAK), (A1_FADE, FPEAK), (A1_FADE + 6, 0.0),
                  (A2_GO - 6, 0.0), (A2_GO, FPEAK), (FRAMES, FPEAK)])
    else:
        key(head, [(1, LO), (A2_GO, LO), (A2_HIT, fr_seg), (A2_END, over)])
        key(amp, [(1, FPEAK)])

SUB = float(opts.get("sub", 0.13))             # how far the failed attempt spreads
key(head_c, [(1, LO), (A1_HIT, LO), (A1_FADE, SUB), (A2_HIT, LO), (A2_END, 1.0)])
key(amp_c, [(1, 0.0), (A1_HIT, 0.0), (A1_HIT + 10, CPEAK * 0.55), (A1_FADE, 0.0),
            (A2_HIT, 0.0), (A2_HIT + 8, CPEAK), (A2_END, CPEAK), (FRAMES, CPEAK)])

# The flare is a real light, so its energy has to be scaled by the framing radius
# squared exactly like the key light, or it is invisible at the contact and a
# supernova once the camera opens out.
PEAK = float(opts.get("flash", 240.0))
CURVE = ((1, 0.0), (A1_HIT - 4, 0.0), (A1_HIT + 2, 0.42), (A1_HIT + 14, 0.10),
         (A1_FADE, 0.0), (A2_HIT - 4, 0.0), (A2_HIT + 2, 1.0), (A2_HIT + 10, 0.34),
         (A2_HIT + 30, 0.08), (A2_END, 0.0), (FRAMES, 0.0))
curve_f = np.array([c[0] for c in CURVE], dtype=float)
curve_k = np.array([c[1] for c in CURVE], dtype=float)
for f in range(1, FRAMES + 1):
    k = float(np.interp(f, curve_f, curve_k))
    s = radii[f - 1] / REF
    flare_data.energy = PEAK * k * s * s
    flare_data.keyframe_insert("energy", frame=f)
    flare_data.shadow_soft_size = 0.05 * radii[f - 1]
    flare_data.keyframe_insert("shadow_soft_size", frame=f)

for holder in [m for m in bpy.data.materials if m.node_tree
               and m.node_tree.animation_data]:
    for fc in holder.node_tree.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
if flare_data.animation_data:
    for fc in flare_data.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# ---- world, render ------------------------------------------------------------------------------
g["build_world"](scene)
g["apply_render_settings"](scene)
scene.render.resolution_x, scene.render.resolution_y = RES

out = opts.get("out", str(ROOT / "renders" / "scale_ladder.mp4"))
stills = opts.get("stills") or opts.get("still")
if stills:
    scene.render.image_settings.file_format = "PNG"
    for token in str(stills).split(","):
        f = int(token)
        scene.frame_set(f)
        scene.render.filepath = str(ROOT / "renders" / f"_ladder_{f:04d}.png")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        _t, _r, _s = path_state(f)
        print(f"[ladder] frame {f} (radius {_r:.2f} um) in {time.time() - t0:.0f}s "
              f"-> {scene.render.filepath}", flush=True)
else:
    scene.render.filepath = out
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    el = time.time() - t0
    print(f"[ladder] {FRAMES} frames in {el / 60:.1f} min "
          f"({el / FRAMES:.1f}s/frame) -> {out}", flush=True)
print("[ladder] DONE", flush=True)
