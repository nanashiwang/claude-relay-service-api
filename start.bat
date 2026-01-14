@echo off
setlocal

cd /d "%~dp0"

set "PYTHON=%~dp0\.venv\Scripts\python.exe"
if exist "%PYTHON%" (
  "%PYTHON%" -m uvicorn "api:app" --reload --host "0.0.0.0" --port 8000
) else (
  python -m uvicorn "api:app" --reload --host "0.0.0.0" --port 8000
)

endlocal
