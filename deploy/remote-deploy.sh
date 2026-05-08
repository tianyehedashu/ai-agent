#!/usr/bin/env bash
# =============================================================================
# AI Agent 远程部署脚本
# 从本地将项目部署到远程服务器 (web01)
# 支持 Windows (Git Bash/WSL) 和 Linux/macOS
#
# 用法:
#   bash deploy/remote-deploy.sh                  # 完整部署
#   bash deploy/remote-deploy.sh --sync-only      # 仅同步代码
#   bash deploy/remote-deploy.sh --rebuild        # 强制重新构建
#   bash deploy/remote-deploy.sh --status         # 查看远程服务状态
#   bash deploy/remote-deploy.sh --logs           # 查看远程服务日志
#   bash deploy/remote-deploy.sh --stop           # 停止远程服务
#   bash deploy/remote-deploy.sh --setup          # 首次环境初始化
# =============================================================================
set -euo pipefail

# ─── 配置 ─────────────────────────────────────────────────────
REMOTE_HOST="web01"
REMOTE_DIR="/home/leo/ai-agent"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ─── SSH 辅助 ─────────────────────────────────────────────────
remote_exec() {
    ssh "$REMOTE_HOST" "$@"
}

# ─── 连接测试 ─────────────────────────────────────────────────
test_connection() {
    log_info "测试 SSH 连接到 $REMOTE_HOST..."
    if ! ssh -o ConnectTimeout=10 "$REMOTE_HOST" "echo ok" &>/dev/null; then
        log_error "无法连接到 $REMOTE_HOST，请检查 SSH 配置"
        exit 1
    fi
    log_ok "SSH 连接成功"
}

# ─── 首次环境初始化 ──────────────────────────────────────────
setup_remote() {
    test_connection

    log_info "初始化远程服务器环境..."

    remote_exec bash <<'SETUP_EOF'
set -euo pipefail

echo "[INFO] 检查 Docker..."
if ! command -v docker &>/dev/null; then
    echo "[INFO] 安装 Docker..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
    echo "[WARN] Docker 已安装，需要重新登录以生效 docker 组权限"
fi

if ! docker compose version &>/dev/null; then
    echo "[INFO] 安装 Docker Compose V2 插件..."
    sudo apt-get update && sudo apt-get install -y docker-compose-plugin
fi

echo "[INFO] 检查 rsync..."
if ! command -v rsync &>/dev/null; then
    sudo apt-get update && sudo apt-get install -y rsync
fi

echo "[OK] 远程环境就绪"
docker --version
docker compose version
SETUP_EOF

    log_ok "远程环境初始化完成"
}

# ─── 同步代码 ─────────────────────────────────────────────────
sync_code() {
    log_info "同步代码到 $REMOTE_HOST:$REMOTE_DIR ..."

    remote_exec "mkdir -p $REMOTE_DIR"

    if command -v rsync &>/dev/null; then
        log_info "使用 rsync 同步..."
        rsync -avz --delete \
            --exclude '.git' \
            --exclude 'node_modules' \
            --exclude '.venv' \
            --exclude '__pycache__' \
            --exclude '*.pyc' \
            --exclude '.pytest_cache' \
            --exclude '.mypy_cache' \
            --exclude '.ruff_cache' \
            --exclude 'frontend/dist' \
            --exclude 'htmlcov' \
            --exclude 'coverage.xml' \
            --exclude '.coverage' \
            --exclude 'backend/workspace' \
            --exclude 'backend/data' \
            --exclude '.cursor' \
            --exclude '.vscode' \
            --exclude 'agent-transcripts' \
            --exclude 'terminals' \
            -e ssh \
            "$PROJECT_DIR/" "$REMOTE_HOST:$REMOTE_DIR/"
    else
        log_info "使用 tar + scp 同步（rsync 不可用）..."
        local tmp_tar="/tmp/ai-agent-deploy-$(date +%s).tar.gz"

        cd "$PROJECT_DIR"
        tar czf "$tmp_tar" \
            --exclude='.git' \
            --exclude='node_modules' \
            --exclude='.venv' \
            --exclude='__pycache__' \
            --exclude='*.pyc' \
            --exclude='.pytest_cache' \
            --exclude='.mypy_cache' \
            --exclude='.ruff_cache' \
            --exclude='frontend/dist' \
            --exclude='htmlcov' \
            --exclude='coverage.xml' \
            --exclude='.coverage' \
            --exclude='backend/workspace' \
            --exclude='backend/data' \
            --exclude='.cursor' \
            --exclude='.vscode' \
            --exclude='agent-transcripts' \
            --exclude='terminals' \
            .

        log_info "上传压缩包 ($(du -h "$tmp_tar" | cut -f1))..."
        scp "$tmp_tar" "$REMOTE_HOST:/tmp/ai-agent-deploy.tar.gz"

        log_info "远程解压..."
        remote_exec bash <<EXTRACT_EOF
set -euo pipefail
mkdir -p $REMOTE_DIR
cd $REMOTE_DIR
tar xzf /tmp/ai-agent-deploy.tar.gz
rm -f /tmp/ai-agent-deploy.tar.gz
EXTRACT_EOF

        rm -f "$tmp_tar"
    fi

    log_ok "代码同步完成"
}

# ─── 远程部署 ─────────────────────────────────────────────────
remote_deploy() {
    local deploy_args="${1:-}"

    log_info "在远程服务器上执行部署..."

    remote_exec bash <<DEPLOY_EOF
set -euo pipefail
cd $REMOTE_DIR

chmod +x deploy/deploy.sh
./deploy/deploy.sh $deploy_args
DEPLOY_EOF

    log_ok "远程部署完成"
}

# ─── 远程状态 ─────────────────────────────────────────────────
remote_status() {
    test_connection
    remote_exec bash <<EOF
cd $REMOTE_DIR 2>/dev/null || { echo "项目目录不存在"; exit 0; }
docker compose -f docker-compose.prod.yml --env-file .env.production ps 2>/dev/null || echo "服务未运行"
EOF
}

remote_logs() {
    test_connection
    remote_exec bash <<EOF
cd $REMOTE_DIR
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f --tail=100
EOF
}

remote_stop() {
    test_connection
    log_info "停止远程服务..."
    remote_exec bash <<EOF
cd $REMOTE_DIR
docker compose -f docker-compose.prod.yml --env-file .env.production down
EOF
    log_ok "远程服务已停止"
}

# ─── 完整远程部署 ──────────────────────────────────────────────
full_remote_deploy() {
    local deploy_args="${1:-}"

    test_connection
    sync_code
    remote_deploy "$deploy_args"
}

# ─── 主入口 ─────────────────────────────────────────────────
case "${1:-}" in
    --setup)
        setup_remote
        ;;
    --sync-only)
        test_connection
        sync_code
        ;;
    --rebuild)
        full_remote_deploy "--rebuild"
        ;;
    --status)
        remote_status
        ;;
    --logs)
        remote_logs
        ;;
    --stop)
        remote_stop
        ;;
    --help|-h)
        head -15 "$0" | tail -13
        ;;
    *)
        full_remote_deploy
        ;;
esac
