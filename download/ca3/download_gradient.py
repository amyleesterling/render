"""
Download + decimate the proximodistal-gradient sample into D:\\Meshes\\gradient\\.

Reads  D:\\Meshes\\renders\\gradient_sample.csv  (root_id column)
Writes D:\\Meshes\\gradient\\<root_id>.obj

Differences from download_partners.py, on purpose:
  * NO `faces*0.40` keep-floor.  That floor won on every cell in the partners run
    and produced 40 MB/cell instead of ~5 MB (see RENDERING_NEURONS.md sec 3).
    Target is purely area-based: max(MIN_FACES, area_um2 * 5.0).
  * multiprocessing across WORKERS processes (downloads are network-bound)
  * per-worker mesh cache directory, wiped as it goes, so peak disk stays small
  * one failure never kills the run

FOOTPRINT. An 8-worker run put 40 GB resident across 90 processes (cloudvolume
spawns its own children) on a 63.7 GB machine. Native meshes are over 130 MB on
disk and several GB in memory while pymeshlab works on them, and the allocator
does not hand it back. Fixes, all of which matter:
  * WORKERS defaults to 4, not 8. The download is network-bound at ~2.4 min/cell
    so wall clock barely moves, but peak memory drops to roughly a third.
  * maxtasksperchild=1: each worker is retired after ONE cell, so its memory is
    genuinely returned to the OS instead of being held by the allocator. Costs a
    few seconds of re-init per cell, which is noise next to the download.
  * the raw OBJ is deleted the moment pymeshlab has read it, not at the end.

usage: python download_gradient.py [workers] [limit]
"""
import os, sys, gc, time, shutil, traceback
from pathlib import Path
import multiprocessing as mp

OUT = Path(r"D:\Meshes\gradient")
CSV = Path(r"D:\Meshes\renders\gradient_sample.csv")
CACHE_ROOT = Path(r"D:\Meshes\_cache_grad")
TARGET_DENSITY = 5.0        # faces per um^2
MIN_FACES = 2000

WORKERS = int(sys.argv[1]) if len(sys.argv) > 1 else 4
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 0

_state = {}


def init():
    import numpy as np
    from caveclient import CAVEclient
    from meshparty import trimesh_io
    cdir = CACHE_ROOT / f"w{os.getpid()}"
    cdir.mkdir(parents=True, exist_ok=True)
    client = CAVEclient("zheng_ca3")
    _state["mm"] = trimesh_io.MeshMeta(cv_path=client.info.segmentation_source(),
                                       disk_cache_path=str(cdir), map_gs_to_https=True)
    _state["cdir"] = cdir


def decimate(src, dst):
    import pymeshlab
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(src))
    # pymeshlab has the geometry now; drop the 130 MB temporary immediately
    # rather than at the end of the cell, so at most WORKERS raws exist at once
    try:
        os.remove(src)
    except OSError:
        pass
    before = ms.current_mesh().face_number()
    ms.meshing_remove_connected_component_by_face_number(mincomponentsize=25)
    ms.apply_coord_hc_laplacian_smoothing()
    area = ms.get_geometric_measures()["surface_area"] / 1e6      # um^2
    target = max(MIN_FACES, int(area * TARGET_DENSITY))           # <- no 0.40 floor
    if ms.current_mesh().face_number() > target:
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=target, qualitythr=0.3, preserveboundary=True,
            boundaryweight=1.0, preservenormal=False, preservetopology=False,
            optimalplacement=True, planarquadric=False, planarweight=0.001,
            qualityweight=False, autoclean=True, selected=False)
    after = ms.current_mesh().face_number()
    ms.save_current_mesh(str(dst))
    return before, after, area


def job(seg):
    dst = OUT / f"{seg}.obj"
    if dst.exists() and dst.stat().st_size > 1000:
        return (seg, "skip", 0, 0, 0, 0.0)
    raw = OUT / f"{seg}.raw.obj"
    tmp = OUT / f"{seg}.tmp.obj"
    t0 = time.time()
    try:
        mesh = _state["mm"].mesh(seg_id=seg)
        mesh.write_to_file(str(raw))
        del mesh
        gc.collect()                      # release the native mesh before pymeshlab loads
        b, a, area = decimate(raw, tmp)
        tmp.replace(dst)
        return (seg, "ok", b, a, area, time.time() - t0)
    except Exception as exc:
        return (seg, f"FAIL {type(exc).__name__}: {exc}", 0, 0, 0, time.time() - t0)
    finally:
        for q in (raw, tmp):
            if q.exists():
                try: os.remove(q)
                except OSError: pass
        try:
            for f in _state["cdir"].glob("*"):
                try: os.remove(f)
                except OSError: pass
        except Exception:
            pass
        gc.collect()


def main():
    import pandas as pd
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(CSV)
    # Interleave: round-robin across arc bins, and inside each bin alternate the
    # lowest and highest convergence outward from the middle. Any prefix of the
    # resulting order therefore spans the whole axis and the whole MF range, so a
    # partial download is already renderable.
    order = []
    per = {}
    for b, g in df.sort_values("n_mf").groupby("arc_bin"):
        ids = g.root_id.tolist()
        zig = []
        lo, hi = 0, len(ids) - 1
        while lo <= hi:
            zig.append(ids[hi]); hi -= 1
            if lo <= hi:
                zig.append(ids[lo]); lo += 1
        per[b] = zig
    while any(per.values()):
        for b in sorted(per):
            if per[b]:
                order.append(per[b].pop(0))
    segs = [int(s) for s in order]
    if LIMIT:
        segs = segs[:LIMIT]
    todo = [s for s in segs if not (OUT / f"{s}.obj").exists()]
    print(f"{len(segs)} in sample, {len(segs)-len(todo)} already on disk, "
          f"{len(todo)} to fetch, {WORKERS} workers", flush=True)

    t0 = time.time()
    ok = fail = 0
    tot_before = tot_after = 0
    # maxtasksperchild=1 retires each worker after one cell so its memory
    # actually goes back to the OS. Without it an 8-worker run held 40 GB.
    with mp.Pool(WORKERS, initializer=init, maxtasksperchild=1) as pool:
        for i, (seg, status, b, a, area, dt) in enumerate(pool.imap_unordered(job, todo), 1):
            if status == "ok":
                ok += 1; tot_before += b; tot_after += a
                print(f"[{i}/{len(todo)}] {seg}: {b:,} -> {a:,} faces "
                      f"({area:,.0f} um2, {a/max(area,1):.1f} f/um2) {dt:.0f}s", flush=True)
            elif status == "skip":
                ok += 1
            else:
                fail += 1
                print(f"[{i}/{len(todo)}] {seg} {status}", flush=True)
            if i % 20 == 0:
                el = time.time() - t0
                mb = sum(p.stat().st_size for p in OUT.glob("*.obj")) / 1024**2
                print(f"  ... {i}/{len(todo)} done, {ok} ok, {fail} fail, "
                      f"{mb:,.0f} MB, {el/60:.1f} min, "
                      f"eta {el/i*(len(todo)-i)/60:.0f} min", flush=True)

    mb = sum(p.stat().st_size for p in OUT.glob("*.obj")) / 1024**2
    n = len(list(OUT.glob("*.obj")))
    print(f"\n=== {ok} ok, {fail} failed | {n} obj, {mb:,.0f} MB "
          f"({mb/max(n,1):.1f} MB/cell) | faces {tot_before:,} -> {tot_after:,} "
          f"| {(time.time()-t0)/60:.1f} min ===", flush=True)
    shutil.rmtree(CACHE_ROOT, ignore_errors=True)
    print("GRADIENT DOWNLOAD DONE", flush=True)


if __name__ == "__main__":
    main()
