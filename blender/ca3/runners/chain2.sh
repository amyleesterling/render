#!/bin/bash
# Fire the MICrONS render when decimation finishes OR at 07:35, whichever first.
# Decimation is I/O bound and projects past the deadline; 25 to 30 cells spanning
# the full depth is a good render, and a late perfect one is worth nothing.
DEADLINE=$(date -d "07:35" +%s 2>/dev/null || echo 0)
while true; do
  grep -q "\[dec\] DONE" /d/Meshes/microns_dec.log 2>/dev/null && { echo "decimation complete"; break; }
  now=$(date +%s)
  if [ "$DEADLINE" -gt 0 ] && [ "$now" -ge "$DEADLINE" ]; then echo "deadline reached, rendering with what is ready"; break; fi
  sleep 45
done
n=$(ls /d/Meshes/microns/*.obj 2>/dev/null | wc -l)
echo "=== rendering $n cells at $(date +%H:%M) ==="
cd /d/Meshes
"/c/Program Files/Blender Foundation/Blender 4.4/blender.exe" --background --python microns_column.py -- \
  res=3840x2160 samples=112 camdist=1.35 view=side \
  out="D:/Meshes/renders/microns_column.png" 2>&1 | grep -E "^\[mic\]|Traceback|Error|SystemExit"
echo "=== microns done $(date +%H:%M) ==="
