#!/usr/bin/env python3
"""Pull meshes for a subset of the proofread bipolar cells, as one GLB each.

    CAVE_TOKEN=... python3 eyewire2/fetch_meshes.py --datastack NAME \
        --center 42900 43384 2007 --radius-um 45 --out eyewire2/meshes

Picks every completed cell in manifest.csv whose soma lies within --radius-um
of --center (voxels, 16 nm in x and y, 40 nm in z), or the ids given with
--ids, downloads each final segment's mesh through CAVE, decimates it to about
--faces triangles and writes <segid>.glb plus an index.json with each cell's
proofreader, type and soma. The token is read from CAVE_TOKEN or the file
~/.cloudvolume/secrets/cave-secret.json, never from the command line.
"""
import argparse, csv, json, math, os, sys

ap = argparse.ArgumentParser()
ap.add_argument("--datastack", required=True)
ap.add_argument("--manifest", default=os.path.join(os.path.dirname(__file__), "manifest.csv"))
ap.add_argument("--center", nargs=3, type=float, metavar=("X", "Y", "Z"))
ap.add_argument("--radius-um", type=float, default=45)
ap.add_argument("--ids", nargs="*", default=[])
ap.add_argument("--limit", type=int, default=200)
ap.add_argument("--faces", type=int, default=60000)
ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "meshes"))
a = ap.parse_args()

VOX = (16e-3, 16e-3, 40e-3)  # µm per voxel
rows = list(csv.DictReader(open(a.manifest, encoding="utf-8")))
if a.ids:
    pick = [r for r in rows if r["final_segid"] in set(a.ids)]
else:
    if not a.center:
        sys.exit("give --center X Y Z (voxels) or --ids")
    cx, cy, cz = a.center
    def d(r):
        return math.hypot((float(r["x_vox"]) - cx) * VOX[0], (float(r["y_vox"]) - cy) * VOX[1])
    pick = sorted((r for r in rows if d(r) <= a.radius_um), key=d)[: a.limit]
ids = [int(r["final_segid"]) for r in pick]
print(f"{len(ids)} cells", file=sys.stderr)

from caveclient import CAVEclient
from cloudvolume import CloudVolume
import trimesh

token = os.environ.get("CAVE_TOKEN")
client = CAVEclient(a.datastack, auth_token=token) if token else CAVEclient(a.datastack)
src = client.info.segmentation_source()
cv = CloudVolume(src, use_https=True, progress=False, secrets=token) if token else CloudVolume(src, use_https=True, progress=False)
res = cv.resolution  # nm per voxel, for the record
print(f"segmentation {src}, resolution {list(res)} nm", file=sys.stderr)

os.makedirs(a.out, exist_ok=True)
index = []
for r, sid in zip(pick, ids):
    p = os.path.join(a.out, f"{sid}.glb")
    if not os.path.exists(p):
        try:
            m = cv.mesh.get(sid, deduplicate_chunk_boundaries=False)[sid]
        except Exception as e:  # a cell that no longer exists under that id, or a hiccup
            print(f"  {sid}: {e}", file=sys.stderr)
            continue
        tm = trimesh.Trimesh(vertices=m.vertices / 1000.0, faces=m.faces, process=False)  # nm -> µm
        if len(tm.faces) > a.faces:
            try:
                tm = tm.simplify_quadric_decimation(face_count=a.faces)
            except BaseException as e:
                print(f"  {sid}: no decimation ({e}); kept {len(tm.faces)} faces", file=sys.stderr)
        tm.export(p)
        print(f"  {sid}: {len(tm.faces)} faces", file=sys.stderr)
    index.append({"segid": str(sid), "proofreader": r["proofreader"], "type": r["ai_type"],
                  "date": r["date_complete"],
                  "soma_um": [float(r["x_vox"]) * VOX[0], float(r["y_vox"]) * VOX[1], float(r["z_vox"]) * VOX[2]]})
json.dump({"datastack": a.datastack, "resolution_nm": [float(x) for x in res], "cells": index},
          open(os.path.join(a.out, "index.json"), "w"), indent=1)
print(f"wrote {len(index)} cells to {a.out}", file=sys.stderr)
