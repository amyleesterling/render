"""Dimension labels on the volume diagram.

Edge midpoints are measured off the rendered wireframe rather than guessed, by
reprojecting the box corners through the same camera the render used.
"""
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC = r"D:\Meshes\renders\_vol_raw.png"
PROJ = r"D:\Meshes\renders\_vol_proj.json"
OUT = r"D:\Meshes\renders\gallery\21_volume.png"

im = Image.open(SRC).convert("RGBA")
W, H = im.size
d = ImageDraw.Draw(im)
proj = json.load(open(PROJ))


def font(sz, bold=False):
    for nm in (("arialbd.ttf", "seguisb.ttf") if bold else ("arial.ttf", "segoeui.ttf")):
        try:
            return ImageFont.truetype(nm, sz)
        except OSError:
            continue
    return ImageFont.load_default()


f_dim = font(34, True)
f_sub = font(23)
CY = (120, 200, 245, 255)
DIM = (150, 165, 185, 255)
INK = (240, 245, 251, 255)


def label(mid, text, sub=None, anchor="mm", dx=0, dy=0):
    x, y = mid[0] + dx, mid[1] + dy
    tw = d.textlength(text, font=f_dim)
    sw = d.textlength(sub, font=f_sub) if sub else 0
    bw = max(tw, sw)
    if anchor == "mm":
        x -= bw / 2
    elif anchor == "rm":
        x -= bw
    d.text((x, y), text, font=f_dim, fill=INK)
    if sub:
        d.text((x, y + 40), sub, font=f_sub, fill=DIM)


# the three block edges, labelled at their measured midpoints
for key, text, sub, anch, dx, dy in (
        ("x", "1 mm", "1000 \u00b5m", "mm", 40, 26),
        ("y", "1 mm", "1000 \u00b5m", "mm", -40, 26),
        # the z edge sits at x=90 of 2000, so this label reads inward or it clips
        ("z", "0.1 mm", "100 \u00b5m thick", "mm", 96, -96)):
    label(proj[key], text, sub, anch, dx, dy)

# And the cell, with a leader out to whichever side has room for it.
#
# This used to run out to the upper right unconditionally. The cell's projected
# position moves whenever the registration or the camera changes, and the first
# time the block was re-registered onto the population the caption ran straight
# off the right edge of the frame and read "one pyramidal c". Measure the text
# and choose the side rather than trusting a hard coded offset.
cx, cy = proj["cell"]
TXT = "one pyramidal cell"
SUB = "337 \u00d7 266 \u00d7 92 \u00b5m"
tw = max(d.textlength(TXT, font=f_dim), d.textlength(SUB, font=f_sub))
PAD = 40
right_fits = cx + 300 + tw + PAD <= W
ex = cx + 300 if right_fits else cx - 300 - tw
ey = max(PAD, cy - 250)
lead_from = cx + 24 if right_fits else cx - 24
lead_to = (ex - 16) if right_fits else (ex + tw + 16)
d.line([(lead_from, cy - 20), (lead_to, ey + 34)], fill=CY, width=3)
d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], outline=CY, width=3)
d.text((ex, ey), TXT, font=f_dim, fill=INK)
d.text((ex, ey + 40), SUB, font=f_sub, fill=DIM)
print(f"cell label to the {'right' if right_fits else 'left'}: "
      f"text {tw:.0f}px, cell at x={cx:.0f} of {W}px")

im.save(OUT)
print(f"wrote {OUT}  {im.size}")
