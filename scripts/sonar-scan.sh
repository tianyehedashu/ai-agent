#!/bin/bash
# ==============================================================================
# SonarQube 本地扫描脚本
# ==============================================================================
# 使用方式:
#   export SONAR_HOST_URL=http://localhost:9000
#   export SONAR_TOKEN=your-token
#   ./scripts/sonar-scan.sh [backend|frontend|all]
# ==============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查环境变量
check_env() {
    if [ -z "$SONAR_HOST_URL" ]; then
        echo -e "${RED}错误: SONAR_HOST_URL 环境变量未设置${NC}"
        echo "请设置: export SONAR_HOST_URL=http://your-sonar-server:9000"
        exit 1
    fi

    if [ -z "$SONAR_TOKEN" ]; then
        echo -e "${RED}错误: SONAR_TOKEN 环境变量未设置${NC}"
        echo "请设置: export SONAR_TOKEN=your-token"
        exit 1
    fi
}

# 检查 sonar-scanner 是否安装
check_scanner() {
    if ! command -v sonar-scanner &> /dev/null; then
        echo -e "${RED}错误: sonar-scanner 未安装${NC}"
        echo "请安装: https://docs.sonarqube.org/latest/analysis/scan/sonarscanner/"
        exit 1
    fi
}

# 扫描后端
scan_backend() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  扫描后端 (Python)${NC}"
    echo -e "${BLUE}========================================${NC}"

    cd backend

    # 生成覆盖率报告
    echo -e "${YELLOW}>> 运行测试并生成覆盖率报告...${NC}"
    python -m pytest --cov --cov-report=xml:coverage.xml --junitxml=test-results.xml || true

    # 运行 SonarQube 扫描
    echo -e "${YELLOW}>> 运行 SonarQube 扫描...${NC}"
    sonar-scanner \
        -Dsonar.host.url="$SONAR_HOST_URL" \
        -Dsonar.token="$SONAR_TOKEN"

    cd ..
    echo -e "${GREEN}✓ 后端扫描完成${NC}"
}

# 扫描前端
scan_frontend() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  扫描前端 (TypeScript)${NC}"
    echo -e "${BLUE}========================================${NC}"

    cd frontend

    # 安装依赖
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}>> 安装依赖...${NC}"
        npm ci
    fi

    # 生成覆盖率报告
    echo -e "${YELLOW}>> 运行测试并生成覆盖率报告...${NC}"
    npm run test:coverage || true

    # 生成 ESLint 报告
    echo -e "${YELLOW}>> 生成 ESLint 报告...${NC}"
    npm run lint -- -f json -o eslint-report.json || true

    # 运行 SonarQube 扫描
    echo -e "${YELLOW}>> 运行 SonarQube 扫描...${NC}"
    sonar-scanner \
        -Dsonar.host.url="$SONAR_HOST_URL" \
        -Dsonar.token="$SONAR_TOKEN"

    cd ..
    echo -e "${GREEN}✓ 前端扫描完成${NC}"
}

# 显示帮助
show_help() {
    echo "AI Agent SonarQube 扫描脚本"
    echo ""
    echo "使用方式: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  backend   只扫描后端 (Python)"
    echo "  frontend  只扫描前端 (TypeScript)"
    echo "  all       扫描全部 (默认)"
    echo "  help      显示此帮助"
    echo ""
    echo "环境变量:"
    echo "  SONAR_HOST_URL  SonarQube 服务器地址"
    echo "  SONAR_TOKEN     访问令牌"
}

# 主函数
main() {
    local target="${1:-all}"

    case "$target" in
        help|-h|--help)
            show_help
            exit 0
            ;;
        backend)
            check_env
            check_scanner
            scan_backend
            ;;
        frontend)
            check_env
            check_scanner
            scan_frontend
            ;;
        all)
            check_env
            check_scanner
            scan_backend
            scan_frontend
            echo -e "${GREEN}========================================${NC}"
            echo -e "${GREEN}  全部扫描完成!${NC}"
            echo -e "${GREEN}========================================${NC}"
            ;;
        *)
            echo -e "${RED}未知选项: $target${NC}"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
