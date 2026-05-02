@echo off
setlocal EnableExtensions
rem LLM Secret Guard - double click entry (ASCII-only launcher)
title LLM Secret Guard - START

pushd "%~dp0" 2>nul
if errorlevel 1 (
  echo [ERROR] Cannot enter the application folder.
  echo Folder: %~dp0
  echo.
  echo Please unzip the package first, then run START_HERE.bat inside the extracted folder.
  echo.
  pause
  exit /b 1
)

call START_HERE_SAFE.cmd
set "RC=%ERRORLEVEL%"

echo.
echo Launcher finished. Exit code: %RC%
echo Press any key to close this window.
pause >nul
popd
exit /b %RC%
