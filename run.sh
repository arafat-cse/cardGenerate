#!/usr/bin/env bash
# BizCard Studio - run from Git Bash / WSL:  ./run.sh   (or:  bash run.sh)
set -e
cd "$(dirname "$0")"

# pick the venv python (Windows-style and Linux-style layouts)
if [ -f ".venv/Scripts/python.exe" ]; then
    PY=".venv/Scripts/python.exe"
elif [ -f ".venv/Scripts/python" ]; then
    PY=".venv/Scripts/python"
elif [ -f ".venv/bin/python" ]; then
    PY=".venv/bin/python"
else
    echo "[setup] Creating Python environment - first run only..."
    if command -v py >/dev/null 2>&1; then
        py -3.11 -m venv .venv 2>/dev/null || py -3 -m venv .venv
    else
        python3 -m venv .venv 2>/dev/null || python -m venv .venv
    fi
    if [ -f ".venv/Scripts/python.exe" ]; then PY=".venv/Scripts/python.exe"
    elif [ -f ".venv/Scripts/python" ]; then PY=".venv/Scripts/python"
    else PY=".venv/bin/python"; fi
fi

if ! "$PY" -c "import fastapi, uvicorn, PIL, qrcode, reportlab" >/dev/null 2>&1; then
    echo "[setup] Installing dependencies - first run only, please wait..."
    "$PY" -m pip install --upgrade pip -q
    "$PY" -m pip install -r requirements.txt
fi

if ! "$PY" -c "import rembg" >/dev/null 2>&1; then
    echo "[setup] Installing local background removal (one-time, ~250 MB)..."
    "$PY" -m pip install "rembg[cpu]" -q || echo "[warn] rembg not installed - app works without it."
fi

echo ""
echo " ================================================="
echo "  BizCard Studio"
echo "  Open:  http://127.0.0.1:8000"
echo "  Keep this window open while you work."
echo " ================================================="
echo ""

( sleep 2; start "http://127.0.0.1:8000" 2>/dev/null || xdg-open "http://127.0.0.1:8000" 2>/dev/null || true ) &

exec "$PY" main.py
