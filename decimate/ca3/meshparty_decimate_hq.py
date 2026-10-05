"""
Higher-quality re-decimation of the meshparty hippocampal folders.

Replaces the flat 40% pass, which measured badly: it bridged branches into big
triangles (the 99th-percentile face area grew 1.65x to 2.12x) because a fixed
percentage over-thins already-sparse meshes.

Two changes, both measured:

1. Strip tiny connected components FIRST. These meshes are shredded, one median
   cell had 10,084 components in 92k faces. Components under 25 faces are ~35% of
   the face count but only ~7% of the surface area, so they are the segment
   fragments inside the somas, not anatomy. Removing them drops the component
   count to ~368 and stops the decimator wasting its budget on debris.

2. Target a constant FACE DENSITY instead of a percentage. Originals run about
   5.1 to 5.6 faces per um2, so targeting 5.0 keeps the surface resolution the
   originals had. This is what Amy asked for: larger cells have more surface area,
   so they automatically receive proportionally more polygons.

Result on the test cells: p99 face area 1.01x to 1.54x of original instead of
1.65x to 2.12x, and 15 to 25 points more surface area retained.

Sources in meshparty are read-only. Output goes to D:\\Meshes\\hq so the earlier
40% set stays available for comparison.
"""
import sys
import time
from pathlib import Path

import numpy as np
import pymeshlab

SRC_ROOT = Path(r"C:\Users\amyle\meshparty")
OUT_ROOT = Path(r"D:\Meshes\hq")

CLEAN_MIN_COMPONENT = 25   # faces; below this a component is soma debris
TARGET_DENSITY = 5.0       # faces per um2, for cell-body populations
MIN_FACES = 2000           # floor so tiny cells stay renderable

# Density is only meaningful within a morphology class. Measured medians:
#   cell-body populations   4.0 to 8.2 faces/um2
#   thin axonal fibres    146.0 to 174.0 faces/um2
# A thin tube has almost no surface area but still needs faces around its
# circumference, so a density target built for dendrites guts it. These two
# populations get a straight keep-fraction instead, measured at 75% where
# bloat stays at 1.10x to 1.35x and degrades quickly below that.
FIBRE_KEEP = 0.75
FOLDER_OVERRIDE = {
    "pyr fibers": FIBRE_KEEP,
    "MF 700": FIBRE_KEEP,
}

# Hard floor. No target may cut a mesh below this fraction of its cleaned face
# count. The first run had no floor and reduced the fibre sets to 4% of their
# faces before anyone noticed.
MIN_KEEP_FRACTION = 0.40

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


def p99_face_area(ms):
    m = ms.current_mesh()
    fm, vm = m.face_matrix(), m.vertex_matrix()
    if not len(fm):
        return 0.0
    tri = vm[fm]
    fa = 0.5 * np.linalg.norm(
        np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    return float(np.percentile(fa, 99))


def process(src, dst, keep_frac=None):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(src))
    before = ms.current_mesh().face_number()
    before_p99 = p99_face_area(ms)

    ms.meshing_remove_connected_component_by_face_number(
        mincomponentsize=CLEAN_MIN_COMPONENT)
    after_clean = ms.current_mesh().face_number()

    ms.apply_coord_hc_laplacian_smoothing()

    if keep_frac is not None:
        target = int(after_clean * keep_frac)
    else:
        area_um2 = ms.get_geometric_measures()["surface_area"] / 1e6
        target = int(area_um2 * TARGET_DENSITY)

    target = max(MIN_FACES, target, int(after_clean * MIN_KEEP_FRACTION))

    # Only decimate if the mesh is actually denser than the target. Cleaning alone
    # sometimes brings a cell under it, and decimating further would just damage it.
    if after_clean > target:
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=target, qualitythr=0.3, preserveboundary=True,
            boundaryweight=1.0, preservenormal=False, preservetopology=False,
            optimalplacement=True, planarquadric=False, planarweight=0.001,
            qualityweight=False, autoclean=True, selected=False)

    after = ms.current_mesh().face_number()
    after_p99 = p99_face_area(ms)
    ms.save_current_mesh(str(dst))
    bloat = (after_p99 / before_p99) if before_p99 else 1.0
    return before, after_clean, after, bloat


def safety_check():
    src, out = SRC_ROOT.resolve(), OUT_ROOT.resolve()
    if src == out or out.is_relative_to(src) or src.is_relative_to(out):
        raise SystemExit(f"REFUSING TO RUN: output {out} overlaps source {src}")
    if src.drive.upper() == out.drive.upper():
        raise SystemExit("REFUSING TO RUN: output is on the same drive as the source")
    print(f"source (read-only): {src}", flush=True)
    print(f"output  (writes):   {out}", flush=True)
    print(f"clean < {CLEAN_MIN_COMPONENT} faces, target {TARGET_DENSITY} faces/um2\n", flush=True)


def main():
    safety_check()
    g_before = g_clean = g_after = 0
    done = skipped = 0
    bloats = []
    failures = []
    t0all = time.time()

    for folder in FOLDERS:
        src_dir, out_dir = SRC_ROOT / folder, OUT_ROOT / folder
        if not src_dir.exists():
            print(f"!! missing {src_dir}", flush=True)
            continue
        out_dir.mkdir(parents=True, exist_ok=True)

        objs = sorted(src_dir.glob("*.obj"))
        print(f"\n=== {folder}: {len(objs)} cells ===", flush=True)
        f_b = f_c = f_a = 0
        f_bloats = []
        t0 = time.time()

        for i, src in enumerate(objs, 1):
            seg = src.stem.replace("-meshlab", "")
            dst, tmp = out_dir / f"{seg}.obj", out_dir / f"{seg}.tmp.obj"
            if dst.exists():
                skipped += 1
                continue
            try:
                b, c, a, bloat = process(src, tmp, FOLDER_OVERRIDE.get(folder))
                tmp.replace(dst)
                f_b += b; f_c += c; f_a += a
                f_bloats.append(bloat); bloats.append(bloat)
                g_before += b; g_clean += c; g_after += a
                done += 1
                if i % 50 == 0:
                    print(f"  [{i}/{len(objs)}] {seg}: {b:,} -> {a:,} "
                          f"bloat {bloat:.2f}x", flush=True)
            except Exception as exc:
                print(f"  [{i}/{len(objs)}] {seg} FAILED: {exc}", flush=True)
                failures.append((folder, seg, repr(exc)))
            finally:
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass

        mb = sum(p.stat().st_size for p in out_dir.glob("*.obj")) / 1024**2
        if not f_b:
            print(f"  -> {folder}: nothing to do, all {len(objs)} cells already "
                  f"present ({mb:,.0f} MB)", flush=True)
            continue
        med = float(np.median(f_bloats)) if f_bloats else 0
        print(f"  -> {folder}: {f_b:,} -> {f_a:,} faces ({f_a/f_b*100:.1f}% kept, "
              f"debris removed {(f_b-f_c)/f_b*100:.1f}%), median bloat {med:.2f}x, "
              f"{mb:,.0f} MB, {time.time()-t0:.0f}s", flush=True)

    print("\n=== hq decimation complete ===", flush=True)
    print(f"processed {done}, skipped {skipped}", flush=True)
    if g_before:
        print(f"faces {g_before:,} -> {g_after:,} ({g_after/g_before*100:.1f}% kept)", flush=True)
        print(f"soma debris removed: {g_before-g_clean:,} faces "
              f"({(g_before-g_clean)/g_before*100:.1f}%)", flush=True)
    if bloats:
        b = np.array(bloats)
        print(f"p99 face-area bloat: median {np.median(b):.2f}x, "
              f"p90 {np.percentile(b,90):.2f}x, worst {b.max():.2f}x "
              f"(shipped 40% pass was 1.65x to 2.12x)", flush=True)
    print(f"elapsed {(time.time()-t0all)/60:.1f} min", flush=True)
    total = sum(p.stat().st_size for f in FOLDERS for p in (OUT_ROOT/f).glob("*.obj"))
    print(f"total output: {total/1024**2:,.0f} MB", flush=True)
    if failures:
        print(f"\n{len(failures)} FAILED:", flush=True)
        for folder, seg, exc in failures[:20]:
            print(f"  {folder}/{seg}: {exc}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
