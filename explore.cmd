@echo off
title NFL Data Explorer
rem Opens the NFL warehouse in DuckDB's browser UI (read-only).
rem Keep this window open while you browse; close it when done.
rem NOTE: close this before running a data refresh - the rebuild needs the file.
cd /d "%~dp0"
echo.
echo  NFL Data Explorer starting...
echo  Your browser will open http://localhost:4213 in a few seconds.
echo  (If it doesn't, open that address yourself.)
echo.
echo  Leave this window open while exploring. Press Ctrl+C or close it to stop.
echo.
"C:\Users\parth\AppData\Local\Microsoft\WinGet\Packages\DuckDB.cli_Microsoft.Winget.Source_8wekyb3d8bbwe\duckdb.exe" -readonly nfl.duckdb -ui
echo.
echo  Explorer stopped. If it exited immediately with an error above,
echo  screenshot this window and ask Claude about it.
pause
