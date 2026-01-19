# AI Agent 沙箱镜像
# 基于 Alpine + Python + Node.js，包含 busybox 和常用工具
# 大小约 300MB，功能丰富但保持轻量

FROM python:3.11-alpine

# 设置工作目录
WORKDIR /workspace

# 安装 Node.js 和相关工具
RUN apk add --no-cache nodejs npm

# 安装系统工具和常用命令
RUN apk add --no-cache \
    bash \
    git \
    curl \
    wget \
    vim \
    nano \
    jq \
    tree \
    htop \
    openssh-client \
    ca-certificates \
    zip \
    unzip \
    tar \
    gzip \
    bzip2 \
    xz \
    procps \
    coreutils \
    util-linux \
    shadow \
    su-exec \
    && rm -rf /var/cache/apk/*

# 安装常用的 Python 包
RUN pip install --no-cache-dir \
    requests \
    ipython \
    && rm -rf /root/.cache/pip

# 设置环境变量（包括 UTF-8 编码支持）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/workspace/bin:$PATH" \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# 验证 Node.js 安装
RUN node --version && npm --version

# 创建非 root 用户（安全最佳实践）
RUN addgroup -g 1000 sandbox && \
    adduser -D -u 1000 -G sandbox sandbox && \
    chown -R sandbox:sandbox /workspace

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python --version || exit 1

# 默认命令：保持容器运行（用于会话模式）
CMD ["tail", "-f", "/dev/null"]
