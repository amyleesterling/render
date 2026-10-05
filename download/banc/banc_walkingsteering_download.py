"""Download the 81 BANC walking+steering neurons from the PUBLIC precomputed bucket.

Deliberately not the graphene source used by banc_download.py: these 81 ids are the
exact set the banc-explorer Neuroglancer scene renders, and that scene points at
`precomputed://gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_meshes`.
Fetching the same source is what lets the Blender camera be checked against the
Neuroglancer framing rather than merely resembling it. No auth needed.

  python banc_walkingsteering_download.py probe   # info scales + one mesh bbox
  python banc_walkingsteering_download.py         # fetch all 81, resumable
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from cloudvolume import CloudVolume

SRC = "precomputed://gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_meshes"
OUT = r"D:\Meshes\banc\walking_steering"
IDS_JSON = r"D:\Meshes\banc\walking_steering_ids.json"
WORKERS = 4  # same cap as banc_download.py; 8 blew up to 40 GB resident on CA3

os.makedirs(OUT, exist_ok=True)
ids = [int(x) for x in json.load(open(IDS_JSON))["segments"]]
cv = CloudVolume(SRC, use_https=True, progress=False)


def fetch_mesh(i):
    m = cv.mesh.get(i)
    return m[i] if isinstance(m, dict) else m


if len(sys.argv) > 1 and sys.argv[1] == "probe":
    print("scales:", json.dumps(cv.info.get("scales", [{}])[0], indent=2)[:400])
    print("mesh dir:", cv.info.get("mesh"))
    mesh = fetch_mesh(ids[0])
    v = np.asarray(mesh.vertices)
    print(f"\nid {ids[0]}: {len(v)} verts, {len(np.asarray(mesh.faces))} faces")
    print("vertex bbox min:", np.round(v.min(0), 1))
    print("vertex bbox max:", np.round(v.max(0), 1))
    print("vertex bbox size:", np.round(v.max(0) - v.min(0), 1))
    print("\nIf these are nanometres, x/y span the fly (~1e5-1e6 nm) and dividing")
    print("by 4 gives the 4nm voxel coords Neuroglancer's matrices expect.")
    sys.exit(0)

todo = [i for i in ids if not os.path.exists(os.path.join(OUT, f"{i}.obj"))]
print(f"[dl] walking_steering: {len(ids)} cells, {len(ids)-len(todo)} on disk, "
      f"{len(todo)} to fetch, {WORKERS} workers", flush=True)


def fetch(i):
    p = os.path.join(OUT, f"{i}.obj")
    tmp = p + ".tmp.obj"          # never glob a partial file into a render
    try:
        mesh = fetch_mesh(i)
        v, f = np.asarray(mesh.vertices), np.asarray(mesh.faces)
        with open(tmp, "w") as fh:
            fh.write("".join(f"v {a[0]:.1f} {a[1]:.1f} {a[2]:.1f}\n" for a in v))
            fh.write("".join(f"f {a[0]+1} {a[1]+1} {a[2]+1}\n" for a in f))
        os.replace(tmp, p)
        return i, len(f), os.path.getsize(p) / 1e6, v.min(0), v.max(0), None
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        return i, 0, 0.0, None, None, f"{type(e).__name__}: {str(e)[:120]}"


t0, done, faces, mb, bad = time.time(), 0, 0, 0.0, []
lo = np.array([np.inf] * 3)
hi = np.array([-np.inf] * 3)
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for fut in as_completed([ex.submit(fetch, i) for i in todo]):
        i, nf, size, vmin, vmax, err = fut.result()
        done += 1
        if err:
            bad.append((i, err))
            print(f"[dl] {done}/{len(todo)} {i} FAILED {err}", flush=True)
        else:
            faces += nf
            mb += size
            lo = np.minimum(lo, vmin)
            hi = np.maximum(hi, vmax)
            if done % 10 == 0 or done == len(todo):
                el = time.time() - t0
                eta = (el / done) * (len(todo) - done) / 60
                print(f"[dl] {done}/{len(todo)}  {faces/1e6:.1f}M faces  {mb/1000:.2f} GB  "
                      f"{el/60:.1f} min  eta {eta:.1f} min", flush=True)

print(f"[dl] DONE: {done-len(bad)} ok, {len(bad)} failed, {faces/1e6:.1f}M faces, "
      f"{mb/1000:.2f} GB in {(time.time()-t0)/60:.1f} min", flush=True)
if np.isfinite(lo).all():
    print("[dl] cast bbox min:", np.round(lo, 1))
    print("[dl] cast bbox max:", np.round(hi, 1))
    print("[dl] cast bbox size:", np.round(hi - lo, 1))
for i, e in bad:
    print("   failed:", i, e, flush=True)
