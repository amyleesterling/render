"""
Download the cells that the hero's 6 mossy fibres also contact.

Those fibres make 291 synapses onto 57 other cells, and we have meshes for none
of them, so in the render the fibres currently run off into nothing. This pulls
them and decimates immediately, so peak disk stays small.

Network-bound, so it is safe to run alongside a GPU render.
"""
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pymeshlab
from caveclient import CAVEclient
from meshparty import trimesh_io

HERO = 648518346438632877
OUT = Path(r"D:\Meshes\partners")
CACHE = Path(r"D:\Meshes\_cache_zheng_ca3")
OUT.mkdir(parents=True, exist_ok=True)

syn = pd.read_csv(r"D:\Meshes\renders\mf_synapses.csv")
mine = syn[syn["post_pt_root_id"] == HERO]
fibres = sorted(mine["pre_pt_root_id"].unique())
theirs = syn[syn["pre_pt_root_id"].isin(fibres)]
counts = theirs.groupby("post_pt_root_id").size().sort_values(ascending=False)
targets = [int(s) for s in counts.index if int(s) != HERO]

print(f"the hero's {len(fibres)} fibres contact {len(targets)} other cells", flush=True)
print(f"{theirs.shape[0]} synapses in total\n", flush=True)

client = CAVEclient("zheng_ca3")
cv_path = client.info.segmentation_source()
mm = trimesh_io.MeshMeta(cv_path=cv_path, disk_cache_path=str(CACHE),
                         map_gs_to_https=True)

TARGET_DENSITY = 5.0     # faces per um2, same as the hq pass
MIN_FACES = 2000


def decimate(src, dst):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(src))
    before = ms.current_mesh().face_number()
    ms.meshing_remove_connected_component_by_face_number(mincomponentsize=25)
    ms.apply_coord_hc_laplacian_smoothing()
    area = ms.get_geometric_measures()["surface_area"] / 1e6
    target = max(MIN_FACES, int(area * TARGET_DENSITY),
                 int(ms.current_mesh().face_number() * 0.40))
    if ms.current_mesh().face_number() > target:
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=target, qualitythr=0.3, preserveboundary=True,
            boundaryweight=1.0, preservenormal=False, preservetopology=False,
            optimalplacement=True, planarquadric=False, planarweight=0.001,
            qualityweight=False, autoclean=True, selected=False)
    after = ms.current_mesh().face_number()
    ms.save_current_mesh(str(dst))
    return before, after


ok = fail = 0
t0all = time.time()
for i, seg in enumerate(targets, 1):
    dst = OUT / f"{seg}.obj"
    if dst.exists():
        print(f"[{i}/{len(targets)}] {seg} already present", flush=True)
        ok += 1
        continue
    raw = OUT / f"{seg}.raw.obj"
    tmp = OUT / f"{seg}.tmp.obj"
    t0 = time.time()
    try:
        mesh = mm.mesh(seg_id=seg)
        mesh.write_to_file(str(raw))
        del mesh
        b, a = decimate(raw, tmp)
        tmp.replace(dst)
        ok += 1
        print(f"[{i}/{len(targets)}] {seg}: {b:,} -> {a:,} faces, "
              f"{counts[seg]} syn, {time.time()-t0:.0f}s", flush=True)
    except Exception as exc:
        fail += 1
        print(f"[{i}/{len(targets)}] {seg} FAILED: {exc}", flush=True)
    finally:
        for q in (raw, tmp):
            if q.exists():
                try:
                    os.remove(q)
                except OSError:
                    pass

mb = sum(p.stat().st_size for p in OUT.glob("*.obj")) / 1024 ** 2
print(f"\n=== partners complete: {ok} ok, {fail} failed, {mb:,.0f} MB, "
      f"{(time.time()-t0all)/60:.1f} min ===", flush=True)
print("[partners] DONE", flush=True)
