@echo off
REM LLM Secret Guard 自動化工具 - 批處理啟動器
REM 支援: 依賴檢查, WSL/Ollama 安裝, 完整工作流程

setlocal enabledelayedexpansion

REM 取得當前目錄
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM 檢查 PowerShell
where powershell >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [Error] PowerShell 未找到
    exit /b 1
)

REM 將所有參數傳遞給 PowerShell 腳本
powershell -NoProfile -ExecutionPolicy Bypass -File "run.ps1" %*
exit /b %ERRORLEVEL%
