@echo off
setlocal
title BizCard Studio - Setup
cd /d "%~dp0"

set PY=.venv\Scripts\python.exe

if exist "%PY%" goto :install

echo [1/3] Creating Python environment...
where py >nul 2>nul
if %errorlevel%==0 (
    py -3.11 -m venv .venv 2>nul || py -3.12 -m venv .venv 2>nul || py -3.10 -m venv .venv 2>nul || py -3 -m venv .venv
) else (
    python -m venv .venv
)

:install
if not exist "%PY%" (
    echo [error] Python not found. Install Python 3.10-3.12 from python.org
    echo         and tick "Add python.exe to PATH" during install.
    pause
    exit /b 1
)

echo [2/3] Installing app dependencies...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt

echo [3/3] Installing local background removal (one-time, ~250 MB)...
"%PY%" -m pip install "rembg[cpu]"
if errorlevel 1 echo [warn] rembg failed to install - the app works without it.

echo.
echo Setup complete! From now on just double-click start.bat
pause
