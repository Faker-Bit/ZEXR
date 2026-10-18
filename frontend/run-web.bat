@echo off
REM ===========================================================================
REM  Web supervisor.
REM
REM  Next.js dev occasionally exits on a crashed compile, a turbopack panic or a
REM  port clash, and nothing restarts it. This loops, with a longer backoff than
REM  the API because a dev server needs a moment to release the port.
REM ===========================================================================
cd /d "%~dp0"

if not exist logs mkdir logs

echo [web] starting... (Ctrl+C twice, or close this window, to stop)
echo.

:run
call npm run dev >> "logs\web.log" 2>> "logs\web.err.log"
set EXITCODE=%errorlevel%

echo.
echo [web] stopped with exit code %EXITCODE%.
if "%EXITCODE%"=="0" (
  echo [web] clean shutdown.
  goto :done
)
echo [web] last error output:
powershell -NoProfile -Command "if (Test-Path 'logs\web.err.log') { Get-Content 'logs\web.err.log' -Tail 8 }"
echo.
echo [web] restarting in 8 seconds...
timeout /t 8 /nobreak >nul
goto :run

:done
echo [web] not restarting an intentional shutdown.
pause