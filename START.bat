@echo off
REM ===========================================================================
REM  ZEXR Deal Hub - start the backend and the frontend.
REM
REM  Assumes dependencies are already installed.
REM  First-time setup? Run scripts\dev-windows.bat once instead.
REM ===========================================================================
cd /d "%~dp0"

REM  Kill anything already holding the ports, otherwise "address already in use".
for %%p in (3000 8000) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
  )
)

start "ZEXR Deal Hub API" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
start "ZEXR Deal Hub Web" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo   Site     http://localhost:3000
echo   API docs http://localhost:8000/docs
echo.
echo   Close the two windows to stop. Waiting for both to come up...
echo.

ping -n 45 127.0.0.1 >nul
curl -s -o nul http://localhost:8000/api/v1/health && echo   API: ready
curl -s -o nul http://localhost:3000 && echo   Web: ready
echo.
pause