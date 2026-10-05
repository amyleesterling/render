"""One EM cross-section covering the reconstructed footprint.

Pulled at mip 4 (288 nm/voxel), which is plenty for a background plate: the
whole 1 mm block comes to about 3,500 pixels across, and mip 0 would be 55,000.
"""
import time

import numpy as np
import pandas as pd
from PIL import Image
from cloudvolume import CloudVolume

SRC = "precomputed://gs://zheng_mouse_hippocampus_production/v2/img_aligned_sharded_18nm"
MIP = 4
OUT = r"D:\Meshes\renders\em_slice.png"

# Frame it on where the CELLS are, not on where the synapses are.
#
# This was the midpoint of the mossy fibre synapse cloud, and that cloud sits in
# stratum lucidum, a band displaced from the centre of the cells. The EM crop, and
# so the wireframe block drawn around it, ended up 188 um off in y from the
# population it was supposed to contain, and cells visibly hung out of the box in
# every render that drew one.
#
# Measured over 242 cells across all four population folders, p0.5 to p99.5 within
# each cell and then p1 to p99 across cells, so a stray fragment cannot set the
# frame:
#
#     cells  x 422..1235  y 508..1362  z 4..96 um  ->  centre (829, 935, 50)
#     old synapse centre                                      (825, 1123, 50)
#
# The population occupies 813 x 854 x 92 um of the nominal 1000 x 1000 x 100 um
# block, so it fits inside the drawn box with margin once the box is on it.
CELL_CENTRE_NM = np.array([829000.0, 935000.0, 50000.0])
mid = CELL_CENTRE_NM
lo = mid - np.array([406500.0, 427000.0, 46000.0])
hi = mid + np.array([406500.0, 427000.0, 46000.0])
print(f"framing on the cell population centre {mid.round(0)} nm")

cv = CloudVolume(SRC, mip=MIP, use_https=True, progress=False, fill_missing=True)
res = np.array(cv.resolution)
print(f"mip {MIP}: {res.tolist()} nm/voxel, volume {cv.volume_size.tolist()} voxels")

HALF_NM = 620_000                       # a little wider than the data, so it reads as context
x0, x1 = int((mid[0] - HALF_NM) / res[0]), int((mid[0] + HALF_NM) / res[0])
y0, y1 = int((mid[1] - HALF_NM) / res[1]), int((mid[1] + HALF_NM) / res[1])
z = int(mid[2] / res[2])
x0, y0 = max(0, x0), max(0, y0)
x1 = min(int(cv.volume_size[0]), x1)
y1 = min(int(cv.volume_size[1]), y1)
print(f"cutting x {x0}:{x1}  y {y0}:{y1}  z {z}   "
      f"({x1-x0} x {y1-y0} px, {(x1-x0)*res[0]/1000:.0f} um across)")

t0 = time.time()
block = cv[x0:x1, y0:y1, z:z + 1]
img = np.asarray(block)[:, :, 0, 0].T          # cloudvolume is x,y,z; images want row=y
print(f"pulled in {time.time()-t0:.0f}s, {img.shape}, "
      f"range {img.min()}..{img.max()}, mean {img.mean():.0f}")

Image.fromarray(img).save(OUT)
print(f"wrote {OUT}")
