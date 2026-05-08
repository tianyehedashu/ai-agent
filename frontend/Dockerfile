# syntax=docker/dockerfile:1
# AI Agent Frontend Dockerfile — 多阶段构建
# 优化策略：依赖层与代码层分离 + cache mount 持久化 npm 缓存

ARG REGISTRY_PREFIX=""

# ============================================
# Stage 1: Dependencies — npm 包（变更频率：低）
# 仅当 package.json / package-lock.json 变化时才重新安装
# cache mount 使得即使该层重建，已下载的包仍可复用
# ============================================
FROM ${REGISTRY_PREFIX}node:20-alpine AS dependencies

ARG NPM_REGISTRY=https://registry.npmmirror.com
RUN npm config set registry ${NPM_REGISTRY}

WORKDIR /app
COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.cache/npm \
    npm ci --cache /root/.cache/npm

# ============================================
# Stage 2: Development
# ============================================
FROM dependencies AS development

COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ============================================
# Stage 3: Build — 编译产物（变更频率：高）
# ============================================
FROM dependencies AS build

COPY . .
RUN npm run build

# ============================================
# Stage 4: Production — 仅包含静态文件 + Nginx
# ============================================
ARG REGISTRY_PREFIX=""
FROM ${REGISTRY_PREFIX}nginx:alpine AS production

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
