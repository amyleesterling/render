"""Download a BANC cast to OBJ, resumable, with the worker pool capped at 4.

The cap is deliberate: an 8 worker pool on the CA3 fetch hit 90 processes and
40.7 GB resident and had to be killed. Any id whose .obj already exists is
skipped, so a restart loses nothing.

  python banc_download.py shotB
  python banc_download.py shotA
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import caveclient
import numpy as np
from cloudvolume import CloudVolume

WORKERS = 4
ROOT = r"D:\Meshes\banc"
which = sys.argv[1] if len(sys.argv) > 1 else "shotB"
OUT = os.path.join(ROOT, which)
os.makedirs(OUT, exist_ok=True)

c = caveclient.CAVEclient("brain_and_nerve_cord")
cv = CloudVolume(c.info.segmentation_source(), use_https=True,
                 progress=False, secrets=c.auth.token)

if which == "shotB":
    cast = json.load(open(os.path.join(ROOT, "cast.json")))
    ids = [cast["shotB_descending_neuron"]] + [int(t) for t in cast["shotB_targets"]]
else:
    ids = [int(x) for x in json.load(open(os.path.join(ROOT, f"{which}_ids.json")))]

ids = list(dict.fromkeys(ids))
todo = [i for i in ids if not os.path.exists(os.path.join(OUT, f"{i}.obj"))]
print(f"[dl] {which}: {len(ids)} cells, {len(ids) - len(todo)} already on disk, "
      f"{len(todo)} to fetch, {WORKERS} workers", flush=True)


def fetch(i):
    p = os.path.join(OUT, f"{i}.obj")
    tmp = p + ".tmp.obj"          # never glob a partial file into a render
    try:
        m = cv.mesh.get(i)
        mesh = m[i] if isinstance(m, dict) else m
        v, f = np.asarray(mesh.vertices), np.asarray(mesh.faces)
        with open(tmp, "w") as fh:
            fh.write("".join(f"v {a[0]:.1f} {a[1]:.1f} {a[2]:.1f}\n" for a in v))
            fh.write("".join(f"f {a[0]+1} {a[1]+1} {a[2]+1}\n" for a in f))
        os.replace(tmp, p)
        return i, len(f), os.path.getsize(p) / 1e6, None
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        return i, 0, 0.0, f"{type(e).__name__}: {str(e)[:120]}"


t0, done, faces, mb, bad = time.time(), 0, 0, 0.0, []
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for fut in as_completed([ex.submit(fetch, i) for i in todo]):
        i, nf, size, err = fut.result()
        done += 1
        if err:
            bad.append((i, err))
            print(f"[dl] {done}/{len(todo)} {i} FAILED {err}", flush=True)
        else:
            faces += nf
            mb += size
            if done % 10 == 0 or done == len(todo):
                el = time.time() - t0
                print(f"[dl] {done}/{len(todo)}  {faces/1e6:.1f}M faces  {mb/1000:.2f} GB  "
                      f"{el/60:.1f} min  eta {(el/done)*(len(todo)-done)/60:.1f} min",
                      flush=True)

print(f"[dl] DONE {which}: {done - len(bad)} ok, {len(bad)} failed, "
      f"{faces/1e6:.1f}M faces, {mb/1000:.2f} GB in {(time.time()-t0)/60:.1f} min", flush=True)
for i, e in bad:
    print("   failed:", i, e, flush=True)
