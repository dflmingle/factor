$target = [int]$args[0]
$log = $args[1]
$limitGB = [double]$args[2]
$limit = $limitGB * 1GB
while ($true) {
  $p = Get-Process -Id $target -ErrorAction SilentlyContinue
  if (-not $p) { Add-Content $log ("{0} process {1} exited" -f (Get-Date -f 'HH:mm:ss'), $target); break }
  $rss = $p.WorkingSet64
  Add-Content $log ("{0} rss={1}GB cpu={2}s" -f (Get-Date -f 'HH:mm:ss'), [math]::Round($rss/1GB,2), [math]::Round($p.CPU,0))
  if ($rss -gt $limit) {
    Add-Content $log ("{0} WATCHDOG KILL target={1} rss={2}GB" -f (Get-Date -f 'HH:mm:ss'), $target, [math]::Round($rss/1GB,2))
    Stop-Process -Id $target -Force
    break
  }
  Start-Sleep -Seconds 20
}
