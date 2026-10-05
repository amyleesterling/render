# Dial in the vertical framing empirically. Cheap now that geometry comes from
# the .blend rather than 13 GB of OBJ. Renders one frame per candidate and tiles
# them so the options can be compared side by side.

$blender = "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
$script  = "D:\Meshes\render_from_cache.py"
$out     = "D:\Meshes\renders\framing"
New-Item -ItemType Directory -Force -Path $out | Out-Null

# shift_y is negative to lift the subject up the frame; camdist pulls it closer
$cases = @(
  @{ n = "a_sh18_d30"; sh = "-0.18"; d = "3.0" },
  @{ n = "b_sh24_d28"; sh = "-0.24"; d = "2.8" },
  @{ n = "c_sh30_d26"; sh = "-0.30"; d = "2.6" },
  @{ n = "d_sh36_d24"; sh = "-0.36"; d = "2.4" }
)

foreach ($c in $cases) {
  $png = Join-Path $out "$($c.n).png"
  & $blender --background --python $script -- `
      "still=470" "frames=480" "res=1080x1920" "samples=48" `
      "turns=0.2" "start=-36" "camdist=$($c.d)" "shifty=$($c.sh)" `
      "reveal=1" "synapses=0" "out=$png" 2>&1 |
    Select-String -Pattern "opened|still frame|rendered in" | ForEach-Object { "$($c.n): $_" }
}

& ffmpeg -y -v error -i "$out\a_sh18_d30.png" -i "$out\b_sh24_d28.png" `
  -i "$out\c_sh30_d26.png" -i "$out\d_sh36_d24.png" `
  -filter_complex "[0]scale=440:-1[a];[1]scale=440:-1[b];[2]scale=440:-1[c];[3]scale=440:-1[d];[a][b][c][d]hstack=inputs=4" `
  "$out\compare.png"
Write-Output "=== framing sweep done ==="
