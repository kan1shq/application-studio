param([int]$Port = 8767)
$ErrorActionPreference = 'Stop'
$address = "http://127.0.0.1:$Port"
try {
    $existing = Invoke-RestMethod -Uri "$address/api/health" -TimeoutSec 2
    if ($existing.app -ne 'application-studio' -or $existing.root -ne $PSScriptRoot) { throw 'The selected port is occupied by another workspace. Run with -Port 8768.' }
    Start-Process $address
    exit
} catch {
    if ($_.Exception.Message -like '*occupied*') { throw }
}
$python = (Get-Command python -ErrorAction Stop).Source
$process = Start-Process -FilePath $python -ArgumentList ('"{0}" --port {1}' -f (Join-Path $PSScriptRoot 'server.py'), $Port) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'server.log') -RedirectStandardError (Join-Path $PSScriptRoot 'server-error.log') -PassThru
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 200
    try {
        $health = Invoke-RestMethod -Uri "$address/api/health" -TimeoutSec 1
        if ($health.app -eq 'application-studio' -and $health.root -eq $PSScriptRoot) { Start-Process $address; exit }
    } catch { }
    if ($process.HasExited) { throw 'Dashboard stopped. Read server-error.log in this folder.' }
}
throw 'Dashboard did not respond. Read server-error.log.'
