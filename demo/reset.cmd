@echo off
rem I-SPOT demo: reset demo data to the initial state. Close the server windows first.
chcp 65001 >nul
cd /d "%~dp0.."
if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Run demo\setup.cmd first.
  pause
  exit /b 1
)
backend\.venv\Scripts\python.exe demo\prepare.py reset
pause
