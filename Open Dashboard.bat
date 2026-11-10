@echo off
rem Starts the local job-search dashboard and opens it in the browser. Close this window to stop it.
cd /d "%~dp0"
python scripts\dashboard_server.py
pause
