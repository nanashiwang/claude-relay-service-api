$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv/Scripts/python.exe"
if (-not (Test-Path $python)) {
  $python = "python"
}

& $python -m uvicorn "api:app" --reload --host "0.0.0.0" --port 8000
