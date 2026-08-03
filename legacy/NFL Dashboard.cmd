@echo off
title NFL Dashboard
cd /d "%~dp0.."
echo.
echo  NFL Dashboard starting... your browser will open in a few seconds.
echo  Leave this window open while you use it; close it when you're done.
echo.
python -m streamlit run legacy\dashboard.py
echo.
echo  Dashboard stopped. If there is an error above, screenshot it and ask Claude.
pause
