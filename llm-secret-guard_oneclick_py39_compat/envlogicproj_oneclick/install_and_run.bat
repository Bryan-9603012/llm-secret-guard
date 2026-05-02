@echo off
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%install.bat" %*
exit /b %ERRORLEVEL%
