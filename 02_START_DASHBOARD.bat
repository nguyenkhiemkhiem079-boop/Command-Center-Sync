@echo off
setlocal
cd /d "%~dp0"
if not exist "private\roles.json" (
 echo Coordinator has not been initialized. Run 01_SETUP.bat first.
 pause
 exit /b 1
)
echo.
echo K-TOOL Command Center starting at http://127.0.0.1:8876/ui
echo Do not close this console window while using the dashboard.
start "" /B powershell -NoProfile -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8876/ui'"
py -3 server.py --port 8876
if errorlevel 1 pause
