# ==============================================================================
# AI Agent Backend - 开发命令
# ==============================================================================
#
# 使用方式:
#   make help        - 显示所有可用命令
#   make install     - 安装依赖
#   make dev         - 启动开发服务器
#   make check       - 运行所有检查
#   make test        - 运行测试
#
# ==============================================================================

.PHONY: help install dev test lint format typecheck security check clean

# 默认目标
.DEFAULT_GOAL := help

# Python 解释器
PYTHON := python3

# ==============================================================================
# 帮助
# ==============================================================================

help: ## 显示帮助信息
	@echo "AI Agent Backend - 开发命令"
	@echo ""
	@echo "使用方式: make [target]"
	@echo ""
	@echo "可用命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ==============================================================================
# 安装与初始化
# ==============================================================================

install: ## 安装生产依赖
	pip install -r requirements.txt

install-dev: ## 安装开发依赖
	pip install -r requirements.txt -r requirements-dev.txt
	pre-commit install
	pre-commit install --hook-type commit-msg

install-all: install-dev ## 安装所有依赖并初始化

# ==============================================================================
# 开发服务器
# ==============================================================================

dev: ## 启动开发服务器 (带热重载)
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-debug: ## 启动开发服务器 (调试模式)
	PYTHONDONTWRITEBYTECODE=1 uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug

# ==============================================================================
# 代码质量检查
# ==============================================================================

lint: ## 运行代码检查 (Ruff)
	@echo "🔍 运行代码检查..."
	ruff check .

lint-fix: ## 运行代码检查并自动修复
	@echo "🔧 运行代码检查并修复..."
	ruff check . --fix

format: ## 格式化代码
	@echo "✨ 格式化代码..."
	ruff format .

format-check: ## 检查代码格式 (不修改)
	@echo "🔍 检查代码格式..."
	ruff format . --check

typecheck: ## 运行类型检查 (Pyright)
	@echo "🔬 运行类型检查..."
	pyright

typecheck-mypy: ## 运行类型检查 (MyPy)
	@echo "🔬 运行 MyPy 类型检查..."
	mypy .

security: ## 运行安全检查 (Bandit)
	@echo "🔒 运行安全检查..."
	bandit -c pyproject.toml -r . --exclude ./tests

# 组合检查命令
check: format-check lint typecheck ## 运行所有检查 (格式 + Lint + 类型)
	@echo "✅ 所有检查通过!"

check-ci: ## CI 环境检查 (严格模式)
	@echo "🚀 运行 CI 检查..."
	ruff format . --check
	ruff check .
	pyright
	bandit -c pyproject.toml -r . --exclude ./tests
	@echo "✅ CI 检查通过!"

fix: lint-fix format ## 自动修复所有问题
	@echo "✅ 自动修复完成!"

# ==============================================================================
# 测试
# ==============================================================================

test: ## 运行测试
	@echo "🧪 运行测试..."
	pytest

test-cov: ## 运行测试并生成覆盖率报告
	@echo "🧪 运行测试 (带覆盖率)..."
	pytest --cov --cov-report=html --cov-report=term-missing

test-unit: ## 只运行单元测试
	@echo "🧪 运行单元测试..."
	pytest -m unit

test-integration: ## 只运行集成测试
	@echo "🧪 运行集成测试..."
	pytest -m integration

test-watch: ## 监视模式运行测试
	@echo "👀 监视模式测试..."
	ptw -- -v

# ==============================================================================
# 数据库
# ==============================================================================

db-migrate: ## 创建数据库迁移
	@echo "📦 创建数据库迁移..."
	alembic revision --autogenerate -m "$(msg)"

db-upgrade: ## 升级数据库到最新
	@echo "⬆️  升级数据库..."
	alembic upgrade head

db-downgrade: ## 回滚数据库一个版本
	@echo "⬇️  回滚数据库..."
	alembic downgrade -1

db-reset: ## 重置数据库
	@echo "🗑️  重置数据库..."
	alembic downgrade base
	alembic upgrade head

# ==============================================================================
# 文档
# ==============================================================================

docs: ## 生成 API 文档
	@echo "📚 生成文档..."
	mkdocs build

docs-serve: ## 启动文档服务器
	@echo "📚 启动文档服务器..."
	mkdocs serve

# ==============================================================================
# 清理
# ==============================================================================

clean: ## 清理临时文件
	@echo "🧹 清理临时文件..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "✅ 清理完成!"

clean-all: clean ## 清理所有生成的文件 (包括虚拟环境)
	rm -rf .venv

# ==============================================================================
# Pre-commit
# ==============================================================================

pre-commit: ## 手动运行 pre-commit 检查
	pre-commit run --all-files

pre-commit-update: ## 更新 pre-commit hooks
	pre-commit autoupdate

# ==============================================================================
# Docker
# ==============================================================================

docker-build: ## 构建 Docker 镜像
	docker build -t ai-agent-backend:dev .

docker-run: ## 运行 Docker 容器
	docker run -p 8000:8000 --env-file .env ai-agent-backend:dev

docker-compose-up: ## 启动所有服务 (docker-compose)
	docker-compose up -d

docker-compose-down: ## 停止所有服务
	docker-compose down

# ==============================================================================
# SonarQube
# ==============================================================================

sonar: ## 运行 SonarQube 扫描 (需要设置 SONAR_HOST_URL 和 SONAR_TOKEN)
	@echo "🔍 生成覆盖率报告..."
	pytest --cov --cov-report=xml:coverage.xml --junitxml=test-results.xml || true
	@echo "🔍 运行 SonarQube 扫描..."
	sonar-scanner

sonar-report: ## 生成 SonarQube 所需的报告
	@echo "📊 生成覆盖率报告..."
	pytest --cov --cov-report=xml:coverage.xml --junitxml=test-results.xml
