#!/bin/bash
# Render a film from col3d.html in resumable chunks, then join them.
#   eyewire2/render.sh 'col3d.html?meshes=meshes1000&layer=plate' OUTDIR/plate.mp4
#   ALPHA=1 eyewire2/render.sh 'col3d.html?meshes=meshes1000&layer=overlay' OUTDIR/overlay.mov
# A chunk that finished is kept, so after a restart the same command picks up
# where it stopped. Needs the site served on 127.0.0.1:8766 and FFMPEG set.
set -e
PAGE="$1"; OUT="$2"; CHUNK=${CHUNK:-240}
HERE="$(cd "$(dirname "$0")" && pwd)"
EXT="${OUT##*.}"; DIR="${OUT%.*}.chunks"; mkdir -p "$DIR"
# frames: the plate stops at the freeze, everything else runs to the end (see col3d.html)
TOTAL=${TOTAL:-$(python3 -c "
import json,sys; d=json.load(open('$HERE/captions.json'))
print(round(d['finale']['at']*30)+1 if 'layer=plate' in sys.argv[1] else round((d['award']['at']+8.0)*30))" "$PAGE")}
echo "rendering $TOTAL frames of $PAGE"
n=0
for ((from=0; from<TOTAL; from+=CHUNK)); do
  to=$((from+CHUNK)); [ $to -gt $TOTAL ] && to=$TOTAL
  part="$DIR/$(printf %04d $from).$EXT"
  if [ -f "$part.done" ]; then echo "chunk $from-$to already done"; else
    echo "chunk $from-$to start $(date -u +%H:%M)"
    FROM=$from TO=$to ANIM_URL="http://127.0.0.1:8766/eyewire2/$PAGE" node "$HERE/cap.js" full "$part.tmp.$EXT" 2>&1 | grep -v "left out" | grep -v "^\[page\]" || true
    mv "$part.tmp.$EXT" "$part"; touch "$part.done"
    echo "chunk $from-$to done $(date -u +%H:%M)"
  fi
  echo "file '$(basename "$part")'" >> "$DIR/list.tmp"; n=$((n+1))
done
mv "$DIR/list.tmp" "$DIR/list.txt"
"$FFMPEG" -hide_banner -loglevel error -y -f concat -safe 0 -i "$DIR/list.txt" -c copy "$OUT"
echo "joined $n chunks into $OUT"
