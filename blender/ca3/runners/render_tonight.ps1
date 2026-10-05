# Overnight render queue.
#
# Every camera setting here comes from measurement, not guesswork. For the two
# widescreen masters the content bounding box was sampled across the orbit and
# frame 340 is the fullest, not 400: at camdist 3.4 it clipped top and bottom, at
# 3.7 it still clipped the green inhibitory cells at the bottom, and 4.1 with a
# vertical shift fills 87 percent of the height with nothing cut anywhere in the
# move. For the gradient, 1.05 clipped three sides and 1.62 wasted a third of the
# frame; 1.52 with shifty -0.045 fills 95 percent of the height and clears every
# edge, verified by thresholding the render and measuring the content box.
#
# Cheap deliverables run FIRST, so a failure four hours in does not cost the
# things that take two minutes.
$b = "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
Set-Location D:\Meshes

$jobs = @(
  # The convergence gradient, 304 cells coloured by mossy fibre input count.
  # A still, so no ffmpeg pass. Reads gradient_scene.blend, which already exists,
  # so it opens in 2 seconds instead of importing 2.4 GB of OBJ.
  @{ name = "gradient_still"; kind = "still"
     py   = "D:\Meshes\render_gradient.py"
     args = @("still=1", "res=3840x2160", "samples=192",
              "camdist=1.52", "shifty=-0.045") },

  @{ name = "build_sequence_wide"; kind = "video"
     py   = "D:\Meshes\render_from_cache.py"
     args = @("frames=480", "res=1920x1080", "samples=64",
              "camdist=4.1", "shifty=-0.066") },

  # story: 2.9 and 3.5 both clipped the top, 4.0 with no shift clears it with
  # 144px above and 95px below at the fullest frame
  @{ name = "synapse_story_wide"; kind = "video"
     py   = "D:\Meshes\synapse_story.py"
     args = @("frames=452", "res=1920x1080", "samples=64",
              "camdist=4.0", "shifty=0.0") },

  # A sixth of a turn across the gradient, eased at both ends, so the arch is
  # read rather than spun. Last because it is the one bonus item here.
  @{ name = "gradient_orbit"; kind = "video"
     py   = "D:\Meshes\render_gradient.py"
     args = @("still=0", "frames=300", "res=1920x1080", "samples=64",
              "camdist=1.52", "shifty=-0.045") }
)

foreach ($j in $jobs) {
  $ext = if ($j.kind -eq "still") { "png" } else { "mp4" }
  $out = "D:\Meshes\renders\$($j.name).$ext"
  Write-Output "=== $($j.name) ==="
  $t0 = Get-Date
  # Build the argument list in EXPRESSION mode first. Writing
  #   -- ("out=$out") + $j.args
  # inline puts PowerShell in argument mode, where "+" is not an operator but a
  # literal argument. render_from_cache.py files any token without an "=" into
  # `extra`, and `extra` is the collection filter, so a stray "+" resolves to
  # "render only the collection named +", hides all 984 objects and emits a
  # black frame in 2 seconds. Caught 29 Jul 2026 before an 8 hour run.
  $argv = @("out=$out") + $j.args
  & $b --background --python $j.py -- $argv |
    Select-String -Pattern 'rendering collections|rendered in|frames in|still ->|Error|Traceback' |
    Select-Object -Last 3
  $mins = [math]::Round(((Get-Date) - $t0).TotalMinutes, 1)

  if (-not (Test-Path $out)) {
    Write-Output "$($j.name): FAILED, no output written after $mins min"
    continue
  }

  if ($j.kind -eq "still") {
    $mb = "{0:N1}" -f ((Get-Item $out).Length / 1MB)
    Write-Output "$($j.name): $mins min, $mb MB -> $out"
  } else {
    $web = "D:\Meshes\renders\$($j.name)_web.mp4"
    ffmpeg -y -v error -i $out -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p `
           -movflags +faststart -an $web
    $mb = "{0:N1}" -f ((Get-Item $web).Length / 1MB)
    Write-Output "$($j.name): $mins min, web $mb MB"
  }
}
Write-Output "TONIGHT QUEUE DONE"
