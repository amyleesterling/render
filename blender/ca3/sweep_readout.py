"""
Composite the live readout onto the gradient sweep frames.

  python sweep_readout.py FRAMEDIR [frames=300] [band=90] [test=150]

Reads the SAME CSV the render read, and recomputes the median input count inside
the same band, from the same arc positions, with the same deep slab cut. The number
on screen therefore cannot drift away from the cells lit underneath it, which is
the only reason this shot is worth more than a caption.

  test=N   composite frame N only and write _sweep_readout_test.png, for eyeballing

The readout is drawn in the site's own HUD idiom: hairline rail, tick marks, small
uppercase label, tabular figures. The marker rides the rail at the band's true
position along the arc, so the graph and the render are the same measurement.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

args = [a for a in sys.argv[1:] if "=" not in a]
opts = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)

FRAMEDIR = Path(args[0]) if args else Path(r"D:\Meshes\renders\sweep_frames")
CSV = Path(r"D:\Meshes\renders\gradient_sample.csv")
GRAD = Path(r"D:\Meshes\gradient")
Z_MIN_UM = 60.0
FRAMES = int(opts.get("frames", 300))
BAND = float(opts.get("band", 90.0))

INK = (214, 232, 252)
DIM_INK = (120, 152, 190)
ACCENT = (255, 194, 74)
RAIL = (86, 122, 168)


def read_sample():
    rows = CSV.read_text(encoding="utf-8").strip().splitlines()
    head = rows[0].split(",")
    i_id, i_n = head.index("root_id"), head.index("n_mf")
    i_z, i_arc = head.index("soma_z_nm"), head.index("arc_um")
    n, arc = [], []
    for r in rows[1:]:
        f = r.split(",")
        if float(f[i_z]) / 1000.0 < Z_MIN_UM:
            continue
        if not (GRAD / f"{f[i_id]}.obj").exists():
            continue
        n.append(int(float(f[i_n])))
        arc.append(float(f[i_arc]))
    return np.array(n), np.array(arc)


N, ARC = read_sample()
ARC_LO, ARC_HI = float(ARC.min()), float(ARC.max())
SWEEP_LO, SWEEP_HI = ARC_LO - BAND, ARC_HI + BAND


def band_centre(frame):
    u = (frame - 1) / max(1, FRAMES - 1)
    return SWEEP_LO + u * (SWEEP_HI - SWEEP_LO)


def stats_at(centre):
    """median, count and p90 of input count for cells inside the band."""
    m = np.abs(ARC - centre) <= BAND
    if not m.any():
        return None, 0, None
    v = N[m]
    return float(np.median(v)), int(m.sum()), float(np.percentile(v, 90))


def font(px, bold=False):
    for name in (("seguisb.ttf", "segoeuib.ttf") if bold else ("segoeui.ttf",)) + \
                ("consola.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


# Precompute the median curve once, so the plotted line is the whole result and the
# marker just travels along it. This is what makes the shot an argument rather than
# a light show: the viewer sees where the current position sits on the full curve.
MIN_IN_BAND = 15
_cx, _cy = [], []
for _x in np.linspace(ARC_LO, ARC_HI, 240):
    _m, _n, _ = stats_at(_x)
    # Plot only where the band actually holds cells. Without this the curve
    # collapsed to zero at the far end, where the sample thins out, which reads as
    # "these cells receive no input" when it means "no cells were sampled here".
    # A graph must never draw an absence as a measurement.
    if _m is not None and _n >= MIN_IN_BAND:
        _cx.append(_x)
        _cy.append(_m)
CURVE_X, CURVE_Y = np.array(_cx), np.array(_cy)
if len(CURVE_X) < 2:
    raise SystemExit("Not enough cells anywhere along the arc to plot a curve.")
PLOT_LO, PLOT_HI = float(CURVE_X.min()), float(CURVE_X.max())


def draw(img, frame):
    w, h = img.size
    d = ImageDraw.Draw(img, "RGBA")
    s = w / 1920.0                      # every size below is authored at 1920 wide
    centre = band_centre(frame)
    med, cnt, p90 = stats_at(centre)

    f_lab = font(int(15 * s))
    f_big = font(int(64 * s), bold=True)
    f_mid = font(int(19 * s))

    # ---- the curve, bottom left ------------------------------------------------
    gx, gy = int(70 * s), h - int(150 * s)
    gw, gh = int(560 * s), int(96 * s)
    ymax = max(CURVE_Y.max(), 1.0)

    d.line([(gx, gy + gh), (gx + gw, gy + gh)], fill=(*RAIL, 190), width=max(1, int(s)))
    for i in range(9):                  # ticks along the arc
        tx = gx + gw * i / 8
        d.line([(tx, gy + gh), (tx, gy + gh + int(6 * s))],
               fill=(*RAIL, 150), width=max(1, int(s)))

    pts = [(gx + gw * (x - PLOT_LO) / (PLOT_HI - PLOT_LO), gy + gh - gh * y / ymax)
           for x, y in zip(CURVE_X, CURVE_Y)]
    d.line(pts, fill=(*DIM_INK, 205), width=max(1, int(2 * s)), joint="curve")

    # the marker, at the band's true arc position
    if PLOT_LO <= centre <= PLOT_HI:
        mx = gx + gw * (centre - PLOT_LO) / (PLOT_HI - PLOT_LO)
        my = gy + gh - gh * (med or 0.0) / ymax
        d.line([(mx, gy), (mx, gy + gh)], fill=(*ACCENT, 130), width=max(1, int(s)))
        r = max(2, int(4.5 * s))
        d.ellipse([mx - r, my - r, mx + r, my + r], fill=(*ACCENT, 255))

    d.text((gx, gy - int(24 * s)), "MEDIAN MOSSY FIBER INPUTS ALONG THE CELL LAYER",
           font=f_lab, fill=(*DIM_INK, 235))
    d.text((gx, gy + gh + int(12 * s)), "0", font=f_lab, fill=(*DIM_INK, 200))
    end = f"{PLOT_HI:.0f} µm"
    tw = d.textlength(end, font=f_lab)
    d.text((gx + gw - tw, gy + gh + int(12 * s)), end, font=f_lab,
           fill=(*DIM_INK, 200))

    # ---- the live figure, bottom right -----------------------------------------
    rx, ry = w - int(70 * s), h - int(150 * s)
    if med is None:
        return img
    val = f"{med:.0f}"
    vw = d.textlength(val, font=f_big)
    d.text((rx - vw, ry - int(16 * s)), val, font=f_big, fill=(*INK, 255))
    lab = "MEDIAN INPUTS"
    lw = d.textlength(lab, font=f_lab)
    d.text((rx - lw, ry - int(40 * s)), lab, font=f_lab, fill=(*DIM_INK, 235))
    sub = f"{cnt} cells in band  \u00b7  p90 {p90:.0f}  \u00b7  arc {centre:.0f} \u00b5m"
    sw = d.textlength(sub, font=f_mid)
    d.text((rx - sw, ry + int(56 * s)), sub, font=f_mid, fill=(*DIM_INK, 225))
    return img


if "test" in opts:
    f = int(opts["test"])
    src = Path(opts.get("src", r"D:\Meshes\renders\_sweep_dim.png"))
    img = Image.open(src).convert("RGB")
    out = Path(r"D:\Meshes\renders\_sweep_readout_test.png")
    draw(img, f).save(out)
    c = band_centre(f)
    m, n, p = stats_at(c)
    print(f"frame {f}: arc {c:.0f} um, {n} cells, median {m:.0f}, p90 {p:.0f}")
    print("wrote", out)
    raise SystemExit

frames = sorted(FRAMEDIR.glob("*.png"))
if not frames:
    raise SystemExit(f"No PNG frames in {FRAMEDIR}")
for i, p in enumerate(frames, start=1):
    img = Image.open(p).convert("RGB")
    draw(img, i).save(p)
    if i % 50 == 0:
        print(f"  composited {i}/{len(frames)}", flush=True)
print(f"composited {len(frames)} frames in {FRAMEDIR}")
