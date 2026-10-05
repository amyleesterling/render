"""
Pull the hero thorny cell and its mossy fibres from CAVE at full resolution.

The decimated copies cannot show thorny excrescences: those are sub-micron
structures, and the 40% pass plus the legacy exports smooth them away. This
downloads native meshes so the boutons wrapping the thorns are actually visible.

  hero  648518346438632877  165 mossy fibre synapses from 6 distinct fibres
"""
import os
import time
from pathlib import Path

from caveclient import CAVEclient
from meshparty import trimesh_io

OUT = Path(r"D:\Meshes\hero")
CACHE = Path(r"D:\Meshes\_cache_zheng_ca3")
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

ids = open(r"D:\Meshes\renders\hero_ids.txt").read().split("\n")
HERO = int(ids[0])
FIBRES = [int(x) for x in ids[1].split(",")]

print(f"hero cell:    {HERO}")
print(f"mossy fibres: {len(FIBRES)}")
print(f"output:       {OUT}\n", flush=True)

client = CAVEclient("zheng_ca3")
cv_path = client.info.segmentation_source()
mm = trimesh_io.MeshMeta(cv_path=cv_path, disk_cache_path=str(CACHE),
                         map_gs_to_https=True)

todo = [("hero", HERO)] + [("fibre", f) for f in FIBRES]
for i, (kind, seg) in enumerate(todo, 1):
    dst = OUT / f"{kind}_{seg}.obj"
    if dst.exists():
        print(f"[{i}/{len(todo)}] {seg} already present", flush=True)
        continue
    t0 = time.time()
    try:
        mesh = mm.mesh(seg_id=seg)
        # full resolution: no decimation, the whole point is the fine detail
        mesh.write_to_file(str(dst))
        mb = dst.stat().st_size / 1024 ** 2
        print(f"[{i}/{len(todo)}] {kind} {seg}: {len(mesh.faces):,} faces, "
              f"{mb:,.0f} MB, {time.time()-t0:.0f}s", flush=True)
        del mesh
    except Exception as exc:
        print(f"[{i}/{len(todo)}] {seg} FAILED: {exc}", flush=True)

total = sum(p.stat().st_size for p in OUT.glob("*.obj")) / 1024 ** 3
print(f"\n=== hero set complete: {len(list(OUT.glob('*.obj')))} meshes, "
      f"{total:.2f} GB ===", flush=True)
print("[hero] DONE", flush=True)
