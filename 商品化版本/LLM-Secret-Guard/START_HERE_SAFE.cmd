@echo off
setlocal EnableExtensions
title LLM Secret Guard - Safe Launcher

rem Always run from this file's folder.
pushd "%~dp0" 2>nul
if errorlevel 1 (
  echo [ERROR] Cannot enter folder: %~dp0
  pause
  exit /b 1
)

if not exist logs mkdir logs >nul 2>nul
set "LOG=logs\launcher_debug.log"

> "%LOG%" echo ==== LLM Secret Guard launcher started ====
>> "%LOG%" echo Folder: %CD%
>> "%LOG%" echo Date: %DATE% %TIME%

echo ========================================
echo  LLM Secret Guard - Safe Launcher
echo ========================================
echo Folder: %CD%
echo Debug log: %CD%\%LOG%
echo.

if not exist "llm_secret_guard.py" (
  echo [ERROR] llm_secret_guard.py was not found.
  echo.
  echo Make sure you have extracted the ZIP first.
  echo Run this file from inside the LLM-Secret-Guard folder.
  >> "%LOG%" echo ERROR: llm_secret_guard.py not found.
  goto END
)

set "PYEXE="
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 set "PYEXE=py -3"
if "%PYEXE%"=="" (
  where python >nul 2>nul
  if %ERRORLEVEL% EQU 0 set "PYEXE=python"
)

if "%PYEXE%"=="" (
  echo [ERROR] Python was not found.
  echo Please install Python 3.9 or newer and enable "Add Python to PATH".
  >> "%LOG%" echo ERROR: Python not found.
  goto END
)

echo [OK] Python command: %PYEXE%
%PYEXE% --version
%PYEXE% --version >> "%LOG%" 2>&1

echo.
echo [CHECK] Virtual environment...
if not exist ".venv\Scripts\python.exe" (
  echo [SETUP] Creating .venv. This may take a while on first run...
  %PYEXE% -m venv .venv >> "%LOG%" 2>&1
  if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to create .venv. See %LOG%.
    goto END
  )
)

echo [OK] Activating .venv...
call ".venv\Scripts\activate.bat"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Failed to activate .venv.
  >> "%LOG%" echo ERROR: venv activation failed.
  goto END
)

echo.
echo [SETUP] Installing dependencies...
python -m pip install --upgrade pip >> "%LOG%" 2>&1
if exist requirements.txt (
  python -m pip install -r requirements.txt >> "%LOG%" 2>&1
  if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Dependency installation failed. See %LOG%.
    echo Common causes: network block, proxy, firewall, or school PC restrictions.
    goto END
  )
) else (
  echo [WARN] requirements.txt was not found. Skipping dependency install.
  >> "%LOG%" echo WARN: requirements.txt not found.
)

where ollama >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [WARN] Ollama command was not found in PATH.
  echo You can still open the tool, but real Ollama tests require Ollama installed and running.
  >> "%LOG%" echo WARN: ollama not found.
) else (
  echo.
  echo [INFO] Starting Ollama server in another window if needed...
  start "Ollama Server - LLM Secret Guard" /min cmd /k "ollama serve"
  timeout /t 3 /nobreak >nul
)

echo.
echo [START] Launching LLM Secret Guard...
echo.
python llm_secret_guard.py
set "RC=%ERRORLEVEL%"

echo.
echo ========================================
echo Program finished. Exit code: %RC%
echo Reports: reports
echo Results: results
echo Logs: logs
echo Debug log: %CD%\%LOG%
echo ========================================

:END
echo.
echo Press any key to close this window...
pause >nul
popd
exit /b 0
