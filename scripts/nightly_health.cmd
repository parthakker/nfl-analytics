@echo off
rem Nightly health loop: headless Claude runs the /health-check skill.
rem Scheduled as NFL-NightlyHealth (daily 06:45). Writes docs/health_report.md
rem + logs/health.log; raw runner output accumulates in logs/health_runner.log.
cd /d "%~dp0.."
if not exist logs mkdir logs
echo ===== %date% %time% nightly health starting ===== >> logs\health_runner.log
rem --model haiku: the check is mechanical (run commands, compare numbers,
rem write the report) - no need to pay frontier-model rates nightly
claude -p "/health-check" --model haiku --output-format json --no-session-persistence >> logs\health_runner.log 2>&1
echo ===== exit %errorlevel% ===== >> logs\health_runner.log
