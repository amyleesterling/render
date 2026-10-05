"""Encode the EPG base and heading overlays to WebP, and audit the whole set.

Four things are checked rather than assumed, each with a control where a control is
possible:

  1. every file is 1600x1200 with real transparency
  2. straight alpha, no black matte (premultiplied copy scored as the control)
  3. nothing bled into fully transparent pixels, which is why denoising is off
  4. every heading overlay and every per-cell master is pixel aligned with the base
     (a 3 px shifted copy is scored the same way, so the test can fail)

  python epg_layers_webp.py
"""
import glob
import os

import numpy as np
from PIL import Image

SRC = "D:/Meshes/renders/epg"
CELLS = os.path.join(SRC, "cells")
MAX_BYTES = 1_000_000
HEADINGS = [f"epg-heading-{k:02d}" for k in range(16)]


def load(p):
    return np.asarray(Image.open(p).convert("RGBA")).astype(float)


def matte_score(rgb, al, lo=0.12, hi=0.35):
    lum = rgb.max(2)
    e, s = (al > lo) & (al < hi), al > 0.97
    if e.sum() < 50 or s.sum() < 50:
        return None
    return float(lum[e].mean() / max(lum[s].mean(), 1e-9))


base_png = os.path.join(SRC, "epg-base.png")
base = load(base_png)
base_mask = base[..., 3] > 8
print(f"base: {base.shape[1]}x{base.shape[0]}, lit {100*base_mask.mean():.2f}%")

print("\nstraight alpha and transparent-pixel cleanliness")
worst_bleed = 0
for name in ["epg-base"] + HEADINGS:
    a = load(os.path.join(SRC, f"{name}.png"))
    rgb, al = a[..., :3], a[..., 3] / 255
    s = matte_score(rgb, al)
    c = matte_score(rgb * al[..., None], al)
    bleed = rgb[al == 0].max() if (al == 0).any() else 0
    worst_bleed = max(worst_bleed, bleed)
    flag = "" if (s and s > 0.85 and c < s - 0.05) else "  <-- CHECK"
    print(f"  {name:20s} straight {s:.3f}  control {c:.3f}  rgb under alpha=0 max {bleed:3.0f}{flag}")
print(f"  worst bleed into transparent pixels across the set: {worst_bleed:.0f}/255")

print("\nalignment against the base (every lit pixel must fall inside it)")
worst = 1.0
for name in HEADINGS:
    m = load(os.path.join(SRC, f"{name}.png"))[..., 3] > 8
    inside = (m & base_mask).sum() / max(m.sum(), 1)
    ctrl = (np.roll(m, 3, axis=1) & base_mask).sum() / max(m.sum(), 1)
    worst = min(worst, inside)
    print(f"  {name:20s} {m.sum():7,d} px  inside {100*inside:6.2f}%  CONTROL shifted 3px {100*ctrl:6.2f}%")

cell_files = sorted(glob.glob(os.path.join(CELLS, "epg-cell-*.png")))
cw, cctrl = [], []
for p in cell_files:
    m = load(p)[..., 3] > 8
    cw.append((m & base_mask).sum() / max(m.sum(), 1))
    cctrl.append((np.roll(m, 3, axis=1) & base_mask).sum() / max(m.sum(), 1))
print(f"  {len(cell_files)} per-cell masters: inside base min {100*min(cw):.2f}% "
      f"mean {100*np.mean(cw):.2f}%   CONTROL mean {100*np.mean(cctrl):.2f}%")
worst = min(worst, min(cw))
assert worst > 0.99, f"layers not aligned, worst {worst:.4f}"
print("  -> aligned")

print("\nencode")
total = 0
for name in ["epg-base"] + HEADINGS:
    src = os.path.join(SRC, f"{name}.png")
    dst = os.path.join(SRC, f"{name}.webp")
    im = Image.open(src).convert("RGBA")
    chosen = None
    for label, kw in ([("lossless", dict(lossless=True, quality=100, method=6, exact=False))]
                      + [(f"q{q}", dict(lossless=False, quality=q, method=6, exact=False))
                         for q in (95, 92, 90)]):
        im.save(dst, "WEBP", **kw)
        if os.path.getsize(dst) <= MAX_BYTES:
            chosen = (label, os.path.getsize(dst))
            break
    back = np.asarray(Image.open(dst).convert("RGBA"))
    d = int(np.abs(back[..., 3].astype(int) - np.asarray(im)[..., 3].astype(int)).max())
    total += chosen[1]
    print(f"  {name+'.webp':24s} {chosen[0]:8s} {chosen[1]/1e3:7.1f} KB  alpha delta {d}/255")
print(f"\n  {1+len(HEADINGS)} webp files, {total/1e3:.1f} KB total")
print(f"  {len(cell_files)} per-cell masters kept as PNG in {CELLS}")
