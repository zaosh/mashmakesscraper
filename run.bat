@echo off
title MashMakes Tracker
echo ==========================================
echo    MashMakes Shipment Tracker
echo ==========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Run install.bat first.
    pause
    exit /b 1
)

:: Create data dir if missing
if not exist "data" mkdir data

echo [1] Starting Background Tracker (main.py)...
start "MashMakes Worker" /min cmd /c "python main.py"

echo [2] Starting Dashboard...
echo     Dashboard will open at http://localhost:8501
echo.
echo Press Ctrl+C to stop the dashboard.
echo Close the "MashMakes Worker" window to stop the tracker.
echo.
python -m streamlit run dashboard.py --server.headless true
