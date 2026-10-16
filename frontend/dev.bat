@echo off
REM Starts only the web app with logs (backend must already be on :8000).
cd /d "%~dp0"
set API_BASE_URL=http://localhost:8000
set NEXT_PUBLIC_SITE_URL=http://localhost:3000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>&1
npx next dev --port 3000 > dev.log 2> dev.err.log