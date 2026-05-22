# 📜 SonarCloud 扫描与 API 脚本使用指南

> **版本**: 1.0.0  
> **更新日期**: 2026-01-12

---

## 📋 目录

1. [概述](#概述)
2. [免费版功能说明](#免费版功能说明)
3. [快速开始](#快速开始)
4. [脚本说明](#脚本说明)
5. [API 功能](#api-功能)
6. [导出格式](#导出格式)
7. [常见问题](#常见问题)

---

## 概述

本项目提供三个脚本用于 SonarCloud 扫描和问题下载：

| 脚本 | 平台 | 功能 |
|------|------|------|
| `sonarcloud-scan.ps1` | Windows | 扫描 + API 下载 |
| `sonarcloud-scan.sh` | Linux/Mac | 扫描 + API 下载 |
| `sonarcloud_api.py` | 跨平台 | 纯 API 操作（推荐） |

---

## 免费版功能说明

### ✅ SonarCloud 免费版支持的功能

| 功能 | 支持情况 | 说明 |
|------|----------|------|
| **公开项目分析** | ✅ 完全免费 | 无限制 |
| **API 访问** | ✅ 完全支持 | 所有 API 端点可用 |
| **问题下载** | ✅ 支持 | 通过 `issues/search` API |
| **指标查询** | ✅ 支持 | 通过 `measures/component` API |
| **质量门禁** | ✅ 支持 | 可自定义规则 |
| **PR 装饰** | ✅ 支持 | 自动在 PR 中显示问题 |
| **Webhook** | ✅ 支持 | 扫描完成通知 |
| **私有项目** | ⚠️ 有限 | 免费版支持少量私有项目 |

### 🔑 API 限制

- **请求频率**: 每秒 10 次请求
- **分页**: 每页最多 500 条记录，最多 10,000 条总记录
- **Token**: 每个用户可创建多个 Token

---

## 快速开始

### 1. 设置环境变量

**Windows PowerShell:**
```powershell
$env:SONAR_TOKEN = "c0305abfab1c7692b74afa207e4dfe2235330407"
```

**Linux/Mac:**
```bash
export SONAR_TOKEN="c0305abfab1c7692b74afa207e4dfe2235330407"
```

### 2. 运行扫描并下载报告

**推荐方式 - Python 脚本:**
```bash
# 安装依赖
pip install requests

# 生成 HTML 报告
python scripts/sonarcloud_api.py --org YOUR_ORG report --format html

# 查看指标
python scripts/sonarcloud_api.py --org YOUR_ORG metrics

# 下载问题列表
python scripts/sonarcloud_api.py --org YOUR_ORG issues --format csv
```

**Windows:**
```powershell
.\scripts\sonarcloud-scan.ps1 -ExportFormat html
```

**Linux/Mac:**
```bash
./scripts/sonarcloud-scan.sh --format html
```

---

## 脚本说明

### sonarcloud_api.py（推荐）

纯 Python 实现，跨平台，功能最完整。

```bash
# 查看帮助
python scripts/sonarcloud_api.py --help

# 可用命令
python scripts/sonarcloud_api.py --org ORG issues    # 下载问题
python scripts/sonarcloud_api.py --org ORG metrics   # 查看指标
python scripts/sonarcloud_api.py --org ORG report    # 生成完整报告
python scripts/sonarcloud_api.py --org ORG dashboard # 打开浏览器
```

**参数说明:**

| 参数 | 说明 | 示例 |
|------|------|------|
| `--org, -o` | SonarCloud 组织名（必需） | `--org myorg` |
| `--format, -f` | 导出格式 | `--format html` |

**依赖:**
```bash
pip install requests
```

### sonarcloud-scan.ps1 (Windows)

```powershell
# 完整扫描 + 报告
.\scripts\sonarcloud-scan.ps1

# 只扫描后端
.\scripts\sonarcloud-scan.ps1 -Target backend

# 跳过扫描，只下载问题
.\scripts\sonarcloud-scan.ps1 -SkipScan

# 生成 HTML 报告
.\scripts\sonarcloud-scan.ps1 -SkipScan -ExportFormat html

# 指定组织名
.\scripts\sonarcloud-scan.ps1 -Organization myorg -SkipScan
```

### sonarcloud-scan.sh (Linux/Mac)

```bash
# 完整扫描 + 报告
./scripts/sonarcloud-scan.sh

# 只扫描后端
./scripts/sonarcloud-scan.sh backend

# 跳过扫描，只下载问题
./scripts/sonarcloud-scan.sh --skip-scan

# 生成 HTML 报告
./scripts/sonarcloud-scan.sh --skip-scan --format html

# 指定组织名
./scripts/sonarcloud-scan.sh --org myorg --skip-scan
```

---

## API 功能

### 可用的 API 端点

| 端点 | 功能 | 示例 |
|------|------|------|
| `issues/search` | 搜索问题 | 获取 Bug、漏洞、代码异味 |
| `measures/component` | 获取指标 | 覆盖率、重复率等 |
| `qualitygates/project_status` | 质量门禁状态 | 通过/失败 |
| `components/tree` | 组件树 | 项目文件结构 |
| `sources/lines` | 源代码 | 查看代码行 |

### 直接调用 API（curl）

```bash
# 获取问题列表
curl -H "Authorization: Bearer $SONAR_TOKEN" \
  "https://sonarcloud.io/api/issues/search?componentKeys=YOUR_ORG_ai-agent-backend&ps=100"

# 获取项目指标
curl -H "Authorization: Bearer $SONAR_TOKEN" \
  "https://sonarcloud.io/api/measures/component?component=YOUR_ORG_ai-agent-backend&metricKeys=bugs,vulnerabilities,code_smells,coverage"

# 获取质量门禁状态
curl -H "Authorization: Bearer $SONAR_TOKEN" \
  "https://sonarcloud.io/api/qualitygates/project_status?projectKey=YOUR_ORG_ai-agent-backend"
```

---

## 导出格式

### JSON 格式

完整的结构化数据，适合程序处理。

```json
{
  "timestamp": "2026-01-12 15:30:00",
  "organization": "myorg",
  "projects": [
    {
      "name": "Backend (Python)",
      "key": "myorg_ai-agent-backend",
      "metrics": {
        "bugs": 5,
        "vulnerabilities": 2,
        "code_smells": 120,
        "coverage": 75.5
      },
      "issues": [...]
    }
  ]
}
```

### CSV 格式

表格数据，可在 Excel 中打开。

```csv
Key,Severity,Type,Component,Line,Message,Status,Effort,Tags
AYxxxx,MAJOR,CODE_SMELL,api/agent.py,45,"考虑重构此函数",OPEN,15min,python
```

### HTML 格式

可视化报告，直接在浏览器中查看。

![HTML Report Preview](https://sonarcloud.io/images/project/overview.png)

**特点:**
- 🌙 深色主题
- 📊 指标卡片
- 📋 问题列表
- 📱 响应式设计

---

## 生成的报告目录

报告保存在 `reports/` 目录下：

```
reports/
└── sonarcloud_20260112_153000/
    ├── report.json      # JSON 完整报告
    ├── issues.csv       # CSV 问题列表
    └── report.html      # HTML 可视化报告
```

---

## 常见问题

### 1. Token 无效或过期

```
API 请求失败: 401 Unauthorized
```

**解决方案:**
1. 登录 SonarCloud → My Account → Security
2. 重新生成 Token
3. 更新环境变量

### 2. 找不到项目

```
Project 'xxx_ai-agent-backend' not found
```

**解决方案:**
1. 确认组织名正确
2. 确认项目已在 SonarCloud 创建
3. 首次需要运行扫描创建项目

### 3. 请求频率限制

```
API 请求失败: 429 Too Many Requests
```

**解决方案:**
脚本已内置分页和延时，一般不会触发。如遇到，等待几分钟后重试。

### 4. 没有 jq 工具 (Bash 脚本)

```
警告: jq 未安装，JSON 处理功能受限
```

**解决方案:**
```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt install jq

# 或使用 Python 脚本代替
python scripts/sonarcloud_api.py --org YOUR_ORG report
```

---

## 最佳实践

### 1. CI/CD 集成

在 GitHub Actions 中自动生成报告：

```yaml
- name: Download SonarCloud Report
  env:
    SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
  run: |
    pip install requests
    python scripts/sonarcloud_api.py --org ${{ github.repository_owner }} report --format html
    
- name: Upload Report
  uses: actions/upload-artifact@v4
  with:
    name: sonarcloud-report
    path: reports/
```

### 2. 定期生成报告

使用 cron 定期下载报告：

```bash
# 每天早上 9 点生成报告
0 9 * * * cd /path/to/project && SONAR_TOKEN=xxx python scripts/sonarcloud_api.py --org myorg report --format html
```

### 3. 与其他工具集成

将问题导入到其他系统：

```python
import json

# 读取 SonarCloud 报告
with open("reports/sonarcloud_xxx/report.json") as f:
    report = json.load(f)

# 处理问题
for project in report["projects"]:
    for issue in project["issues"]:
        # 同步到 Jira、GitHub Issues 等
        create_ticket(issue)
```

---

<div align="center">

**代码质量可视化 · 问题追踪自动化**

*SonarCloud API 文档: [sonarcloud.io/web_api](https://sonarcloud.io/web_api)*

</div>
