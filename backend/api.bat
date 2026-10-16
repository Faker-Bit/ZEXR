@echo off
REM Starts only the API with logs (web must already be on :3000).
cd /d "%~dp0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>&1
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 > api.log 2> api.err.log