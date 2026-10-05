"""Label the BANC descending neuron film, so it says what it is showing.

Amy, 3 August 2026: "we also need labels on this animation, it's unclear what it
is supposed to show."

The shot's argument is the ORDER OF ARRIVAL: one descending neuron is established
alone in the brain, its axon is followed down the neck connective, and then each
body part it reaches fades up in anatomical order. Without labels that reads as
coloured shapes appearing, and the argument is lost.

So the labels arrive WITH their group and stay: by the end the panel is a list of
everywhere one cell reaches, which is the point of the film.

TIMINGS COME FROM THE RENDER. banc_shotB_anim.py writes shotB_beats.json as it
builds the fades, and this reads it. A second copy of the schedule would drift the
moment either was edited, and a label that names a group before it appears is worse
than no label at all.

  python banc_shotB_overlay.py --frames DIR --out DIR
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

AP = argparse.ArgumentParser()
# NO DEFAULT for --frames. It used to default to banc_shotB_frames, which is the
# v2 sequence; when the retimed v3 render wrote to banc_shotB_v3_frames instead, a
# manual run of this script silently labelled the OLD frames and produced a film
# that looked finished and carried none of the fixes. A stale default is worse
# than a missing one, because it fails quietly. The render passes this explicitly.
AP.add_argument("--frames", required=True)
AP.add_argument("--out", required=True)
AP.add_argument("--beats", default=r"D:\Meshes\renders\shotB_beats.json")
A = AP.parse_args()
os.makedirs(A.out, exist_ok=True)

INK = (239, 244, 251)
DIM = (154, 162, 177)
LINE = (196, 228, 255)
PANEL = (15, 18, 24)

NAME = {"neck": "neck", "t1": "front leg", "wing": "wing",
        "t2": "middle leg", "t3": "hind leg", "other": "elsewhere"}
SEG = {"t1": "T1", "t2": "T2", "t3": "T3"}

B = json.load(open(A.beats, encoding="utf-8"))
TOTAL = B["frames"]
ORDER = [r for r in ("neck", "t1", "wing", "t2", "t3", "other") if r in B["groups"]]
print(f"[ov] {TOTAL} frames, {len(ORDER)} groups from {A.beats}")


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def font(sz, bold=False):
    for n in (("seguisb.ttf", "segoeuib.ttf") if bold else ("segoeui.ttf",)):
        try:
            return ImageFont.truetype(n, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def brackets(d, x, y, w, h, col, ln=14, wd=1):
    for (cx, cy, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1),
                             (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        d.line([cx, cy, cx + dx * ln, cy], fill=col, width=wd)
        d.line([cx, cy, cx, cy + dy * ln], fill=col, width=wd)


files = sorted(f for f in os.listdir(A.frames) if f.endswith(".png"))
print(f"[ov] {len(files)} frames on disk", flush=True)

# ---- when is each group ACTUALLY on screen? -----------------------------------
# Measured from the rendered frames, not derived from the fade schedule.
#
# Two earlier attempts got this wrong from opposite ends. Labelling on fade START
# put the label 2.2 to 2.8 seconds ahead of its cells, because a fade begins at
# alpha zero and the cells inside a group are staggered. Labelling on fade END was
# better but still led by up to 17 frames, because "fully opaque" is not the same
# as "large enough on screen to notice", and how long that takes depends on where
# the camera is and how big the group is in frame.
#
# Both of those are guesses about rendering from outside the render. The frames
# are right here, so the honest thing is to look: scan for each group's own colour
# and take the first frame where enough of it is present to read. That number
# re-derives itself if the beats, the camera or the cast ever change.
import numpy as np


def _hex(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def _count(fr, tgt):
    im = Image.open(os.path.join(A.frames, files[fr - 1])).convert("RGB")
    a = np.asarray(im.resize((im.width // 4, im.height // 4))).astype(float)
    # close to the group's hue AND bright enough to actually register
    return int(((np.abs(a - tgt).sum(2) < 90) & (a.max(2) > 45)).sum())


def first_visible(role, g, stride=2):
    """First frame where this group is genuinely on screen, against a control.

    THE BASELINE IS THE CONTROL, and it is the whole point. A fixed pixel
    threshold is not safe: other groups already on screen contribute pixels that
    fall inside this group's colour tolerance. Measured on t3, 67 to 74 pixels
    matched its magenta at frames 350 to 379, BEFORE t3 existed at all, which is
    above any sensible fixed threshold and made the detector fire on the first
    frame it looked at.

    So the baseline is sampled just before the fade begins, when the true count is
    zero by construction, and the group counts as visible only once it clears that
    contamination by a wide margin.
    """
    tgt = _hex(g["hex"])
    pre = [max(1, g["start"] - k) for k in (25, 18, 12, 6)]
    base = max(_count(fr, tgt) for fr in pre)
    need = max(60, base * 3 + 40)
    hi = min(len(files), g["end"] + int((g["end"] - g["start"]) * 1.5) + 60)
    for fr in range(max(1, g["start"]), hi + 1, stride):
        if _count(fr, tgt) >= need:
            return fr, base, need
    return g["end"], base, need          # never cleared: fall back to full opacity


SHOW_AT = {}
for r in ORDER:
    if r == "other":
        continue
    g = B["groups"][r]
    SHOW_AT[r], base, need = first_visible(r, g)
    print(f"[ov]   {r:<6} fade {g['start']}-{g['end']}  baseline {base:>4} px, "
          f"needs {need:>4}  ->  visible at {SHOW_AT[r]} "
          f"(+{SHOW_AT[r] - g['start']} frames)", flush=True)

for i, fn in enumerate(files, 1):
    fr = int(fn[1:6])
    im = Image.open(os.path.join(A.frames, fn)).convert("RGBA")
    W, H = im.size
    S = W / 1080.0                      # this shot is portrait 1080x1920
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f_eye = font(int(17 * S), True)
    f_ttl = font(int(30 * S), True)
    f_lab = font(int(21 * S))
    f_sub = font(int(16 * S))

    # ---- title, top left. The one thing true for the whole run. --------------
    pad = int(22 * S)
    T1 = "BANC  ·  BRAIN AND NERVE CORD"
    T2 = "One descending neuron"
    T3 = "and everywhere it reaches"
    tw = max(d.textlength(T1, font=f_eye), d.textlength(T2, font=f_ttl),
             d.textlength(T3, font=f_lab))
    pw = int(tw + 2 * pad)
    x0, y0 = int(48 * S), int(48 * S)
    ph = int(120 * S)
    d.rectangle([x0, y0, x0 + pw, y0 + ph], fill=PANEL + (170,))
    brackets(d, x0, y0, pw, ph, LINE + (150,))
    d.text((x0 + pad, y0 + int(14 * S)), T1, font=f_eye, fill=DIM)
    d.text((x0 + pad, y0 + int(42 * S)), T2, font=f_ttl, fill=INK)
    d.text((x0 + pad, y0 + int(82 * S)), T3, font=f_lab, fill=DIM)

    # ---- the list, lower left. Each group joins when it starts to fade. ------
    # A group is listed once its fade COMPLETES, not when it begins.
    #
    # The first version listed on `start`, reasoning that the label and the colour
    # would arrive together. That was wrong: a fade begins at alpha zero, and the
    # cells within a group are staggered across the window, so nothing is on
    # screen for a long time after the fade starts. Measured against the rendered
    # frames, the labels led their cells by 2.2 to 2.8 seconds on four of five
    # groups, which reads as the panel announcing things that are not there.
    #
    # SHOW_AT is measured from the frames themselves, above.
    arrived = [r for r in ORDER if r != "other" and fr >= SHOW_AT[r]]
    reached = sum(B["groups"][r]["n"] for r in arrived)
    rows = [("descending neuron", "1", B["dn_hex"])]
    for r in arrived:
        nm = NAME[r] + (f"  {SEG[r]}" if r in SEG else "")
        rows.append((nm, str(B["groups"][r]["n"]), B["groups"][r]["hex"]))

    sw = int(17 * S)
    gap = int(13 * S)
    row_h = int(36 * S)
    HEAD = "PARTNERS BY BODY PART"
    w_nm = max(d.textlength(t[0], font=f_lab) for t in rows)
    w_ct = max(d.textlength(t[1], font=f_lab) for t in rows)
    inner = max(d.textlength(HEAD, font=f_eye), sw + gap + w_nm + gap * 2 + w_ct)
    lw = int(inner + 2 * pad)
    lh = int(row_h * len(rows) + int(58 * S))
    lx = int(48 * S)
    ly = H - lh - int(60 * S)
    d.rectangle([lx, ly, lx + lw, ly + lh], fill=PANEL + (170,))
    brackets(d, lx, ly, lw, lh, LINE + (150,))
    d.text((lx + pad, ly + int(16 * S)), HEAD, font=f_eye, fill=DIM)
    yy = ly + int(48 * S)
    for nm, ct, hx in rows:
        d.rectangle([lx + pad, yy + int(5 * S), lx + pad + sw, yy + int(5 * S) + sw],
                    fill=hexrgb(hx) + (255,))
        d.text((lx + pad + sw + gap, yy), nm, font=f_lab, fill=INK)
        d.text((lx + pad + sw + gap + w_nm + gap * 2, yy), ct, font=f_lab, fill=DIM)
        yy += row_h

    # ---- running total, under the title -------------------------------------
    if reached:
        cap = f"{reached} partner cells so far"
        d.text((x0, y0 + ph + int(18 * S)), cap, font=f_sub, fill=DIM)

    # ---- the honest note, held on the final pull back ------------------------
    if fr >= int(TOTAL * 0.80):
        note = "One cell. Five body parts. The order is anatomical, not temporal."
        nw = d.textlength(note, font=f_sub)
        d.text(((W - nw) / 2, H - int(30 * S)), note, font=f_sub, fill=DIM)

    Image.alpha_composite(im, ov).convert("RGB").save(os.path.join(A.out, fn))
    if i % 60 == 0 or i == len(files):
        print(f"[ov] {i}/{len(files)}", flush=True)
print("[ov] DONE", flush=True)
