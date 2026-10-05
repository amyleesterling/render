#!/bin/bash
# wait for decimation, then render the column still
for i in $(seq 1 120); do
  if grep -q "\[dec\] DONE" /d/Meshes/microns_dec.log 2>/dev/null; then break; fi
  sleep 30
done
grep "\[dec\] DONE" /d/Meshes/microns_dec.log
echo "=== rendering microns column $(date +%H:%M) ==="
cd /d/Meshes
"/c/Program Files/Blender Foundation/Blender 4.4/blender.exe" --background --python microns_column.py -- \
  res=3840x2160 samples=128 camdist=1.35 view=side \
  out="D:/Meshes/renders/microns_column.png" 2>&1 | grep -E "^\[mic\]|Traceback|Error"
echo "=== done $(date +%H:%M) ==="
