# ==============================================================================
# AI Agent 项目 - 统一管理前后端
# ==============================================================================
# 使用方式:
#   make help        - 显示所有可用命令
#   make install     - 安装所有依赖
#   make dev         - 启动前后端开发服务器
#   make test        - 运行所有测试
#   make check       - 运行所有检查
# ==============================================================================

.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend test test-backend test-frontend check check-backend check-frontend clean clean-backend clean-frontend sonar sonar-backend docker-up docker-down docker-logs docker-restart docker-services docker-ps deploy deploy-rebuild deploy-quick deploy-status deploy-logs deploy-stop deploy-setup deploy-sync

# 默认目标
.DEFAULT_GOAL := help

# ==============================================================================
# 帮助
# ==============================================================================

help: ## 显示帮助信息
	@echo ==========================================
	@echo   AI Agent 项目 - 统一管理命令
	@echo ==========================================
	@echo.
	@echo 安装与依赖:
	@echo   make install          安装所有依赖（后端 + 前端）
	@echo   make install-backend  只安装后端依赖
	@echo   make install-frontend 只安装前端依赖
	@echo.
	@echo 开发服务器:
	@echo   make dev              启动前后端开发服务器（需要两个终端）
	@echo   make dev-backend      只启动后端开发服务器
	@echo   make dev-frontend     只启动前端开发服务器
	@echo.
	@echo 测试:
	@echo   make test             运行所有测试
	@echo   make test-backend     只运行后端测试
	@echo   make test-frontend    只运行前端测试
	@echo.
	@echo 代码质量:
	@echo   make check            运行所有检查（后端 + 前端）
	@echo   make check-backend    只检查后端
	@echo   make check-frontend    只检查前端
	@echo.
	@echo SonarCloud:
	@echo   make sonar            运行后端 SonarCloud 扫描并下载报告
	@echo   make sonar-backend    只运行后端扫描（不下载报告）
	@echo.
	@echo Docker 服务:
	@echo   make docker-services  启动基础服务（postgres, redis, qdrant）
	@echo   make docker-up        启动所有服务
	@echo   make docker-down      停止所有服务
	@echo   make docker-logs      查看服务日志
	@echo   make docker-restart   重启所有服务
	@echo   make docker-ps        查看运行中的容器
	@echo.
	@echo 部署 (远程 web01):
	@echo   make deploy           完整部署到 web01（同步代码 + 构建 + 启动）
	@echo   make deploy-rebuild   强制重新构建并部署（--no-cache）
	@echo   make deploy-quick     快速部署（同步代码 + 重启，跳过构建）
	@echo   make deploy-sync      仅同步代码（不构建不启动）
	@echo   make deploy-build-base 重建后端基础镜像（python + uv + git）
	@echo   make deploy-status    查看远程服务状态
	@echo   make deploy-logs      查看远程服务日志
	@echo   make deploy-stop      停止远程服务
	@echo   make deploy-setup     首次部署：初始化远程环境
	@echo.
	@echo 清理:
	@echo   make clean            清理所有临时文件
	@echo   make clean-backend    只清理后端
	@echo   make clean-frontend   只清理前端
	@echo.

# ==============================================================================
# 安装与依赖
# ==============================================================================

install: install-backend install-frontend ## 安装所有依赖（后端 + 前端）
	@echo.
	@echo ✓ 所有依赖安装完成！

install-backend: ## 安装后端依赖
	@echo ==========================================
	@echo   安装后端依赖
	@echo ==========================================
	@cd backend && make sync

install-frontend: ## 安装前端依赖
	@echo ==========================================
	@echo   安装前端依赖
	@echo ==========================================
	@cd frontend && npm ci

# ==============================================================================
# 开发服务器
# ==============================================================================

dev: ## 启动前后端开发服务器（提示：需要两个终端）
	@echo ==========================================
	@echo   启动开发服务器
	@echo ==========================================
	@echo 提示: 前后端需要分别启动，请使用两个终端:
	@echo   终端 1: make dev-backend
	@echo   终端 2: make dev-frontend
	@echo.
	@echo 或者使用 docker-compose:
	@echo   docker-compose up

dev-backend: ## 启动后端开发服务器
	@echo ==========================================
	@echo   启动后端开发服务器
	@echo ==========================================
	@cd backend && make dev

dev-frontend: ## 启动前端开发服务器
	@echo ==========================================
	@echo   启动前端开发服务器
	@echo ==========================================
	@cd frontend && npm run dev

# ==============================================================================
# 测试
# ==============================================================================

test: test-backend test-frontend ## 运行所有测试
	@echo.
	@echo ✓ 所有测试完成！

test-backend: ## 运行后端测试
	@echo ==========================================
	@echo   运行后端测试
	@echo ==========================================
	@cd backend && make test

test-frontend: ## 运行前端测试
	@echo ==========================================
	@echo   运行前端测试
	@echo ==========================================
	@cd frontend && npm run test:run

# ==============================================================================
# 代码质量检查
# ==============================================================================

check: check-backend check-frontend ## 运行所有检查（后端 + 前端）
	@echo.
	@echo ✓ 所有检查完成！

check-backend: ## 检查后端代码质量
	@echo ==========================================
	@echo   检查后端代码质量
	@echo ==========================================
	@cd backend && make check

check-frontend: ## 检查前端代码质量
	@echo ==========================================
	@echo   检查前端代码质量
	@echo ==========================================
	@cd frontend && npm run check

# ==============================================================================
# SonarCloud
# ==============================================================================

sonar: ## 运行后端 SonarCloud 扫描并下载报告
	@echo ==========================================
	@echo   运行 SonarCloud 扫描（后端）
	@echo ==========================================
	@cd backend && make sonar

sonar-backend: ## 只运行后端扫描（不下载报告）
	@cd backend && make sonar-scan

# ==============================================================================
# Docker 服务
# ==============================================================================

docker-services: ## 启动基础服务（postgres, redis, qdrant）
	@echo ==========================================
	@echo   启动基础服务（数据库、缓存、向量数据库）
	@echo ==========================================
	@docker-compose up -d db redis qdrant
	@echo.
	@echo ✓ 基础服务已启动:
	@echo   - PostgreSQL: localhost:5432
	@echo   - Redis:      localhost:6379
	@echo   - Qdrant:     localhost:6333
	@echo.
	@echo 提示: 服务正在启动中，请稍候...
	@echo 使用 'make docker-ps' 查看服务状态

docker-up: ## 启动所有 Docker 服务
	@echo ==========================================
	@echo   启动所有 Docker 服务
	@echo ==========================================
	@docker-compose up -d
	@echo.
	@echo ✓ 所有服务已启动
	@make docker-ps

docker-down: ## 停止所有 Docker 服务
	@echo ==========================================
	@echo   停止所有 Docker 服务
	@echo ==========================================
	@docker-compose down
	@echo ✓ 所有服务已停止

docker-restart: ## 重启所有 Docker 服务
	@echo ==========================================
	@echo   重启所有 Docker 服务
	@echo ==========================================
	@docker-compose restart
	@echo ✓ 所有服务已重启

docker-logs: ## 查看 Docker 服务日志
	@echo ==========================================
	@echo   Docker 服务日志
	@echo ==========================================
	@docker-compose logs -f

docker-ps: ## 查看运行中的容器
	@echo ==========================================
	@echo   运行中的容器
	@echo ==========================================
	@docker-compose ps

# ==============================================================================
# 清理
# ==============================================================================

clean: clean-backend clean-frontend ## 清理所有临时文件
	@echo.
	@echo ✓ 清理完成！

clean-backend: ## 清理后端临时文件
	@echo ==========================================
	@echo   清理后端临时文件
	@echo ==========================================
	@cd backend && make clean

clean-frontend: ## 清理前端临时文件
	@echo ==========================================
	@echo   清理前端临时文件
	@echo ==========================================
	-@powershell -Command "cd frontend; @('node_modules/.vite', 'dist', 'coverage', '.turbo') | ForEach-Object { if (Test-Path $$_) { Remove-Item -Recurse -Force $$_ } }"

# ==============================================================================
# 部署 (远程 web01)
# ==============================================================================

deploy: ## 完整部署到 web01（同步代码 + 构建 + 启动）
	@echo ==========================================
	@echo   部署到 web01
	@echo ==========================================
	@powershell -ExecutionPolicy Bypass -File deploy/remote-deploy.ps1 -Action deploy

deploy-rebuild: ## 强制重新构建并部署到 web01（--no-cache）
	@powershell -ExecutionPolicy Bypass -File deploy/remote-deploy.ps1 -Action rebuild

deploy-quick: ## 快速部署到 web01（同步代码 + 重启，跳过构建）
	@powershell -ExecutionPolicy Bypass -File deploy/remote-deploy.ps1 -Action quick

deploy-sync: ## 仅同步代码到 web01（不构建不启动）
	@powershell -ExecutionPolicy Bypass -File deploy/remote-deploy.ps1 -Action sync

deploy-build-base: ## 重建 web01 后端基础镜像（python + uv + git）
	@powershell -ExecutionPolicy Bypass -File deploy/remote-deploy.ps1 -Action build-base

deploy-status: ## 查看 web01 服务状态
	@powershell -ExecutionPolicy Bypass -File deploy/remote-deploy.ps1 -Action status

deploy-logs: ## 查看 web01 服务日志
	@powershell -ExecutionPolicy Bypass -File deploy/remote-deploy.ps1 -Action logs

deploy-stop: ## 停止 web01 服务
	@powershell -ExecutionPolicy Bypass -File deploy/remote-deploy.ps1 -Action stop

deploy-setup: ## 首次部署：初始化 web01 远程环境（安装 Docker 等）
	@powershell -ExecutionPolicy Bypass -File deploy/remote-deploy.ps1 -Action setup
