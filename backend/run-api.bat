@echo off
REM ===========================================================================
REM  API supervisor.
REM
REM  uvicorn exits on a reload crash, a port clash or an unhandled startup
REM  error, and a one-shot launch just leaves the window dead. This loops
REM  instead, so a transient failure self-heals and the exit code is visible.
REM
REM  Logs go to logs\ rather than this directory: anything written into the
REM  source tree while --reload is watching it is asking for trouble.
REM ===========================================================================
cd /d "%~dp0"

REM UTF-8 by default, before the interpreter starts. Python otherwise builds
REM stdout with the ANSI codepage (cp1252) when output is redirected to a file,
REM and a single rupee sign or em dash in a log line then raises
REM UnicodeEncodeError and takes the process down. The runtime guard in
REM app/core/logging.py is the second line of defence.
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if not exist logs mkdir logs

echo [api] starting... (Ctrl+C twice, or close this window, to stop)
echo.

:run
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 >> "logs\api.log" 2>> "logs\api.err.log"
set EXITCODE=%errorlevel%

echo.
echo [api] stopped with exit code %EXITCODE%.
if "%EXITCODE%"=="0" (
  echo [api] clean shutdown.
  goto :done
)
echo [api] last error output:
powershell -NoProfile -Command "if (Test-Path 'logs\api.err.log') { Get-Content 'logs\api.err.log' -Tail 8 }"
echo.
echo [api] restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto :run

:done
echo [api] not restarting an intentional shutdown.
pause