param(
    [switch]$NoRun,
    [switch]$CheckOnly,
    [switch]$InstallOllama,
    [switch]$StartOllama,
    [switch]$SkipOllamaApiCheck,
    [string]$VenvName = ".venv",
    [string]$OllamaUrl = "http://127.0.0.1:11434"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPath = Join-Path $ProjectRoot $VenvName
$PythonVenv = Join-Path $VenvPath "Scripts\python.exe"
$PipVenv = Join-Path $VenvPath "Scripts\pip.exe"
$TestScript = Join-Path $ProjectRoot "test_ollama.ps1"

function Write-OK { Write-Host "[OK]    $args" -ForegroundColor Green }
function Write-FAIL { Write-Host "[FAIL]  $args" -ForegroundColor Red }
function Write-INFO { Write-Host "[INFO]  $args" -ForegroundColor Cyan }
function Write-WARN { Write-Host "[WARN]  $args" -ForegroundColor Yellow }
function Write-Header { Write-Host "`n========================================`n$args`n========================================`n" -ForegroundColor Yellow }

function Require-File {
    param([string]$RelativePath)
    $path = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path $path)) {
        Write-FAIL "Missing required file: $RelativePath"
        exit 1
    }
    Write-OK "Found: $RelativePath"
}

function Test-CommandExists {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Add-OllamaCommonPaths {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Ollama"),
        (Join-Path $env:LOCALAPPDATA "Ollama"),
        (Join-Path $env:USERPROFILE "AppData\Local\Programs\Ollama"),
        "C:\Program Files\Ollama"
    )

    foreach ($path in $candidates) {
        if ((Test-Path $path) -and ($env:Path -notlike "*$path*")) {
            $env:Path = "$path;$env:Path"
            Write-INFO "Added possible Ollama path for current session: $path"
        }
    }
}

function Get-CommandPathOrNull {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { return $null }
    return $cmd.Source
}

function Test-OllamaApi {
    param([string]$Url)
    $tagsUrl = $Url.TrimEnd('/') + "/api/tags"
    try {
        $response = Invoke-WebRequest -Uri $tagsUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        return $response.StatusCode -eq 200
    }
    catch {
        Write-WARN "Cannot reach Ollama API: $tagsUrl"
        Write-WARN "Reason: $($_.Exception.Message)"
        return $false
    }
}

function Ensure-ProjectFolders {
    $folders = @("reports", "results", "logs")
    foreach ($folder in $folders) {
        $path = Join-Path $ProjectRoot $folder
        if (-not (Test-Path $path)) {
            New-Item -ItemType Directory -Path $path | Out-Null
            Write-OK "Created folder: $folder"
        } else {
            Write-OK "Folder exists: $folder"
        }
    }
}

function Get-PythonCreatorCommand {
    if (Test-CommandExists "py") {
        return @{ Cmd = "py"; Args = @("-3", "-m", "venv", $VenvPath); Label = "Python launcher: py -3" }
    }
    if (Test-CommandExists "python") {
        return @{ Cmd = "python"; Args = @("-m", "venv", $VenvPath); Label = "python" }
    }
    return $null
}

function Check-PythonHost {
    Write-Header "Python Check"

    $pyPath = Get-CommandPathOrNull "py"
    $pythonPath = Get-CommandPathOrNull "python"

    if ($pyPath) {
        Write-OK "py launcher found: $pyPath"
        & py -3 --version
    } else {
        Write-WARN "py launcher not found"
    }

    if ($pythonPath) {
        Write-OK "python command found: $pythonPath"
        & python --version
    } else {
        Write-WARN "python command not found"
    }

    if (-not $pyPath -and -not $pythonPath) {
        Write-FAIL "Python 3 not found. Install Python first."
        Write-WARN "Suggested command: winget install -e --id Python.Python.3.12"
        exit 1
    }
}

function Ensure-Venv {
    Write-Header "Virtual Environment Check"

    $creator = Get-PythonCreatorCommand
    if ($null -eq $creator) {
        Write-FAIL "Python not found. Please install Python 3 first."
        exit 1
    }

    if ((Test-Path $VenvPath) -and (-not (Test-Path $PythonVenv))) {
        Write-WARN "Broken virtual environment detected: $VenvPath"
        Write-WARN "Reason: $PythonVenv does not exist"
        Write-WARN "Removing broken virtual environment and rebuilding it..."
        Remove-Item -Recurse -Force $VenvPath
    }

    if (-not (Test-Path $VenvPath)) {
        Write-INFO "Creating virtual environment: $VenvName"
        Write-INFO "Using: $($creator.Label)"
        & $creator.Cmd @($creator.Args)
        if ($LASTEXITCODE -ne 0) {
            Write-FAIL "Failed to create virtual environment. Exit code: $LASTEXITCODE"
            exit $LASTEXITCODE
        }
    } else {
        Write-OK "Virtual environment folder exists: $VenvName"
    }

    if (-not (Test-Path $PythonVenv)) {
        Write-FAIL "Cannot find venv python: $PythonVenv"
        Write-WARN "Manual test command: py -3 -m venv .venv"
        exit 1
    }

    if (-not (Test-Path $PipVenv)) {
        Write-FAIL "Cannot find venv pip: $PipVenv"
        exit 1
    }

    Write-OK "Virtual environment ready"
    & $PythonVenv --version
}

function Install-PythonDependencies {
    Write-Header "Python Dependencies"

    $req = Join-Path $ProjectRoot "requirements.txt"

    Write-INFO "Upgrading pip..."
    & $PythonVenv -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        Write-FAIL "pip upgrade failed. Exit code: $LASTEXITCODE"
        exit $LASTEXITCODE
    }

    Write-INFO "Installing dependencies from requirements.txt..."
    & $PythonVenv -m pip install -r $req
    if ($LASTEXITCODE -ne 0) {
        Write-FAIL "Dependency installation failed. Exit code: $LASTEXITCODE"
        exit $LASTEXITCODE
    }

    Write-OK "Dependencies installed"
}

function Install-OllamaIfNeeded {
    Write-Header "Ollama Check"

    Add-OllamaCommonPaths

    if (Test-CommandExists "ollama") {
        Write-OK "Ollama command found: $(Get-CommandPathOrNull 'ollama')"
        & ollama --version
        return
    }

    Write-WARN "Ollama command not found."

    if (-not $InstallOllama) {
        Write-WARN "Ollama was not installed because -InstallOllama was not provided."
        Write-Host "To install Ollama automatically:" -ForegroundColor Yellow
        Write-Host "  .\install.bat" -ForegroundColor White
        Write-Host "Or install manually from: https://ollama.com/download/windows" -ForegroundColor White
        return
    }

    Write-INFO "Installing Ollama with the official Windows PowerShell installer..."
    Write-WARN "This downloads and executes Ollama's official install.ps1."

    # Do NOT use Invoke-Expression on Invoke-WebRequest.Content here.
    # On some Windows PowerShell versions, .Content can be System.Byte[], which causes:
    # Cannot convert 'System.Byte[]' to the type 'System.String' required by parameter 'Command'.
    $installerPath = Join-Path $env:TEMP "ollama-install.ps1"

    try {
        Write-INFO "Downloading installer to: $installerPath"
        Invoke-WebRequest `
            -Uri "https://ollama.com/install.ps1" `
            -OutFile $installerPath `
            -UseBasicParsing `
            -ErrorAction Stop

        if (-not (Test-Path $installerPath)) {
            Write-FAIL "Failed to download Ollama installer."
            Write-WARN "Manual install page: https://ollama.com/download/windows"
            exit 1
        }

        Write-INFO "Running Ollama installer..."
        powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installerPath
        $code = $LASTEXITCODE

        if ($code -ne 0) {
            Write-FAIL "Ollama installer failed. Exit code: $code"
            Write-WARN "Manual install page: https://ollama.com/download/windows"
            exit $code
        }
    }
    catch {
        Write-FAIL "Ollama installer failed: $($_.Exception.Message)"
        Write-WARN "Manual install page: https://ollama.com/download/windows"
        exit 1
    }

    Write-OK "Ollama installer finished."

    Add-OllamaCommonPaths

    if (-not (Test-CommandExists "ollama")) {
        Write-WARN "Ollama installation may have completed, but current terminal cannot find ollama yet."
        Write-WARN "Trying common install paths one more time..."
        Add-OllamaCommonPaths
    }

    if (-not (Test-CommandExists "ollama")) {
        Write-FAIL "Ollama installed, but ollama.exe is still not available in this CMD session."
        Write-WARN "Close this CMD and open a new one, then run: ollama --version"
        Write-WARN "If still missing, install manually from: https://ollama.com/download/windows"
        exit 1
    }

    Write-OK "Ollama installed and detected: $(Get-CommandPathOrNull 'ollama')"
    & ollama --version
}

function Start-OllamaIfRequested {
    if (-not $StartOllama) { return }

    Write-Header "Ollama Server Start"

    Add-OllamaCommonPaths

    if (-not (Test-CommandExists "ollama")) {
        Write-FAIL "Cannot start Ollama because ollama command is missing."
        exit 1
    }

    if (Test-OllamaApi -Url $OllamaUrl) {
        Write-OK "Ollama API is already reachable: $OllamaUrl"
        return
    }

    Write-INFO "Starting Ollama in a new terminal window..."
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "ollama serve"

    Write-INFO "Waiting for Ollama API to become ready..."
    for ($i = 1; $i -le 45; $i++) {
        Start-Sleep -Seconds 1
        if (Test-OllamaApi -Url $OllamaUrl) {
            Write-OK "Ollama API reachable after start: $OllamaUrl"
            return
        }
        Write-INFO "Waiting for Ollama API... ($i/45)"
    }

    Write-FAIL "Ollama was started, but API did not become reachable in time."
    Write-WARN "Please check the new 'ollama serve' terminal window."
    Write-WARN "Manual check: ollama serve"
    exit 1
}

function Check-OllamaApiIfNeeded {
    if ($SkipOllamaApiCheck) {
        Write-WARN "Skipping Ollama API check because -SkipOllamaApiCheck was provided."
        return
    }

    if (Test-OllamaApi -Url $OllamaUrl) {
        Write-OK "Ollama API reachable: $OllamaUrl"
    } else {
        Write-WARN "Ollama API is not reachable now."
        Write-WARN "Before testing, run one of these:"
        Write-Host "  ollama serve" -ForegroundColor White
        Write-Host "  .\install.bat -StartOllama -NoRun" -ForegroundColor White
    }
}

try {
    Write-Header "LLM Secret Guard Installer"
    Write-INFO "Project root: $ProjectRoot"
    Write-INFO "Mode: Windows CMD -> PowerShell -> Python"

    Set-Location $ProjectRoot

    Write-Header "Project File Check"
    Require-File "requirements.txt"
    Require-File "semi_auto_ollama.py"
    Require-File "src\run_benchmark.py"
    Require-File "src\report_generator.py"
    Require-File "attacks\attacks.json"
    Require-File "test_ollama.ps1"

    Ensure-ProjectFolders
    Check-PythonHost
    Ensure-Venv
    Install-PythonDependencies
    Install-OllamaIfNeeded
    Start-OllamaIfRequested
    Check-OllamaApiIfNeeded

    if ($CheckOnly) {
        Write-OK "Check-only mode completed. No test script was started."
        exit 0
    }

    Write-Header "Install Complete"
    Write-OK "Environment is ready."

    if ($NoRun) {
        Write-INFO "NoRun enabled. Test script was not started."
        Write-Host "Next command:" -ForegroundColor Cyan
        Write-Host "  .\test_ollama.bat" -ForegroundColor White
        exit 0
    }

    Write-WARN "The next step will run the test script."
    Write-WARN "If Ollama API is not reachable, test_ollama.ps1 will stop and show the reason."
    Write-Host ""

    & $TestScript -VenvName $VenvName -OllamaUrl $OllamaUrl
    exit $LASTEXITCODE
}
catch {
    Write-FAIL "Unhandled installer error: $($_.Exception.Message)"
    exit 1
}
