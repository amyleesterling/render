"""
Phase 1: download full-resolution CA3 pyramidal meshes from CAVE (zheng_ca3).

Downloads only. No MeshLab work, so this is safe to run alongside a GPU render:
network + disk I/O, negligible CPU, no GPU.

Full-res meshes land in the .h5 disk cache, so phase 2 (smooth + decimate) can run
later without re-downloading anything.
"""
import os
import sys
import time
from pathlib import Path

from caveclient import CAVEclient
from meshparty import trimesh_io

ROOT = Path(r"D:\Meshes")
CACHE = ROOT / "_cache_zheng_ca3"

GROUPS = {
    "CA3 deep layer": [
        648518346436346772,
        648518346436545406,
        648518346439964368,
        648518346446946719,
        648518346447895955,
        648518346457155090,
        648518346462169475,
    ],
    "CA3 superficial layer": [
        648518346432336695,
        648518346435405466,
        648518346436628698,
        648518346437066717,
        648518346440500437,
        648518346440674342,
        648518346441086045,
        648518346443001707,
        648518346447553683,
    ],
}


def main():
    CACHE.mkdir(parents=True, exist_ok=True)

    client = CAVEclient("zheng_ca3")
    cv_path = client.info.segmentation_source()
    print(f"segmentation source: {cv_path}", flush=True)
    print(f"cache: {CACHE}", flush=True)

    mesh_meta = trimesh_io.MeshMeta(
        cv_path=cv_path,
        disk_cache_path=str(CACHE),
        map_gs_to_https=True,
    )

    todo = [(g, s) for g, ids in GROUPS.items() for s in ids]
    print(f"{len(todo)} meshes queued\n", flush=True)

    failures = []
    for i, (group, seg_id) in enumerate(todo, 1):
        cached = CACHE / f"{seg_id}.h5"
        if cached.exists():
            mb = cached.stat().st_size / (1024 * 1024)
            print(f"[{i}/{len(todo)}] {seg_id} ({group}) already cached, {mb:.1f} MB", flush=True)
            continue

        t0 = time.time()
        try:
            mesh = mesh_meta.mesh(seg_id=seg_id)
        except Exception as exc:
            print(f"[{i}/{len(todo)}] {seg_id} ({group}) FAILED: {exc}", flush=True)
            failures.append((seg_id, group, repr(exc)))
            continue

        mb = cached.stat().st_size / (1024 * 1024) if cached.exists() else 0.0
        print(
            f"[{i}/{len(todo)}] {seg_id} ({group}) "
            f"{len(mesh.faces):,} faces, {mb:.1f} MB, {time.time() - t0:.0f}s",
            flush=True,
        )

    print("\n=== download phase complete ===", flush=True)
    if failures:
        print(f"{len(failures)} FAILED:", flush=True)
        for seg_id, group, exc in failures:
            print(f"  {seg_id} ({group}): {exc}", flush=True)
        sys.exit(1)
    print("all meshes cached", flush=True)


if __name__ == "__main__":
    main()
