#!/usr/bin/env python3
"""Lay the overlay on the plate: the patch film in post.

    python3 eyewire2/compose.py PLATE.mp4 OVERLAY.mov OUT.mp4

PLATE is the cells alone (col3d.html?layer=plate), rendered once. OVERLAY is every
word, fade and the closing award on a transparent background (?layer=overlay,
captured with ALPHA=1), which takes minutes. Changing a caption means editing
captions.json, re-capturing the overlay and running this; the plate stays.

The plate stops where the cells freeze (finale.at in captions.json); its last frame
is held for as long as the overlay runs.

The award blurs whatever is behind it (a CSS backdrop-filter). In the overlay pass
there is nothing behind it, so the blur is made here from the plate: blurred 8 px
and saturated 1.5x like the CSS, faded in over the overlay's own 0.3 s from the
award's time in captions.json.
"""
import json, os, subprocess, sys
import imageio_ffmpeg

plate, overlay, out = sys.argv[1:4]
here = os.path.dirname(os.path.abspath(__file__))
at = json.load(open(os.path.join(here, "captions.json")))["award"]["at"]
ff = os.environ.get("FFMPEG") or imageio_ffmpeg.get_ffmpeg_exe()
graph = (
    "[0:v]tpad=stop_mode=clone:stop_duration=60,split=2[p][pb];"
    f"[pb]gblur=sigma=8,eq=saturation=1.5,format=yuva420p,fade=t=in:st={at:.3f}:d=0.3:alpha=1[blur];"
    "[p][blur]overlay=format=auto[pp];"
    "[pp][1:v]overlay=format=auto:shortest=1,format=yuv420p[v]"
)
subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", plate, "-i", overlay,
                "-filter_complex", graph, "-map", "[v]", "-c:v", "libx264", "-preset", "slow",
                "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-r", "30", out],
               check=True)
print("wrote", out)
