@echo off
REM Task Scheduler entry: daily paper-trading scan after market close.
set "PATH=C:\Users\Glpaiadmin\tools\node-v22.17.0-win-x64;%PATH%"
cd /d "%~dp0"
"C:\Users\Glpaiadmin\repos\stock-exchange\.venv\Scripts\python.exe" scripts\paper_scan.py >> "%~dp0data\paper_task.log" 2>&1
