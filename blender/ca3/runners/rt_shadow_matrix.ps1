# Controlled 2x2: does raytracing interact with shadows to explain the timing?
# One population only (CA3_deep, ~9.9M faces) so each cell of the matrix is quick.
# Scene build cost is identical across all four, so only the render time varies.

$blender = "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
$script  = "D:\Meshes\render_still.py"
$out     = "D:\Meshes\renders\matrix"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$cases = @(
  @{ name = "rt1_sh1"; rt = "1"; sh = "1" },
  @{ name = "rt0_sh1"; rt = "0"; sh = "1" },
  @{ name = "rt1_sh0"; rt = "1"; sh = "0" },
  @{ name = "rt0_sh0"; rt = "0"; sh = "0" }
)

foreach ($c in $cases) {
  $png = Join-Path $out ("$($c.name).png")
  $log = Join-Path $out ("$($c.name).txt")
  & $blender --background --python $script -- 235 $png `
      "zoom=2.6" "res=1280x720" "samples=192" `
      "rt=$($c.rt)" "shadows=$($c.sh)" CA3_deep 2>&1 |
    Select-String -Pattern "raytracing|rendered in|total," | Out-File $log -Encoding utf8
  $line = (Get-Content $log | Select-String "rendered in").Line
  Write-Output ("{0}  rt={1} shadows={2}  ->  {3}" -f $c.name, $c.rt, $c.sh, $line)
}
