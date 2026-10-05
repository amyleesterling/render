"""Is the small-component "dust" really dust, on FULL RESOLUTION meshes?

The same question asked of the staged meshes gave a flat no: cell 720575940550200928
had 10,122 components with the largest at 6.5%, and dropping everything under 250
faces deleted 58% of the cell. But those meshes were already downsampled by
something that destroyed their connectivity, so that answer was about the
downsampler, not about the segmentation.

Full resolution is a different object: 4,876 components with the largest at 94.9%.
That LOOKS like one neuron plus litter. This checks whether it actually is, before
anything gets deleted.

THE TEST. Face count cannot tell a fragment from a dendrite tip, because both are
small. Position can. Real dendrite tips are at the PERIPHERY of the arbor and are
CLOSE to the main body they broke off from. Segmentation litter is scattered, and
sits far from any surface of the main component. So for every small piece we ask:

  1. how far from the arbor centre does it sit, against the main component's reach
  2. how far is it from the nearest point of the MAIN component

A piece that is 2 nm from the main body is a tip that lost its connection and must
be kept. A piece floating 5 um away in empty space is litter. That distance, not
the face count, is the honest discriminator.

  python mesh_dust_probe.py [--cell ID] [--minfaces 250]
"""
import argparse
import os
import time

import numpy as np
import trimesh

AP = argparse.ArgumentParser()
AP.add_argument("--cell", default="720575940550200928")
AP.add_argument("--dir", default=r"D:\Meshes\retina\meshes_full")
AP.add_argument("--minfaces", type=int, default=250)
A = AP.parse_args()

p = os.path.join(A.dir, f"{A.cell}.obj")
t0 = time.time()
m = trimesh.load(p, process=False)
print(f"[d] {A.cell}: {len(m.faces):,} faces, loaded in {time.time()-t0:.0f}s", flush=True)

parts = m.split(only_watertight=False)
parts = sorted(parts, key=lambda x: len(x.faces), reverse=True)
main, rest = parts[0], parts[1:]
print(f"[d] {len(parts):,} components, main is {100*len(main.faces)/len(m.faces):.1f}% of faces",
      flush=True)

small = [x for x in rest if len(x.faces) < A.minfaces]
big = [x for x in rest if len(x.faces) >= A.minfaces]
print(f"[d] under {A.minfaces} faces: {len(small):,} pieces, "
      f"{sum(len(x.faces) for x in small):,} faces "
      f"({100*sum(len(x.faces) for x in small)/len(m.faces):.2f}% of the mesh)", flush=True)

# Distance from each small piece to the nearest point on the MAIN component. A
# ProximityQuery over 5.4M faces is far too slow per piece, so the main body is
# sampled to a point cloud and a KD tree answers the query. Sampling can only
# OVERestimate the distance, which is the safe direction: it makes a piece look
# further from the body than it is, so anything this calls litter really is.
t0 = time.time()
NS = 400_000
cloud, _ = trimesh.sample.sample_surface(main, NS)
tree = trimesh.points.PointCloud(cloud).kdtree
print(f"[d] sampled {NS:,} points on the main body in {time.time()-t0:.0f}s", flush=True)

lo, hi = m.bounds
diag = float(np.linalg.norm(hi - lo))
cen = (lo + hi) / 2.0

rows = []
for x in small:
    v = np.asarray(x.vertices)
    d_body = float(tree.query(v)[0].min())          # nearest approach to the main body
    d_cen = float(np.linalg.norm(v - cen, axis=1).max())
    rows.append((len(x.faces), d_body, d_cen))
rows = np.array(rows) if rows else np.zeros((0, 3))

main_reach = float(np.linalg.norm(np.asarray(main.vertices) - cen, axis=1).max())
print(f"\n[d] main component reaches {main_reach:.0f} from centre "
      f"({100*main_reach/diag:.1f}% of the bbox diagonal, {diag:.0f})", flush=True)

if len(rows):
    d = rows[:, 1]
    print(f"\n[d] distance from each dust piece to the nearest main-body surface:")
    for q in (5, 25, 50, 75, 95, 100):
        print(f"      p{q:<4} {np.percentile(d, q):>12,.0f} nm")
    # A tip that merely lost its link sits essentially ON the body. Litter does not.
    for cut in (50, 200, 1000, 5000, 20000):
        n = int((d <= cut).sum())
        f = int(rows[d <= cut, 0].sum())
        print(f"      within {cut:>6,} nm of the body: {n:>6,} pieces, {f:>9,} faces "
              f"({100*f/len(m.faces):5.2f}% of mesh)  <- these are TIPS, keep them")
    far = d > 20000
    print(f"\n[d] beyond 20,000 nm from the body: {int(far.sum()):,} pieces, "
          f"{int(rows[far,0].sum()):,} faces "
          f"({100*rows[far,0].sum()/len(m.faces):.3f}% of mesh)  <- litter, safe to drop")
    print(f"[d] of those, furthest reaches {100*rows[far,2].max()/diag if far.any() else 0:.1f}% "
          f"of the diagonal from centre")
