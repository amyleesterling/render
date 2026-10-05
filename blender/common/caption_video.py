"""
Burn timed captions onto a rendered sequence, in the house HUD idiom.

  python caption_video.py SPEC.json [crf=23]

Captions are composited after rendering rather than built in Blender, which is
how this project has always added labels: a text object whose string changes per
frame needs a frame_change handler, and handlers during a headless animation
render are a known way to lose a whole run.

SPEC is JSON:
  {"src": "...mp4", "out": "...mp4", "fps": 24,
   "cards": [{"in": 12, "out": 96, "eyebrow": "...", "title": "...",
              "body": "..."}]}

Frames are inclusive. Each card fades in and out over FADE frames so nothing
snaps, and cards are drawn bottom left where these shots keep their empty
corner. Every number in a card should be checkable against the data; nothing
here invents one.
"""
import json
import os
import subprocess
import sys
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont

spec_path = sys.argv[1]
opts = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
SPEC = json.load(open(spec_path, encoding="utf-8"))
SRC, OUT = SPEC["src"], SPEC["out"]
FPS = SPEC.get("fps", 24)
CRF = opts.get("crf", "23")
FADE = SPEC.get("fade", 8)

INK = (238, 244, 252)
DIM = (150, 178, 210)
ACCENT = (255, 194, 74)
RAIL = (96, 136, 186)

WORK = os.path.join(os.path.dirname(OUT), "_cap_frames")
if os.path.isdir(WORK):
    shutil.rmtree(WORK)
os.makedirs(WORK)


def font(px, bold=False):
    names = ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf") if bold else \
            ("segoeui.ttf", "arial.ttf")
    for nm in names:
        try:
            return ImageFont.truetype(nm, px)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap(d, text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


print(f"[cap] {SRC} -> {OUT}, {len(SPEC['cards'])} cards", flush=True)
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", SRC,
                os.path.join(WORK, "f_%04d.png")], check=True)
frames = sorted(os.listdir(WORK))
print(f"[cap] {len(frames)} frames extracted", flush=True)

for i, name in enumerate(frames, start=1):
    active = [c for c in SPEC["cards"] if c["in"] - FADE <= i <= c["out"] + FADE]
    if not active:
        continue
    p = os.path.join(WORK, name)
    im = Image.open(p).convert("RGB")
    W, H = im.size
    s = W / 1920.0
    for c in active:
        if i < c["in"]:
            a = (i - (c["in"] - FADE)) / FADE
        elif i > c["out"]:
            a = 1.0 - (i - c["out"]) / FADE
        else:
            a = 1.0
        a = float(np.clip(a, 0.0, 1.0))
        if a <= 0.01:
            continue
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        f_eye = font(int(15 * s))
        f_tit = font(int(38 * s), bold=True)
        f_bod = font(int(21 * s))
        x = int(78 * s)
        y = H - int(232 * s)
        col = int(760 * s)

        if c.get("eyebrow"):
            d.text((x, y), c["eyebrow"].upper(), font=f_eye,
                   fill=(*DIM, int(235 * a)))
            y += int(28 * s)
        # a hairline that draws itself as the card arrives
        d.line([(x, y), (x + int(col * a), y)], fill=(*RAIL, int(200 * a)),
               width=max(1, int(1.5 * s)))
        y += int(20 * s)
        if c.get("title"):
            d.text((x, y), c["title"], font=f_tit, fill=(*INK, int(255 * a)))
            y += int(52 * s)
        for line in wrap(d, c.get("body", ""), f_bod, col):
            d.text((x, y), line, font=f_bod, fill=(*DIM, int(238 * a)))
            y += int(30 * s)
        im = Image.alpha_composite(im.convert("RGBA"), lay).convert("RGB")
    im.save(p)
    if i % 100 == 0:
        print(f"[cap]   {i}/{len(frames)}", flush=True)

subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
                "-i", os.path.join(WORK, "f_%04d.png"),
                "-c:v", "libx264", "-preset", "slow", "-crf", str(CRF),
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", OUT],
               check=True)
shutil.rmtree(WORK)
print(f"[cap] wrote {OUT} ({os.path.getsize(OUT)/1048576:.1f} MB)", flush=True)
