@echo off
title OCRATION - Master Launcher
cls
echo ======================================================================
echo    OCRATION: All-in-One Launcher
echo ======================================================================
echo.

echo [1/3] Starting Local Server...
:: Launching Python directly in a new window so we don't depend on run_server.bat
start "OCRATION Server" ".\.venv\Scripts\python.exe" "run_web.py"

echo [2/3] Waiting for server warm-up (5s)...
timeout /t 5 >nul

echo [3/3] Opening Laptop Interface...
start http://127.0.0.1:5000

echo.
echo ======================================================================
echo    MOBILE ACCESS (Optional)
echo ======================================================================
echo    Starting secure tunnel for mobile access...
echo    Look for the link ending in ".localhost.run" below.
echo.
echo    Or just use the Laptop Interface that opened.
echo ======================================================================
echo.

:: Start Tunnel (Blocking)
ssh -o StrictHostKeyChecking=no -R 80:127.0.0.1:5000 nokey@localhost.run

pause
