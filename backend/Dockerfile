ARG DEPS_IMAGE=giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/prod/ai-agent-backend-deps:v1.0.0
ARG RUNTIME_IMAGE=giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/common/python-kubectl:3.11-slim
# ============================================
# Stage 1: Dependencies
# 直接使用已经构建好的依赖镜像
# ============================================


FROM ${DEPS_IMAGE} AS dependencies
# ============================================
# Stage 2: Production
# ============================================
FROM ${RUNTIME_IMAGE} AS production
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
    && apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser
COPY --from=dependencies /app/.venv /app/.venv
COPY . .
RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "bootstrap.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
