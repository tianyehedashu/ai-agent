# syntax=docker/dockerfile:1
# AI Agent Backend Dockerfile — 基于预构建 base 镜像
# 前置条件: 需先构建 base 镜像 (docker build -f Dockerfile.base -t ai-agent-backend-base .)
# 日常部署只执行本文件，无需重复下载系统包和 uv
# 优化: --mount=type=cache 持久化 uv/pip 下载缓存，依赖变更时跳过已下载的包

ARG BASE_IMAGE=ai-agent-backend-base:latest

# ============================================
# Stage 1: Dependencies — Python packages
# 仅当 pyproject.toml / uv.lock 变化时才重新构建
# cache mount 使得即使该层重建，已下载的 wheel 仍可复用
# ============================================
FROM ${BASE_IMAGE} AS dependencies

ARG UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV UV_INDEX_URL=${UV_INDEX_URL}

COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ============================================
# Stage 2: Development
# ============================================
FROM dependencies AS development

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-extras
COPY . .

EXPOSE 8000
CMD ["uvicorn", "bootstrap.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================
# Stage 3: Production — 最小运行时镜像
# 从 dependencies 拷贝已安装的 .venv，不携带构建工具
# ============================================
ARG REGISTRY_PREFIX=""
FROM ${REGISTRY_PREFIX}python:3.11-slim AS production

ARG APT_MIRROR=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN if [ -n "$APT_MIRROR" ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

COPY --from=dependencies /app/.venv /app/.venv
COPY . .
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8000
CMD ["uvicorn", "bootstrap.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
