"""Assemble canonical skeletons + ap_paths.json + report.json.

Canonical <segid>.npz is built from the densest available skeleton:
  preferred  <segid>_meshparty.npz   (meshparty.skeletonize_mesh, dense)
  fallback   <segid>_cave.npz        (CAVE pcg_skel precomputed, coarse)

Everything stays in OBJ FILE SPACE, nanometres. No axis transform is applied.
"""
import json, os, glob, collections
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

OUT = r"D:\Meshes\skeletons"
HERO = 648518346438632877
MFS = [648518346432881590, 648518346440660317, 648518346448994107,
       648518346450631673, 648518346452106477, 648518346460875907]
ALL = [HERO] + MFS
NM = 1000.0
soma = json.load(open(os.path.join(OUT, "_soma.json")))
SOMA_XYZ = np.array(soma["soma_centre_nm"])


def adjacency(n, edges):
    adj = collections.defaultdict(list)
    for a, b in edges:
        adj[int(a)].append(int(b))
        adj[int(b)].append(int(a))
    return adj


def bfs(root, adj, n):
    parent = np.full(n, -1, np.int64)
    seen = np.zeros(n, bool)
    seen[root] = True
    q = collections.deque([root])
    order = [root]
    while q:
        u = q.popleft()
        for w in adj[u]:
            if not seen[w]:
                seen[w] = True
                parent[w] = u
                q.append(w)
                order.append(w)
    return parent, seen, order


def dists(v, root, parent, order, n):
    d = np.full(n, np.nan)
    d[root] = 0.0
    for u in order[1:]:
        d[u] = d[parent[u]] + float(np.linalg.norm(v[u] - v[parent[u]]) / NM)
    return d


def path_to(node, parent):
    p = [int(node)]
    while parent[p[-1]] != -1:
        p.append(int(parent[p[-1]]))
    return p[::-1]


def mkpath(v, idx, kind):
    arc = [0.0]
    for k in range(1, len(idx)):
        arc.append(arc[-1] + float(np.linalg.norm(v[idx[k]] - v[idx[k - 1]]) / NM))
    return dict(kind=kind, n_nodes=len(idx), length_um=round(arc[-1], 2),
                indices=[int(i) for i in idx], arc_um=[round(x, 3) for x in arc])


# ---- synapses (raw CSV coords verified to be nanometres, same space) ----
df = pd.read_csv(r"D:\Meshes\renders\mf_synapses.csv")
hs = df[df.post_pt_root_id == HERO]
syn_xyz = np.stack([np.array([float(t) for t in str(x).strip("[]").split()])
                    for x in hs.ctr_pt_position])
syn_pre = hs.pre_pt_root_id.values

report, paths_out = {}, {}

for seg in ALL:
    mp = os.path.join(OUT, f"{seg}_meshparty.npz")
    cv = os.path.join(OUT, f"{seg}_cave.npz")
    if os.path.exists(mp):
        src_file, src_name = mp, "meshparty.skeletonize_mesh (dense)"
    elif os.path.exists(cv):
        src_file, src_name = cv, "CAVE pcg_skel precomputed (coarse)"
    else:
        print(f"{seg}: NO SKELETON AVAILABLE", flush=True)
        continue

    d = np.load(src_file, allow_pickle=True)
    v = np.asarray(d["vertices"], float)
    e = np.asarray(d["edges"], np.int64)
    n = len(v)
    adj = adjacency(n, e)
    deg = np.zeros(n, int)
    for a, b in e:
        deg[a] += 1
        deg[b] += 1
    cable = float(np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1).sum() / NM)

    # ---- pick a physiologically sensible root ----
    if seg == HERO:
        root = int(np.argmin(np.linalg.norm(v - SOMA_XYZ, axis=1)))
        root_note = "node nearest the measured soma centre"
    else:
        r0 = int(d["root"]) if "root" in d else 0
        p0, _, o0 = bfs(r0, adj, n)
        d0 = dists(v, r0, p0, o0, n)
        a0 = int(np.nanargmax(d0))
        pa, _, oa = bfs(a0, adj, n)
        da = dists(v, a0, pa, oa, n)
        b0 = int(np.nanargmax(da))
        sxyz = syn_xyz[syn_pre == seg]
        if len(sxyz):
            c = sxyz.mean(0)
            root = a0 if np.linalg.norm(v[a0] - c) > np.linalg.norm(v[b0] - c) else b0
            other = b0 if root == a0 else a0
            root_note = ("end of the fibre farthest from its synapses onto the hero, "
                         "so the pulse travels toward the boutons")
        else:
            root, other = a0, b0
            root_note = "one end of the longest geodesic"

    parent, seen, order = bfs(root, adj, n)
    dist = dists(v, root, parent, order, n)
    tips = [i for i in range(n) if deg[i] == 1 and i != root and seen[i]]
    far = int(np.nanargmax(dist))

    np.savez_compressed(os.path.join(OUT, f"{seg}.npz"),
                        vertices=v, edges=e, root=root,
                        parent=parent, dist_from_root_um=dist,
                        source=src_name, seg_id=str(seg),
                        coordinate_space="OBJ file space, nanometres, no transform applied")

    tree = cKDTree(v)
    if seg == HERO:
        sd, si = tree.query(syn_xyz, k=1)
    else:
        sd, si = tree.query(syn_xyz[syn_pre == seg], k=1)

    cave_extra = {}
    if os.path.exists(cv):
        cd = np.load(cv, allow_pickle=True)
        cr = cd["radius"]
        cave_extra = dict(
            cave_n_vertices=int(len(cd["vertices"])),
            cave_n_edges=int(len(cd["edges"])),
            cave_root=int(cd["root"]),
            cave_cable_um=round(float(np.linalg.norm(
                cd["vertices"][cd["edges"][:, 0]] - cd["vertices"][cd["edges"][:, 1]],
                axis=1).sum() / NM), 1),
            cave_radius_nm=[round(float(cr.min()), 2), round(float(cr.max()), 2)] if cr.size else None,
            cave_radius_is_constant=bool(cr.size and np.allclose(cr, cr[0])),
            cave_compartment_values=np.unique(cd["compartment"]).tolist(),
            cave_mesh_to_skel_map_len=int(cd["mesh_to_skel_map"].shape[0]),
            cave_lvl2_ids_len=int(cd["lvl2_ids"].shape[0]),
        )

    report[seg] = dict(
        source=src_name, n_vertices=n, n_edges=len(e), root=root, root_note=root_note,
        cable_length_um=round(cable, 1), n_tips=len(tips),
        reachable_from_root=int(seen.sum()),
        n_connected_components_unreached=int(n - seen.sum()),
        max_path_from_root_um=round(float(np.nanmax(dist)), 1), farthest_tip=far,
        mean_node_spacing_um=round(cable / max(len(e), 1), 3),
        n_synapses=int(len(si)),
        synapse_median_dist_to_cable_um=round(float(np.median(sd)) / NM, 2) if len(sd) else None,
        bbox_min_nm=v.min(0).round(1).tolist(), bbox_max_nm=v.max(0).round(1).tolist(),
        **cave_extra)

    if seg == HERO:
        cand = sorted([t for t in tips if dist[t] >= 20.0], key=lambda t: -dist[t])[:250]
        plist = [mkpath(v, path_to(t, parent), "soma_to_tip") for t in cand]
        paths_out[str(seg)] = dict(
            role="hero_thorny_pyramidal", root=root, root_note=root_note,
            soma_centre_nm=soma["soma_centre_nm"],
            soma_volume_um3=soma["soma_volume_um3"],
            soma_equiv_radius_um=soma["soma_equiv_radius_um"],
            n_paths=len(plist), paths=plist,
            synapse_nodes=[int(x) for x in si],
            synapse_xyz_nm=syn_xyz.round(1).tolist(),
            synapse_pre_root_id=[str(x) for x in syn_pre])
    else:
        main = path_to(int(np.nanargmax(dist)), parent)
        onmain = set(main)
        plist = [mkpath(v, main, "main_axis")]
        for t in tips:
            if t in onmain:
                continue
            p = path_to(t, parent)
            hit = [k for k, q in enumerate(p) if q in onmain]
            if not hit:
                continue
            br = p[hit[-1]:]
            if len(br) > 1:
                m = mkpath(v, br, "branch")
                if m["length_um"] >= 3.0:
                    plist.append(m)
        paths_out[str(seg)] = dict(
            role="mossy_fibre", root=root, root_note=root_note,
            n_paths=len(plist), paths=plist,
            synapse_nodes=[int(x) for x in si],
            synapse_xyz_nm=syn_xyz[syn_pre == seg].round(1).tolist())

    r = report[seg]
    print(f"\n{seg}  [{src_name}]")
    print(f"   V={r['n_vertices']:,} E={r['n_edges']:,} root={r['root']} ({r['root_note']})")
    print(f"   cable={r['cable_length_um']:,} um   root->farthest={r['max_path_from_root_um']} um"
          f"   tips={r['n_tips']}   spacing={r['mean_node_spacing_um']} um")
    print(f"   reachable {r['reachable_from_root']}/{r['n_vertices']}"
          f"   synapses={r['n_synapses']} (median {r['synapse_median_dist_to_cable_um']} um off cable)")
    print(f"   paths={paths_out[str(seg)]['n_paths']}", flush=True)

doc = {
    "coordinate_space": "OBJ FILE SPACE. Identical to the .obj vertex coordinates in D:/Meshes/hero/. NO transform has been applied.",
    "units": "vertices are NANOMETRES; every *_um field is micrometres",
    "blender_conversion": "Blender's OBJ importer maps file (x,y,z) -> (x,-z,y). The consumer MUST apply: pts = np.column_stack([pts[:,0], -pts[:,2], pts[:,1]])",
    "indices": "index into the vertices array of D:/Meshes/skeletons/<segid>.npz",
    "arc_um": "cumulative path length in micrometres from the first node of that path; drive a constant-velocity pulse off this",
    "synapse_xyz_nm": "mossy-fibre synapse centres from renders/mf_synapses.csv, already nanometres, same space",
    "hero_root": "the node nearest the measured soma centre, NOT the CAVE root field (which is a degree-1 tip)",
    "mossy_fibre_root": "the fibre end farthest from its synapses onto the hero, so a pulse launched at the root travels toward the boutons",
}
json.dump({"_doc": doc, "cells": paths_out},
          open(os.path.join(OUT, "ap_paths.json"), "w"), indent=1)
json.dump({str(k): v for k, v in report.items()},
          open(os.path.join(OUT, "report.json"), "w"), indent=1)
sz = os.path.getsize(os.path.join(OUT, "ap_paths.json")) / 1e6
print(f"\nWROTE ap_paths.json ({sz:.1f} MB) + report.json", flush=True)
