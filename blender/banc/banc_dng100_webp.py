"""Encode the DNg100 walking-speed layer to lossless WebP, and audit the alpha.

Spec: 1600x1200, transparent straight alpha, LOSSLESS WebP. One static poster plus
a 16 frame non-looping pulse, frames 00 and 15 fully transparent.

Lossless is not negotiable here the way it was for the poster, so there is no
quality ladder to fall back on. If a frame is too big that is a fact to report,
not something to silently fix by degrading the file the app composites.

The straight-alpha audit is the one from banc_walkingsteering_webp.py, including
its premultiplied control: without a control that must fail, a pass means nothing.

  python banc_dng100_webp.py
"""
import os
import shutil

import numpy as np
from PIL import Image

SRC_STATIC = r"D:\Meshes\renders\layers\banc-walk-speed-dng100.png"
SRC_SEQ = r"D:\Meshes\renders\layers\banc-walk-speed-dng100-seq"
PUBLIC = r"C:\Users\amyle\Documents\New project\banc-explorer\public"
DST_STATIC = os.path.join(PUBLIC, "banc-walk-speed-dng100.webp")
DST_SEQ = os.path.join(PUBLIC, "banc-walk-speed-dng100")
REF = os.path.join(PUBLIC, "banc-context-base.webp")


def matte_score(rgb, alpha, lo=0.12, hi=0.35):
    """Soft-edge brightness over opaque brightness. ~1.0 means straight alpha."""
    lum = rgb.max(2)
    edge = (alpha > lo) & (alpha < hi)
    solid = alpha > 0.97
    if edge.sum() < 50 or solid.sum() < 50:
        return None, int(edge.sum()), int(solid.sum())
    return float(lum[edge].mean() / max(lum[solid].mean(), 1e-9)), int(edge.sum()), int(solid.sum())


def audit(path, label):
    a = np.asarray(Image.open(path).convert("RGBA")).astype(np.float64)
    rgb, alpha = a[..., :3], a[..., 3] / 255.0
    s, ne, _ = matte_score(rgb, alpha)
    ctrl, _, _ = matte_score(rgb * alpha[..., None], alpha)   # a black matte, as control
    if s is None:
        print(f"  {label}: too few edge px to audit ({ne})")
        return
    verdict = ("straight alpha confirmed" if s > 0.85 and ctrl is not None and ctrl < s - 0.05
               else "!! CHECK: control did not separate" if ctrl is None or ctrl >= s - 0.05
               else "!! edges look matted")
    print(f"  {label}: edge/solid {s:.3f}  control(premultiplied) {ctrl:.3f}  -> {verdict}")


def encode(src, dst):
    im = Image.open(src).convert("RGBA")
    assert im.size == (1600, 1200), f"{src} is {im.size}, must be 1600x1200"
    # exact=True keeps RGB under fully transparent pixels rather than letting the
    # encoder rewrite it. For a compositing layer that costs a little size and
    # removes a whole class of "why is there a fringe" question later.
    im.save(dst, "WEBP", lossless=True, quality=100, method=6, exact=True)
    return os.path.getsize(dst)


os.makedirs(DST_SEQ, exist_ok=True)
print(f"public -> {PUBLIC}")
if os.path.exists(REF):
    r = Image.open(REF)
    print(f"reference banc-context-base.webp is {r.size[0]}x{r.size[1]}")
    assert r.size == (1600, 1200), "the context layer is not 1600x1200; layers would not register"
else:
    print("!! banc-context-base.webp not found: cannot confirm the layers register")

print("\nstatic poster")
n = encode(SRC_STATIC, DST_STATIC)
print(f"  {n/1e3:.1f} KB lossless -> {DST_STATIC}")
audit(SRC_STATIC, "alpha")

print("\n16 frame pulse")
total = 0
blank = []
for i in range(16):
    src = os.path.join(SRC_SEQ, f"frame-{i:02d}.png")
    if not os.path.exists(src):
        raise SystemExit(f"missing {src}")
    dst = os.path.join(DST_SEQ, f"frame-{i:02d}.webp")
    total += encode(src, dst)
    a = np.asarray(Image.open(dst).convert("RGBA"))[..., 3]
    if a.max() == 0:
        blank.append(i)
print(f"  16 frames, {total/1e3:.1f} KB total, {total/16/1e3:.1f} KB mean -> {DST_SEQ}")
print(f"  fully transparent frames: {blank}  (spec asks for [0, 15])")
assert blank == [0, 15], f"transparent frames are {blank}, spec requires exactly [0, 15]"
audit(os.path.join(SRC_SEQ, "frame-07.png"), "mid-pulse alpha")

print("\nDONE")
