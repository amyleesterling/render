"""One-off: bake the native hero + its 6 fibres + the 56 partner cells into a
second scene cache, D:\\Meshes\\ca3_scene_partners.blend.

Importing 2.3 GB of partner OBJ costs 63 s every run, which is most of the wall
clock of a test still. This does the import once. hero_full.py opens this file
instead of ca3_scene.blend whenever scope=partners and the file exists.

Nothing else is changed: no materials, no keyframes, no camera. hero_full.py
rebuilds all of that from scratch either way, so the cache stays neutral.

  blender --background --python build_partner_cache.py
"""
import time
from pathlib import Path

import bpy
from mathutils import Matrix

SRC = r"D:\Meshes\ca3_scene.blend"
DST = r"D:\Meshes\ca3_scene_partners.blend"
HERO_DIR = Path(r"D:\Meshes\hero")
PART_DIR = (Path(r"D:\Meshes\partners_lite")
            if Path(r"D:\Meshes\partners_lite").exists()
            else Path(r"D:\Meshes\partners"))

t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=SRC)
print(f"[pcache] opened base cache in {time.time()-t0:.0f}s", flush=True)

pivot = bpy.data.objects.get("pivot_thorny_pyramidals")
if pivot is None:
    raise SystemExit("pivot_thorny_pyramidals missing from the cache")


def bring_in(path, prefix):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    for o in new:
        o.name = prefix + path.stem
        # Same parenting hero_full.py uses: identity parent inverse, so the
        # root's scale carries these down with everything else. The importer's
        # 90 deg X rotation stays on the object, which is correct.
        o.parent = pivot
        o.matrix_parent_inverse = Matrix.Identity(4)
    return new


t0 = time.time()
n_hero = 0
for p in sorted(HERO_DIR.glob("*.obj")):
    n_hero += len(bring_in(p, "NATIVE_"))
print(f"[pcache] native hero set: {n_hero} objects in {time.time()-t0:.0f}s", flush=True)

t0 = time.time()
part = []
for p in sorted(PART_DIR.glob("*.obj")):
    if p.name.endswith((".raw.obj", ".tmp.obj")):
        continue
    part.extend(bring_in(p, "PARTNER_"))
bpy.context.view_layer.update()
faces = sum(len(o.data.polygons) for o in part)
print(f"[pcache] {len(part)} partners, {faces:,} faces, "
      f"{time.time()-t0:.0f}s", flush=True)

# shade smooth once here so hero_full.py does not have to walk 62 objects
for o in bpy.data.objects:
    if o.type == "MESH" and (o.name.startswith("PARTNER_")
                             or o.name.startswith("NATIVE_")):
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.shade_smooth()
print("[pcache] shaded smooth", flush=True)

t0 = time.time()
bpy.ops.wm.save_as_mainfile(filepath=DST, compress=False)
mb = Path(DST).stat().st_size / 1024 ** 2
print(f"[pcache] saved {mb:,.0f} MB in {time.time()-t0:.0f}s -> {DST}", flush=True)
print("[pcache] DONE", flush=True)
