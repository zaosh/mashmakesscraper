@echo off
title Antigravity Launcher
echo ==========================================
echo    🚀 Antigravity Tracking System
echo ==========================================
echo.
echo [1] Starting Background Scheduler (main.py)...
start "Antigravity Worker" cmd /c "python main.py"

echo [2] Starting Streamlit Dashboard...
streamlit run dashboard.py
