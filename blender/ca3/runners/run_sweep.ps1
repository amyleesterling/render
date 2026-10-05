# The arc sweep, in three passes, because the readout is composited rather than
# drawn in Blender: a text object whose string changes per frame needs a
# frame_change handler, and handlers during a headless animation render are a
# known way to lose a whole run. PNG sequence, composite, encode.
$b = "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
$py = "D:\Meshes\.venv\Scripts\python.exe"
$dir = "D:\Meshes\renders\sweep_frames"
$frames = 300
Set-Location D:\Meshes

if (Test-Path $dir) { Remove-Item "$dir\*.png" -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Force $dir | Out-Null

Write-Output "=== pass 1: render $frames frames ==="
$t0 = Get-Date
& $b --background --python D:\Meshes\gradient_sweep.py -- `
    "frames=$frames" "res=1920x1080" "samples=64" "png=1" "out=$dir\f_" |
  Select-String -Pattern 'keyframed|frames in|Error|Traceback' | Select-Object -Last 3
$n = (Get-ChildItem "$dir\*.png" -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Output "wrote $n frames in $([math]::Round(((Get-Date)-$t0).TotalMinutes,1)) min"
if ($n -lt $frames) { Write-Output "ABORT: expected $frames frames, got $n"; exit 1 }

Write-Output "=== pass 2: composite the readout ==="
& $py D:\Meshes\sweep_readout.py $dir "frames=$frames" | Select-Object -Last 2

Write-Output "=== pass 3: encode ==="
$out = "D:\Meshes\renders\gradient_sweep.mp4"
$web = "D:\Meshes\renders\gradient_sweep_web.mp4"
ffmpeg -y -v error -framerate 24 -i "$dir\f_%04d.png" `
       -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -movflags +faststart -an $out
ffmpeg -y -v error -i $out -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p `
       -movflags +faststart -an $web
foreach ($f in @($out, $web)) {
  if (Test-Path $f) { Write-Output ("{0}: {1:N1} MB" -f (Split-Path $f -Leaf), ((Get-Item $f).Length/1MB)) }
  else { Write-Output "FAILED: $f" }
}
Write-Output "SWEEP DONE"
