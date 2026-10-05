# Render every banc-explorer layer that is missing, static and pulse.
#
# These are 1600x1200 Cycles stills at 256 samples: about 5 seconds a frame, so a
# 14 frame pulse is roughly 70 seconds and the whole backlog is minutes, not hours.
# I had confused their cost with the 576 frame shotB animation, which is the 90
# minute job. They are not the same kind of work and should never have been
# waiting on the same queue slot.
#
# Static first, then the pulse sequence, per layer, so a layer is either complete
# or visibly absent rather than half done.

$ErrorActionPreference = 'Continue'
$B = "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
$SCRIPT = "D:\Meshes\banc_walkingsteering_poster.py"
$L = "D:\Meshes\renders\layers"
New-Item -ItemType Directory -Force -Path $L | Out-Null

# no static yet: these need both
$NEED_BOTH = @(
  'flight-power-dng02','flight-steer-mnb1-all','flight-steer-mnb1-anatomical-left',
  'flight-steer-mnb1-anatomical-right','landing-dnp07-dnp10','landing-dnp07','landing-dnp10'
)
# static exists, pulse does not. context-base is deliberately excluded: it is the
# always-visible backdrop the other layers composite over, so a pulse on it would
# animate the context rather than the cells being explained.
$NEED_PULSE = @(
  'forward','backward','turn-left','turn-right','eat','threat-walk',
  'flight-dodge-dnp03-all','flight-dodge-dnp03-anatomical-left',
  'flight-dodge-dnp03-anatomical-right'
)

$t0 = Get-Date
foreach ($n in $NEED_BOTH) {
  Write-Output "=== $n : static ==="
  & $B --background --python $SCRIPT -- "layer=$n" "out=$L\banc-$n.png" 2>&1 |
    Select-String -Pattern '^\[poster\] (imported|DONE|camera)|Error|Traceback'
}
foreach ($n in ($NEED_BOTH + $NEED_PULSE)) {
  Write-Output "=== $n : pulse ==="
  & $B --background --python $SCRIPT -- pulse "layer=$n" "out=$L\banc-$n-seq.png" 2>&1 |
    Select-String -Pattern '^\[pulse\] (Y |\d+ lit|wrote)|^\[poster\] DONE|Error|Traceback'
}
Write-Output ("`nall renders done in {0:N1} min" -f ((Get-Date) - $t0).TotalMinutes)
