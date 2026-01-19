# AI Agent 沙箱镜像构建脚本 (PowerShell)

param(
    [string]$ImageName = "ai-agent-sandbox",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dockerfile = Join-Path $ScriptDir "Dockerfile"
$FullImage = "${ImageName}:${ImageTag}"

Write-Host "Building ${FullImage}..." -ForegroundColor Cyan
Write-Host "Dockerfile: ${Dockerfile}" -ForegroundColor Gray

Set-Location $ScriptDir

docker build `
    -t $FullImage `
    -f $Dockerfile `
    .

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Build complete!" -ForegroundColor Green
    Write-Host "   Image: ${FullImage}" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To test:" -ForegroundColor Cyan
    Write-Host "   docker run -it --rm ${FullImage} bash"
    Write-Host ""
    Write-Host "To push (if needed):" -ForegroundColor Cyan
    Write-Host "   docker tag ${FullImage} <registry>/${FullImage}"
    Write-Host "   docker push <registry>/${FullImage}"
} else {
    Write-Host "❌ Build failed!" -ForegroundColor Red
    exit 1
}
