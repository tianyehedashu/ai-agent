# 🔍 SonarQube 代码质量检测配置

> **版本**: 1.0.0
> **更新日期**: 2026-01-12

---

## 📋 目录

1. [概述](#概述)
2. [本地 SonarQube 环境](#本地-sonarqube-环境)
3. [后端配置 (Python)](#后端配置-python)
4. [前端配置 (TypeScript)](#前端配置-typescript)
5. [CI/CD 集成](#cicd-集成)
6. [质量门禁](#质量门禁)
7. [常见问题](#常见问题)

---

## 概述

本项目使用 SonarQube 进行代码质量检测，分别为前端和后端配置了独立的项目。

| 项目 | 语言 | 项目 Key |
|------|------|----------|
| Backend | Python 3.11 | `ai-agent-backend` |
| Frontend | TypeScript/React | `ai-agent-frontend` |

### 检测内容

- 🐛 **Bug 检测** - 潜在的代码缺陷
- 🔓 **安全漏洞** - 安全问题扫描
- 🧹 **代码异味** - 可维护性问题
- 📊 **重复代码** - 代码重复率分析
- 📈 **测试覆盖率** - 单元测试覆盖情况

---

## 本地 SonarQube 环境

### 使用 Docker 启动 SonarQube

```bash
# 启动 SonarQube 服务
docker-compose -f docker-compose.sonar.yml up -d

# 查看日志
docker-compose -f docker-compose.sonar.yml logs -f

# 停止服务
docker-compose -f docker-compose.sonar.yml down
```

### 访问 SonarQube

- **地址**: http://localhost:9000
- **默认账号**: admin
- **默认密码**: admin (首次登录需修改)

### 创建项目令牌

1. 登录 SonarQube
2. 进入 **My Account** > **Security**
3. 生成新令牌 (Token)
4. 保存令牌用于后续配置

### 配置环境变量

**Linux/Mac:**
```bash
export SONAR_HOST_URL=http://localhost:9000
export SONAR_TOKEN=your-generated-token
```

**Windows PowerShell:**
```powershell
$env:SONAR_HOST_URL = "http://localhost:9000"
$env:SONAR_TOKEN = "your-generated-token"
```

---

## 后端配置 (Python)

### 配置文件

`backend/sonar-project.properties`:

```properties
# 项目标识
sonar.projectKey=ai-agent-backend
sonar.projectName=AI Agent Backend

# Python 配置
sonar.language=py
sonar.python.version=3.11

# 源代码目录
sonar.sources=api,app,core,db,models,schemas,services,tools,utils
sonar.tests=tests

# 覆盖率报告
sonar.python.coverage.reportPaths=coverage.xml

# 测试报告
sonar.python.xunit.reportPath=test-results.xml
```

### 运行扫描

```bash
cd backend

# 方法 1: 使用 Makefile
make sonar

# 方法 2: 手动执行
pytest --cov --cov-report=xml:coverage.xml --junitxml=test-results.xml
sonar-scanner
```

### 生成的报告

| 文件 | 说明 | 生成命令 |
|------|------|----------|
| `coverage.xml` | 代码覆盖率 (Cobertura) | `pytest --cov-report=xml` |
| `test-results.xml` | 测试结果 (JUnit) | `pytest --junitxml=...` |

---

## 前端配置 (TypeScript)

### 配置文件

`frontend/sonar-project.properties`:

```properties
# 项目标识
sonar.projectKey=ai-agent-frontend
sonar.projectName=AI Agent Frontend

# TypeScript 配置
sonar.typescript.tsconfigPath=tsconfig.json

# 源代码目录
sonar.sources=src
sonar.tests=src
sonar.test.inclusions=**/*.test.ts,**/*.test.tsx

# 覆盖率报告
sonar.javascript.lcov.reportPaths=coverage/lcov.info
```

### 运行扫描

```bash
cd frontend

# 方法 1: 使用 npm 脚本
npm run sonar

# 方法 2: 手动执行
npm run test:coverage
sonar-scanner
```

### 生成的报告

| 文件 | 说明 | 生成命令 |
|------|------|----------|
| `coverage/lcov.info` | 代码覆盖率 (LCOV) | `npm run test:coverage` |
| `eslint-report.json` | ESLint 报告 (可选) | `npm run lint -- -f json -o eslint-report.json` |

---

## CI/CD 集成

### GitHub Actions

项目已配置 `.github/workflows/sonar.yml`，会在以下情况自动运行扫描：

- Push 到 `main` 或 `develop` 分支
- 创建 Pull Request

### 配置 Secrets

在 GitHub 仓库设置中添加以下 Secrets：

| Secret | 说明 |
|--------|------|
| `SONAR_HOST_URL` | SonarQube 服务器地址 |
| `SONAR_TOKEN` | 访问令牌 |

### 使用 SonarCloud

如果使用 SonarCloud (免费的公共项目)：

1. 在 [sonarcloud.io](https://sonarcloud.io) 注册
2. 导入 GitHub 仓库
3. 获取令牌并添加到 GitHub Secrets
4. 修改 `sonar-project.properties`:

```properties
sonar.organization=your-org
sonar.host.url=https://sonarcloud.io
```

---

## 质量门禁

### 推荐的质量门禁配置

| 指标 | 条件 | 说明 |
|------|------|------|
| 覆盖率 | ≥ 70% | 新代码覆盖率 |
| 重复率 | ≤ 3% | 代码重复率 |
| 可维护性评级 | A | 代码异味评级 |
| 可靠性评级 | A | Bug 评级 |
| 安全评级 | A | 安全漏洞评级 |

### 在 SonarQube 中配置

1. 进入 **Quality Gates**
2. 创建或编辑门禁规则
3. 添加上述条件
4. 将门禁应用到项目

---

## 常见问题

### 1. sonar-scanner 未找到

**安装 sonar-scanner:**

```bash
# macOS
brew install sonar-scanner

# Linux (手动安装)
wget https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip
unzip sonar-scanner-cli-*.zip
export PATH=$PATH:$(pwd)/sonar-scanner-*/bin

# Windows
# 下载并安装: https://docs.sonarqube.org/latest/analysis/scan/sonarscanner/
```

### 2. ES 内存不足 (Docker)

如果 SonarQube 启动失败，可能是 Elasticsearch 内存限制：

```bash
# Linux
sudo sysctl -w vm.max_map_count=262144

# 永久设置
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### 3. 覆盖率报告未识别

确保报告路径正确：

```bash
# 后端 - 检查文件存在
ls backend/coverage.xml

# 前端 - 检查文件存在
ls frontend/coverage/lcov.info
```

### 4. 扫描超时

对于大型项目，增加扫描超时：

```properties
# sonar-project.properties
sonar.ws.timeout=300
```

---

## 快速参考

### 本地扫描命令

```bash
# 扫描全部 (Linux/Mac)
./scripts/sonar-scan.sh all

# 扫描全部 (Windows)
.\scripts\sonar-scan.ps1 -Target all

# 只扫描后端
./scripts/sonar-scan.sh backend

# 只扫描前端
./scripts/sonar-scan.sh frontend
```

### 后端快速扫描

```bash
cd backend
make sonar
```

### 前端快速扫描

```bash
cd frontend
npm run sonar
```

---

<div align="center">

**代码质量可视化 · 持续改进**

*文档版本: v1.0.0 | 最后更新: 2026-01-12*

</div>
