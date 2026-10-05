"""
Decimate the MICrONS cells to a constant face density, not a constant face count.

  python decimate_microns_area.py [workers=3] [density=100] [dst=...]

WHY. RENDERING_NEURONS.md section 3 says to target density per unit AREA rather
than a global face count, and the first pass here ignored it: a flat 1,500,000
faces for every cell gave the smallest cell 276 faces per square micrometre and
the largest only 35, an **8x spread**. Cortical cells are big, up to 42,475 um^2
of membrane against a 22,038 um^2 median, so exactly the cells carrying the apical
tufts were the worst resolved. Amy caught this from the render.

Total membrane across the 38 cells is 809,115 um^2, so 100 faces per um^2 is about
81M faces, which is inside what this machine has rendered (124M proven) and gives
every cell the same surface detail.

Areas are read from renders/microns_area.json, measured on the previous pass.
"""
import os
import sys
import glob
import json
import time
from multiprocessing import Pool

SRC = r"C:\Users\amyle\meshparty"
FOLDERS = ["giant proofread pycs", "L1 cluster", "L5 cluster", "L5 cluster 2"]
AREAS = json.load(open(r"D:\Meshes\renders\microns_area.json"))

opts = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
WORKERS = int(opts.get("workers", 3))
DENSITY = float(opts.get("density", 100))
DST = opts.get("dst", r"D:\Meshes\microns_area")
FLOOR = 60000          # a fragment still needs enough faces to read as a surface


def jobs():
    seen, out = set(), []
    for d in FOLDERS:
        for f in sorted(glob.glob(os.path.join(SRC, d, "*.obj"))):
            seg = os.path.basename(f).split("-")[0].split(".")[0]
            if seg in seen:
                continue
            seen.add(seg)
            area = AREAS.get(seg, AREAS.get(seg[:18], 0.0))
            target = max(FLOOR, int(area * DENSITY))
            out.append((f, seg, d, target))
    return out


def one(job):
    src, seg, folder, target = job
    dst = os.path.join(DST, f"{seg}.obj")
    if os.path.exists(dst) and os.path.getsize(dst) > 1000:
        return (seg, "skip", 0, 0, target, 0.0)
    import pymeshlab
    t0 = time.time()
    try:
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(src)
        before = ms.current_mesh().face_number()
        if before == 0:
            return (seg, "empty", 0, 0, target, time.time() - t0)
        ms.meshing_remove_duplicate_vertices()
        ms.meshing_remove_unreferenced_vertices()
        if before > target:
            ms.meshing_decimation_quadric_edge_collapse(
                targetfacenum=target,
                preservetopology=False,
                preserveboundary=True,
                preservenormal=True,
                planarquadric=True,
            )
        ms.save_current_mesh(dst, save_vertex_normal=False, save_vertex_color=False)
        return (seg, "ok", before, ms.current_mesh().face_number(), target,
                time.time() - t0)
    except Exception as e:
        return (seg, f"FAIL {type(e).__name__}: {str(e)[:60]}", 0, 0, target,
                time.time() - t0)


if __name__ == "__main__":
    os.makedirs(DST, exist_ok=True)
    js = jobs()
    tot_target = sum(j[3] for j in js)
    print(f"[dec] {len(js)} cells, {DENSITY:.0f} faces/um^2, "
          f"{tot_target/1e6:.1f}M faces planned, {WORKERS} workers -> {DST}",
          flush=True)
    done = 0
    t0 = time.time()
    with Pool(WORKERS) as p:
        for seg, status, before, after, target, el in p.imap_unordered(one, js):
            done += 1
            print(f"[dec] {done:2d}/{len(js)} {seg} {status} "
                  f"{before:,} -> {after:,} (target {target:,}) {el:.0f}s", flush=True)
    tot = sum(os.path.getsize(f) for f in glob.glob(os.path.join(DST, "*.obj")))
    print(f"[dec] DONE in {(time.time()-t0)/60:.1f} min, {tot/1048576:.0f} MB",
          flush=True)
