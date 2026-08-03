@echo off
title NFL Jarvis
cd /d "%~dp0"
echo.
echo  NFL Jarvis coming online... your browser will open in a few seconds.
echo  Leave this window open while you use it; close it (or Ctrl+C) when done.
echo.
python web\run_web.py
echo.
echo  Jarvis offline. If there is an error above, screenshot it and ask Claude.
pause
