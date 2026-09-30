@echo off
rem I-SPOT demo: install packages and prepare demo data (run once).
chcp 65001 >nul
cd /d "%~dp0.."
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY (
  echo [ERROR] Python 3.11 - 3.13 is not installed.
  echo         Install it from https://www.python.org/downloads/ and check "Add python.exe to PATH".
  pause
  exit /b 1
)
%PY% demo\prepare.py setup
pause
