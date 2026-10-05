"""Move meshparty skeleton nodes onto the tube axis.

meshparty's skeleton vertices ARE mesh vertices, so the centreline hugs the
membrane. For a glowing pulse we want it down the middle. Each node is moved to
the centroid of the mesh vertices inside a ball big enough to wrap the tube;
on a cylinder that centroid lies on the axis.

Verification: distance from node to the NEAREST mesh vertex should rise from
~0 nm to roughly the local cable radius. That is the signature of being on axis.
"""
import sys, os, time
import numpy as np
from scipy.spatial import cKDTree


def load_obj_verts(path):
    out = []
    with open(path) as f:
        for line in f:
            if line[0] == "v" and line[1] == " ":
                out.append(line[2:])
    return np.fromstring(" ".join(out), sep=" ").reshape(-1, 3)


def recenter(v, mv, radii=(2000.0, 1500.0, 1200.0), min_pts=8):
    tree = cKDTree(mv)
    p = v.copy()
    for R in radii:
        nbr = tree.query_ball_point(p, R)
        newp = p.copy()
        for i, ids in enumerate(nbr):
            if len(ids) >= min_pts:
                newp[i] = mv[ids].mean(0)
        p = newp
    return p


def run(seg, obj_path, npz_path):
    t0 = time.time()
    d = np.load(npz_path, allow_pickle=True)
    v = np.asarray(d["vertices"], float)
    mv = load_obj_verts(obj_path)
    tree = cKDTree(mv)
    before, _ = tree.query(v, k=1)
    p = recenter(v, mv)
    after, _ = tree.query(p, k=1)
    # segment lengths must not blow up: recentering should shorten slightly
    e = np.asarray(d["edges"], np.int64)
    c0 = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1).sum() / 1000.
    c1 = np.linalg.norm(p[e[:, 0]] - p[e[:, 1]], axis=1).sum() / 1000.
    keep = dict(d)
    keep["vertices"] = p
    prev = str(d["source"]) if "source" in d.files else "meshparty.skeletonize_mesh"
    keep["source"] = prev + " + axis recentring"
    np.savez_compressed(npz_path, **keep)
    print(f"{seg}: node->surface distance median {np.median(before):.0f} -> "
          f"{np.median(after):.0f} nm (p90 {np.percentile(after,90):.0f} nm), "
          f"cable {c0:,.1f} -> {c1:,.1f} um  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    MFS = [648518346432881590, 648518346440660317, 648518346448994107,
           648518346450631673, 648518346452106477, 648518346460875907]
    for seg in MFS:
        npz = rf"D:\Meshes\skeletons\{seg}_meshparty.npz"
        if os.path.exists(npz):
            run(seg, rf"D:\Meshes\hero\fibre_{seg}.obj", npz)
    hero = r"D:\Meshes\skeletons\648518346438632877_meshparty.npz"
    if os.path.exists(hero):
        run(648518346438632877, r"D:\Meshes\hero\hero_648518346438632877.obj", hero)
    else:
        print("hero meshparty skeleton not present yet", flush=True)
    print("RECENTER DONE", flush=True)
