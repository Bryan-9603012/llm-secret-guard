@echo off
setlocal EnableExtensions
title LLM Secret Guard - Debug Window
pushd "%~dp0" 2>nul
if errorlevel 1 (
  echo [ERROR] Cannot enter folder: %~dp0
  pause
  exit /b 1
)
echo Debug shell opened in:
echo %CD%
echo.
echo Try running:
echo   START_HERE_SAFE.cmd
echo.
cmd /k
