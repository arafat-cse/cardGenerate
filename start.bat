@echo off
setlocal
title BizCard Studio
cd /d "%~dp0"

set PY=.venv\Scripts\python.exe

if exist "%PY%" goto :deps

echo [setup] Creating Python environment - first run only...
where py >nul 2>nul
if %errorlevel%==0 (
    py -3.11 -m venv .venv 2>nul || py -3.12 -m venv .venv 2>nul || py -3.10 -m venv .venv 2>nul || py -3 -m venv .venv
) else (
    python -m venv .venv
)

:deps
if not exist "%PY%" (
    echo.
    echo [error] Python was not found on this PC.
    echo         1. Install Python 3.10 - 3.12 from https://www.python.org/downloads/
    echo         2. IMPORTANT: tick "Add python.exe to PATH" during install.
    echo         3. Run start.bat again.
    echo.
    pause
    exit /b 1
)

"%PY%" -c "import fastapi, uvicorn, PIL, qrcode, reportlab" >nul 2>nul
if errorlevel 1 (
    echo [setup] Installing dependencies - first run only, please wait...
    "%PY%" -m pip install --upgrade pip >nul
    "%PY%" -m pip install -r requirements.txt
)

"%PY%" -c "import rembg" >nul 2>nul
if errorlevel 1 (
    echo [setup] Installing local background removal ^(one-time, ~250 MB^)...
    "%PY%" -m pip install "rembg[cpu]" >nul 2>nul
    if errorlevel 1 echo [warn] Background removal could not be installed. Everything else still works.
)

echo.
echo  =================================================
echo    BizCard Studio
echo    Open:  http://127.0.0.1:8000
echo    Keep this window open while you work.
echo  =================================================
echo.

start /b cmd /c "timeout /t 2 /nobreak >nul & start "" http://127.0.0.1:8000"
"%PY%" main.py

echo.
echo Server stopped.
pause
