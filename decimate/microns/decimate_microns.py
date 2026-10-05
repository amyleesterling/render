"""
Decimate the MICrONS cells to something renderable.

  python decimate_microns.py [workers=3] [faces=400000]

The count was never the problem. 40 cells is trivial. The problem is that these
are full resolution MICrONS meshes averaging 691 MB each, 195M faces across the
set, which is above the 124M this machine has actually rendered.

Playbook rules that apply, RENDERING_NEURONS.md section 3:
  * preservetopology=False. True refuses most collapses on a mesh that is already
    a forest of components and you get a fraction of the reduction you asked for.
  * clean before decimating: duplicate and unreferenced vertices first, or the
    quadric error metric is computed against geometry that is not really there.
  * target a face count per cell, not a global one, so a small cell is not
    crushed to nothing while a giant one stays heavy.

Worker count is deliberately low. An 8 worker pool on this machine hit 90
processes and 40.7 GB resident during the gradient download and had to be killed;
Blender is also holding several GB right now.
"""
import os
import sys
import glob
import time
from multiprocessing import Pool

SRC = r"C:\Users\amyle\meshparty"
DST = os.environ.get("MIC_DST", r"D:\Meshes\microns")
FOLDERS = ["giant proofread pycs", "L1 cluster", "L5 cluster", "L5 cluster 2"]

opts = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
WORKERS = int(opts.get("workers", 3))
TARGET = int(opts.get("faces", 400000))


def jobs():
    seen, out = set(), []
    for d in FOLDERS:
        for f in sorted(glob.glob(os.path.join(SRC, d, "*.obj"))):
            seg = os.path.basename(f).split("-")[0].split(".")[0]
            if seg in seen:          # the same cell appears in more than one folder
                continue
            seen.add(seg)
            out.append((f, seg, d))
    return out


def one(job):
    src, seg, folder = job
    dst = os.path.join(DST, f"{seg}.obj")
    if os.path.exists(dst) and os.path.getsize(dst) > 1000:
        return (seg, folder, "skip", 0, 0, 0.0)
    import pymeshlab
    t0 = time.time()
    try:
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(src)
        before = ms.current_mesh().face_number()
        if before == 0:
            return (seg, folder, "empty", 0, 0, time.time() - t0)
        ms.meshing_remove_duplicate_vertices()
        ms.meshing_remove_unreferenced_vertices()
        if before > TARGET:
            ms.meshing_decimation_quadric_edge_collapse(
                targetfacenum=TARGET,
                preservetopology=False,
                preserveboundary=True,      # open edges are where thin neurites tear
                preservenormal=True,
                planarquadric=True,
            )
        ms.save_current_mesh(dst, save_vertex_normal=False, save_vertex_color=False)
        after = ms.current_mesh().face_number()
        return (seg, folder, "ok", before, after, time.time() - t0)
    except Exception as e:
        return (seg, folder, f"FAIL {type(e).__name__}: {str(e)[:70]}", 0, 0,
                time.time() - t0)


if __name__ == "__main__":
    os.makedirs(DST, exist_ok=True)
    js = jobs()
    print(f"[dec] {len(js)} unique cells, {WORKERS} workers, target {TARGET:,} faces",
          flush=True)
    t0 = time.time()
    done = 0
    with Pool(WORKERS) as p:
        for seg, folder, status, before, after, el in p.imap_unordered(one, js):
            done += 1
            print(f"[dec] {done:2d}/{len(js)} {seg} [{folder}] {status} "
                  f"{before:,} -> {after:,} in {el:.0f}s", flush=True)
    tot = sum(os.path.getsize(f) for f in glob.glob(os.path.join(DST, "*.obj")))
    print(f"[dec] DONE in {(time.time()-t0)/60:.1f} min, "
          f"{tot/1048576:.0f} MB total, ~{tot/1048576*8858/1e6:.0f}M faces", flush=True)
