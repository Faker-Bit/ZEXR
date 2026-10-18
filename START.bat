@echo off
REM ===========================================================================
REM  ZEXR Deal Hub - start the backend and the frontend.
REM
REM  Assumes dependencies are already installed.
REM  First-time setup? Run scripts\dev-windows.bat once instead.
REM
REM  Each service runs under a supervisor (backend\run-api.bat and
REM  frontend\run-web.bat) that restarts it if it exits unexpectedly, so a
REM  crashed reload or a port clash no longer leaves the site dead.
REM ===========================================================================
cd /d "%~dp0"

REM Free the ports first, otherwise "address already in use".
for %%p in (3000 8000) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
  )
)
timeout /t 2 /nobreak >nul

REM No nested quotes here on purpose. The previous form embedded "%~dp0backend"
REM inside an already-quoted cmd /k string, which closes the quote early and
REM leaves the new window running the wrong command. The supervisors cd
REM themselves, so START only has to name a file.
start "ZEXR Deal Hub API" cmd /k call "%~dp0backend\run-api.bat"
start "ZEXR Deal Hub Web" cmd /k call "%~dp0frontend\run-web.bat"

echo.
echo   Site     http://localhost:3000
echo   API docs http://localhost:8000/docs
echo   Logs     backend\logs\  and  frontend\logs\
echo.
echo   Both services restart themselves if they crash.
echo   To stop everything, close the two windows.
echo.

REM Wait for readiness with retries instead of a fixed sleep, so the message
REM below is true rather than hopeful.
set /a TRIES=0
:wait
timeout /t 3 /nobreak >nul
set /a TRIES+=1
set API=waiting
set WEB=waiting
curl -s -f -o nul http://localhost:8000/api/v1/health 2>nul && set API=ready
curl -s -f -o nul http://localhost:3000 2>nul && set WEB=ready

if "%API%"=="ready" if "%WEB%"=="ready" goto :ready
if %TRIES% GEQ 12 goto :timeout
goto :wait

:ready
echo   API: ready    Web: ready
echo.
pause
exit /b 0

:timeout
echo   API: %API%    Web: %WEB%
echo.
echo   They did not both come up within ~40 seconds. Check the two service
echo   windows for the error, and backend\logs\api.err.log or
echo   frontend\logs\web.err.log for the detail.
echo.
pause