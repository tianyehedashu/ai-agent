# ==============================================================================
# SonarQube 本地扫描脚本 (Windows PowerShell)
# ==============================================================================
# 使用方式:
#   $env:SONAR_HOST_URL = "http://localhost:9000"
#   $env:SONAR_TOKEN = "your-token"
#   .\scripts\sonar-scan.ps1 [-Target backend|frontend|all]
# ==============================================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("backend", "frontend", "all", "help")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"

# 检查环境变量
function Test-Environment {
    if (-not $env:SONAR_HOST_URL) {
        Write-Host "错误: SONAR_HOST_URL 环境变量未设置" -ForegroundColor Red
        Write-Host '请设置: $env:SONAR_HOST_URL = "http://your-sonar-server:9000"'
        exit 1
    }

    if (-not $env:SONAR_TOKEN) {
        Write-Host "错误: SONAR_TOKEN 环境变量未设置" -ForegroundColor Red
        Write-Host '请设置: $env:SONAR_TOKEN = "your-token"'
        exit 1
    }
}

# 检查 sonar-scanner
function Test-Scanner {
    if (-not (Get-Command sonar-scanner -ErrorAction SilentlyContinue)) {
        Write-Host "错误: sonar-scanner 未安装" -ForegroundColor Red
        Write-Host "请安装: https://docs.sonarqube.org/latest/analysis/scan/sonarscanner/"
        exit 1
    }
}

# 扫描后端
function Invoke-BackendScan {
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host "  扫描后端 (Python)" -ForegroundColor Blue
    Write-Host "========================================" -ForegroundColor Blue

    Push-Location backend

    try {
        # 生成覆盖率报告
        Write-Host ">> 运行测试并生成覆盖率报告..." -ForegroundColor Yellow
        python -m pytest --cov --cov-report=xml:coverage.xml --junitxml=test-results.xml 2>$null

        # 运行 SonarQube 扫描
        Write-Host ">> 运行 SonarQube 扫描..." -ForegroundColor Yellow
        sonar-scanner `
            "-Dsonar.host.url=$env:SONAR_HOST_URL" `
            "-Dsonar.token=$env:SONAR_TOKEN"

        Write-Host "✓ 后端扫描完成" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}

# 扫描前端
function Invoke-FrontendScan {
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host "  扫描前端 (TypeScript)" -ForegroundColor Blue
    Write-Host "========================================" -ForegroundColor Blue

    Push-Location frontend

    try {
        # 安装依赖
        if (-not (Test-Path "node_modules")) {
            Write-Host ">> 安装依赖..." -ForegroundColor Yellow
            npm ci
        }

        # 生成覆盖率报告
        Write-Host ">> 运行测试并生成覆盖率报告..." -ForegroundColor Yellow
        npm run test:coverage 2>$null

        # 生成 ESLint 报告
        Write-Host ">> 生成 ESLint 报告..." -ForegroundColor Yellow
        npm run lint -- -f json -o eslint-report.json 2>$null

        # 运行 SonarQube 扫描
        Write-Host ">> 运行 SonarQube 扫描..." -ForegroundColor Yellow
        sonar-scanner `
            "-Dsonar.host.url=$env:SONAR_HOST_URL" `
            "-Dsonar.token=$env:SONAR_TOKEN"

        Write-Host "✓ 前端扫描完成" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}

# 显示帮助
function Show-Help {
    Write-Host "AI Agent SonarQube 扫描脚本"
    Write-Host ""
    Write-Host "使用方式: .\sonar-scan.ps1 [-Target <选项>]"
    Write-Host ""
    Write-Host "选项:"
    Write-Host "  backend   只扫描后端 (Python)"
    Write-Host "  frontend  只扫描前端 (TypeScript)"
    Write-Host "  all       扫描全部 (默认)"
    Write-Host "  help      显示此帮助"
    Write-Host ""
    Write-Host "环境变量:"
    Write-Host "  SONAR_HOST_URL  SonarQube 服务器地址"
    Write-Host "  SONAR_TOKEN     访问令牌"
}

# 主函数
switch ($Target) {
    "help" {
        Show-Help
    }
    "backend" {
        Test-Environment
        Test-Scanner
        Invoke-BackendScan
    }
    "frontend" {
        Test-Environment
        Test-Scanner
        Invoke-FrontendScan
    }
    "all" {
        Test-Environment
        Test-Scanner
        Invoke-BackendScan
        Invoke-FrontendScan
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "  全部扫描完成!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
    }
}
