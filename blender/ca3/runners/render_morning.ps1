# The two built shots, serially. Launched 05:30 against an 08:30 deadline.
# Ladder first: it is the longer and the more finished of the two, and if only
# one lands it should be that one.
$b = "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
Set-Location D:\Meshes

$jobs = @(
  @{ name = "scale_ladder"; py = "D:\Meshes\scale_ladder.py";  args = @("res=1920x1080", "samples=64") },
  @{ name = "inhibition";   py = "D:\Meshes\hero_full.py";     args = @("scope=inhibition", "res=1920x1080", "samples=64") }
)

foreach ($j in $jobs) {
  $out = "D:\Meshes\renders\$($j.name).mp4"
  Write-Output "=== $($j.name) === $(Get-Date -Format HH:mm)"
  $t0 = Get-Date
  # expression mode first: inline "+" is a literal argument in argument mode, and
  # a stray token without "=" is read as a collection filter and renders black
  $argv = @("out=$out") + $j.args
  & $b --background --python $j.py -- $argv |
    Select-String -Pattern 'rendered in|frames in|Error|Traceback' | Select-Object -Last 3
  $mins = [math]::Round(((Get-Date) - $t0).TotalMinutes, 1)

  if (Test-Path $out) {
    $web = "D:\Meshes\renders\$($j.name)_web.mp4"
    ffmpeg -y -v error -i $out -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p `
           -movflags +faststart -an $web
    $mb = "{0:N1}" -f ((Get-Item $web).Length / 1MB)
    Write-Output "$($j.name): $mins min, web $mb MB  [$(Get-Date -Format HH:mm)]"
  } else {
    Write-Output "$($j.name): FAILED after $mins min"
  }
}
Write-Output "MORNING QUEUE DONE $(Get-Date -Format HH:mm)"
