# Two full-population frames, identical except for the palette variant.
# A: as keyed.  B: sparsely thorny (2) and presynaptic superficial (6) swapped.

$blender = "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
$script  = "D:\Meshes\render_still.py"
$groups  = @("CA3_deep","CA3_superficial","thorny_pyramidals","sparsely_thorny","inhibitory","mossy_fibers")

$runs = @(
  @{ name = "variantA_keyed";   swap = $null },
  @{ name = "variantB_swap2_6"; swap = "swapcolors=sparsely_thorny,CA3_superficial" }
)

foreach ($r in $runs) {
  $png = "D:\Meshes\renders\$($r.name).png"
  $log = "D:\Meshes\renders\$($r.name).txt"
  $args = @("--background","--python",$script,"--","235",$png,
            "zoom=1.0","res=2560x1440","samples=128")
  if ($r.swap) { $args += $r.swap }
  $args += $groups

  Write-Output "=== rendering $($r.name) ==="
  & $blender @args 2>&1 |
    Select-String -Pattern "total,|swapped colours|^\[render\]|^\[verify\]|Error|Traceback" |
    Out-File $log -Encoding utf8
  Get-Content $log
}
Write-Output "=== both variants done ==="
