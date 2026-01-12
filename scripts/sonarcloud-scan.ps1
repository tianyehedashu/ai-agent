# ==============================================================================
# SonarCloud 扫描与问题报告脚本 (Windows PowerShell)
# ==============================================================================
# 使用方式:
#   $env:SONAR_TOKEN = "your-token"
#   .\scripts\sonarcloud-scan.ps1 [-Target backend|frontend|all] [-SkipScan] [-ExportFormat json|csv|html]
#
# 参数说明:
#   -Target       扫描目标: backend, frontend, all (默认: all)
#   -SkipScan     跳过扫描，只下载问题报告
#   -ExportFormat 导出格式: json, csv, html (默认: json)
#   -Organization SonarCloud 组织名 (默认: 从 git remote 获取)
# ==============================================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("backend", "frontend", "all", "help")]
    [string]$Target = "all",
    
    [switch]$SkipScan,
    
    [ValidateSet("json", "csv", "html")]
    [string]$ExportFormat = "json",
    
    [string]$Organization = ""
)

$ErrorActionPreference = "Stop"

# SonarCloud API 基础 URL
$SONARCLOUD_API = "https://sonarcloud.io/api"

# 颜色输出函数
function Write-Info { param($msg) Write-Host $msg -ForegroundColor Cyan }
function Write-Success { param($msg) Write-Host $msg -ForegroundColor Green }
function Write-Warning { param($msg) Write-Host $msg -ForegroundColor Yellow }
function Write-Error { param($msg) Write-Host $msg -ForegroundColor Red }

# 检查环境
function Test-Environment {
    if (-not $env:SONAR_TOKEN) {
        Write-Error "错误: SONAR_TOKEN 环境变量未设置"
        Write-Host '请设置: $env:SONAR_TOKEN = "your-sonarcloud-token"'
        exit 1
    }
    
    # 检查 sonar-scanner
    if (-not $SkipScan -and -not (Get-Command sonar-scanner -ErrorAction SilentlyContinue)) {
        Write-Error "错误: sonar-scanner 未安装"
        Write-Host "请安装: https://docs.sonarqube.org/latest/analysis/scan/sonarscanner/"
        exit 1
    }
}

# 获取组织名
function Get-Organization {
    if ($Organization) {
        return $Organization
    }
    
    # 尝试从 git remote 获取
    try {
        $remoteUrl = git remote get-url origin 2>$null
        if ($remoteUrl -match "github\.com[:/]([^/]+)/") {
            return $Matches[1]
        }
    } catch {}
    
    Write-Warning "无法自动获取组织名，请使用 -Organization 参数指定"
    return "your-org"
}

# 运行后端扫描
function Invoke-BackendScan {
    param([string]$Org)
    
    Write-Info "=========================================="
    Write-Info "  扫描后端 (Python) - SonarCloud"
    Write-Info "=========================================="
    
    Push-Location backend
    
    try {
        # 生成覆盖率报告
        Write-Info ">> 运行测试并生成覆盖率报告..."
        python -m pytest --cov --cov-report=xml:coverage.xml --junitxml=test-results.xml -q 2>$null
        
        # 运行 SonarCloud 扫描
        Write-Info ">> 运行 SonarCloud 扫描..."
        sonar-scanner `
            "-Dsonar.host.url=https://sonarcloud.io" `
            "-Dsonar.organization=$Org" `
            "-Dsonar.projectKey=${Org}_ai-agent-backend" `
            "-Dsonar.token=$env:SONAR_TOKEN"
        
        Write-Success "✓ 后端扫描完成"
    }
    finally {
        Pop-Location
    }
}

# 运行前端扫描
function Invoke-FrontendScan {
    param([string]$Org)
    
    Write-Info "=========================================="
    Write-Info "  扫描前端 (TypeScript) - SonarCloud"
    Write-Info "=========================================="
    
    Push-Location frontend
    
    try {
        # 安装依赖
        if (-not (Test-Path "node_modules")) {
            Write-Info ">> 安装依赖..."
            npm ci
        }
        
        # 生成覆盖率报告
        Write-Info ">> 运行测试并生成覆盖率报告..."
        npm run test:coverage 2>$null
        
        # 运行 SonarCloud 扫描
        Write-Info ">> 运行 SonarCloud 扫描..."
        sonar-scanner `
            "-Dsonar.host.url=https://sonarcloud.io" `
            "-Dsonar.organization=$Org" `
            "-Dsonar.projectKey=${Org}_ai-agent-frontend" `
            "-Dsonar.token=$env:SONAR_TOKEN"
        
        Write-Success "✓ 前端扫描完成"
    }
    finally {
        Pop-Location
    }
}

# 调用 SonarCloud API
function Invoke-SonarCloudAPI {
    param(
        [string]$Endpoint,
        [hashtable]$Params = @{}
    )
    
    $uri = "$SONARCLOUD_API/$Endpoint"
    if ($Params.Count -gt 0) {
        $query = ($Params.GetEnumerator() | ForEach-Object { "$($_.Key)=$([uri]::EscapeDataString($_.Value))" }) -join "&"
        $uri = "$uri`?$query"
    }
    
    $headers = @{
        "Authorization" = "Bearer $env:SONAR_TOKEN"
    }
    
    try {
        $response = Invoke-RestMethod -Uri $uri -Headers $headers -Method Get
        return $response
    }
    catch {
        Write-Error "API 调用失败: $_"
        return $null
    }
}

# 获取项目问题
function Get-ProjectIssues {
    param(
        [string]$ProjectKey,
        [int]$PageSize = 100
    )
    
    Write-Info ">> 获取项目问题: $ProjectKey"
    
    $allIssues = @()
    $page = 1
    $totalPages = 1
    
    do {
        $params = @{
            "componentKeys" = $ProjectKey
            "ps" = $PageSize
            "p" = $page
            "statuses" = "OPEN,CONFIRMED,REOPENED"
        }
        
        $response = Invoke-SonarCloudAPI -Endpoint "issues/search" -Params $params
        
        if ($response) {
            $allIssues += $response.issues
            $totalPages = [math]::Ceiling($response.total / $PageSize)
            Write-Info "   页 $page/$totalPages, 已获取 $($allIssues.Count)/$($response.total) 个问题"
        }
        
        $page++
    } while ($page -le $totalPages -and $page -le 10)  # 最多获取 10 页
    
    return $allIssues
}

# 获取项目指标
function Get-ProjectMetrics {
    param([string]$ProjectKey)
    
    $params = @{
        "component" = $ProjectKey
        "metricKeys" = "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,ncloc,sqale_rating,reliability_rating,security_rating"
    }
    
    $response = Invoke-SonarCloudAPI -Endpoint "measures/component" -Params $params
    
    if ($response -and $response.component.measures) {
        $metrics = @{}
        foreach ($measure in $response.component.measures) {
            $metrics[$measure.metric] = $measure.value
        }
        return $metrics
    }
    
    return @{}
}

# 导出为 JSON
function Export-AsJson {
    param($Data, $FilePath)
    $Data | ConvertTo-Json -Depth 10 | Out-File -FilePath $FilePath -Encoding UTF8
    Write-Success "✓ 已导出到: $FilePath"
}

# 导出为 CSV
function Export-AsCsv {
    param($Issues, $FilePath)
    
    $csvData = $Issues | ForEach-Object {
        [PSCustomObject]@{
            Key = $_.key
            Severity = $_.severity
            Type = $_.type
            Component = $_.component
            Line = $_.line
            Message = $_.message
            Status = $_.status
            Effort = $_.effort
            Tags = ($_.tags -join ", ")
        }
    }
    
    $csvData | Export-Csv -Path $FilePath -NoTypeInformation -Encoding UTF8
    Write-Success "✓ 已导出到: $FilePath"
}

# 导出为 HTML 报告
function Export-AsHtml {
    param($Report, $FilePath)
    
    $html = @"
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SonarCloud 代码质量报告</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 2rem; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #58a6ff; margin-bottom: 1.5rem; border-bottom: 1px solid #30363d; padding-bottom: 1rem; }
        h2 { color: #8b949e; margin: 1.5rem 0 1rem; font-size: 1.2rem; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .metric-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.5rem; text-align: center; }
        .metric-value { font-size: 2rem; font-weight: bold; color: #58a6ff; }
        .metric-label { color: #8b949e; margin-top: 0.5rem; }
        .issues-table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        .issues-table th, .issues-table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #30363d; }
        .issues-table th { background: #161b22; color: #8b949e; font-weight: 600; }
        .issues-table tr:hover { background: #161b22; }
        .severity-BLOCKER, .severity-CRITICAL { color: #f85149; }
        .severity-MAJOR { color: #f0883e; }
        .severity-MINOR { color: #d29922; }
        .severity-INFO { color: #8b949e; }
        .type-BUG { background: #f8514933; color: #f85149; padding: 0.25rem 0.5rem; border-radius: 4px; }
        .type-VULNERABILITY { background: #f0883e33; color: #f0883e; padding: 0.25rem 0.5rem; border-radius: 4px; }
        .type-CODE_SMELL { background: #d2992233; color: #d29922; padding: 0.25rem 0.5rem; border-radius: 4px; }
        .summary { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; }
        .timestamp { color: #8b949e; font-size: 0.875rem; margin-top: 2rem; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 SonarCloud 代码质量报告</h1>
        <p class="summary">生成时间: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")</p>
"@
    
    foreach ($project in $Report.projects) {
        $html += @"
        <h2>📦 $($project.name)</h2>
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-value">$($project.metrics.bugs ?? 'N/A')</div>
                <div class="metric-label">🐛 Bugs</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">$($project.metrics.vulnerabilities ?? 'N/A')</div>
                <div class="metric-label">🔓 漏洞</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">$($project.metrics.code_smells ?? 'N/A')</div>
                <div class="metric-label">🧹 代码异味</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">$($project.metrics.coverage ?? 'N/A')%</div>
                <div class="metric-label">📊 覆盖率</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">$($project.metrics.duplicated_lines_density ?? 'N/A')%</div>
                <div class="metric-label">📋 重复率</div>
            </div>
        </div>
        
        <h3>问题列表 ($($project.issues.Count) 个)</h3>
        <table class="issues-table">
            <thead>
                <tr>
                    <th>严重程度</th>
                    <th>类型</th>
                    <th>文件</th>
                    <th>行号</th>
                    <th>描述</th>
                </tr>
            </thead>
            <tbody>
"@
        
        foreach ($issue in $project.issues | Select-Object -First 50) {
            $component = $issue.component -replace ".*:", ""
            $html += @"
                <tr>
                    <td class="severity-$($issue.severity)">$($issue.severity)</td>
                    <td><span class="type-$($issue.type)">$($issue.type)</span></td>
                    <td>$component</td>
                    <td>$($issue.line ?? '-')</td>
                    <td>$([System.Web.HttpUtility]::HtmlEncode($issue.message))</td>
                </tr>
"@
        }
        
        $html += @"
            </tbody>
        </table>
"@
    }
    
    $html += @"
        <p class="timestamp">由 SonarCloud 扫描脚本生成</p>
    </div>
</body>
</html>
"@
    
    Add-Type -AssemblyName System.Web
    $html | Out-File -FilePath $FilePath -Encoding UTF8
    Write-Success "✓ 已导出到: $FilePath"
}

# 下载问题报告
function Get-IssuesReport {
    param([string]$Org)
    
    Write-Info "=========================================="
    Write-Info "  下载 SonarCloud 问题报告"
    Write-Info "=========================================="
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $reportDir = "reports/sonarcloud_$timestamp"
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
    
    $report = @{
        timestamp = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        organization = $Org
        projects = @()
    }
    
    $projectKeys = @(
        @{ key = "${Org}_ai-agent-backend"; name = "Backend (Python)" },
        @{ key = "${Org}_ai-agent-frontend"; name = "Frontend (TypeScript)" }
    )
    
    foreach ($proj in $projectKeys) {
        Write-Info ""
        Write-Info "处理项目: $($proj.name)"
        
        $issues = Get-ProjectIssues -ProjectKey $proj.key
        $metrics = Get-ProjectMetrics -ProjectKey $proj.key
        
        $projectReport = @{
            name = $proj.name
            key = $proj.key
            metrics = $metrics
            issues = $issues
            summary = @{
                total = $issues.Count
                byType = $issues | Group-Object -Property type | ForEach-Object { @{ $_.Name = $_.Count } }
                bySeverity = $issues | Group-Object -Property severity | ForEach-Object { @{ $_.Name = $_.Count } }
            }
        }
        
        $report.projects += $projectReport
        
        # 输出摘要
        Write-Info "   - 总问题数: $($issues.Count)"
        Write-Info "   - Bugs: $($metrics.bugs ?? 'N/A')"
        Write-Info "   - 漏洞: $($metrics.vulnerabilities ?? 'N/A')"
        Write-Info "   - 代码异味: $($metrics.code_smells ?? 'N/A')"
        Write-Info "   - 覆盖率: $($metrics.coverage ?? 'N/A')%"
    }
    
    # 导出报告
    Write-Info ""
    Write-Info ">> 导出报告..."
    
    switch ($ExportFormat) {
        "json" {
            Export-AsJson -Data $report -FilePath "$reportDir/report.json"
        }
        "csv" {
            foreach ($proj in $report.projects) {
                $fileName = $proj.key -replace "[^a-zA-Z0-9]", "_"
                Export-AsCsv -Issues $proj.issues -FilePath "$reportDir/${fileName}_issues.csv"
            }
        }
        "html" {
            Export-AsHtml -Report $report -FilePath "$reportDir/report.html"
        }
    }
    
    Write-Success ""
    Write-Success "=========================================="
    Write-Success "  报告已生成: $reportDir"
    Write-Success "=========================================="
    
    return $report
}

# 显示帮助
function Show-Help {
    Write-Host @"

SonarCloud 扫描与问题报告脚本

使用方式:
  .\sonarcloud-scan.ps1 [-Target <选项>] [-SkipScan] [-ExportFormat <格式>]

参数:
  -Target        扫描目标
                 backend   - 只扫描后端
                 frontend  - 只扫描前端
                 all       - 扫描全部 (默认)

  -SkipScan      跳过扫描，只下载问题报告

  -ExportFormat  导出格式
                 json - JSON 格式 (默认)
                 csv  - CSV 表格格式
                 html - HTML 可视化报告

  -Organization  SonarCloud 组织名 (默认从 git remote 获取)

示例:
  # 完整扫描并生成 JSON 报告
  .\sonarcloud-scan.ps1

  # 只扫描后端
  .\sonarcloud-scan.ps1 -Target backend

  # 跳过扫描，只下载问题并生成 HTML 报告
  .\sonarcloud-scan.ps1 -SkipScan -ExportFormat html

  # 指定组织名
  .\sonarcloud-scan.ps1 -Organization myorg -SkipScan

环境变量:
  SONAR_TOKEN    SonarCloud 访问令牌 (必需)

"@
}

# 主函数
function Main {
    if ($Target -eq "help") {
        Show-Help
        return
    }
    
    Test-Environment
    $org = Get-Organization
    
    Write-Info "组织: $org"
    Write-Info ""
    
    # 运行扫描
    if (-not $SkipScan) {
        switch ($Target) {
            "backend" {
                Invoke-BackendScan -Org $org
            }
            "frontend" {
                Invoke-FrontendScan -Org $org
            }
            "all" {
                Invoke-BackendScan -Org $org
                Invoke-FrontendScan -Org $org
            }
        }
        
        Write-Info ""
        Write-Warning "等待 SonarCloud 处理结果 (30秒)..."
        Start-Sleep -Seconds 30
    }
    
    # 下载问题报告
    Get-IssuesReport -Org $org
}

Main
