"""Identification gate for the grooming job: DNg12 and wPN1 in BANC v888.

Renders nothing. Gathers evidence and reports, so that a blocked identity stops
the job rather than being quietly substituted.

  python banc_grooming_identify.py
"""
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import caveclient
import numpy as np
import pandas as pd

MESH_BASE = ("https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome"
             "/neuron_meshes/meshes")
CONTROL = "999999999999999999"
MIDLINE_NM = 487478.0
NECK_Y_NM = 92500 * 4
OUT = "D:/Meshes/banc/grooming_identity.json"
V = 888


def mesh_exists(sid):
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(f"{MESH_BASE}/{sid}:0", method="HEAD"), timeout=30)
        return r.status == 200
    except urllib.error.HTTPError:
        return False
    except Exception:
        return False


c = caveclient.CAVEclient("brain_and_nerve_cord")
c.version = V
report = {"materialization": V}

# ---------------------------------------------------------------- DNg12
print("=" * 70)
print("DNg12")
print("=" * 70)
tags = {}
for t in ["DNg12", "DNg12_a", "DNg12_b"]:
    df = c.materialize.query_table("cell_info", filter_equal_dict={"tag": t})
    tags[t] = sorted({str(r) for r in df["pt_root_id"]})
    print(f"  tag {t!r}: {len(df)} rows, {len(tags[t])} distinct roots")

A, B, base = set(tags["DNg12_a"]), set(tags["DNg12_b"]), set(tags["DNg12"])
print(f"  DNg12_a & DNg12_b overlap: {sorted(A & B)}")
print(f"  DNg12_a subset of DNg12: {A <= base}   DNg12_b subset of DNg12: {B <= base}")
print(f"  union of all three: {len(base | A | B)} roots")

cells = sorted(base)
print(f"\n  auditing the {len(cells)} cells tagged exactly 'DNg12'")

# all tags carried by each, so a conflicting identity shows up
rows = c.materialize.query_table("cell_info",
                                 filter_in_dict={"pt_root_id": [int(x) for x in cells]})
tags_of = {}
for _, r in rows.iterrows():
    tags_of.setdefault(str(r["pt_root_id"]), set()).add(str(r["tag"]))

# soma positions
soma = {}
try:
    sdf = c.materialize.query_table("somas_v1a",
                                    filter_in_dict={"pt_root_id": [int(x) for x in cells]})
    for _, r in sdf.iterrows():
        soma.setdefault(str(r["pt_root_id"]), []).append(list(r["pt_position"]))
    print(f"  somas_v1a: {len(sdf)} rows covering {len(soma)}/{len(cells)} cells")
except Exception as e:
    print(f"  somas_v1a failed: {str(e)[:90]}")

# lineage
lineage = {}
try:
    latest = c.chunkedgraph.is_latest_roots([int(x) for x in cells])
    lineage = {sid: bool(l) for sid, l in zip(cells, latest)}
    print(f"  root ids current: {sum(lineage.values())}/{len(cells)}")
except Exception as e:
    print(f"  chunkedgraph unavailable: {str(e)[:90]}")

# frozen meshes
with ThreadPoolExecutor(8) as ex:
    present = dict(zip(cells + [CONTROL], ex.map(mesh_exists, cells + [CONTROL])))
print(f"  control {CONTROL}: {'RESOLVED - void' if present[CONTROL] else '404 as required'}")
print(f"  meshes in frozen source: {sum(present[s] for s in cells)}/{len(cells)}")

# skeletons
skel_ok, skel_err = {}, None
for sid in cells[:6]:
    try:
        sk = c.skeleton.get_skeleton(int(sid), output_format="dict")
        n = len(sk.get("vertices", []))
        skel_ok[sid] = n
    except Exception as e:
        skel_err = str(e)[:120]
        skel_ok[sid] = None
print(f"  skeleton service sample: {skel_ok}")
if skel_err:
    print(f"  skeleton error: {skel_err}")

report["DNg12"] = {"tags": tags, "cells": cells, "tags_of": {k: sorted(v) for k, v in tags_of.items()},
                   "soma": soma, "lineage": lineage,
                   "mesh_present": {s: bool(present[s]) for s in cells},
                   "mesh_control_404": not present[CONTROL],
                   "skeleton_sample": skel_ok, "skeleton_error": skel_err}

# ---------------------------------------------------------------- wPN1
print("\n" + "=" * 70)
print("wPN1")
print("=" * 70)
wpn = {"cell_info_exact": {}, "tag_scan": None, "wing_mn_types": None,
       "codex_annotations": None, "cell_info2_test": None}
for probe in ["wPN1", "wPN", "WPN1", "wpn1"]:
    df = c.materialize.query_table("cell_info", filter_equal_dict={"tag": probe})
    wpn["cell_info_exact"][probe] = len(df)
    print(f"  cell_info tag == {probe!r}: {len(df)} rows")

alltags = json.load(open("D:/Meshes/banc/cell_info_tags_v888.json"))
hits = [t for t in alltags if "wpn" in t.lower()]
wpn["tag_scan"] = {"distinct_tags": len(alltags), "containing_wpn": hits}
print(f"  exhaustive scan of all {len(alltags)} distinct cell_info tag values: "
      f"{len(hits)} contain 'wpn'")

w = c.materialize.query_table("wing_mn_cell_type_table_v0")
wpn["wing_mn_types"] = sorted(set(w["cell_type"].astype(str)))
print(f"  wing_mn_cell_type_table_v0 cell types: {wpn['wing_mn_types']}")

for t in ["codex_annotations", "cell_info2_test"]:
    try:
        df = c.materialize.query_table(t)
        wpn[t] = f"readable, {len(df)} rows"
    except Exception as e:
        wpn[t] = f"UNAVAILABLE: {str(e)[:110]}"
    print(f"  {t}: {wpn[t]}")

resolved = any(v > 0 for v in wpn["cell_info_exact"].values()) or bool(hits)
wpn["resolved"] = resolved
report["wPN1"] = wpn

print("\n" + "=" * 70)
print("GATE")
print("=" * 70)
print(f"  DNg12: {len(cells)} cells tagged exactly 'DNg12'. NOT a bilateral pair.")
print(f"  wPN1 : {'RESOLVED' if resolved else 'NOT RESOLVED - no such identity in BANC v888'}")
json.dump(report, open(OUT, "w"), indent=1, default=str)
print(f"\nwrote {OUT}")
