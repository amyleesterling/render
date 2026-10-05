"""Measure framing instead of eyeballing it.

  python framecheck.py <png> [<png> ...] [thresh=10]

Thresholds the luminance, finds the bounding box of the lit content, and reports
how much of the frame it fills plus whether it touches an edge. The playbook's
rule is 85 to 90 percent height fill with visible margin; 100 percent means
clipped, and the fix is old_distance * fill / target_fill.
"""
import sys

import numpy as np
from PIL import Image

args = [a for a in sys.argv[1:] if "=" not in a]
opts = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
TH = float(opts.get("thresh", 10))
PCT = float(opts.get("pct", 0.5))   # percent of lit pixels trimmed from each end

print(f"{'file':38s} {'fillH':>6} {'fillW':>6} {'top':>5} {'bot':>5} "
      f"{'left':>5} {'right':>5} {'lit%':>6}  edges")
for path in args:
    im = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    H, W = im.shape[:2]
    lum = 0.2126 * im[..., 0] + 0.7152 * im[..., 1] + 0.0722 * im[..., 2]
    lit = lum > TH
    if not lit.any():
        print(f"{path.split('/')[-1][:38]:38s}  EMPTY FRAME, nothing above "
              f"luminance {TH:.0f}")
        continue
    # Percentile bounds on the lit pixels, not min/max. A single thin axon
    # trailing off the bottom of a frame otherwise reports the whole shot as
    # clipped while the mass of the subject sits comfortably inside. Same lesson
    # as the stray vertices in section 3 of RENDERING_NEURONS.md. The raw extent
    # is printed alongside so real clipping is still visible.
    ys, xs = np.nonzero(lit)
    r0, r1 = np.percentile(ys, [PCT, 100 - PCT]).astype(int)
    c0, c1 = np.percentile(xs, [PCT, 100 - PCT]).astype(int)
    rows = np.where(lit.sum(1) > 0)[0]
    cols = np.where(lit.sum(0) > 0)[0]
    fh = (r1 - r0 + 1) / H
    fw = (c1 - c0 + 1) / W
    edges = []
    if rows[0] <= 1:
        edges.append("TOP")
    if rows[-1] >= H - 2:
        edges.append("BOTTOM")
    if cols[0] <= 1:
        edges.append("LEFT")
    if cols[-1] >= W - 2:
        edges.append("RIGHT")
    print(f"{path.split('/')[-1][:38]:38s} {fh:6.3f} {fw:6.3f} "
          f"{r0:5d} {H-1-r1:5d} {c0:5d} {W-1-c1:5d} "
          f"{100*lit.mean():6.2f}  raw {rows[0]}/{H-1-rows[-1]}/"
          f"{cols[0]}/{W-1-cols[-1]}  {','.join(edges) if edges else 'clear'}")
