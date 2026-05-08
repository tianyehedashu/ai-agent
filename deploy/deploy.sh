#!/usr/bin/env bash
# =============================================================================
# AI Agent 一键部署脚本
# 用法:
#   ./deploy/deploy.sh              # 标准部署（构建 + 迁移 + 启动）
#   ./deploy/deploy.sh --rebuild    # 强制重新构建镜像（--no-cache）
#   ./deploy/deploy.sh --build-base # 构建/更新后端 base 镜像（首次或升级时执行）
#   ./deploy/deploy.sh --quick      # 快速部署（跳过构建，仅重启应用）
#   ./deploy/deploy.sh --restart    # 仅重启服务（不重新构建）
#   ./deploy/deploy.sh --status     # 查看服务状态
#   ./deploy/deploy.sh --logs       # 查看服务日志
#   ./deploy/deploy.sh --stop       # 停止所有服务
# =============================================================================
set -euo pipefail

if ! docker info &>/dev/null 2>&1; then
    if sg docker -c "docker info" &>/dev/null 2>&1; then
        exec sg docker -c "bash $0 $*"
    fi
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/.env.production"
BACKEND_ENV="$PROJECT_DIR/backend/.env"
BACKEND_ENV_TEMPLATE="$SCRIPT_DIR/backend.env.production"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[ OK ]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERR ]${NC} $*"; }

SECONDS=0
step_start() { STEP_START=$SECONDS; log_info "$*"; }
step_done()  { log_ok "$* ($(( SECONDS - STEP_START ))s)"; }

dc() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }

# --- Prerequisites ---
check_prerequisites() {
    step_start "Checking prerequisites..."

    for cmd in docker curl; do
        command -v "$cmd" &>/dev/null || { log_error "$cmd not found"; exit 1; }
    done

    docker compose version &>/dev/null || { log_error "docker compose (V2) not found"; exit 1; }

    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$PROJECT_DIR/.env.production.example" ]; then
            log_warn ".env.production not found, creating from template..."
            cp "$PROJECT_DIR/.env.production.example" "$ENV_FILE"
            log_warn "Please edit $ENV_FILE and re-run"
            exit 1
        fi
        log_error ".env.production not found"; exit 1
    fi

    if [ ! -f "$BACKEND_ENV" ]; then
        if [ -f "$BACKEND_ENV_TEMPLATE" ]; then
            log_warn "backend/.env not found, creating from production template..."
            cp "$BACKEND_ENV_TEMPLATE" "$BACKEND_ENV"
            log_warn "Please edit $BACKEND_ENV with API keys and re-run"
            exit 1
        fi
        log_error "backend/.env not found"; exit 1
    fi

    step_done "Prerequisites OK"
}

# --- Status / Logs / Stop ---
show_status() { dc ps; }
show_logs()   { dc logs -f --tail=100; }

stop_services() {
    log_info "Stopping all services..."
    dc down
    log_ok "All services stopped"
}

# --- Build backend base image ---
BASE_IMAGE_NAME="ai-agent-backend-base:latest"

build_base_image() {
    local build_args=""
    [ "${FORCE_REBUILD:-false}" = "true" ] && build_args="--no-cache"

    step_start "Building backend base image (python + uv + git)..."

    local registry_prefix
    registry_prefix=$(grep -E '^REGISTRY_PREFIX=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "")

    docker build -f "$PROJECT_DIR/backend/Dockerfile.base" \
        --build-arg REGISTRY_PREFIX="${registry_prefix}" \
        --build-arg APT_MIRROR="mirrors.aliyun.com" \
        -t "$BASE_IMAGE_NAME" \
        $build_args \
        "$PROJECT_DIR/backend"

    step_done "Base image built: $BASE_IMAGE_NAME"
}

ensure_base_image() {
    if ! docker image inspect "$BASE_IMAGE_NAME" &>/dev/null; then
        log_warn "Base image not found, building..."
        build_base_image
    else
        log_info "Base image exists: $BASE_IMAGE_NAME"
    fi
}

# --- Build images (parallel) ---
build_images() {
    local build_args=""
    [ "${FORCE_REBUILD:-false}" = "true" ] && build_args="--no-cache"

    ensure_base_image

    step_start "Building backend + frontend images (parallel)..."
    dc build $build_args --parallel backend frontend
    step_done "Images built"
}

# --- Start infrastructure ---
start_infra() {
    if dc ps --status running 2>/dev/null | grep -qE "(db|redis|qdrant)"; then
        log_info "Infrastructure already running, skipping"
        return
    fi

    step_start "Starting infrastructure (PostgreSQL, Redis, Qdrant)..."
    dc up -d db redis qdrant

    local retries=30
    while [ $retries -gt 0 ]; do
        dc exec -T db pg_isready -U postgres &>/dev/null && break
        retries=$((retries - 1))
        sleep 2
    done
    [ $retries -eq 0 ] && { log_error "Database startup timeout"; exit 1; }

    step_done "Infrastructure ready"
}

# --- Database migration ---
run_migrations() {
    step_start "Running database migrations..."
    dc run --rm backend alembic upgrade head
    step_done "Migrations complete"
}

# --- Start app services ---
start_app() {
    step_start "Starting app services..."
    dc up -d backend frontend

    local retries=20
    while [ $retries -gt 0 ]; do
        dc exec -T backend curl -sf http://localhost:8000/health &>/dev/null && break
        retries=$((retries - 1))
        sleep 3
    done

    if [ $retries -eq 0 ]; then
        log_warn "Backend health check timeout, check: dc logs backend"
    else
        step_done "App services ready"
    fi
}

# --- Summary ---
print_summary() {
    local frontend_port backend_port
    frontend_port=$(grep -E '^FRONTEND_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "80")
    backend_port=$(grep -E '^BACKEND_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "8000")
    local ip
    ip=$(hostname -I | awk '{print $1}')

    echo ""
    echo "=========================================="
    echo "  AI Agent deployed (total ${SECONDS}s)"
    echo "=========================================="
    echo ""
    echo "  Frontend: http://${ip}:${frontend_port:-80}"
    echo "  Backend:  http://${ip}:${backend_port:-8000}"
    echo "  API docs: http://${ip}:${backend_port:-8000}/docs"
    echo ""
    echo "  Commands:"
    echo "    Status:  ./deploy/deploy.sh --status"
    echo "    Logs:    ./deploy/deploy.sh --logs"
    echo "    Quick:   ./deploy/deploy.sh --quick"
    echo "    Restart: ./deploy/deploy.sh --restart"
    echo "    Stop:    ./deploy/deploy.sh --stop"
    echo "=========================================="
}

# --- Full deploy ---
full_deploy() {
    check_prerequisites
    start_infra
    build_images
    run_migrations
    start_app
    print_summary
}

# --- Quick deploy (skip build, just recreate) ---
quick_deploy() {
    check_prerequisites
    start_infra
    log_info "Quick deploy: skipping image build"
    dc up -d --force-recreate backend frontend
    step_start "Waiting for services..."
    sleep 5
    step_done "Quick deploy complete"
    print_summary
}

# --- Restart only ---
restart_services() {
    check_prerequisites
    log_info "Restarting app services..."
    dc restart backend frontend
    log_ok "Services restarted"
    show_status
}

# --- Main ---
case "${1:-}" in
    --rebuild)    FORCE_REBUILD=true full_deploy ;;
    --build-base) check_prerequisites; build_base_image ;;
    --quick)      quick_deploy ;;
    --restart)    restart_services ;;
    --status)     show_status ;;
    --logs)       show_logs ;;
    --stop)       stop_services ;;
    --help|-h)    head -13 "$0" | tail -11 ;;
    *)            full_deploy ;;
esac
