param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Test-Path -LiteralPath '.venv311/Scripts/python.exe') {
    $wealthPython = Join-Path $PSScriptRoot '.venv311/Scripts/python.exe'
} elseif (Test-Path -LiteralPath '.venv/Scripts/python.exe') {
    $wealthPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
} else {
    throw 'Set up Python 3.11 and the dependencies as described in README.md first.'
}
Write-Host "Wealth Command Center: http://127.0.0.1:$Port"
& $wealthPython -m uvicorn wealth_command_center.app:app --host 127.0.0.1 --port $Port --no-proxy-headers --no-access-log

