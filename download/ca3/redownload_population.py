"""
Re-download a meshparty population from CAVE at full resolution.

Why: the legacy .obj exports in meshparty are far coarser than the source data.
Measured edge lengths, per cell:

  CAVE-downloaded CA3 cells   74-76 faces/um2   p99.9 edge   426 nm   0.00% of edges >2um
  inhibitory ca3 28 (legacy)   2.1 faces/um2    p99   edge 12,830 nm  13.53% of edges >2um

A dendrite is about 1 um across, so a 12.8 um edge spans a dozen branch widths.
Those are the blade triangles, and they are baked into the legacy files. No
decimation setting can restore detail that is not in the input, so the fix is to
pull the meshes again from the segmentation.

Freshly downloaded CAVE meshes are clean (few components, no non-manifold edges),
so the plain 40% quadric pass used for the other CA3 cells applies here and lands
at ~74 faces/um2 with no long edges.

Usage:  python redownload_population.py "inhibitory ca3 28"
"""
import os
import re
import sys
import time
from pathlib import Path

import pymeshlab
from caveclient import CAVEclient
from meshparty import trimesh_io

SRC_ROOT = Path(r"C:\Users\amyle\meshparty")
OUT_ROOT = Path(r"D:\Meshes\hq")
CACHE = Path(r"D:\Meshes\_cache_zheng_ca3")
TARGET_PERC = 0.4
ID_RE = re.compile(r"(\d{8,25})")


def seg_ids_for(folder):
    d = SRC_ROOT / folder
    if not d.exists():
        raise SystemExit(f"no such folder: {d}")
    ids = []
    for p in sorted(d.glob("*.obj")):
        m = ID_RE.search(p.stem)
        if m:
            ids.append(int(m.group(1)))
    return sorted(set(ids))


def smooth_and_decimate(src, dst):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(src))
    before = ms.current_mesh().face_number()
    ms.apply_coord_hc_laplacian_smoothing()
    ms.meshing_decimation_quadric_edge_collapse(
        targetperc=TARGET_PERC, qualitythr=0.3, preserveboundary=True,
        boundaryweight=1.0, preservenormal=False, preservetopology=True,
        optimalplacement=True, planarquadric=False, planarweight=0.001,
        qualityweight=False, autoclean=True, selected=False)
    after = ms.current_mesh().face_number()
    ms.save_current_mesh(str(dst))
    return before, after


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "inhibitory ca3 28"
    seg_ids = seg_ids_for(folder)
    out_dir = OUT_ROOT / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    print(f"population: {folder}", flush=True)
    print(f"{len(seg_ids)} segment ids", flush=True)
    print(f"output: {out_dir}\n", flush=True)

    client = CAVEclient("zheng_ca3")
    cv_path = client.info.segmentation_source()
    mesh_meta = trimesh_io.MeshMeta(cv_path=cv_path, disk_cache_path=str(CACHE),
                                    map_gs_to_https=True)

    tot_b = tot_a = 0
    failures = []
    t0all = time.time()
    for i, seg_id in enumerate(seg_ids, 1):
        final = out_dir / f"{seg_id}.obj"
        tmp = out_dir / f"{seg_id}.tmp.obj"
        raw = out_dir / f"{seg_id}.raw.obj"
        t0 = time.time()
        try:
            mesh = mesh_meta.mesh(seg_id=seg_id)
            mesh.write_to_file(str(raw))
            del mesh
            b, a = smooth_and_decimate(raw, tmp)
            tmp.replace(final)
            tot_b += b
            tot_a += a
            print(f"[{i}/{len(seg_ids)}] {seg_id}: {b:,} -> {a:,} faces "
                  f"({a/b*100:.1f}%), {time.time()-t0:.0f}s", flush=True)
        except Exception as exc:
            print(f"[{i}/{len(seg_ids)}] {seg_id} FAILED: {exc}", flush=True)
            failures.append((seg_id, repr(exc)))
        finally:
            for p in (raw, tmp):
                if p.exists():
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    print(f"\n=== redownload complete: {folder} ===", flush=True)
    if tot_b:
        print(f"faces {tot_b:,} -> {tot_a:,} ({tot_a/tot_b*100:.1f}% kept)", flush=True)
    mb = sum(p.stat().st_size for p in out_dir.glob("*.obj")) / 1024**2
    print(f"{len(list(out_dir.glob('*.obj')))} files, {mb:,.0f} MB", flush=True)
    print(f"elapsed {(time.time()-t0all)/60:.1f} min", flush=True)
    if failures:
        print(f"\n{len(failures)} FAILED:", flush=True)
        for seg_id, exc in failures:
            print(f"  {seg_id}: {exc}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
