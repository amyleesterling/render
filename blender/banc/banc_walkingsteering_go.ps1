<#
The "Go" button for the BANC walking+steering poster.

Everything before the render is already done and is CPU/network only. This script
runs the remaining steps in order and stops at the first failure.

Decimation runs at BelowNormal priority on purpose: there is one GPU on this
machine and usually another session's animation on it, and the CPU-side mesh work
is the only part of this job that could steal time from it.

  .\banc_walkingsteering_go.ps1 -DryRun     # build the scene, render nothing
  .\banc_walkingsteering_go.ps1 -Test       # 400x300 test frame to LOOK at first
  .\banc_walkingsteering_go.ps1             # decimate if needed, full 1600x1200, webp
  .\banc_walkingsteering_go.ps1 -Device CPU # stay off the GPU entirely
#>
param(
  [switch]$DryRun,
  [switch]$Test,
  [switch]$Layers,          # render every layer in walking_steering_layers.json, then encode
  [string]$Only,            # just one layer, e.g. -Only turn-left
  [string]$Device = "GPU",
  [int]$Samples = 256
)

$ErrorActionPreference = "Stop"
$py = "D:\Meshes\.venv\Scripts\python.exe"
$blender = "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
$dec = "D:\Meshes\banc\walking_steering_dec"

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# Who else is on the GPU right now. Not fatal, but say it out loud.
Step "GPU check"
$busy = Get-Process blender -ErrorAction SilentlyContinue
if ($busy) {
  foreach ($b in $busy) { Write-Host ("  blender PID {0} running since {1}" -f $b.Id, $b.StartTime) -ForegroundColor Yellow }
  if ($Device -eq "GPU" -and -not $DryRun) {
    Write-Host "  another render holds the GPU. Ctrl-C now, or pass -Device CPU." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
  }
} else { Write-Host "  GPU is free" -ForegroundColor Green }

Step "Decimate (CPU, BelowNormal priority)"
$n = if (Test-Path $dec) { (Get-ChildItem $dec -Filter *.obj -ErrorAction SilentlyContinue).Count } else { 0 }
if ($n -ge 81) {
  Write-Host "  $n decimated meshes already present, skipping"
} else {
  $p = Start-Process -FilePath $py -ArgumentList "D:\Meshes\banc_walkingsteering_decimate.py" `
       -NoNewWindow -PassThru
  $p.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
  $p.WaitForExit()
  if ($p.ExitCode -ne 0) { throw "decimation failed with exit code $($p.ExitCode)" }
}

# Adding an action layer means one entry in walking_steering_layers.json and this.
if ($Layers -or $Only) {
  $cfg = Get-Content "D:\Meshes\banc\walking_steering_layers.json" | ConvertFrom-Json
  $names = if ($Only) { @($Only) } else { $cfg.layers.PSObject.Properties.Name }
  foreach ($n in $names) {
    if (-not $cfg.layers.PSObject.Properties.Name.Contains($n)) { throw "no layer '$n' in walking_steering_layers.json" }
    Step "Render layer $n"
    & $blender --background --python "D:\Meshes\banc_walkingsteering_poster.py" -- "layer=$n" "samples=$Samples" "device=$Device"
    if ($LASTEXITCODE -ne 0) { throw "blender exited $LASTEXITCODE on layer $n" }
  }
  Step "Encode layers and check alignment"
  & $py "D:\Meshes\banc_walkingsteering_layers_webp.py"
  if ($LASTEXITCODE -ne 0) { throw "layer encode or alignment check failed" }
  Write-Host "`nDone." -ForegroundColor Green
  exit 0
}

Step "Render"
$blenderArgs = @("--background", "--python", "D:\Meshes\banc_walkingsteering_poster.py", "--")
if ($DryRun) { $blenderArgs += "dryrun" }
elseif ($Test) { $blenderArgs += "test" }
else { $blenderArgs += "samples=$Samples" }
$blenderArgs += "device=$Device"
& $blender @blenderArgs
if ($LASTEXITCODE -ne 0) { throw "blender exited $LASTEXITCODE" }

if ($DryRun) { Write-Host "`nDry run only, nothing rendered." -ForegroundColor Green; exit 0 }
if ($Test) {
  Write-Host "`nTest frame written. LOOK AT IT before running the full render." -ForegroundColor Yellow
  exit 0
}

Step "Encode to WebP and audit the alpha"
& $py "D:\Meshes\banc_walkingsteering_webp.py"
if ($LASTEXITCODE -ne 0) { throw "webp encode failed" }

Write-Host "`nDone." -ForegroundColor Green
