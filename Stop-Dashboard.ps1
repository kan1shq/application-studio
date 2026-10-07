param([int]$Port = 8767)
$ErrorActionPreference = 'Stop'
$address = "http://127.0.0.1:$Port"
try { $health = Invoke-RestMethod -Uri "$address/api/health" -TimeoutSec 2 }
catch { Write-Output 'Dashboard is not responding on this port.'; exit }
if ($health.app -ne 'application-studio' -or $health.root -ne $PSScriptRoot) { throw 'This port belongs to another app or workspace; left it running.' }
Invoke-RestMethod -Uri "$address/api/shutdown" -Method Post -ContentType 'application/json' -Body '{}' | Out-Null
Write-Output 'Dashboard stopped. Saved data remains in this folder.'
