"""Resolve DNp03 in BANC v888 before anything is rendered.

The brief is explicit: cross-check every candidate, do not assume the historical
functional name "AX" is DNp03, and stop rather than guess if it does not resolve.
So this script only gathers evidence and prints a verdict; it renders nothing.

Checks per candidate:
  1. cell_info tag at materialization 888 (the release named in the brief)
  2. whether the v888 root id still exists in the frozen precomputed mesh bucket
  3. root-id lineage: is it current, and if not what does it map to now
  4. anatomical hemisphere from mesh geometry, using the midline calibrated on the
     DNa01 pair whose sides were given earlier (left = higher x)
  5. morphology: does it actually descend, i.e. span brain y to VNC y

  python banc_dnp03_identify.py
"""
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import caveclient
import numpy as np

MESH_BASE = ("https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome"
             "/neuron_meshes/meshes")
CONTROL = "999999999999999999"
MIDLINE_NM = 487478.0          # from the DNa01 pair, see BANC_WALKING_STEERING_POSTER.md
OUT = "D:/Meshes/banc/dnp03_candidates.json"

# BANC landmarks in 4nm voxels, from the project notes: DN somata sit around
# y=63,328; the neck connective crosses at y=92,500 and y=121,000; T1 leg sensory
# endings run y=134,000 to 163,000. A real descending neuron must cross the neck.
NECK_Y_VOX = 92500
NECK_Y_NM = NECK_Y_VOX * 4


def mesh_exists(sid):
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(f"{MESH_BASE}/{sid}:0", method="HEAD"), timeout=30)
        return r.status == 200
    except urllib.error.HTTPError as e:
        return e.code == 200
    except Exception:
        return False


c = caveclient.CAVEclient("brain_and_nerve_cord")
versions = c.materialize.get_versions()
print("materialization versions available:", sorted(versions))
V = 888 if 888 in versions else max(versions)
if V != 888:
    print(f"!! v888 not available, using {V}. The brief asks for v888; say so in the report.")
c.version = V
print(f"using materialization {V}\n")

# ---------------------------------------------------------------- 1. annotations
print("1. cell_info annotations")
exact = c.materialize.query_table("cell_info", filter_equal_dict={"tag": "DNp03"})
print(f"   tag == 'DNp03': {len(exact)} rows, "
      f"{len(set(exact['pt_root_id']))} distinct root ids")

# Anything else that mentions DNp03, plus the provisional name the brief warns about.
related = {}
for probe in ["DNp03", "AX", "DNp3"]:
    try:
        df = c.materialize.query_table("cell_info", filter_equal_dict={"tag": probe})
        related[probe] = sorted({str(r) for r in df["pt_root_id"]})
    except Exception as e:
        related[probe] = f"query failed: {str(e)[:80]}"
    print(f"   tag == {probe!r}: {related[probe] if isinstance(related[probe], str) else len(related[probe])}")

cands = sorted({str(r) for r in exact["pt_root_id"]})
print(f"\n   DNp03 candidates: {cands}")

# Every tag carried by each candidate, so a conflicting identity is visible.
tags_of = {}
if cands:
    allrows = c.materialize.query_table(
        "cell_info", filter_in_dict={"pt_root_id": [int(x) for x in cands]})
    for _, r in allrows.iterrows():
        tags_of.setdefault(str(r["pt_root_id"]), set()).add(str(r["tag"]))
    for sid in cands:
        print(f"   {sid}: {sorted(tags_of.get(sid, []))}")

# ---------------------------------------------------------------- 2. meshes
print("\n2. present in the frozen precomputed mesh source")
with ThreadPoolExecutor(8) as ex:
    present = dict(zip(cands + [CONTROL], ex.map(mesh_exists, cands + [CONTROL])))
print(f"   control {CONTROL}: {'RESOLVED (test void!)' if present[CONTROL] else '404 as required'}")
for sid in cands:
    print(f"   {sid}: {'present' if present[sid] else 'MISSING'}")

# ---------------------------------------------------------------- 3. lineage
print("\n3. root-id lineage")
lineage = {}
if cands:
    try:
        latest = c.chunkedgraph.is_latest_roots([int(x) for x in cands])
        for sid, is_l in zip(cands, latest):
            entry = {"is_latest": bool(is_l), "maps_to": None}
            if not is_l:
                try:
                    entry["maps_to"] = [str(x) for x in
                                        c.chunkedgraph.get_latest_roots(int(sid))]
                except Exception as e:
                    entry["maps_to"] = f"err {str(e)[:60]}"
            lineage[sid] = entry
            print(f"   {sid}: current={entry['is_latest']}"
                  + (f"  -> {entry['maps_to']}" if entry["maps_to"] else ""))
    except Exception as e:
        print(f"   chunkedgraph unavailable: {str(e)[:140]}")
        lineage = {sid: {"is_latest": None, "maps_to": None, "error": "chunkedgraph 503"}
                   for sid in cands}

# ---------------------------------------------------------------- 4/5. morphology
print("\n4/5. hemisphere and morphology, measured from the mesh")
from cloudvolume import CloudVolume
cv = CloudVolume("precomputed://gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_meshes",
                 use_https=True, progress=False)
geom = {}
for sid in cands:
    if not present.get(sid):
        continue
    m = cv.mesh.get(int(sid))
    m = m[int(sid)] if isinstance(m, dict) else m
    v = np.asarray(m.vertices)
    brain = v[v[:, 1] < np.percentile(v[:, 1], 15)]
    bx = float(brain[:, 0].mean())
    side = "left" if bx > MIDLINE_NM else "right"
    crosses = bool(v[:, 1].min() < NECK_Y_NM < v[:, 1].max())
    geom[sid] = {
        "brain_end_centroid_x_nm": round(bx, 1),
        "anatomical_side": side,
        "distance_from_midline_nm": round(abs(bx - MIDLINE_NM), 1),
        "y_range_nm": [round(float(v[:, 1].min()), 1), round(float(v[:, 1].max()), 1)],
        "crosses_neck_connective": crosses,
        "faces": int(len(np.asarray(m.faces))),
        "vertices": int(len(v)),
    }
    print(f"   {sid}: {side:5s}  brain x {bx:9.0f}  y {geom[sid]['y_range_nm'][0]:.0f}"
          f" to {geom[sid]['y_range_nm'][1]:.0f}  crosses neck: {crosses}  "
          f"{geom[sid]['faces']/1e6:.2f}M faces")

# ---------------------------------------------------------------- verdict
sides = [g["anatomical_side"] for g in geom.values()]
print("\nVERDICT")
ok = (len(cands) > 0 and all(present.get(s) for s in cands)
      and sorted(sides) == ["left", "right"]
      and all(g["crosses_neck_connective"] for g in geom.values()))
if ok:
    print(f"   RESOLVED: {len(cands)} DNp03 cells, one per hemisphere, both present in the")
    print( "   frozen mesh source, both crossing the neck connective as descending cells must.")
else:
    print( "   NOT CLEANLY RESOLVED. Do not render. Details:")
    print(f"     candidates={len(cands)} sides={sides}")
    print(f"     all meshes present={all(present.get(s) for s in cands) if cands else False}")
    print(f"     all cross neck={[g['crosses_neck_connective'] for g in geom.values()]}")

json.dump({
    "materialization": V,
    "candidates": cands,
    "tags": {k: sorted(v) for k, v in tags_of.items()},
    "related_tag_probes": related,
    "mesh_present": {k: bool(v) for k, v in present.items() if k != CONTROL},
    "mesh_control_404": not present[CONTROL],
    "lineage": lineage,
    "geometry": geom,
    "midline_nm": MIDLINE_NM,
    "resolved": bool(ok),
}, open(OUT, "w"), indent=1)
print(f"\nwrote {OUT}")
