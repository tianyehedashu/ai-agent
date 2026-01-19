# ==============================================================================
# AI Agent Backend - 开发命令 (Windows 兼容)
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

# Python 解释器 (Windows 使用 python)
PYTHON := python
UV := uv

# 设置 uv 链接模式为 copy，避免硬链接警告（Windows 文件系统兼容性）
export UV_LINK_MODE := copy

# ==============================================================================
# 帮助
# ==============================================================================

help: ## 显示帮助信息
	@echo AI Agent Backend - 开发命令
	@echo.
	@echo 使用方式: make [target]
	@echo.
	@echo 可用命令:
	@echo   venv            创建虚拟环境
	@echo   install         安装生产依赖
	@echo   install-dev     安装开发依赖
	@echo   install-all     同步所有依赖
	@echo   sync            同步依赖
	@echo   dev             启动开发服务器
	@echo   test            运行测试（不含 E2E，并发执行）
	@echo   test-e2e        运行 E2E 测试（需要启动环境）
	@echo   test-all        运行所有测试（包含 E2E，并发执行）
	@echo   test-llm-providers  测试所有 LLM 提供商实际访问
	@echo.
	@echo 并发配置:
	@echo   可通过环境变量 PYTEST_NUM_WORKERS 设置并发数（默认: auto）
	@echo   例如: PYTEST_NUM_WORKERS=4 make test
	@echo   lint            运行代码检查
	@echo   format          格式化代码
	@echo   typecheck       运行类型检查
	@echo   check           运行所有检查
	@echo   clean           清理临时文件
	@echo.
	@echo SonarCloud 命令:
	@echo   sonar            运行扫描并下载报告 (推荐)
	@echo   sonar-scan       只运行扫描（不下载报告）

# ==============================================================================
# 安装与初始化
# ==============================================================================

venv: ## 创建虚拟环境
	@echo 创建虚拟环境...
	$(PYTHON) -m venv .venv

install: ## 安装生产依赖 (使用 uv)
	@echo 安装生产依赖...
	$(UV) pip install -e "."

install-dev: ## 安装开发依赖 (使用 uv)
	@echo 安装开发依赖...
	$(UV) pip install -e ".[dev]"
	@echo 安装 pre-commit hooks...
	-$(UV) run pre-commit install || echo 警告: pre-commit 安装失败，请检查 git 配置
	-$(UV) run pre-commit install --hook-type commit-msg || echo 警告: pre-commit commit-msg hook 安装失败

install-all: ## 同步所有依赖 (使用 uv sync)
	@echo 同步依赖...
	$(UV) sync --all-extras
	@echo 安装 pre-commit hooks...
	-$(UV) run pre-commit install || echo 警告: pre-commit 安装失败，请检查 git 配置
	-$(UV) run pre-commit install --hook-type commit-msg || echo 警告: pre-commit commit-msg hook 安装失败

sync: ## 同步依赖 (从 pyproject.toml 和 uv.lock，包含开发依赖)
	@echo 同步依赖（包含开发依赖）...
	$(UV) sync --all-extras

lock: ## 生成/更新 uv.lock 文件
	@echo 生成锁文件...
	$(UV) lock

# ==============================================================================
# 开发服务器
# ==============================================================================

dev: ## 启动开发服务器 (带热重载)
	$(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-debug: ## 启动开发服务器 (调试模式)
	$(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug

# ==============================================================================
# 代码质量检查
# ==============================================================================

lint: ## 运行代码检查 (Ruff)
	@echo 运行代码检查...
	$(UV) run ruff check .

lint-fix: ## 运行代码检查并自动修复
	@echo 运行代码检查并修复...
	$(UV) run ruff check . --fix

lint-pylint: ## 运行 Pylint 检查
	@echo 运行 Pylint 检查...
	-$(UV) run pylint app api core models schemas services db utils workers scripts --output-format=parseable

format: ## 格式化代码
	@echo 格式化代码...
	$(UV) run ruff format .

format-check: ## 检查代码格式 (不修改)
	@echo 检查代码格式...
	$(UV) run ruff format . --check

typecheck: ## 运行类型检查 (Pyright)
	@echo 运行类型检查...
	$(UV) run pyright

typecheck-mypy: ## 运行类型检查 (MyPy)
	@echo 运行 MyPy 类型检查...
	$(UV) run mypy .

security: ## 运行安全检查 (Bandit)
	@echo 运行安全检查...
	$(UV) run bandit -c pyproject.toml -r . --exclude ./tests

# 组合检查命令
check: format-check lint lint-pylint typecheck ## 运行所有检查
	@echo 所有检查通过!

check-ci: ## CI 环境检查 (严格模式)
	@echo 运行 CI 检查...
	$(UV) run ruff format . --check
	$(UV) run ruff check .
	$(UV) run pyright
	$(UV) run bandit -c pyproject.toml -r . --exclude ./tests
	@echo CI 检查通过!

fix: lint-fix format ## 自动修复所有问题
	@echo 自动修复完成!

# ==============================================================================
# 测试
# ==============================================================================
# 并发测试配置: 使用 pytest-xdist 加速测试执行
# 可通过环境变量 PYTEST_NUM_WORKERS 自定义并发数，默认为 auto（自动检测 CPU 核心数）
PYTEST_NUM_WORKERS ?= auto

test: ## 运行测试（不含 E2E，并发执行）
	@echo 运行测试（排除 E2E，并发数: $(PYTEST_NUM_WORKERS)）...
	$(UV) run pytest -m "not e2e" -n $(PYTEST_NUM_WORKERS)

test-all: ## 运行所有测试（包含 E2E，需要启动环境，并发执行）
	@echo 运行所有测试（并发数: $(PYTEST_NUM_WORKERS)）...
	$(UV) run pytest -n $(PYTEST_NUM_WORKERS)

test-cov: ## 运行测试并生成覆盖率报告（不含 E2E，并发执行）
	@echo 运行测试 (带覆盖率，并发数: $(PYTEST_NUM_WORKERS))...
	$(UV) run pytest -m "not e2e" --cov --cov-report=html --cov-report=term-missing -n $(PYTEST_NUM_WORKERS)

test-unit: ## 只运行单元测试（并发执行）
	@echo 运行单元测试（并发数: $(PYTEST_NUM_WORKERS)）...
	$(UV) run pytest -m unit -n $(PYTEST_NUM_WORKERS)

test-integration: ## 只运行集成测试（使用 TestClient，不需要启动服务，并发执行）
	@echo 运行集成测试（并发数: $(PYTEST_NUM_WORKERS)）...
	$(UV) run pytest -m integration -n $(PYTEST_NUM_WORKERS)

test-e2e: ## 运行 E2E 测试（跳过慢测试，需要启动 docker-compose 和后端服务，单进程执行避免资源冲突）
	@echo ==========================================
	@echo   运行 E2E 测试（跳过慢测试）
	@echo ==========================================
	@echo 前提条件:
	@echo   1. docker-compose up -d（数据库、Redis）
	@echo   2. make dev（后端服务）
	@echo ==========================================
	@echo 提示: 使用 make test-e2e-slow 运行所有测试（包括慢测试）
	@echo 注意: E2E 测试使用单进程执行以避免资源冲突
	@echo ==========================================
	$(UV) run pytest -m "e2e and not slow" -v -s
	@echo ==========================================
	@echo ✓ E2E 测试完成（已跳过慢测试）
	@echo ==========================================

test-e2e-slow: ## 运行所有 E2E 测试（包括慢测试，多轮对话长上下文，单进程执行）
	@echo ==========================================
	@echo   运行所有 E2E 测试（包括慢测试）
	@echo ==========================================
	@echo 前提条件:
	@echo   1. docker-compose up -d（数据库、Redis）
	@echo   2. make dev（后端服务）
	@echo ==========================================
	@echo 警告: 此命令会运行多轮对话长上下文测试，可能耗时较长
	@echo 注意: E2E 测试使用单进程执行以避免资源冲突
	@echo ==========================================
	$(UV) run pytest -m e2e -v -s
	@echo ==========================================
	@echo ✓ 所有 E2E 测试完成
	@echo ==========================================

test-watch: ## 监视模式运行测试（单进程，避免并发冲突）
	@echo 监视模式测试（单进程）...
	$(UV) run ptw -- -v -m "not e2e"

test-performance: ## 运行性能测试
	@echo 运行性能测试...
	$(UV) run pytest tests/performance/ -v --benchmark-only

# ==============================================================================
# LLM 提供商测试
# ==============================================================================

test-llm-providers: ## 测试所有 LLM 提供商实际访问 (DeepSeek, 火山引擎, 智谱AI, 阿里云DashScope，单进程执行)
	@echo ==========================================
	@echo   测试 LLM 提供商实际访问
	@echo ==========================================
	@echo 注意: 未配置的提供商将自动跳过
	@echo 运行 LLM 提供商实际访问测试（单进程，避免 API 限流）...
	$(UV) run pytest tests/integration/test_llm_providers.py -v -s
	@echo ==========================================
	@echo ✓ LLM 提供商测试完成
	@echo ==========================================

# ==============================================================================
# 数据库
# ==============================================================================

db-migrate: ## 创建数据库迁移
	@echo 创建数据库迁移...
	$(UV) run alembic revision --autogenerate -m "$(msg)"

db-upgrade: ## 升级数据库到最新
	@echo 升级数据库...
	$(UV) run alembic upgrade head

db-downgrade: ## 回滚数据库一个版本
	@echo 回滚数据库...
	$(UV) run alembic downgrade -1

db-reset: ## 重置数据库
	@echo 重置数据库...
	$(UV) run alembic downgrade base
	$(UV) run alembic upgrade head

# ==============================================================================
# 文档
# ==============================================================================

docs: ## 生成 API 文档
	@echo 生成文档...
	mkdocs build

docs-serve: ## 启动文档服务器
	@echo 启动文档服务器...
	mkdocs serve

# ==============================================================================
# 清理 (Windows 兼容)
# ==============================================================================

clean: ## 清理临时文件
	@echo 清理临时文件...
	-@powershell -Command "Get-ChildItem -Path . -Recurse -Directory -Name '__pycache__' | ForEach-Object { Remove-Item -Recurse -Force $$_ }" 2>nul
	-@powershell -Command "Get-ChildItem -Path . -Recurse -Directory -Name '.pytest_cache' | ForEach-Object { Remove-Item -Recurse -Force $$_ }" 2>nul
	-@powershell -Command "Get-ChildItem -Path . -Recurse -Directory -Name '.mypy_cache' | ForEach-Object { Remove-Item -Recurse -Force $$_ }" 2>nul
	-@powershell -Command "Get-ChildItem -Path . -Recurse -Directory -Name '.ruff_cache' | ForEach-Object { Remove-Item -Recurse -Force $$_ }" 2>nul
	-@powershell -Command "Remove-Item -Recurse -Force htmlcov -ErrorAction SilentlyContinue" 2>nul
	-@powershell -Command "Remove-Item -Force .coverage -ErrorAction SilentlyContinue" 2>nul
	@echo 清理完成!

clean-all: clean ## 清理所有生成的文件 (包括虚拟环境)
	-@powershell -Command "Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue" 2>nul

# ==============================================================================
# Pre-commit
# ==============================================================================

pre-commit: ## 手动运行 pre-commit 检查
	$(UV) run pre-commit run --all-files

pre-commit-update: ## 更新 pre-commit hooks
	$(UV) run pre-commit autoupdate

# ==============================================================================
# Docker
# ==============================================================================

docker-build: ## 构建 Docker 镜像
	docker build -t ai-agent-backend:dev .

docker-run: ## 运行 Docker 容器
	docker run -p 8000:8000 --env-file .env ai-agent-backend:dev

docker-build-sandbox: ## 构建沙箱镜像（包含 busybox 和常用工具）
	@echo 构建 AI Agent 沙箱镜像...
	@if exist docker\sandbox\build.ps1 (powershell -ExecutionPolicy Bypass -File docker\sandbox\build.ps1) else (bash docker/sandbox/build.sh)

docker-test-sandbox: ## 测试沙箱镜像
	docker run -it --rm ai-agent-sandbox:latest bash

docker-compose-up: ## 启动所有服务 (docker-compose)
	docker-compose up -d

docker-compose-down: ## 停止所有服务
	docker-compose down

# ==============================================================================
# SonarCloud (后端)
# ==============================================================================
# 使用方式:
#   # 在 .env 文件中配置 SONAR_TOKEN 和 SONAR_ORGANIZATION
#   make sonar              # 运行扫描并自动下载报告
#   make sonar-scan         # 只运行扫描（不上传）
#
# 注意: sonar-scanner 需要单独安装
# 安装: https://docs.sonarqube.org/latest/analysis/scan/sonarscanner/
# ==============================================================================

sonar: ## 运行 SonarCloud 扫描并下载报告 (支持从 .env 文件读取配置)
	@echo ==========================================
	@echo   扫描后端 (Python) - SonarCloud
	@echo ==========================================
	@echo 检查环境...
	@$(PYTHON) scripts/check_sonar_env.py
	@echo 生成覆盖率报告（并发数: $(PYTEST_NUM_WORKERS)）...
	-$(UV) run pytest --cov --cov-report=xml:coverage.xml --junitxml=test-results.xml -q -n $(PYTEST_NUM_WORKERS)
	@echo 运行 SonarCloud 扫描...
	@$(PYTHON) scripts/run_sonar_scanner.py
	@echo ✓ SonarCloud 扫描完成
	@echo 等待 SonarCloud 处理结果 (30秒)...
	@$(PYTHON) -c "import time; time.sleep(30)"
	@echo 下载报告...
	@$(PYTHON) ../scripts/sonarcloud_api.py report --format html
	@echo.
	@echo ==========================================
	@echo ✓ 完整流程已完成！
	@echo ==========================================

sonar-scan: ## 只运行 SonarCloud 扫描（不下载报告）
	@echo ==========================================
	@echo   扫描后端 (Python) - SonarCloud
	@echo ==========================================
	@echo 检查环境...
	@$(PYTHON) scripts/check_sonar_env.py
	@echo 生成覆盖率报告（并发数: $(PYTEST_NUM_WORKERS)）...
	-$(UV) run pytest --cov --cov-report=xml:coverage.xml --junitxml=test-results.xml -q -n $(PYTEST_NUM_WORKERS)
	@echo 运行 SonarCloud 扫描...
	@$(PYTHON) scripts/run_sonar_scanner.py
	@echo ✓ SonarCloud 扫描完成
