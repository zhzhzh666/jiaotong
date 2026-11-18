@echo off
cd /d "%~dp0"
".conda-env\python.exe" "scripts\serve_digital_twin.py"
if errorlevel 1 pause
