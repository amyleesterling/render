"""Copy the calcium-imaged cell meshes out of the read-only meshparty library.

HANDOFF.md marks C:\\Users\\amyle\\meshparty read-only, so this copies rather than
touching anything there. Names become <root_id>.obj so the renderer can look a
cell up by id.
"""
import json
import os
import shutil

import pandas as pd

SRC_MAP = r"D:\Meshes\retina\mesh_paths.json"
DST = r"D:\Meshes\retina\meshes"
os.makedirs(DST, exist_ok=True)

paths = json.load(open(SRC_MAP))
j = pd.read_csv(r"D:\Meshes\retina\functional\joined.csv")
want = set(int(x) for x in j["root_id"])

todo = [(int(k), v) for k, v in paths.items() if int(k) in want]
print(f"[stage] {len(todo)} meshes wanted, of {len(paths)} known", flush=True)

done = skipped = failed = 0
mb = 0.0
for rid, src in todo:
    dst = os.path.join(DST, f"{rid}.obj")
    if os.path.exists(dst):
        skipped += 1
        continue
    try:
        shutil.copy2(src, dst)
        mb += os.path.getsize(dst) / 1e6
        done += 1
        if done % 25 == 0:
            print(f"[stage] {done} copied, {mb:.0f} MB", flush=True)
    except Exception as e:
        failed += 1
        print(f"[stage] FAIL {rid}: {type(e).__name__} {e}", flush=True)

print(f"[stage] done: {done} copied ({mb:.0f} MB), {skipped} already present, "
      f"{failed} failed", flush=True)
print(f"[stage] total in {DST}: "
      f"{len([f for f in os.listdir(DST) if f.endswith('.obj')])}", flush=True)
