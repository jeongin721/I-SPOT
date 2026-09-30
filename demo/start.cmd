@echo off
rem I-SPOT demo: start the backend and the screens, then open the browser.
rem To stop, close the two windows "I-SPOT Backend" and "I-SPOT Frontend".
chcp 65001 >nul
cd /d "%~dp0.."
if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Run demo\setup.cmd first.
  pause
  exit /b 1
)
if not exist "backend\.env.demo" (
  echo [ERROR] Run demo\setup.cmd first.
  pause
  exit /b 1
)
start "I-SPOT Backend" /d "%CD%\backend" cmd /k .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file .env.demo
start "I-SPOT Frontend" /d "%CD%\ispotvscode" cmd /k npx --no-install vite --host 127.0.0.1 --port 5173 --strictPort
backend\.venv\Scripts\python.exe demo\prepare.py open
pause
