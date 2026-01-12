# 🔍 SonarQube & SonarCloud 代码质量检测配置

> **版本**: 2.0.0  
> **更新日期**: 2026-01-12

---

## 📋 目录

1. [概述](#概述)
2. [SonarCloud 配置（推荐）](#sonarcloud-配置推荐)
3. [GitHub 集成配置](#github-集成配置)
4. [本地 SonarQube 环境](#本地-sonarqube-环境)
5. [后端配置 (Python)](#后端配置-python)
6. [前端配置 (TypeScript)](#前端配置-typescript)
7. [质量门禁](#质量门禁)
8. [常见问题](#常见问题)

---

## 概述

本项目支持 **SonarCloud**（云端服务）和 **SonarQube**（自托管）两种代码质量检测方案。

| 方案 | 适用场景 | 优势 |
|------|----------|------|
| **SonarCloud** | 公开仓库、团队协作 | 免费（公开项目）、无需维护服务器、自动 PR 检查 |
| **SonarQube** | 私有部署、离线环境 | 完全控制、可定制规则 |

### 项目配置

| 项目 | 语言 | 项目 Key |
|------|------|----------|
| Backend | Python 3.11 | `ai-agent-backend` |
| Frontend | TypeScript/React | `ai-agent-frontend` |
| Monorepo | Full Stack | `ai-agent` |

### 检测内容

- 🐛 **Bug 检测** - 潜在的代码缺陷
- 🔓 **安全漏洞** - 安全问题扫描 (OWASP Top 10)
- 🧹 **代码异味** - 可维护性问题
- 📊 **重复代码** - 代码重复率分析
- 📈 **测试覆盖率** - 单元测试覆盖情况

---

## SonarCloud 配置（推荐）

### 步骤 1: 注册 SonarCloud

1. 访问 [sonarcloud.io](https://sonarcloud.io)
2. 使用 **GitHub** 账号登录
3. 授权 SonarCloud 访问你的仓库

### 步骤 2: 创建项目

1. 点击 **"+"** → **"Analyze new project"**
2. 选择 **GitHub** 仓库 `ai-agent`
3. 选择组织（Organization）
4. 完成项目创建

### 步骤 3: 生成访问令牌

1. 进入 **My Account** → **Security**
2. 点击 **"Generate Tokens"**
3. 输入令牌名称（如 `ai-agent-ci`）
4. 复制生成的令牌（只显示一次！）

### 步骤 4: 配置 GitHub Secrets

在 GitHub 仓库中配置 Secrets：

1. 进入仓库 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **"New repository secret"**
3. 添加以下 Secret：

| Name | Value | 说明 |
|------|-------|------|
| `SONAR_TOKEN` | `c0305abfab1c7692b74afa207e4dfe2235330407` | SonarCloud 访问令牌 |

> ⚠️ **安全提示**: 令牌应保密，不要提交到代码仓库中！

---

## GitHub 集成配置

### 自动分析工作流

项目已配置 `.github/workflows/sonarcloud.yml`，会在以下情况自动运行：

| 触发事件 | 分析范围 |
|----------|----------|
| Push 到 `main`/`master`/`develop` | 完整分析 + Monorepo 分析 |
| Pull Request | 增量分析（仅变更代码） |

### 工作流文件结构

```
.github/workflows/
├── sonar.yml        # 本地 SonarQube 分析（可选）
└── sonarcloud.yml   # SonarCloud 分析（推荐）
```

### 配置 GitHub Secrets

**必需的 Secrets:**

```
Repository → Settings → Secrets and variables → Actions
```

| Secret 名称 | 描述 | 示例值 |
|-------------|------|--------|
| `SONAR_TOKEN` | SonarCloud 访问令牌 | `c0305abfab1c7692b74afa207e4dfe2235330407` |

**可选的 Secrets（用于本地 SonarQube）:**

| Secret 名称 | 描述 | 示例值 |
|-------------|------|--------|
| `SONAR_HOST_URL` | SonarQube 服务器地址 | `http://your-server:9000` |

### PR 检查集成

配置后，每次 Pull Request 都会：

1. ✅ 运行代码质量分析
2. ✅ 在 PR 中显示检查结果
3. ✅ 自动添加代码注释（问题标注）
4. ✅ 显示质量门禁状态

### 查看分析结果

- **SonarCloud Dashboard**: https://sonarcloud.io/project/overview?id=YOUR_ORG_ai-agent
- **GitHub Checks**: PR 页面的 "Checks" 标签页

---

## 本地 SonarQube 环境

如果需要本地部署 SonarQube：

### 使用 Docker 启动

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

### 配置环境变量

**Windows PowerShell:**
```powershell
$env:SONAR_HOST_URL = "http://localhost:9000"
$env:SONAR_TOKEN = "your-generated-token"
```

**Linux/Mac:**
```bash
export SONAR_HOST_URL=http://localhost:9000
export SONAR_TOKEN=your-generated-token
```

---

## 后端配置 (Python)

### 配置文件

`backend/sonar-project.properties`:

```properties
sonar.projectKey=ai-agent-backend
sonar.projectName=AI Agent Backend
sonar.sources=api,app,core,db,models,schemas,services,tools,utils
sonar.tests=tests
sonar.python.version=3.11
sonar.python.coverage.reportPaths=coverage.xml
```

### 运行本地扫描

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
sonar.projectKey=ai-agent-frontend
sonar.projectName=AI Agent Frontend
sonar.sources=src
sonar.typescript.tsconfigPath=tsconfig.json
sonar.javascript.lcov.reportPaths=coverage/lcov.info
```

### 运行本地扫描

```bash
cd frontend

# 方法 1: 使用 npm 脚本
npm run sonar

# 方法 2: 手动执行
npm run test:coverage
sonar-scanner
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

### 在 SonarCloud 中配置

1. 进入项目 → **Administration** → **Quality Gates**
2. 选择或创建质量门禁
3. 添加上述条件

---

## 常见问题

### 1. sonar-scanner 未找到

**安装方法:**

```bash
# macOS
brew install sonar-scanner

# Windows - 使用 Chocolatey
choco install sonarscanner-msbuild-net46

# 或下载安装: https://docs.sonarqube.org/latest/analysis/scan/sonarscanner/
```

### 2. SonarCloud 分析失败

检查以下配置：

1. **SONAR_TOKEN** Secret 是否正确配置
2. 项目 Key 是否与 SonarCloud 上的一致
3. 组织名称是否正确

### 3. 覆盖率报告未识别

确保报告路径正确：

```bash
# 后端
ls backend/coverage.xml

# 前端
ls frontend/coverage/lcov.info
```

### 4. PR 检查不显示

确保：
1. GitHub App 已安装并授权
2. SonarCloud 项目已绑定 GitHub 仓库
3. 工作流文件位于 `.github/workflows/` 目录

---

## 快速参考

### 本地扫描命令

```bash
# Windows
.\scripts\sonar-scan.ps1 -Target all

# Linux/Mac
./scripts/sonar-scan.sh all

# 只扫描后端
./scripts/sonar-scan.sh backend

# 只扫描前端
./scripts/sonar-scan.sh frontend
```

### 查看 SonarCloud 报告

```
https://sonarcloud.io/project/overview?id=YOUR_ORG_ai-agent-backend
https://sonarcloud.io/project/overview?id=YOUR_ORG_ai-agent-frontend
```

---

## 配置清单 ✅

完成以下步骤以启用 SonarCloud + GitHub 集成：

- [ ] 在 SonarCloud 创建账号并导入项目
- [ ] 生成 SonarCloud 访问令牌
- [ ] 在 GitHub 仓库添加 `SONAR_TOKEN` Secret
- [ ] 推送代码触发首次分析
- [ ] 在 SonarCloud 查看分析结果
- [ ] 配置质量门禁（可选）

---

<div align="center">

**代码质量可视化 · 持续改进**

*SonarCloud Dashboard: [sonarcloud.io](https://sonarcloud.io)*

*文档版本: v2.0.0 | 最后更新: 2026-01-12*

</div>
