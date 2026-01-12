# AI Agent Frontend Dockerfile
# 多阶段构建

# ============================================
# Stage 1: Base
# ============================================
FROM node:20-alpine as base

WORKDIR /app

# ============================================
# Stage 2: Dependencies
# ============================================
FROM base as dependencies

COPY package.json package-lock.json* ./
RUN npm ci

# ============================================
# Stage 3: Development
# ============================================
FROM dependencies as development

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ============================================
# Stage 4: Build
# ============================================
FROM dependencies as build

COPY . .
RUN npm run build

# ============================================
# Stage 5: Production
# ============================================
FROM nginx:alpine as production

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
