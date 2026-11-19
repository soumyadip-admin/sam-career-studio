@echo off
setlocal
cd /d "%~dp0"
title Sam Career Studio Setup

echo Installing required Python packages...
py -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo Initializing the SQLite database...
py init_db.py
if errorlevel 1 goto :error

echo Starting Sam Career Studio on http://127.0.0.1:8000 ...
start "Sam Career Studio Server" /min cmd /c "cd /d ""%~dp0"" && py server.py"
timeout /t 3 /nobreak >nul
start "" msedge.exe --app=http://127.0.0.1:8000 --window-size=1600,950
exit /b 0

:error
echo.
echo Setup failed. Review the message above, then run this file again.
pause
exit /b 1
