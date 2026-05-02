@echo off
setlocal EnableExtensions
pushd "%~dp0" 2>nul
if errorlevel 1 (
  echo [ERROR] Cannot enter folder: %~dp0
  pause
  exit /b 1
)
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
python llm_secret_guard.py
echo.
pause
popd
