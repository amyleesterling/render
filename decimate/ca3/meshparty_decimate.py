"""
Smooth + decimate the meshparty hippocampal folders to 40% of their face count.

Same pipeline as ca3_layers_decimate.py:
  1. HC Laplacian smoothing (volume preserving)
  2. Quadric edge collapse to targetperc=0.4, using the settings from
     "eyewire2 downsample ca2.mlx"

Sources are read from C:\\Users\\amyle\\meshparty and never modified. Output goes to
D:\\Meshes\\<same folder name>.

Resumable: any cell whose output .obj already exists is skipped, so this can be
stopped and restarted freely.

Note: these meshes carry a handful of stray vertices each, sitting far outside the
dataset volume. That is left alone deliberately, since deleting geometry risks real
detail. ca3_animation.py handles it with percentile-based bounds instead.
"""
import os
import sys
import time
from pathlib import Path

import pymeshlab

SRC_ROOT = Path(r"C:\Users\amyle\meshparty")
OUT_ROOT = Path(r"D:\Meshes")
TARGET_PERC = 0.4

# smallest first, so usable output appears early and the 2.8 GB set runs last
FOLDERS = [
    "inhibitory ca3 28",
    "sparsely thorny pyramidals ca3 68",
    "pyr pyr 2",
    "pyr fibers",
    "pyr 600",
    "pyr MF pyc",
    "thorny pyramidals ca3 250",
    "MF 700",
]


def smooth_and_decimate(src, dst):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(src))
    before = ms.current_mesh().face_number()

    ms.apply_coord_hc_laplacian_smoothing()
    ms.meshing_decimation_quadric_edge_collapse(
        targetperc=TARGET_PERC,
        qualitythr=0.3,
        preserveboundary=True,
        boundaryweight=1.0,
        preservenormal=False,
        # Must be False for these meshes. They are heavily fragmented, one 74k-face
        # cell measured 6,200 connected components and 966 non-two-manifold edges,
        # and topology preservation blocks nearly every collapse on geometry like
        # that: it yielded 95.1% kept instead of 40%. The CAVE meshes are far
        # cleaner (272 components, 0 non-manifold edges) and hit 40% either way.
        preservetopology=False,
        optimalplacement=True,
        planarquadric=False,
        planarweight=0.001,
        qualityweight=False,
        autoclean=True,
        selected=False,
    )
    after = ms.current_mesh().face_number()
    ms.save_current_mesh(str(dst))
    return before, after


def safety_check():
    """Refuse to run if anything could write into the source tree.

    Originals in meshparty are read-only inputs. Every write must land under
    OUT_ROOT on D:, and OUT_ROOT must not sit inside SRC_ROOT.
    """
    src = SRC_ROOT.resolve()
    out = OUT_ROOT.resolve()
    if src == out or out.is_relative_to(src) or src.is_relative_to(out):
        raise SystemExit(f"REFUSING TO RUN: output {out} overlaps source {src}")
    if src.drive.upper() == out.drive.upper():
        raise SystemExit(f"REFUSING TO RUN: output is on the same drive as the source")

    collisions = []
    for folder in FOLDERS:
        d = OUT_ROOT / folder
        if d.exists():
            existing = list(d.glob("*.obj"))
            if existing:
                collisions.append((folder, len(existing)))
    if collisions:
        print("note: resuming, these output folders already hold files:", flush=True)
        for folder, n in collisions:
            print(f"  {folder}: {n} .obj already present, will be skipped", flush=True)

    print(f"source (read-only): {src}", flush=True)
    print(f"output  (writes):   {out}", flush=True)


def main():
    safety_check()
    grand_before = grand_after = 0
    grand_done = grand_skip = 0
    failures = []
    off_target = []
    t_start = time.time()

    for folder in FOLDERS:
        src_dir = SRC_ROOT / folder
        out_dir = OUT_ROOT / folder
        if not src_dir.exists():
            print(f"!! missing source: {src_dir}", flush=True)
            continue
        out_dir.mkdir(parents=True, exist_ok=True)

        objs = sorted(src_dir.glob("*.obj"))
        print(f"\n=== {folder}: {len(objs)} cells ===", flush=True)
        f_before = f_after = 0
        t_folder = time.time()

        for i, src in enumerate(objs, 1):
            seg = src.stem.replace("-meshlab", "")
            dst = out_dir / f"{seg}.obj"
            tmp = out_dir / f"{seg}.tmp.obj"

            if dst.exists():
                grand_skip += 1
                continue

            t0 = time.time()
            try:
                before, after = smooth_and_decimate(src, tmp)
                ratio = after / before if before else 0
                # Guard: a mesh that refuses to decimate means the settings are
                # wrong for it, and silently shipping it would look like success.
                if ratio > TARGET_PERC * 1.5:
                    off_target.append((folder, seg, before, after))
                    print(f"  [{i}/{len(objs)}] {seg}: OFF TARGET "
                          f"{before:,} -> {after:,} ({ratio * 100:.1f}% kept)", flush=True)
                tmp.replace(dst)
                f_before += before
                f_after += after
                grand_before += before
                grand_after += after
                grand_done += 1
                if i % 25 == 0 or before > 2_000_000:
                    print(f"  [{i}/{len(objs)}] {seg}: {before:,} -> {after:,} "
                          f"({time.time() - t0:.0f}s)", flush=True)
            except Exception as exc:
                print(f"  [{i}/{len(objs)}] {seg} FAILED: {exc}", flush=True)
                failures.append((folder, seg, repr(exc)))
            finally:
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass

        mb = sum(p.stat().st_size for p in out_dir.glob("*.obj")) / (1024 ** 2)
        pct = (f_after / f_before * 100) if f_before else 0
        print(f"  -> {folder}: {f_before:,} -> {f_after:,} faces ({pct:.1f}% kept), "
              f"{mb:,.0f} MB on disk, {time.time() - t_folder:.0f}s", flush=True)

    print("\n=== meshparty decimation complete ===", flush=True)
    print(f"processed {grand_done} cells, skipped {grand_skip} already done", flush=True)
    if grand_before:
        print(f"faces {grand_before:,} -> {grand_after:,} "
              f"({grand_after / grand_before * 100:.1f}% kept)", flush=True)
    print(f"elapsed {(time.time() - t_start) / 60:.1f} min", flush=True)

    total_mb = sum(p.stat().st_size for f in FOLDERS
                   for p in (OUT_ROOT / f).glob("*.obj")) / (1024 ** 2)
    print(f"total output: {total_mb:,.0f} MB", flush=True)

    if off_target:
        print(f"\n{len(off_target)} cells did NOT reach the target ratio:", flush=True)
        for folder, seg, before, after in off_target[:20]:
            print(f"  {folder}/{seg}: {before:,} -> {after:,} "
                  f"({after / before * 100:.1f}% kept)", flush=True)
        if len(off_target) > 20:
            print(f"  ... and {len(off_target) - 20} more", flush=True)
    else:
        print("every cell reached the target ratio", flush=True)

    if failures:
        print(f"\n{len(failures)} FAILED:", flush=True)
        for folder, seg, exc in failures:
            print(f"  {folder}/{seg}: {exc}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
