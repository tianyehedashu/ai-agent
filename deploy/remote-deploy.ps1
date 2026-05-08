<#
.SYNOPSIS
    AI Agent remote deploy script (PowerShell)
.DESCRIPTION
    Deploy project from Windows to remote server (web01)
.PARAMETER Action
    deploy      - Full deploy (sync + build + start)
    rebuild     - Force rebuild and deploy
    build-base  - Rebuild backend base image (gcc, uv) only
    sync        - Sync code only
    quick       - Quick deploy (sync code + restart, skip build)
    status      - Show remote service status
    logs        - Show remote service logs
    stop        - Stop remote services
    setup       - First-time environment setup
#>

param(
    [ValidateSet("deploy", "rebuild", "build-base", "sync", "quick", "status", "logs", "stop", "setup")]
    [string]$Action = "deploy"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$REMOTE_HOST = "web01"
$REMOTE_DIR = "/home/leo/ai-agent"
$SCRIPT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_DIR = Split-Path -Parent $SCRIPT_ROOT

function Log-Info  { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Log-Ok    { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Log-Warn  { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Log-Error { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }

function Test-SSHConnection {
    Log-Info "Testing SSH connection to $REMOTE_HOST..."
    $null = ssh -o ConnectTimeout=10 $REMOTE_HOST "echo ok" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Log-Error "Cannot connect to $REMOTE_HOST"
        exit 1
    }
    Log-Ok "SSH connected"
}

function Initialize-Remote {
    Test-SSHConnection
    Log-Info "Initializing remote environment..."
    ssh $REMOTE_HOST "bash -c 'set -euo pipefail; if ! command -v docker &>/dev/null; then curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker \$USER; fi; if ! docker compose version &>/dev/null; then sudo apt-get update && sudo apt-get install -y docker-compose-plugin; fi; echo [OK] Remote environment ready; docker --version; docker compose version'"
    Log-Ok "Remote environment initialized"
}

function Sync-Code {
    Log-Info "Syncing code to ${REMOTE_HOST}:${REMOTE_DIR}..."

    ssh $REMOTE_HOST "mkdir -p $REMOTE_DIR"

    $excludes = @(
        '.git', 'node_modules', '.venv', '__pycache__',
        '.pytest_cache', '.mypy_cache', '.ruff_cache', 'frontend/dist',
        'htmlcov', 'coverage.xml', '.coverage', 'backend/workspace',
        'backend/data', '.cursor', '.vscode', 'agent-transcripts', 'terminals',
        'backend/tests', 'frontend/coverage', '.scannerwork',
        'backend/.env', '.env.production'
    )

    $tarFile = Join-Path $env:TEMP "ai-agent-deploy.tar.gz"

    Log-Info "Creating archive..."

    Push-Location $PROJECT_DIR
    try {
        $argList = @("czf", $tarFile)
        foreach ($ex in $excludes) {
            $argList += "--exclude=$ex"
        }
        $argList += "."

        $proc = Start-Process -FilePath "tar" -ArgumentList $argList -NoNewWindow -Wait -PassThru
        if ($proc.ExitCode -ne 0) {
            throw "tar failed with exit code $($proc.ExitCode)"
        }
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path $tarFile)) {
        Log-Error "Archive creation failed"
        exit 1
    }

    $sizeMB = [math]::Round((Get-Item $tarFile).Length / 1MB, 1)
    Log-Info "Uploading archive (${sizeMB}MB)..."

    scp $tarFile "${REMOTE_HOST}:/tmp/ai-agent-deploy.tar.gz" 2>$null
    $remoteSize = ssh $REMOTE_HOST "stat -c%s /tmp/ai-agent-deploy.tar.gz 2>/dev/null || echo 0"
    $localSize = (Get-Item $tarFile).Length.ToString()

    if ($remoteSize.Trim() -ne $localSize) {
        Log-Warn "scp transfer incomplete, using pipe fallback..."
        $tarWin = $tarFile -replace '/', '\'
        cmd /c "type `"$tarWin`" | ssh $REMOTE_HOST `"cat > /tmp/ai-agent-deploy.tar.gz`""
        if ($LASTEXITCODE -ne 0) {
            Log-Error "Upload failed"
            exit 1
        }
    }

    Log-Info "Extracting on remote..."
    ssh $REMOTE_HOST "set -euo pipefail && mkdir -p $REMOTE_DIR && cd $REMOTE_DIR && tar xzf /tmp/ai-agent-deploy.tar.gz && rm -f /tmp/ai-agent-deploy.tar.gz && find . -maxdepth 3 \( -name '*.sh' -o -name '*.yml' -o -name '*.yaml' -o -name 'Dockerfile*' -o -name '.env*' -o -name '*.toml' -o -name '*.conf' \) -exec sed -i 's/\r$//' {} + && chmod +x deploy/*.sh"

    Remove-Item -Force $tarFile -ErrorAction SilentlyContinue
    Log-Ok "Code sync completed"
}

function Invoke-RemoteDeploy {
    param([string]$DeployArgs = "")

    Log-Info "Executing deploy on remote server..."
    ssh $REMOTE_HOST "cd $REMOTE_DIR && chmod +x deploy/deploy.sh && ./deploy/deploy.sh $DeployArgs"
    Log-Ok "Remote deploy completed"
}

function Show-RemoteStatus {
    Test-SSHConnection
    ssh $REMOTE_HOST "cd $REMOTE_DIR 2>/dev/null && docker compose -f docker-compose.prod.yml --env-file .env.production ps 2>/dev/null || echo 'Services not running'"
}

function Show-RemoteLogs {
    Test-SSHConnection
    ssh $REMOTE_HOST "cd $REMOTE_DIR && docker compose -f docker-compose.prod.yml --env-file .env.production logs -f --tail=100"
}

function Stop-RemoteServices {
    Test-SSHConnection
    Log-Info "Stopping remote services..."
    ssh $REMOTE_HOST "cd $REMOTE_DIR && docker compose -f docker-compose.prod.yml --env-file .env.production down"
    Log-Ok "Remote services stopped"
}

function Start-FullDeploy {
    param([string]$DeployArgs = "")
    Test-SSHConnection
    Sync-Code
    Invoke-RemoteDeploy -DeployArgs $DeployArgs
}

switch ($Action) {
    "deploy"      { Start-FullDeploy }
    "rebuild"     { Start-FullDeploy -DeployArgs "--rebuild" }
    "build-base"  { Start-FullDeploy -DeployArgs "--build-base" }
    "sync"        { Test-SSHConnection; Sync-Code }
    "quick"       { Start-FullDeploy -DeployArgs "--quick" }
    "status"      { Show-RemoteStatus }
    "logs"        { Show-RemoteLogs }
    "stop"        { Stop-RemoteServices }
    "setup"       { Initialize-Remote }
}
