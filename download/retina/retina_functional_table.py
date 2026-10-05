"""Build one row per cell: mesh, cell type, direction tuning, and the bar tuning curve.

This is the table the animation reads. Everything in it is measured, nothing is
derived for looks:
  pref_dir_deg   the direction the cell responds to most strongly
  ds_index       how sharply it prefers it (0 = none, ~0.7 max here)
  ds_p           significance; only p < 0.05 is called direction selective
  dir_tuning     response at each bar direction, which is what makes cells light
                 up in turn as the bar sweeps

JOIN NOTE. Root ids are version specific and the two sources were snapshotted at
different times, so joining on them returns nothing. Supervoxel ids only agree
when the annotator clicked the same voxel, which gave 25 of 380. The soma
COORDINATES are identical between the mapping sheet and the CAVE point table, so
position is the key. That gave 370 of 380.
"""
import json
import os

import numpy as np
import pandas as pd

F = r"D:\Meshes\retina\functional"
OUT = r"D:\Meshes\retina"

joined = pd.read_csv(os.path.join(F, "joined.csv"))
print(f"[fn] {len(joined)} joined ROIs", flush=True)

rois = []
for i in range(5):
    d = pd.read_parquet(os.path.join(F, f"df_eyewire2_roi_level_GCL{i}.parquet"))
    d["field"] = f"GCL{i}"
    rois.append(d)
roi = pd.concat(rois, ignore_index=True)
print(f"[fn] {len(roi)} ROIs with traces", flush=True)

# the mapping sheet numbers ROIs per field, matching roi_id in the parquet
roi["key"] = roi["field"].astype(str) + "_" + roi["roi_id"].astype(str)
joined["key"] = joined["field"].astype(str) + "_" + joined["roi"].astype(str)
df = joined.merge(roi, on="key", how="inner", suffixes=("", "_r"))
print(f"[fn] {len(df)} rows after attaching traces", flush=True)


def as_array(v):
    """Several columns are stored as strings of numbers rather than arrays."""
    if isinstance(v, (list, np.ndarray)):
        return np.asarray(v, dtype=float)
    if isinstance(v, str):
        s = v.strip().strip("[]")
        for sep in (",", " "):
            try:
                a = np.array([float(x) for x in s.replace("\n", " ").split(sep) if x.strip()])
                if a.size:
                    return a
            except Exception:
                continue
    return np.array([])


rows = []
staged = set()
mesh_dir = os.path.join(OUT, "meshes")
if os.path.isdir(mesh_dir):
    staged = {int(f[:-4]) for f in os.listdir(mesh_dir) if f.endswith(".obj")}

for r in df.itertuples():
    tune = as_array(getattr(r, "bar_dir_component", None))
    pref = getattr(r, "bar_pref_dir", np.nan)
    rows.append({
        "root_id": int(r.root_id),
        "field": r.field,
        "roi": int(r.roi),
        "cls": r.cls,
        "cell_type": r.cell_type,
        "x": r.x, "y": r.y, "z": r.z,
        "pref_dir_rad": float(pref) if pd.notna(pref) else np.nan,
        "pref_dir_deg": float(np.degrees(pref) % 360) if pd.notna(pref) else np.nan,
        "ds_index": float(getattr(r, "bar_ds_index", np.nan)),
        "ds_p": float(getattr(r, "bar_ds_pvalue", np.nan)),
        "os_index": float(getattr(r, "bar_os_index", np.nan)),
        "os_p": float(getattr(r, "bar_os_pvalue", np.nan)),
        "bar_qidx": float(getattr(r, "bar_qidx", np.nan)),
        "n_dir_bins": int(tune.size),
        "dir_tuning": json.dumps([round(float(x), 4) for x in tune]) if tune.size else "",
        "has_mesh": int(r.root_id) in staged,
    })

out = pd.DataFrame(rows).drop_duplicates(subset=["root_id"])
out["is_ds"] = (out["ds_p"] < 0.05)
out.to_csv(os.path.join(OUT, "functional_cells.csv"), index=False)

print(f"\n[fn] {len(out)} unique cells")
print(f"[fn]   with a mesh staged:            {int(out['has_mesh'].sum())}")
print(f"[fn]   direction selective (p<0.05):  {int(out['is_ds'].sum())}")
print(f"[fn]   with a direction tuning curve: {int((out['n_dir_bins'] > 0).sum())}")
if (out["n_dir_bins"] > 0).any():
    print(f"[fn]   tuning bins: {sorted(out.loc[out['n_dir_bins']>0,'n_dir_bins'].unique())}")
print(f"\n[fn] by field:\n{out.groupby('field').size().to_string()}")
ds = out[out["is_ds"] & out["has_mesh"]]
print(f"\n[fn] DS cells that also have a mesh: {len(ds)}")
print(f"[fn] wrote {OUT}\\functional_cells.csv")
