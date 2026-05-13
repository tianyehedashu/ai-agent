#Requires -Version 5.1
<#
.SYNOPSIS
  本地 E2E：启动 Docker 基础服务、执行迁移、后台启动 uvicorn，再跑 pytest e2e。

.DESCRIPTION
  前置：已安装 Docker Desktop；backend\.venv 已就绪；backend\.env 中已配置可用的 LLM Key（与开发环境一致）。

  默认仅跑 ``e2e and not slow``。加 ``-Slow`` 跑全部 e2e。

  覆盖 API 地址：``$env:E2E_API_BASE_URL = 'http://127.0.0.1:8000'``（须与 uvicorn 一致）。

.PARAMETER Slow
  包含标记为 slow 的 E2E 用例。
#>
param(
    [switch]$Slow
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

Write-Host "==> docker compose: db redis qdrant" -ForegroundColor Cyan
docker compose up -d db redis qdrant

Write-Host "==> wait for Postgres health" -ForegroundColor Cyan
Start-Sleep -Seconds 10

$backend = Join-Path $RepoRoot "backend"
Set-Location $backend

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Error "缺少 backend\.venv。请在 backend 目录执行: uv sync 或创建 venv 并 pip install -e `".[dev]`""
}

$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_agent"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:APP_ENV = "development"
$env:PYTHONUNBUFFERED = "1"
if (-not $env:E2E_API_BASE_URL) {
    $env:E2E_API_BASE_URL = "http://127.0.0.1:8000"
}

Write-Host "==> alembic upgrade head" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m alembic upgrade head

Write-Host "==> uvicorn bootstrap.main:app (background)" -ForegroundColor Cyan
$uvicorn = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -WorkingDirectory $backend `
    -ArgumentList @("-m", "uvicorn", "bootstrap.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -PassThru -WindowStyle Hidden

try {
    $deadline = (Get-Date).AddMinutes(3)
    $ok = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -eq 200) {
                $ok = $true
                break
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $ok) {
        throw "健康检查超时。请检查 .env、数据库与端口 8000 是否被占用。"
    }

    Write-Host "==> pytest e2e" -ForegroundColor Cyan
    if ($Slow) {
        & .\.venv\Scripts\python.exe -m pytest tests/e2e -m e2e -v --tb=short
    }
    else {
        & .\.venv\Scripts\python.exe -m pytest tests/e2e -m "e2e and not slow" -v --tb=short
    }
    exit $LASTEXITCODE
}
finally {
    if ($null -ne $uvicorn -and -not $uvicorn.HasExited) {
        Stop-Process -Id $uvicorn.Id -Force -ErrorAction SilentlyContinue
    }
}
