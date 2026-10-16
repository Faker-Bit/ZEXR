@echo off
REM ===========================================================================
REM  ZEXR Deal Hub - one-click development launcher
REM
REM  Creates the virtualenv, installs dependencies, applies migrations, seeds
REM  taxonomy + the real public deal sources, then starts the API and the web
REM  app and waits until both are actually answering before reporting success.
REM
REM  Safe to run repeatedly. Everything it creates is idempotent.
REM ===========================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0\.."

set "ROOT=%CD%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "API=http://localhost:8000"
set "WEB=http://localhost:3000"
set "PY=%BACKEND%\.venv\Scripts\python.exe"
set "FAILURES=0"

echo.
echo  ==========================================================
echo    ZEXR Deal Hub
echo  ==========================================================
echo.

REM ---------------------------------------------------------------- preflight
where python >nul 2>nul || (echo  [X] Python 3.11+ is required ^(python not found^). & set /a FAILURES+=1)
where node   >nul 2>nul || (echo  [X] Node.js 20+ is required ^(node not found^).   & set /a FAILURES+=1)
if not "%FAILURES%"=="0" goto :failed

echo  [1/6] Freeing ports 3000 and 8000...
call :freeport 3000
call :freeport 8000
echo.

REM ------------------------------------------------------------------ backend
echo  [2/6] Preparing the Python environment...
if not exist "%PY%" (
  echo        Creating virtualenv...
  python -m venv "%BACKEND%\.venv" || (echo  [X] venv creation failed. & set /a FAILURES+=1 & goto :failed)
)
"%PY%" -m pip install --quiet --upgrade pip >nul 2>&1
"%PY%" -m pip install --quiet -r "%BACKEND%\requirements-dev.txt" || (echo  [X] pip install failed. & set /a FAILURES+=1 & goto :failed)

if not exist "%BACKEND%\.env" (
  copy /y "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
  echo        Created backend\.env from the template.
)
echo        Ready.
echo.

REM ------------------------------------------------------- migrations + seed
echo  [3/6] Applying schema and loading deal sources...
pushd "%BACKEND%"
"%PY%" -m app.db.seed || (echo  [X] Database setup failed. & popd & set /a FAILURES+=1 & goto :failed)
popd
echo.

REM ----------------------------------------------------------------- frontend
echo  [4/6] Preparing the web app...
pushd "%FRONTEND%"
if not exist "node_modules" (
  echo        Installing npm packages ^(first run, this takes a while^)...
  call npm install --no-fund --no-audit || (echo  [X] npm install failed. & popd & set /a FAILURES+=1 & goto :failed)
) else (
  echo        node_modules present.
)
if not exist ".env.local" (
  copy /y ".env.example" ".env.local" >nul
  echo        Created frontend\.env.local from the template.
)
popd
echo.

REM --------------------------------------------------------------------- API
echo  [5/6] Starting the API on :8000...
start "ZEXR Deal Hub API" cmd /k "cd /d "%BACKEND%" && "%PY%" -m uvicorn app.main:app --reload --port 8000"
call :waitfor "%API%/api/v1/health" 60 "API"
echo.

REM --------------------------------------------------------------------- WEB
echo  [6/6] Starting the web app on :3000...
start "ZEXR Deal Hub Web" cmd /k "cd /d "%FRONTEND%" && set API_BASE_URL=%API% && set NEXT_PUBLIC_SITE_URL=%WEB% && npm run dev"
call :waitfor "%WEB%" 120 "web app"
echo.

REM ------------------------------------------------------------------ summary
echo  ==========================================================
if "%FAILURES%"=="0" (
  echo    ZEXR Deal Hub is running
  echo  ==========================================================
  echo.
  echo    Site       %WEB%
  echo    API docs   %API%/docs
  echo    Admin      %WEB%/admin
  echo.
  echo    admin@zexrdealhub.dev  /  AdminPass123
  echo.
  echo    Pull in fresh deals ^(new terminal^):
  echo      cd backend
  echo      .venv\Scripts\python -m app.cli discover --force
  echo      .venv\Scripts\python -m app.cli verify --limit 50
  echo.
  echo    Close the two server windows to stop everything.
  echo.
  if not defined ZEXRDEALHUB_NO_PAUSE pause
  exit /b 0
) else (
  echo    Started with problems - see [X] above
  echo  ==========================================================
  echo.
  if not defined ZEXRDEALHUB_NO_PAUSE pause
  exit /b 1
)

:failed
echo.
echo  Setup did not complete. Fix the [X] items above and run this file again.
echo.
  if not defined ZEXRDEALHUB_NO_PAUSE pause
exit /b 1

REM =========================================================== helper routines

:freeport
REM  Kill whatever is holding %1, otherwise "address already in use".
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%1" ^| findstr "LISTENING"') do (
  echo        Stopping PID %%p on port %1.
  taskkill /PID %%p /F >nul 2>&1
)
REM  `ping` is used instead of `timeout` because timeout requires an attached
REM  console and dies when this script is launched from CI or another shell.
ping -n 2 127.0.0.1 >nul
exit /b 0

:waitfor
REM  Poll %1 until it answers, up to %2 seconds. Label %3.
set "URL=%~1"
set "LIMIT=%~2"
set "LABEL=%~3"
set "WAITED=0"
:waitloop
powershell -NoProfile -Command ^
  "try { $r = Invoke-WebRequest -Uri '%URL%' -UseBasicParsing -TimeoutSec 4; if ($r.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
  echo        %LABEL% is up.
  exit /b 0
)
if !WAITED! geq %LIMIT% (
  echo  [X] %LABEL% did not answer within %LIMIT% seconds.
  echo        Check the "%LABEL%" window for the error.
  exit /b 1
)
ping -n 3 127.0.0.1 >nul
set /a WAITED+=2
goto :waitloop
