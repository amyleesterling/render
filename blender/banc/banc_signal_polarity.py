"""Skeletons, synapse polarity and geodesic path distance for any BANC cell set.

Produces the data the signal animation is driven from. Nothing here is invented:
the direction of travel comes from where this cell's POSTsynaptic (input) sites sit
versus its PREsynaptic (output) sites, measured on the authoritative CAVE skeleton.

Per cell:
  1. fetch the CAVE skeleton (vertices + edges)
  2. fetch synapses where the cell is postsynaptic (its inputs) and presynaptic
     (its outputs), and map each to its nearest skeleton node
  3. find the input-dominant region: nodes whose local balance favours inputs
  4. geodesic distance along skeleton edges from that region, normalised 0..1
  5. record how far the output sites sit along that axis, which is the check that
     the inferred direction actually runs input -> output

  python banc_dng12_polarity.py
"""
import json
import os
import time

import caveclient
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

import sys
POP = sys.argv[1] if len(sys.argv) > 1 else "D:/Meshes/banc/dng12_population.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "D:/Meshes/banc/dng12_polarity.npz"
AUDIT = sys.argv[3] if len(sys.argv) > 3 else "D:/Meshes/banc/dng12_polarity_audit.json"
V = 888
SYN_TABLE = "synapses_v2"   # v1 is deprecated, v3 is flagged still-in-testing

_raw = json.load(open(POP))
cells = _raw if isinstance(_raw, list) else _raw["root_ids"]
cells = [str(x) for x in cells]
c = caveclient.CAVEclient("brain_and_nerve_cord")
c.version = V
SYN_RES = np.array(c.annotation.get_table_metadata(SYN_TABLE)["voxel_resolution"], dtype=float)
print(f"{len(cells)} cells, materialization {V}, synapse table {SYN_TABLE}")
print(f"synapse voxel_resolution read from metadata: {SYN_RES.tolist()} nm per unit")

store, audit = {}, []
t0 = time.time()
for n, sid in enumerate(cells, 1):
    rec = {"segment_id": sid}
    try:
        sk = c.skeleton.get_skeleton(int(sid), output_format="dict")
        V_ = np.asarray(sk["vertices"], dtype=float)      # nm
        E = np.asarray(sk["edges"], dtype=int)
    except Exception as e:
        rec["error"] = f"skeleton: {str(e)[:90]}"
        audit.append(rec)
        print(f"  {n}/{len(cells)} {sid}  SKELETON FAILED {rec['error']}")
        continue

    # --- synapses, both polarities -------------------------------------------
    try:
        post = c.materialize.query_table(SYN_TABLE,
                                         filter_equal_dict={"post_pt_root_id": int(sid)})
        pre = c.materialize.query_table(SYN_TABLE,
                                        filter_equal_dict={"pre_pt_root_id": int(sid)})
    except Exception as e:
        rec["error"] = f"synapses: {str(e)[:90]}"
        audit.append(rec)
        print(f"  {n}/{len(cells)} {sid}  SYNAPSES FAILED {rec['error']}")
        continue

    def coords(df, col):
        if len(df) == 0:
            return np.zeros((0, 3))
        return np.array([list(p) for p in df[col]], dtype=float) * SYN_RES

    P_in = coords(post, "ctr_pt_position")     # this cell receives here
    P_out = coords(pre, "ctr_pt_position")     # this cell outputs here

    # --- map synapses to nearest skeleton node -------------------------------
    def nearest(pts):
        if len(pts) == 0:
            return np.zeros(0, int), np.zeros(0)
        d = np.linalg.norm(pts[:, None, :] - V_[None, :, :], axis=2)
        idx = d.argmin(1)
        return idx, d[np.arange(len(pts)), idx]

    i_in, d_in = nearest(P_in)
    i_out, d_out = nearest(P_out)

    # --- input-dominant region ------------------------------------------------
    n_nodes = len(V_)
    cin = np.bincount(i_in, minlength=n_nodes).astype(float)
    cout = np.bincount(i_out, minlength=n_nodes).astype(float)
    bal = cin - cout
    if bal.max() <= 0:
        seeds = np.array([int(cin.argmax())]) if cin.sum() else np.array([0])
    else:
        thr = np.percentile(bal[bal > 0], 70) if (bal > 0).sum() > 3 else bal.max()
        seeds = np.where(bal >= thr)[0]

    # --- geodesic distance along the skeleton --------------------------------
    w = np.linalg.norm(V_[E[:, 0]] - V_[E[:, 1]], axis=1)
    g = coo_matrix((np.r_[w, w], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
                   shape=(n_nodes, n_nodes)).tocsr()
    dist = dijkstra(g, indices=seeds, min_only=True)
    finite = np.isfinite(dist)
    if finite.sum() < 2:
        rec["error"] = "skeleton disconnected from seeds"
        audit.append(rec)
        continue
    dmax = dist[finite].max()
    t = np.where(finite, dist / max(dmax, 1e-9), 1.0)      # normalised path distance

    # --- does the inferred direction actually run input -> output? -----------
    t_in = float(t[i_in].mean()) if len(i_in) else float("nan")
    t_out = float(t[i_out].mean()) if len(i_out) else float("nan")

    store[sid] = {"skel_v": V_, "skel_e": E, "t": t,
                  "syn_in_idx": i_in, "syn_out_idx": i_out}
    rec.update({
        "skeleton_nodes": int(n_nodes), "skeleton_edges": int(len(E)),
        "cable_length_um": round(float(w.sum()) / 1000, 1),
        "post_synapses_inputs": int(len(P_in)), "pre_synapses_outputs": int(len(P_out)),
        "syn_to_skel_median_nm_inputs": round(float(np.median(d_in)), 1) if len(d_in) else None,
        "syn_to_skel_p95_nm_inputs": round(float(np.percentile(d_in, 95)), 1) if len(d_in) else None,
        "syn_to_skel_median_nm_outputs": round(float(np.median(d_out)), 1) if len(d_out) else None,
        "syn_to_skel_p95_nm_outputs": round(float(np.percentile(d_out, 95)), 1) if len(d_out) else None,
        "seed_nodes": int(len(seeds)),
        "mean_t_of_inputs": round(t_in, 4), "mean_t_of_outputs": round(t_out, 4),
        "direction_input_to_output": bool(t_out > t_in),
        "separation": round(t_out - t_in, 4),
        "geodesic_span_um": round(float(dmax) / 1000, 1),
    })
    audit.append(rec)
    print(f"  {n}/{len(cells)} {sid}  nodes {n_nodes:4d}  in {len(P_in):5d} out {len(P_out):5d}  "
          f"t_in {t_in:.3f} -> t_out {t_out:.3f}  {'OK' if t_out > t_in else 'REVERSED'}  "
          f"({(time.time()-t0)/60:.1f} min)", flush=True)

np.savez_compressed(OUT, **{f"{sid}|{k}": v for sid, d in store.items() for k, v in d.items()})
json.dump(audit, open(AUDIT, "w"), indent=1)
good = [a for a in audit if "error" not in a]
fwd = [a for a in good if a["direction_input_to_output"]]
print(f"\n{len(good)}/{len(cells)} cells with skeleton + synapses")
print(f"{len(fwd)}/{len(good)} run input -> output on the geodesic axis")
if good:
    sep = np.array([a["separation"] for a in good])
    print(f"separation t_out - t_in: median {np.median(sep):+.3f}, "
          f"min {sep.min():+.3f}, max {sep.max():+.3f}")
    md = np.array([a["syn_to_skel_median_nm_inputs"] for a in good if a["syn_to_skel_median_nm_inputs"]])
    print(f"synapse-to-skeleton median distance across cells: {np.median(md):.0f} nm")
print(f"wrote {OUT} and {AUDIT}")
