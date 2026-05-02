@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title LLM Secret Guard - Launcher

rem Always keep this window open and write a debug log.
set "LOG=logs\launcher_debug.log"
if not exist logs mkdir logs >nul 2>nul

echo ========================================
echo  LLM Secret Guard - START HERE
echo ========================================
echo.
echo [INFO] Current folder: %CD%
echo [INFO] Log file: %CD%\%LOG%
echo.

> "%LOG%" echo ==== LLM Secret Guard launcher started ====
>> "%LOG%" echo Folder: %CD%
>> "%LOG%" echo Date: %DATE% %TIME%

if not exist "llm_secret_guard.py" (
  echo [ERROR] 找不到 llm_secret_guard.py。
  echo.
  echo 可能原因：你直接在 ZIP 壓縮檔裡面雙擊執行。
  echo 請先把 ZIP 解壓縮，再到解壓縮後的 LLM-Secret-Guard 資料夾裡雙擊 START_HERE.cmd。
  echo.
  >> "%LOG%" echo ERROR: llm_secret_guard.py not found. User may be running inside ZIP/temp folder.
  pause
  exit /b 1
)

set "PYEXE="
where py >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3"
if "%PYEXE%"=="" (
  where python >nul 2>nul
  if not errorlevel 1 set "PYEXE=python"
)

if "%PYEXE%"=="" (
  echo [ERROR] 找不到 Python。
  echo 請先安裝 Python 3.9 或更新版本，並勾選 Add Python to PATH。
  echo.
  >> "%LOG%" echo ERROR: Python not found.
  pause
  exit /b 1
)

echo [OK] Python command: %PYEXE%
>> "%LOG%" echo Python command: %PYEXE%
%PYEXE% --version
%PYEXE% --version >> "%LOG%" 2>&1

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo [SETUP] 第一次啟動：建立本機 Python 環境...
  >> "%LOG%" echo Creating venv...
  %PYEXE% -m venv .venv >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo [ERROR] 建立 .venv 失敗，詳細資訊請看 logs\launcher_debug.log。
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] 無法啟用 .venv。
  >> "%LOG%" echo ERROR: activate venv failed.
  pause
  exit /b 1
)

echo.
echo [SETUP] 安裝 / 更新必要套件...
python -m pip install --upgrade pip >> "%LOG%" 2>&1
python -m pip install -r requirements.txt >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [ERROR] 安裝 Python 套件失敗，詳細資訊請看 logs\launcher_debug.log。
  echo 常見原因：網路不穩、學校電腦權限限制、或 pip 被防火牆擋住。
  pause
  exit /b 1
)

where ollama >nul 2>nul
if errorlevel 1 (
  echo.
  echo [WARN] 找不到 Ollama 指令。
  echo 請先安裝 Ollama，然後重新執行 START_HERE.cmd。
  echo.
  echo 如果已安裝，請關掉這個視窗後重新開機或重開 CMD。
  >> "%LOG%" echo WARN: Ollama command not found.
  pause
  exit /b 1
)

echo.
echo [INFO] 嘗試啟動 Ollama 服務...
start "Ollama Server - LLM Secret Guard" /min cmd /k "ollama serve"
timeout /t 3 /nobreak >nul

echo.
echo [START] 啟動 LLM Secret Guard...
echo.
>> "%LOG%" echo Starting app...
python llm_secret_guard.py
set "RC=%ERRORLEVEL%"

echo.
echo ========================================
echo 程式已結束。Exit code: %RC%
echo 報告位置：reports / results / logs
echo Debug log：logs\launcher_debug.log
echo ========================================
pause
exit /b %RC%
