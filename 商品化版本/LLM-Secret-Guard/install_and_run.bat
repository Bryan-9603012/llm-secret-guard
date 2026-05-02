@echo off
setlocal
cd /d "%~dp0"
call install.bat
python llm_secret_guard.py
pause
