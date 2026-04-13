@echo off
title MashMakes Tracker - Installer
echo ==========================================
echo    MashMakes Tracker - Installer
echo ==========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo [OK] Python found.

:: Check pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip is not available. Reinstall Python with pip enabled.
    pause
    exit /b 1
)
echo [OK] pip found.

:: Install Python dependencies
echo.
echo Installing Python packages...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install some packages. Check the output above.
    pause
    exit /b 1
)
echo [OK] Python packages installed.

:: Install Twilio (for SMS, optional but needed for import)
pip install twilio >nul 2>&1
echo [OK] Twilio installed.

:: Create data directory
if not exist "data" mkdir data
echo [OK] Data directory ready.

:: Check if .env exists (don't overwrite existing setup)
if exist ".env" (
    echo [OK] .env file found (existing setup preserved).
) else (
    echo [INFO] No .env file yet. The setup wizard will create one on first run.
)

echo.
echo ==========================================
echo    Installation Complete!
echo ==========================================
echo.
echo Next steps:
echo   1. Run "run.bat" to start the system
echo   2. Open http://localhost:8501 in your browser
echo   3. Follow the setup wizard (first time only)
echo.
pause
