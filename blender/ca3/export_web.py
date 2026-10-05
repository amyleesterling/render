"""Web-sized meshes with the action potential field baked into vertex colours.

The native hero is 4.5M faces and 225 MB, which is not a web asset. This cuts
both meshes down, resamples the skeleton distance field onto the reduced
vertices, and writes a GLB per mesh with the field packed into COLOR_0:

    R = distance along the cable, normalised 0 to 1
    G = 1 where the signal reaches, 0 where it never does
    B = unused

so the viewer needs no side-car data and no lookup, just the attribute.
"""
import numpy as np
import pymeshlab
import trimesh
from pathlib import Path

SRC = Path(r"D:\Meshes\hero")
OUT = Path(r"C:\Users\amyle\ca3\web")
OUT.mkdir(parents=True, exist_ok=True)
F = np.load(r"D:\Meshes\skeletons\ap_fields.npz")

HERO = "648518346438632877"
FIBRE = "648518346448994107"
TARGETS = {"cell": 110_000, "fibre": 26_000}


def reduce_mesh(path, target):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(path))
    before = ms.current_mesh().face_number()
    ms.meshing_remove_connected_component_by_face_number(mincomponentsize=60)
    ms.apply_coord_hc_laplacian_smoothing()
    # preservetopology stays off: these meshes have thousands of components and
    # it blocks almost every collapse
    ms.meshing_decimation_quadric_edge_collapse(
        targetfacenum=target, qualitythr=0.35, preserveboundary=True,
        preservenormal=False, preservetopology=False, optimalplacement=True,
        autoclean=True)
    m = ms.current_mesh()
    print(f"    {before:,} -> {m.face_number():,} faces")
    return m.vertex_matrix().copy(), m.face_matrix().copy()


def nearest(verts, nodes, values, chunk=40000):
    """|a-b|^2 = |a|^2 - 2a.b + |b|^2 so this is a matmul, not a 3D broadcast."""
    nn = (nodes ** 2).sum(1)
    out = np.empty(len(verts))
    for i in range(0, len(verts), chunk):
        blk = verts[i:i + chunk]
        out[i:i + chunk] = values[(nn[None, :] - 2.0 * (blk @ nodes.T)).argmin(1)]
    return out


def nearest_lit(verts, nodes, values, span, within):
    """Search only the nodes the signal reaches, so the corridor stays continuous
    instead of alternating between lit and parked nodes along a dendrite."""
    keep = values < span * 1.5
    sub_n, sub_v = nodes[keep], values[keep]
    nn = (sub_n ** 2).sum(1)
    d = np.empty(len(verts))
    lit = np.zeros(len(verts), dtype=bool)
    for i in range(0, len(verts), 40000):
        blk = verts[i:i + 40000]
        d2 = nn[None, :] - 2.0 * (blk @ sub_n.T)
        j = d2.argmin(1)
        d[i:i + 40000] = sub_v[j]
        true2 = d2[np.arange(len(blk)), j] + (blk ** 2).sum(1)
        lit[i:i + 40000] = true2 <= within ** 2
    return d, lit


meta = {}
for key, seg in (("cell", HERO), ("fibre", FIBRE)):
    print(f"[web] {key} {seg}")
    src = SRC / (f"hero_{seg}.obj" if key == "cell" else f"fibre_{seg}.obj")
    verts, faces = reduce_mesh(src, TARGETS[key])

    nodes = F[f"{key}_{seg}_verts"]
    values = F[f"{key}_{seg}_dist"]
    span = float(F[f"{key}_{seg}_span"])

    if key == "cell":
        d, lit = nearest_lit(verts, nodes, values, span, 5500.0)
    else:
        d = nearest(verts, nodes, values)
        lit = np.ones(len(verts), dtype=bool)

    norm = np.clip(d / span, 0.0, 1.0)
    col = np.zeros((len(verts), 4), dtype=np.uint8)
    col[:, 0] = np.round(norm * 255)
    col[:, 1] = np.where(lit, 255, 0)
    col[:, 3] = 255

    # centre on the contacts and scale to metres-ish so the viewer is sane
    if key == "cell":
        meta["centre"] = verts.mean(axis=0).tolist()
    centre = np.array(meta["centre"])
    v = (verts - centre) / 1000.0        # nanometres to micrometres

    mesh = trimesh.Trimesh(vertices=v, faces=faces, vertex_colors=col, process=False)
    path = OUT / f"{key}.glb"
    mesh.export(path)
    mb = path.stat().st_size / 1024 ** 2
    print(f"    {len(v):,} verts, span {span:.1f} um, "
          f"{100*lit.mean():.0f}% lit -> {path.name} {mb:.1f} MB")
    meta[key] = {"span_um": span, "verts": int(len(v)), "faces": int(len(faces))}

syn = (F["syn_nm"] - np.array(meta["centre"])) / 1000.0
meta["synapses"] = syn.tolist()
meta["soma_dist_um"] = float(F["soma_dist"])
meta["cell_span_um"] = float(F["cell_span"])
import json
(OUT / "scene.json").write_text(json.dumps(meta, indent=1))
print(f"[web] wrote scene.json, {len(syn)} synapse points")
