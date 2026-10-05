"""Download the calcium-imaged cells that have no mesh staged yet.

180 of the 364 functional cells were already in the meshparty library. This pulls
the rest from CAVE so the mosaic can be rendered whole.

Worker pool capped at 4, as the CA3 queue doc warns: an 8 worker pool once hit 90
processes and 40.7 GB resident and had to be killed. Any id already on disk is
skipped, so a restart loses nothing.
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import caveclient
import numpy as np
import pandas as pd
from cloudvolume import CloudVolume

WORKERS = 4
# FULL RESOLUTION, not the staged directory. The staged library is unusable as a
# decimation source: the same cell is one intact object at full resolution (4,876
# components, largest 94.9% of the mesh) and 10,122 fragments after the meshparty
# downsample (largest 6.5%). Quadric edge collapse cannot preserve a branch with no
# continuous surface to collapse along, so re-decimating that library can only make
# it worse. Everything gets rebuilt from here.
OUT = r"D:\Meshes\retina\meshes_full"
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(r"D:\Meshes\retina\functional_cells.csv")
have = {int(f[:-4]) for f in os.listdir(OUT) if f.endswith(".obj")}
todo = [int(r) for r in df["root_id"] if int(r) not in have]
print(f"[dl] {len(df)} functional cells, {len(have)} staged, {len(todo)} to fetch",
      flush=True)

c = caveclient.CAVEclient("stroeh_mouse_retina")
cv = CloudVolume(c.info.segmentation_source(), use_https=True, progress=False,
                 secrets=c.auth.token)


def fetch(rid, tries=4):
    p = os.path.join(OUT, f"{rid}.obj")
    tmp = p + ".tmp.obj"           # never glob a partial file into a render
    last = None
    for attempt in range(tries):
        try:
            m = cv.mesh.get(rid)
            mesh = m[rid] if isinstance(m, dict) else m
            v, f = np.asarray(mesh.vertices), np.asarray(mesh.faces)
            with open(tmp, "w") as fh:
                fh.write("".join(f"v {a[0]:.1f} {a[1]:.1f} {a[2]:.1f}\n" for a in v))
                fh.write("".join(f"f {a[0]+1} {a[1]+1} {a[2]+1}\n" for a in f))
            os.replace(tmp, p)
            return rid, len(f), os.path.getsize(p) / 1e6, None
        except Exception as e:
            if os.path.exists(tmp):
                os.remove(tmp)
            last = f"{type(e).__name__}: {str(e)[:110]}"
            # 503 and 504 are the meshing service shedding load, not a bad id, and
            # they hit 21 of 364 cells on the first pass purely by timing. Backing
            # off and retrying is the whole fix. Anything else is a real error and
            # retrying it just wastes four round trips, so fail fast on those.
            transient = any(s in str(e) for s in ("503", "504", "502", "Timeout",
                                                  "Connection", "Temporarily"))
            if not transient or attempt == tries - 1:
                break
            time.sleep(2 ** attempt * 3)      # 3s, 6s, 12s
    return rid, 0, 0.0, last


t0, done, mb, bad = time.time(), 0, 0.0, []
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for fut in as_completed([ex.submit(fetch, i) for i in todo]):
        rid, nf, size, err = fut.result()
        done += 1
        if err:
            bad.append((rid, err))
        else:
            mb += size
        if done % 20 == 0 or done == len(todo):
            el = time.time() - t0
            print(f"[dl] {done}/{len(todo)}  {mb/1000:.2f} GB  {el/60:.1f} min  "
                  f"eta {(el/done)*(len(todo)-done)/60:.1f} min", flush=True)

print(f"[dl] DONE: {done - len(bad)} ok, {len(bad)} failed, {mb/1000:.2f} GB "
      f"in {(time.time()-t0)/60:.1f} min", flush=True)
for rid, e in bad[:12]:
    print("   failed:", rid, e, flush=True)
print(f"[dl] meshes now on disk: "
      f"{len([f for f in os.listdir(OUT) if f.endswith('.obj')])}", flush=True)
