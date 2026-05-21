# AI Agent Backend Dockerfile — 基于预构建 base 镜像
# 前置条件: 需先构建并推送 base 镜像，或本地 tag 为下方 BASE_IMAGE
#   docker build -f Dockerfile.base -t giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/prod/ai-agent-backend-base:latest ./backend
# 构建生产镜像:
#   docker build -f Dockerfile --target production -t <acr>/prod/ai-agent-backend:v1.0.0 ./backend
# 注意: 不使用 "# syntax=docker/dockerfile:1"，避免从 Docker Hub 拉取 docker/dockerfile 镜像

ARG BASE_IMAGE=giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/prod/ai-agent-backend-base:latest

# ============================================
# Stage 1: Dependencies — Python packages
# 仅当 pyproject.toml / uv.lock 变化时才重新构建
# ============================================
FROM ${BASE_IMAGE} AS dependencies

ARG UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG UV_HTTP_TIMEOUT=1800
ENV UV_DEFAULT_INDEX=${UV_INDEX_URL} \
    UV_HTTP_TIMEOUT=${UV_HTTP_TIMEOUT} \
    UV_CONCURRENT_DOWNLOADS=4

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# ============================================
# Stage 2: Development
# ============================================
FROM dependencies AS development

RUN uv sync --frozen --all-extras
COPY . .

EXPOSE 8000
CMD ["uvicorn", "bootstrap.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================
# Stage 3: Production — 最小运行时镜像
# 从 dependencies 拷贝已安装的 .venv，不携带构建工具
# ============================================
FROM giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/common/python:3.11-slim AS production

ARG APT_MIRROR=mirrors.aliyun.com

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
