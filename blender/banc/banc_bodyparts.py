"""Label each of the descending neuron's targets with the body part it innervates.

The annotations already say this in plain words: cell_info tags read
"innervates T1 leg", "innervates neck", "innervates wing" and so on. This just
reads them and writes a root_id -> part map for the renderer.
"""
import json
import os

import caveclient
import pandas as pd

ROOT = r"D:\Meshes\banc"
PARTS = [("T1 leg", "t1"), ("T2 leg", "t2"), ("T3 leg", "t3"),
         ("neck", "neck"), ("wing", "wing"), ("haltere", "haltere"),
         ("abdomen", "abdomen")]

c = caveclient.CAVEclient("brain_and_nerve_cord")
MV = max(c.materialize.get_versions())
ci = c.materialize.query_table("cell_info", materialization_version=MV)
ci["rid"] = ci["pt_root_id"].astype("int64")

cast = json.load(open(os.path.join(ROOT, "cast.json")))
targets = [int(x) for x in cast["shotB_targets"]]
sub = ci[ci["rid"].isin(targets)]

part_of, side_of = {}, {}
for rid, rows in sub.groupby("rid"):
    tags = " | ".join(str(t) for t in rows["tag"].dropna())
    for label, key in PARTS:
        if f"innervates {label}".lower() in tags.lower():
            part_of[int(rid)] = key
            break
    if "innervates left side" in tags.lower():
        side_of[int(rid)] = "left"
    elif "innervates right side" in tags.lower():
        side_of[int(rid)] = "right"

missing = [t for t in targets if t not in part_of]
print(f"[parts] {len(targets)} targets, {len(part_of)} labelled, {len(missing)} unlabelled")
counts = pd.Series(list(part_of.values())).value_counts()
print("\nby body part:")
print(counts.to_string())
print("\nby side:")
print(pd.Series(list(side_of.values())).value_counts().to_string())

json.dump({"part": {str(k): v for k, v in part_of.items()},
           "side": {str(k): v for k, v in side_of.items()},
           "unlabelled": missing},
          open(os.path.join(ROOT, "shotB_bodyparts.json"), "w"), indent=1)
print(f"\n[parts] wrote {ROOT}\\shotB_bodyparts.json")
