"""Draw a colour key onto a BANC render.

No box around the labels and small type, per Amy's preferences. Swatch, name,
count. Counts are read from the real cast files so the key can never drift from
what was actually rendered.

  python banc_label.py <in.png> <out.png> [corner=bottomleft]
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = r"D:\Meshes\banc"
src = sys.argv[1]
dst = sys.argv[2]

bp = json.load(open(os.path.join(ROOT, "shotB_bodyparts.json")))
part = bp["part"]
n = lambda k: sum(1 for v in part.values() if v == k)

KEY = [("#FF7A2F", "descending neuron", 1),
       ("#E8A93A", "neck", n("neck")),
       ("#2E8BE0", "front leg  T1", n("t1")),
       ("#FF4FA3", "wing", n("wing")),
       ("#17A06B", "middle leg  T2", n("t2")),
       ("#B84DD8", "hind leg  T3", n("t3")),
       ("#46536B", "unlabelled", len(bp["unlabelled"]))]

im = Image.open(src).convert("RGB")
W, H = im.size
d = ImageDraw.Draw(im)

SC = W / 1080.0                       # so the key scales with the render
size = int(25 * SC)
lead = int(46 * SC)
sw = int(19 * SC)
# Top right by default: in this framing the animal hangs down the left and centre,
# so the upper right is the only quadrant that is reliably empty. Bottom left put
# the key straight on top of the hind leg population.
corner = dict(a.split("=", 1) for a in sys.argv[3:] if "=" in a).get("corner", "topright")
if corner == "topright":
    x = int(600 * SC)
    y = int(120 * SC)
else:
    x = int(56 * SC)
    y = H - int(60 * SC) - lead * len(KEY)


def font(sz, bold=False):
    for name in (("seguisb.ttf", "segoeuib.ttf") if bold else ("segoeui.ttf",)):
        try:
            return ImageFont.truetype(name, sz)
        except OSError:
            pass
    return ImageFont.load_default()


f_lab = font(size)
f_num = font(size, bold=True)

# Two short lines rather than one long one: at this type size a single line runs
# off the right edge of a 1080 wide frame.
f_ttl = font(int(21 * SC), bold=True)
title = ["ONE DESCENDING NEURON", f"{sum(n(k) for _, k, _ in [(0,'neck',0),(0,'t1',0),(0,'t2',0),(0,'t3',0),(0,'wing',0)]) + len(bp['unlabelled'])} MOTOR NEURONS"]
for j, line in enumerate(title):
    d.text((x, y - lead * (len(title) - j) - int(10 * SC)), line,
           font=f_ttl, fill=(150, 168, 196))
y += int(6 * SC)

for i, (hexc, name, cnt) in enumerate(KEY):
    yy = y + i * lead
    rgb = tuple(int(hexc[1:][j:j + 2], 16) for j in (0, 2, 4))
    d.rounded_rectangle([x, yy, x + sw, yy + sw], radius=int(3 * SC), fill=rgb)
    tx = x + sw + int(16 * SC)
    d.text((tx, yy - int(3 * SC)), f"{cnt}", font=f_num, fill=(235, 242, 250))
    wnum = d.textlength(f"{cnt}", font=f_num)
    d.text((tx + wnum + int(10 * SC), yy - int(3 * SC)), name, font=f_lab,
           fill=(154, 172, 196))

im.save(dst, quality=95)
print(f"[label] {dst}  ({W}x{H})")
for hexc, name, cnt in KEY:
    print(f"   {hexc}  {cnt:>3}  {name}")
