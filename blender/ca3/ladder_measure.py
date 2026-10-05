"""Measure the framing of the scale ladder test frames, instead of eyeballing it.

  .venv/Scripts/python ladder_measure.py renders/_ladder_0024.png [...]

Reports, per frame: the lit content bounding box as a fraction of the frame, how
far it sits from each edge, whether it touches an edge (which means clipped), and
the number of separate bright components, which is what tells you whether the
last rung resolves 53 synapses or one glowing blob.

Target is 85 to 90 percent height fill with visible margin. 100 percent is
clipped. The distance correction that holds well here is
    new_distance = old_distance * fill / target_fill
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

THRESH = 10.0        # 0..255 luminance, the same cut the playbook uses
TARGET_FILL = 0.87


def measure(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im, dtype=np.float64)
    lum = 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]
    H, W = lum.shape
    lit = lum > THRESH
    if not lit.any():
        print(f"{Path(path).name}: EMPTY FRAME, nothing above luminance {THRESH}")
        return
    rows = np.where(lit.sum(1) > 0)[0]
    cols = np.where(lit.sum(0) > 0)[0]
    fh = (rows[-1] - rows[0] + 1) / H
    fw = (cols[-1] - cols[0] + 1) / W
    clipped = rows[0] <= 1 or rows[-1] >= H - 2 or cols[0] <= 1 or cols[-1] >= W - 2

    # brightness weighted centroid, for the shift a subject off the origin needs
    cy = float((lum * np.arange(H)[:, None]).sum() / lum.sum())
    cx = float((lum * np.arange(W)[None, :]).sum() / lum.sum())

    # separate bright components, at a cut well above the tissue floor
    hot = lum > max(THRESH * 8, 90.0)
    lab, n = ndimage.label(hot)
    if n:
        sizes = ndimage.sum(hot, lab, range(1, n + 1))
        n_real = int((sizes >= 12).sum())
    else:
        n_real = 0

    print(f"{Path(path).name}  {W}x{H}")
    print(f"   lit coverage      {lit.mean() * 100:6.2f} % of the frame")
    print(f"   content bbox      rows {rows[0]:4d}..{rows[-1]:4d}   "
          f"cols {cols[0]:4d}..{cols[-1]:4d}")
    print(f"   fill              height {fh * 100:5.1f} %   width {fw * 100:5.1f} %"
          f"   {'CLIPPED' if clipped else 'clear of every edge'}")
    print(f"   margins px        top {rows[0]:4d}  bottom {H - 1 - rows[-1]:4d}  "
          f"left {cols[0]:4d}  right {W - 1 - cols[-1]:4d}")
    print(f"   luminance centroid ({cx / W:.3f}, {cy / H:.3f}) of the frame "
          f"(0.5, 0.5 is centred)")
    print(f"   bright components  {n_real} over 12 px at luminance > "
          f"{max(THRESH * 8, 90.0):.0f}")
    if not clipped:
        print(f"   suggested camera distance x{fh / TARGET_FILL:.3f} "
              f"for {TARGET_FILL * 100:.0f} % height fill")
    else:
        print("   content touches an edge, so pull back before trusting the fill")
    print()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        measure(p)
