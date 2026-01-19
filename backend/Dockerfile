# AI Agent Backend Dockerfile
# 多阶段构建

# ============================================
# Stage 1: Base
# ============================================
FROM python:3.11-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    UV_LINK_MODE=copy \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 设置 PATH 以包含 uv 虚拟环境
ENV PATH="/app/.venv/bin:$PATH"

# ============================================
# Stage 2: Dependencies
# ============================================
FROM base as dependencies

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN chmod +x /usr/local/bin/uv

# 复制项目文件
COPY pyproject.toml uv.lock ./

# 使用 uv 安装生产依赖
RUN uv sync --frozen --no-dev

# ============================================
# Stage 3: Development
# ============================================
FROM dependencies as development

# 使用 uv 安装开发依赖
RUN uv sync --frozen --all-extras

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================
# Stage 4: Production
# ============================================
FROM dependencies as production

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash appuser

COPY . .

# 更改文件所有权
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
