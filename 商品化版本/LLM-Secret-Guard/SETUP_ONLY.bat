@echo off
setlocal EnableExtensions
pushd "%~dp0" 2>nul
if errorlevel 1 (
  echo [ERROR] Cannot enter folder: %~dp0
  pause
  exit /b 1
)
call START_HERE_SAFE.cmd
popd
