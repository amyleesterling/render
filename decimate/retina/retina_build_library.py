"""Build the render-ready retina mesh library from full resolution.

  clean (remove everything no ray can reach)  ->  decimate to a DENSITY

Two budgets, because only some of these cells are ever looked at. In the direction
selectivity film the 106 direction-selective cells take colour and light up; the
other 258 sit as dim ghost wireframes so the responders read as part of a
population rather than as sparks in the dark. Beading is invisible at ghost
brightness, so spending the same detail on both wastes most of it. Amy approved the
split on 31 July 2026.

WHY DENSITY AND NOT A FACE COUNT. Cells here differ in surface area by more than
tenfold, so one face count gives a small cell luxurious detail and a large one a
dotted outline. Faces per um2 transfers; a face count does not. Thresholds measured
by rendering a ladder on cell 720575940550200928 at a fixed camera:

  74 faces/um2  indistinguishable from the 5.7M face original
  37            mostly continuous, thin processes begin to bead
  18.5          broken into dotted strings
  7.9           the old meshparty library, far past broken

DS cells get 35, which is just under the "begins to bead" line, chosen because in
the mosaic film one cell spans a few hundred pixels rather than the whole frame, so
the beading that shows in a close up is sub-pixel here. Ghosts get 6.

CLEAN BEFORE DECIMATING. About 30% of a full resolution mesh is geometry no ray can
reach: marching cubes inner shells, which are also the polygons hidden inside somas
and the "dust". Removing it first means the whole budget buys visible surface.
Ambient occlusion on this pymeshlab build spans 0 to about 16, NOT 0 to 1, so the
enclosed set is AO at exactly zero.

Resumable: any cell already written is skipped, so an interruption costs one cell.

  python retina_build_library.py [--workers 4] [--ds-density 35] [--ghost-density 6]
"""
import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

AP = argparse.ArgumentParser()
AP.add_argument("--src", default=r"D:\Meshes\retina\meshes_full")
AP.add_argument("--out", default=r"D:\Meshes\retina\meshes_clean")
AP.add_argument("--workers", type=int, default=4)
AP.add_argument("--ds-density", type=float, default=35.0, help="faces per um2, cells that light up")
AP.add_argument("--ghost-density", type=float, default=6.0, help="faces per um2, cells that do not")
AP.add_argument("--min-faces", type=int, default=20_000,
                help="floor, so a small cell never collapses entirely")
A = AP.parse_args()


def build_one(args):
    """One cell, in its own process. pymeshlab is imported here so each worker
    gets its own instance rather than sharing one across forks."""
    import numpy as np
    import pymeshlab

    rid, density, src, out, min_faces = args
    dst = os.path.join(out, f"{rid}.obj")
    if os.path.exists(dst):
        return rid, None, None, None, "skip"
    tmp = dst + ".tmp.obj"
    t0 = time.time()
    try:
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(os.path.join(src, f"{rid}.obj"))
        f0 = ms.current_mesh().face_number()

        # 1. remove everything invisible from every direction
        ms.compute_scalar_ambient_occlusion()
        q = np.asarray(ms.current_mesh().vertex_scalar_array(), dtype=float)
        ms.compute_selection_by_scalar_per_vertex(minq=-1e9, maxq=1e-9)
        ms.meshing_remove_selected_vertices()
        f1 = ms.current_mesh().face_number()

        # 2. decimate to the density. Area is measured AFTER cleaning, so the
        # budget is spent on the surface that survives rather than on a number
        # inflated by the interior shells we just deleted.
        area_um2 = float(ms.get_geometric_measures()["surface_area"]) / 1e6
        target = max(min_faces, int(density * area_um2))
        if target < f1:
            # preservetopology MUST be False: these meshes carry thousands of
            # components and the topology-preserving path refuses most collapses,
            # never reaches the target, and hands back a mesh still near full size.
            ms.meshing_decimation_quadric_edge_collapse(
                targetfacenum=target, preservenormal=True,
                preservetopology=False, planarquadric=True)
        f2 = ms.current_mesh().face_number()

        ms.save_current_mesh(tmp, save_vertex_normal=False)
        os.replace(tmp, dst)          # never leave a partial file a render can glob

        # pymeshlab writes a .mtl beside every .obj and puts an "mtllib" line at
        # the top pointing at it. Renaming the .obj orphans that file, and then
        # Blender logs an ERROR per cell about the mtl it cannot find. With 364
        # cells that is 364 error lines in every render log, which is how a real
        # failure gets buried. Nothing here needs the material: every render
        # script clears materials on import and assigns its own.
        #
        # The reference is removed IN PLACE by turning "mtllib" into "#tllib".
        # Same byte length, and a leading # is an OBJ comment, so no rewrite.
        with open(dst, "r+b") as fh:
            head = fh.read(4096)
            i = head.find(b"mtllib ")
            if i != -1 and (i == 0 or head[i - 1] in (10, 13)):
                fh.seek(i)
                fh.write(b"#")
        mtl = tmp + ".mtl"
        if os.path.exists(mtl):
            os.remove(mtl)
        return rid, f0, f1, f2, f"{time.time()-t0:.0f}s"
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        return rid, None, None, None, f"FAILED {type(e).__name__}: {str(e)[:90]}"


def main():
    os.makedirs(A.out, exist_ok=True)
    df = pd.read_csv(r"D:\Meshes\retina\functional_cells.csv")
    have = {int(f[:-4]) for f in os.listdir(A.src)
            if f.endswith(".obj") and f[:-4].isdigit()}
    jobs = []
    n_ds = 0
    for _, r in df.iterrows():
        rid = int(r["root_id"])
        if rid not in have:
            continue
        is_ds = str(r["is_ds"]) in ("True", "true", "1")
        n_ds += is_ds
        jobs.append((rid, A.ds_density if is_ds else A.ghost_density,
                     A.src, A.out, A.min_faces))
    done_already = len([f for f in os.listdir(A.out) if f.endswith(".obj")])
    print(f"[lib] {len(jobs)} cells ({n_ds} direction selective at "
          f"{A.ds_density} faces/um2, {len(jobs)-n_ds} ghosts at {A.ghost_density}), "
          f"{done_already} already built, {A.workers} workers", flush=True)

    t0, done, total_f, bad = time.time(), 0, 0, []
    with ProcessPoolExecutor(max_workers=A.workers) as ex:
        futs = [ex.submit(build_one, j) for j in jobs]
        for fut in as_completed(futs):
            rid, f0, f1, f2, note = fut.result()
            done += 1
            if note == "skip":
                continue
            if note.startswith("FAILED"):
                bad.append((rid, note))
            else:
                total_f += f2
            if done % 20 == 0 or done == len(jobs):
                el = time.time() - t0
                print(f"[lib] {done}/{len(jobs)}  {el/60:.0f} min  "
                      f"eta {(el/max(1,done))*(len(jobs)-done)/60:.0f} min", flush=True)

    # The number that decides whether the film can be rendered at all. 81M faces
    # renders at about 27 s a frame at 1080p and 64 samples on this card and the
    # cost climbs steeply past there, so this has to be reported, not assumed.
    built = [os.path.join(A.out, f) for f in os.listdir(A.out) if f.endswith(".obj")]
    gb = sum(os.path.getsize(p) for p in built) / 1e9
    print(f"\n[lib] {len(built)} meshes, {gb:.1f} GB", flush=True)
    print(f"[lib] faces written this run: {total_f/1e6:.1f}M", flush=True)
    if bad:
        print(f"[lib] {len(bad)} FAILED:", flush=True)
        for rid, n in bad[:10]:
            print(f"        {rid}  {n}", flush=True)
    print("[lib] DONE", flush=True)


if __name__ == "__main__":
    main()
