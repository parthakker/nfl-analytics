@echo off
title NFL Data Explorer
rem Opens the NFL warehouse in DuckDB's browser UI (read-only).
rem Keep this window open while you browse; close it when done.
rem NOTE: close this before running a data refresh - the rebuild needs the file.
cd /d "%~dp0"
where duckdb >nul 2>&1
if errorlevel 1 (
  echo  duckdb CLI not found on PATH.
  echo  Install it with:  winget install DuckDB.cli
  echo  then open a NEW terminal window and run this again.
  pause
  exit /b 1
)
echo.
echo  NFL Data Explorer starting...
echo  Your browser will open http://localhost:4213 in a few seconds.
echo  (If it doesn't, open that address yourself.)
echo.
echo  Leave this window open while exploring. Press Ctrl+C or close it to stop.
echo.
duckdb -readonly nfl.duckdb -ui
echo.
echo  Explorer stopped. If it exited immediately with an error above,
echo  screenshot this window and ask Claude about it.
pause
