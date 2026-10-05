#!/bin/bash
DEADLINE=$(date -d "07:45" +%s 2>/dev/null || echo 0)
while true; do
  grep -q "\[dec\] DONE" /d/Meshes/microns_dec2.log 2>/dev/null && { echo "decimation complete"; break; }
  now=$(date +%s); [ "$DEADLINE" -gt 0 ] && [ "$now" -ge "$DEADLINE" ] && { echo "deadline, rendering with what is ready"; break; }
  sleep 45
done
n=$(ls /d/Meshes/microns_hi/*.obj 2>/dev/null | wc -l)
echo "=== rendering $n cells at $(date +%H:%M) ==="
cd /d/Meshes
"/c/Program Files/Blender Foundation/Blender 4.4/blender.exe" --background --python microns_column.py -- \
  src="D:/Meshes/microns_hi" res=3840x2160 samples=112 camdist=1.35 view=side \
  out="D:/Meshes/renders/microns_column.png" 2>&1 | grep -E "^\[mic\]|Traceback|Error"
echo "=== microns done $(date +%H:%M) ==="
