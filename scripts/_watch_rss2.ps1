$target = [int]$args[0]
$log = $args[1]
$limit = ([double]$args[2]) * 1GB
$grace = [int]$args[3]
$over = 0
while ($true) {
  $p = Get-Process -Id $target -ErrorAction SilentlyContinue
  if (-not $p) { Add-Content $log ("{0} process {1} exited" -f (Get-Date -f 'HH:mm:ss'), $target); break }
  $rss = $p.WorkingSet64
  Add-Content $log ("{0} rss={1}GB cpu={2}s over={3}" -f (Get-Date -f 'HH:mm:ss'), [math]::Round($rss/1GB,2), [math]::Round($p.CPU,0), $over)
  if ($rss -gt $limit) {
    $over++
    if ($over -ge $grace) {
      Add-Content $log ("{0} WATCHDOG KILL target={1} rss={2}GB sustained={3}" -f (Get-Date -f 'HH:mm:ss'), $target, [math]::Round($rss/1GB,2), $over)
      Stop-Process -Id $target -Force
      break
    }
  } else { $over = 0 }
  Start-Sleep -Seconds 20
}