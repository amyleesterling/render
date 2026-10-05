"""
Phase 2: smooth + decimate the CA3 meshes to 40% of their original face count.

CPU and RAM heavy. Run this only when the Cinema 4D render is finished.

Reads full-res meshes from the .h5 cache written by ca3_layers_download.py, so it
does no network work and can be re-run at a different ratio cheaply.

Pipeline per mesh, in this order:
  1. HC Laplacian smoothing (Vollmer et al.) - volume preserving, keeps spines
  2. Quadric edge collapse decimation to targetperc=0.4

Decimation parameters match the settings in "eyewire2 downsample ca2.mlx".
"""
import os
import time
from pathlib import Path

import pymeshlab
from caveclient import CAVEclient
from meshparty import trimesh_io

ROOT = Path(r"D:\Meshes")
CACHE = ROOT / "_cache_zheng_ca3"

TARGET_PERC = 0.4  # final mesh keeps 40% of original faces

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


def smooth_and_decimate(temp_path, final_path, seg_id):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(temp_path))
    before = ms.current_mesh().face_number()

    ms.apply_coord_hc_laplacian_smoothing()

    ms.meshing_decimation_quadric_edge_collapse(
        targetperc=TARGET_PERC,
        qualitythr=0.3,
        preserveboundary=True,
        boundaryweight=1.0,
        preservenormal=False,
        preservetopology=True,
        optimalplacement=True,
        planarquadric=False,
        planarweight=0.001,
        qualityweight=False,
        autoclean=True,
        selected=False,
    )

    after = ms.current_mesh().face_number()
    ms.save_current_mesh(str(final_path))

    mb = os.path.getsize(final_path) / (1024 * 1024)
    pct = (after / before * 100) if before else 0
    print(
        f"    {before:,} -> {after:,} faces ({pct:.1f}% kept), {mb:.1f} MB",
        flush=True,
    )


def main():
    client = CAVEclient("zheng_ca3")
    cv_path = client.info.segmentation_source()
    mesh_meta = trimesh_io.MeshMeta(
        cv_path=cv_path,
        disk_cache_path=str(CACHE),
        map_gs_to_https=True,
    )

    todo = [(g, s) for g, ids in GROUPS.items() for s in ids]
    print(f"smoothing + decimating {len(todo)} meshes to {TARGET_PERC:.0%} of faces\n", flush=True)

    failures = []
    for i, (group, seg_id) in enumerate(todo, 1):
        out_dir = ROOT / group
        out_dir.mkdir(parents=True, exist_ok=True)

        final_path = out_dir / f"{seg_id}.obj"
        temp_path = out_dir / f"{seg_id}_temp.obj"

        if final_path.exists():
            print(f"[{i}/{len(todo)}] {seg_id} ({group}) already done, skipping", flush=True)
            continue

        t0 = time.time()
        print(f"[{i}/{len(todo)}] {seg_id} ({group})", flush=True)
        try:
            mesh = mesh_meta.mesh(seg_id=seg_id)
            mesh.write_to_file(str(temp_path))
            del mesh

            smooth_and_decimate(temp_path, final_path, seg_id)
            print(f"    {time.time() - t0:.0f}s", flush=True)
        except Exception as exc:
            print(f"    FAILED: {exc}", flush=True)
            failures.append((seg_id, group, repr(exc)))
        finally:
            if temp_path.exists():
                os.remove(temp_path)

    print("\n=== decimation complete ===", flush=True)
    for group in GROUPS:
        d = ROOT / group
        if d.exists():
            objs = sorted(d.glob("*.obj"))
            total = sum(o.stat().st_size for o in objs) / (1024 * 1024)
            print(f"  {group}: {len(objs)} .obj files, {total:.1f} MB", flush=True)
    if failures:
        print(f"\n{len(failures)} FAILED:", flush=True)
        for seg_id, group, exc in failures:
            print(f"  {seg_id} ({group}): {exc}", flush=True)


if __name__ == "__main__":
    main()
