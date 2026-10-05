"""Count cells and synapses per app layer, so the HUD stats are measured.

Writes app/data/layer-stats.json. Synapse counts are the number of synaptic
connections in BANC v888 where a cell of that layer is presynaptic (outputs) or
postsynaptic (inputs). Only the id column is fetched, so this counts rows rather
than hauling coordinates across the network.

  python banc_layer_stats.py
"""
import json
import time

import caveclient

LAYERS = "D:/Meshes/banc/walking_steering_layers.json"
OUT = "C:/Users/amyle/Documents/New project/banc-explorer-dng100/app/data/layer-stats.json"
V = 888
SYN = "synapses_v2"

# layer key in the render config -> the app's circuit mode
APP_LAYERS = {
    "forward": "walk", "backward": "backward", "turn-left": "left", "turn-right": "right",
    "eat": "eat", "threat-walk": "threat", "flight-dodge-dnp03-all": "dodge",
    "groom-head-dng12": "groom-head", "walk-speed-dng100": "walk-speed",
    "flight-power-dng02": "flight-forward", "landing-dnp07-dnp10": "landing",
    "flight-steer-mnb1-all": "flight-steer",
}

cfg = json.load(open(LAYERS))["layers"]
c = caveclient.CAVEclient("brain_and_nerve_cord")
c.version = V

out, t0 = {}, time.time()
for key, mode in APP_LAYERS.items():
    spec = cfg.get(key)
    if not spec or spec.get("ids") == "ALL":
        continue
    ids = [int(row[0]) for row in spec["ids"]]
    try:
        pre = c.materialize.query_table(SYN, filter_in_dict={"pre_pt_root_id": ids})
        post = c.materialize.query_table(SYN, filter_in_dict={"post_pt_root_id": ids})
        n_out, n_in = len(pre), len(post)
        # A synapse with both ends inside the layer is an output of one cell and
        # an input of another, so summing the two row counts counts it twice.
        n_total = len(set(pre["id"]) | set(post["id"]))
    except Exception as e:
        print(f"  {key}: synapse query failed, {str(e)[:70]}")
        n_out = n_in = n_total = None
    out[mode] = {
        "cells": len(ids),
        "outputs": n_out,
        "inputs": n_in,
        "synapses": n_total,
        "dataset": "BANC v888",
        "layer": key,
    }
    print(f"  {mode:14s} {len(ids):3d} cells   in {n_in}   out {n_out}   "
          f"({(time.time()-t0)/60:.1f} min)", flush=True)

# The compass layer is a different dataset and must say so rather than borrow BANC's label.
out["heading"] = {"cells": 53, "outputs": None, "inputs": None, "synapses": None,
                  "dataset": "FAFB / FlyWire", "layer": "epg",
                  "note": "EPG compass cells are FAFB, not BANC"}

json.dump({"_note": 'Measured from BANC v888 synapses_v2. A count is the number of DISTINCT synapses with a cell of that layer at either end, inputs and outputs together. A synapse with both ends inside the layer is counted once, not twice: summing input rows and output rows over-counted every layer, by 177 to 2,871 synapses.',
           "materialization": V, "source_table": SYN, "layers": out},
          open(OUT, "w"), indent=1)
print(f"\nwrote {OUT}  ({len(out)} layers, {(time.time()-t0)/60:.1f} min)")
