"""Final validation of ap_paths.json against the npz files."""
import json, os
import numpy as np

OUT = r"D:\Meshes\skeletons"
J = json.load(open(os.path.join(OUT, "ap_paths.json")))
ok = True

for seg, cell in J["cells"].items():
    d = np.load(os.path.join(OUT, f"{seg}.npz"), allow_pickle=True)
    v = d["vertices"]
    n = len(v)
    edges = set()
    for a, b in d["edges"]:
        edges.add((int(a), int(b)))
        edges.add((int(b), int(a)))
    root = int(d["root"])
    bad_idx = bad_edge = bad_arc = bad_root = 0
    lens = []
    for p in cell["paths"]:
        idx, arc = p["indices"], p["arc_um"]
        if len(idx) != len(arc):
            bad_arc += 1
        if max(idx) >= n or min(idx) < 0:
            bad_idx += 1
        if cell["role"] == "hero_thorny_pyramidal" and idx[0] != root:
            bad_root += 1
        for k in range(1, len(idx)):
            if (idx[k - 1], idx[k]) not in edges:
                bad_edge += 1
            step = np.linalg.norm(v[idx[k]] - v[idx[k - 1]]) / 1000.0
            if abs((arc[k] - arc[k - 1]) - step) > 1e-2:
                bad_arc += 1
        lens.append(p["length_um"])
    print(f"{seg} [{cell['role']}] paths={len(cell['paths'])} "
          f"len um min/med/max {min(lens):.1f}/{np.median(lens):.1f}/{max(lens):.1f}")
    print(f"    out-of-range idx={bad_idx}  non-edge steps={bad_edge}  "
          f"arc mismatches={bad_arc}  paths not starting at root={bad_root}")
    if bad_idx or bad_edge or bad_arc or bad_root:
        ok = False
    # Blender-space sanity
    p0 = v[cell["paths"][0]["indices"]]
    b = np.column_stack([p0[:, 0], -p0[:, 2], p0[:, 1]])
    print(f"    first path file-space bbox {p0.min(0).round(0).tolist()} .. {p0.max(0).round(0).tolist()}")
    print(f"    after Blender axis swap    {b.min(0).round(0).tolist()} .. {b.max(0).round(0).tolist()}")

print("\nALL PATH CHECKS PASSED" if ok else "\nPROBLEMS FOUND")
