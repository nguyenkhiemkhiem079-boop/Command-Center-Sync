@echo off
setlocal
cd /d "%~dp0"
echo.
echo =====================================
echo   K-TOOL MCP DASHBOARD - FIRST SETUP
echo =====================================
py -3 --version
if errorlevel 1 (
 echo Python Launcher not found. Install Python 3.11 or newer.
 pause
 exit /b 1
)
if exist "private\roles.json" (
 echo Existing role tokens detected. Keeping all private data unchanged.
) else (
 py -3 bootstrap.py
 if errorlevel 1 (
   echo Setup failed. See error above.
   pause
   exit /b 1
 )
)
echo.
echo NEXT: Inspect and secure the private folder.
echo The CODEX token is needed to login to the dashboard.
echo Do not share or upload private tokens.
echo Run 02_START_DASHBOARD.bat to open dashboard.
pause
