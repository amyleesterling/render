"""Build the EPG manifest and verify it against the pixels that were actually rendered.

A manifest that merely restates what the render script intended is worth little, so
each cell's declared colour is checked against the hue of its own rendered master.
If a cell were assigned the wrong colour, or the masters and the manifest drifted
apart, that check fails.

  python epg_manifest.py
"""
import ast
import glob
import json
import os
import colorsys

import numpy as np
from PIL import Image

RENDER_SCRIPT = "D:/Meshes/epg_ring_poster.py"
ANGLES = "D:/Meshes/banc/epg_angles.json"
SECTORS = "D:/Meshes/banc/epg_sectors.json"
CELLS = "D:/Meshes/renders/epg/cells"
OUT = "D:/Meshes/renders/epg/epg-manifest.json"
EXCLUDED = "720575940637920582"

# Parse the palette out of the render script rather than keeping a second copy,
# so the manifest cannot silently disagree with what was rendered.
src = open(RENDER_SCRIPT, encoding="utf-8").read()
start = src.index("PALETTE_STOPS = [")
stops = ast.literal_eval(src[src.index("[", start):src.index("]", start) + 1])
print(f"palette: {len(stops)} stops parsed from {os.path.basename(RENDER_SCRIPT)}")


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def palette_rgb(t):
    t %= 360
    for i in range(len(stops) - 1):
        a, ca = stops[i]
        b, cb = stops[i + 1]
        if a <= t <= b:
            f = (t - a) / (b - a) if b > a else 0.0
            ra, rb = hex_rgb(ca), hex_rgb(cb)
            return tuple(ra[k] + (rb[k] - ra[k]) * f for k in range(3))
    return hex_rgb(stops[0][1])


ang = {c["id"]: c["angle"] for c in json.load(open(ANGLES))["cells"]}
sec = json.load(open(SECTORS)) if os.path.exists(SECTORS) else {}

rows, checked, bad = [], 0, []
for p in sorted(glob.glob(os.path.join(CELLS, "epg-cell-*.png"))):
    sid = os.path.basename(p)[len("epg-cell-"):-len(".png")]
    t = (ang[sid] - 90.0) % 360.0
    rgb = palette_rgb(t)
    hexcol = "#%02X%02X%02X" % tuple(int(round(c * 255)) for c in rgb)
    want_h = colorsys.rgb_to_hsv(*rgb)[0] * 360

    # Verify against the render: take the median hue of that cell's own solid pixels.
    a = np.asarray(Image.open(p).convert("RGBA")).astype(float)
    solid = a[..., 3] > 240
    got_h = None
    if solid.sum() > 200:
        px = a[..., :3][solid] / 255.0
        mx, mn = px.max(1), px.min(1)
        keep = (mx - mn) > 0.05            # ignore near-white specular pixels
        if keep.sum() > 100:
            hs = np.array([colorsys.rgb_to_hsv(*q)[0] * 360 for q in px[keep][::17]])
            got_h = float(np.median(hs))
            d = abs(((got_h - want_h + 180) % 360) - 180)
            checked += 1
            if d > 25:
                bad.append((sid, want_h, got_h, d))

    rows.append({
        "segment_id": sid,
        "angle_deg_from_right": round(ang[sid], 2),
        "angle_deg_ccw_from_top": round(t, 2),
        "sector": sec.get(sid, {}).get("sector", int(t // 22.5) % 16),
        "color": hexcol,
        "hue_deg": round(want_h, 1),
        "rendered_hue_deg": round(got_h, 1) if got_h is not None else None,
        "master": f"cells/epg-cell-{sid}.png",
    })

rows.sort(key=lambda r: r["angle_deg_ccw_from_top"])
print(f"colour check: {checked} cells compared against their own render, {len(bad)} off by >25 deg")
for sid, w, g, d in bad:
    print(f"  MISMATCH {sid} declared {w:.0f} rendered {g:.0f} (off {d:.0f})")

by_sector = {}
for r in rows:
    by_sector.setdefault(r["sector"], []).append(r["segment_id"])

manifest = {
    "name": "EPG compass neurons, ellipsoid body",
    "cells": len(rows),
    "resolution": [1600, 1200],
    "alpha": "straight, no black matte; transparent background; full canvas preserved",
    "denoising": "disabled, so nothing is filtered across the alpha boundary",
    "camera": {
        "shared": True,
        "note": "One camera solved from the 53-cell set and locked. Every master, the "
                "base and all 16 heading overlays use it, so they are pixel aligned.",
        "file": "D:/Meshes/banc/epg_camera.json",
    },
    "dataset": {
        "name": "FAFB / FlyWire",
        "datastack": "flywire_fafb_production",
        "source": "local meshparty export, C:/Users/amyle/meshparty/EPG (*-meshlab.obj, welded)",
        "materialization_version": None,
        "version_note": "NOT RECORDED in the local export, and deliberately not guessed. "
                        "Materialization versions visible on the datastack at build time "
                        "were [258, 630, 783, 1238]. Currency of these root ids could not "
                        "be confirmed: the chunkedgraph returned 503 during the build. "
                        "Re-run the check before publishing if the version matters.",
        "units": "mesh vertices in nanometres; render world units are micrometres",
    },
    "excluded": {
        "segment_id": EXCLUDED,
        "reason": "Not an EPG. 651k vertices against ~140k typical, with 41% of its mass "
                  "in a separate arbor down and left of the ellipsoid body. Reads as a "
                  "segmentation merge, and confirmed unwanted.",
    },
    "colour_scheme": {
        "basis": "angular position around the ellipsoid body",
        "note": "EPGs tile the EB, and these 53 spread over the full 360 degrees, so hue "
                "runs around the ring. Stops are interpolated in sRGB, not HSV, because a "
                "hue sweep detours through yellow-green between gold and teal.",
        "stops": [{"t_deg_ccw_from_top": a, "color": c} for a, c in stops],
    },
    "headings": {
        "count": 16,
        "sector_width_deg": 22.5,
        "convention": "sector = floor(t / 22.5) where t is degrees counter-clockwise from "
                      "the TOP of the ring; heading 00 is centred at 12 o'clock",
        "bump_weights": {"centre": 1.0, "neighbour": 0.45, "next_neighbour": 0.15},
        "applied_as": "colour lerp from the dim base colour to the full palette colour, "
                      "with lit cells kept opaque. Mesh alpha was not used: overlapping "
                      "front and back walls of the same tube would compound 0.45 into "
                      "about 0.70 and occlusion between neighbours would be lost.",
        "files": [f"epg-heading-{k:02d}.webp" for k in range(16)],
    },
    "base": {"file": "epg-base.webp", "note": "all 53 cells, dim and desaturated"},
    "sectors": {str(k): by_sector.get(k, []) for k in range(16)},
    "cells_detail": rows,
}
json.dump(manifest, open(OUT, "w"), indent=1)
print(f"\nwrote {OUT}")
print(f"  {len(rows)} cells across {len([k for k in range(16) if by_sector.get(k)])} of 16 sectors")
counts = [len(by_sector.get(k, [])) for k in range(16)]
print(f"  cells per sector: {counts}  (min {min(counts)}, max {max(counts)})")
