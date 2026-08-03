@echo off
title NFL Jarvis
cd /d "%~dp0"
echo.
echo  NFL Jarvis coming online... your browser will open in a few seconds.
echo  Leave this window open while you use it; close it when done.
echo  (If the server ever crashes it restarts itself automatically.)
echo.
set RESTARTS=0
:run
python web\run_web.py
if errorlevel 1 (
  set /a RESTARTS+=1
  if %RESTARTS% GEQ 5 (
    echo.
    echo  Jarvis failed 5 times in a row - see logs\jarvis.log, then ask Claude.
    pause
    exit /b 1
  )
  echo.
  echo  Jarvis stopped unexpectedly - restarting (%RESTARTS%/5) ...
  timeout /t 3 /nobreak >nul
  goto run
)
echo.
echo  Jarvis offline (normal shutdown).
pause
