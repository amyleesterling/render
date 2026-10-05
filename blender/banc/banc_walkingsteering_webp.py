"""Encode the poster PNG to spec WebP, and audit the alpha rather than trust it.

Spec: 1600x1200, transparent background, STRAIGHT alpha with no black matte, sRGB,
lossless or near-lossless alpha, <= 1 MB.

"No black matte" is the part that can silently fail, so it is measured. If the
render were premultiplied (or composited over black), the soft edge pixels would
be dragged toward black in proportion to their alpha. The audit compares the hue
of semi-transparent edge pixels against fully opaque interior pixels of the same
neuron colour: under straight alpha they match, under a black matte the edges go
dark. A synthetic premultiplied copy is run through the same test as a control, so
a pass cannot be vacuous.

  python banc_walkingsteering_webp.py
  python banc_walkingsteering_webp.py D:\\Meshes\\renders\\banc_walking_steering_poster.png
"""
import os
import sys

import numpy as np
from PIL import Image

SRC = sys.argv[1] if len(sys.argv) > 1 else r"D:\Meshes\renders\banc_walking_steering_poster.png"
DST = r"C:\Users\amyle\Documents\New project\banc-explorer\public\banc-walking-steering-poster.webp"
PREVIEW = r"D:\Meshes\renders\banc_walking_steering_poster_on_panel.png"
MAX_BYTES = 1_000_000
PANEL_BG = (10, 14, 18)      # the dark panel the poster sits on

if not os.path.exists(SRC):
    raise SystemExit(f"no render at {SRC} - run banc_walkingsteering_poster.py first")

im = Image.open(SRC).convert("RGBA")
a = np.asarray(im).astype(np.float64)
rgb, alpha = a[..., :3], a[..., 3] / 255.0
print(f"source {im.size[0]}x{im.size[1]}  {os.path.getsize(SRC)/1e6:.2f} MB")


def matte_score(rgb, alpha, lo=0.12, hi=0.35):
    """Mean brightness of soft edge pixels / mean brightness of opaque pixels.

    Both measured only where there is real colour. ~1.0 means straight alpha.
    Much less than 1 means the colour has been dragged toward black by a matte.
    """
    lum = rgb.max(2)
    edge = (alpha > lo) & (alpha < hi)
    solid = alpha > 0.97
    if edge.sum() < 50 or solid.sum() < 50:
        return None, edge.sum(), solid.sum()
    return float(lum[edge].mean() / max(lum[solid].mean(), 1e-9)), int(edge.sum()), int(solid.sum())


score, n_edge, n_solid = matte_score(rgb, alpha)
prem = rgb * alpha[..., None]                      # what a black matte would look like
ctrl, _, _ = matte_score(prem, alpha)

print("\nalpha audit")
print(f"  fully transparent px : {(alpha==0).sum():,} ({100*(alpha==0).mean():.2f}%)")
print(f"  partial alpha px     : {((alpha>0)&(alpha<1)).sum():,}")
print(f"  fully opaque px      : {(alpha==1).sum():,} ({100*(alpha==1).mean():.2f}%)")
if score is None:
    print(f"  edge/solid brightness: not enough sample px (edge={n_edge}, solid={n_solid})")
else:
    print(f"  edge/solid brightness: {score:.3f}   (straight alpha ~1.0; {n_edge:,} edge px)")
    print(f"  CONTROL premultiplied: {ctrl:.3f}   (must be clearly lower, else the test is void)")
    if ctrl >= score - 0.05:
        print("  !! CONTROL DID NOT SEPARATE - do not trust the straight-alpha claim")
    elif score > 0.85:
        print("  -> straight alpha confirmed, no black matte")
    else:
        print("  !! edges look matted, investigate before shipping")

# Colour left in fully transparent pixels tells you whether `exact` is needed.
if (alpha == 0).any():
    print(f"  rgb under alpha=0    : max channel {rgb[alpha==0].max():.0f} "
          f"(0 means the renderer already zeroed it)")

# ---------------------------------------------------------------- encode
os.makedirs(os.path.dirname(DST), exist_ok=True)
# exact=False lets the encoder rewrite RGB under fully transparent pixels, which
# compresses far better. Blender leaves real colour there (measured: max channel
# 219 under alpha=0) and it is invisible under any correct compositing. The edge
# pixels that carry the straight-alpha guarantee all have alpha>0 and are kept.
attempts = [("lossless", dict(lossless=True, quality=100, method=6, exact=False))]
attempts += [(f"q{q}", dict(lossless=False, quality=q, method=6, exact=False))
             for q in (95, 92, 90, 88, 85)]

chosen = None
for name, kw in attempts:
    im.save(DST, "WEBP", **kw)
    size = os.path.getsize(DST)
    ok = size <= MAX_BYTES
    print(f"\n  {name:9s} -> {size/1e3:7.1f} KB  {'OK' if ok else 'over budget'}")
    if ok:
        chosen = (name, size)
        break

if chosen is None:
    raise SystemExit("could not hit the 1 MB budget even at q85 - reduce coverage or size")

# ---------------------------------------------------------------- verify the file
back = Image.open(DST).convert("RGBA")
b = np.asarray(back).astype(np.float64)
da = np.abs(b[..., 3] - a[..., 3])
print(f"\nwrote {DST}")
print(f"  {back.size[0]}x{back.size[1]}  {chosen[0]}  {chosen[1]/1e3:.1f} KB  "
      f"(budget {MAX_BYTES/1e3:.0f} KB)")
print(f"  alpha round-trip: max delta {da.max():.0f}/255, mean {da.mean():.3f}")
assert back.size == (1600, 1200), f"wrong size {back.size}"
assert b[..., 3].min() == 0, "no transparent pixels survived the encode"

# Composite over the real panel colour so a dark fringe would be visible.
flat = Image.new("RGBA", back.size, PANEL_BG + (255,))
flat.alpha_composite(back)
flat.convert("RGB").save(PREVIEW)
print(f"  preview on panel bg -> {PREVIEW}")

# Content bounding box, so the panel crop can be decided from measurement.
ys, xs = np.where(np.asarray(back)[..., 3] > 8)
if len(xs):
    print(f"  content bbox: x {xs.min()}-{xs.max()} ({xs.max()-xs.min()+1} px), "
          f"y {ys.min()}-{ys.max()} ({ys.max()-ys.min()+1} px)")
    print(f"  height fill: {100*(ys.max()-ys.min()+1)/1200:.1f}%  "
          f"width fill: {100*(xs.max()-xs.min()+1)/1600:.1f}%")
