@echo off
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
set "LOG_DIR=%SCRIPT_DIR%logs"
set "LOG_FILE=%LOG_DIR%install_and_run_last.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
cd /d "%SCRIPT_DIR%"

echo ========================================
echo LLM Secret Guard - One Click Installer
echo Project: %SCRIPT_DIR%
echo Log: %LOG_FILE%
echo ========================================
echo.

echo [INFO] Double-click mode: install environment, prepare Ollama, start server, then enter test workflow.
echo [INFO] This .bat runs in Windows CMD and calls PowerShell.
echo [INFO] Optional debug usage:
echo        install.bat -NoRun
echo        install.bat -CheckOnly
echo.

where powershell >nul 2>nul
if errorlevel 1 (
    echo [FAIL] PowerShell not found.
    echo Please install Windows PowerShell or PowerShell 7.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Transcript -Path '%LOG_FILE%' -Force | Out-Null; & '%SCRIPT_DIR%install_and_run.ps1' -InstallOllama -StartOllama %*; $rc=$LASTEXITCODE; if ($null -eq $rc) { $rc=0 }; Stop-Transcript | Out-Null; exit $rc"
set "RC=%ERRORLEVEL%"

echo.
echo ========================================
if not "%RC%"=="0" (
    echo [FAIL] install failed. Exit code: %RC%
    echo Log saved to: %LOG_FILE%
) else (
    echo [OK] install finished successfully.
    echo Log saved to: %LOG_FILE%
)
echo ========================================
echo.
echo Press any key to close this window...
pause >nul
exit /b %RC%
