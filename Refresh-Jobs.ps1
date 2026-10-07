$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try { python server.py --refresh } finally { Pop-Location }
