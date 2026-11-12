@echo off
rem Opens the Email Tracker dashboard. Starts the local server first if it is not running.
rem Double-click this file, or pin a shortcut to it on the desktop or taskbar.
setlocal
cd /d "%~dp0..\web"

powershell -NoProfile -Command "try { (New-Object Net.Sockets.TcpClient('127.0.0.1', 3000)).Close(); exit 0 } catch { exit 1 }"
if %errorlevel%==0 goto open

if not exist node_modules (
  echo Installing the dashboard's packages, one time only...
  call npm install --no-fund --no-audit || goto failed
)
echo Building the dashboard...
call npm run build || goto failed
echo Starting the dashboard server (minimized window; close it to stop the server)...
start "Email Tracker server" /min cmd /c "npm run start"
powershell -NoProfile -Command "for ($i = 0; $i -lt 60; $i++) { try { (New-Object Net.Sockets.TcpClient('127.0.0.1', 3000)).Close(); exit 0 } catch { Start-Sleep -Seconds 1 } }; exit 1"

:open
start "" "http://127.0.0.1:3000"
exit /b 0

:failed
echo Could not start the dashboard. See the messages above.
pause
exit /b 1
