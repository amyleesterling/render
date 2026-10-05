# The three action potential cuts, then a web encode of each.
$b = "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
$py = "D:\Meshes\ap_test.py"
Set-Location D:\Meshes

$runs = @(
  @{ name = "ap_follow";  args = @("aim=follow",  "camdist=1.9",  "fstop=2.4") },
  @{ name = "ap_synapse"; args = @("aim=synapse", "camdist=0.95", "fstop=1.8") },
  @{ name = "ap_cell";    args = @("aim=cell",    "camdist=3.1",  "fstop=3.2") }
)

foreach ($r in $runs) {
  $out = "D:\Meshes\renders\$($r.name).mp4"
  Write-Output "=== $($r.name) ==="
  $a = @("--background", "--python", $py, "--",
         "frames=288", "res=1920x1080", "samples=64", "out=$out") + $r.args
  & $b @a 2>&1 | Select-String -Pattern 'frames in|Error|Traceback' | Select-Object -Last 2

  # faststart so it plays inline on an iPhone straight off GitHub Pages
  $web = "D:\Meshes\renders\$($r.name)_web.mp4"
  ffmpeg -y -v error -i $out -c:v libx264 -preset slow -crf 22 -pix_fmt yuv420p `
         -movflags +faststart -an $web
  $mb = "{0:N1}" -f ((Get-Item $web).Length / 1MB)
  Write-Output "$($r.name)_web.mp4  $mb MB"
}
Write-Output "ALL THREE DONE"
