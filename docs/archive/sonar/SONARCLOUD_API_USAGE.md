# SonarCloud API 使用指南

## 📋 概述

`sonarcloud_api.py` 是一个通过 SonarCloud API 获取代码质量报告的工具，**无需运行 sonar-scanner**，直接从 SonarCloud 服务器下载已分析的问题和指标。

## ✅ 优势

- ✅ **无需本地扫描**：直接从 SonarCloud 获取已分析的结果
- ✅ **支持 .env 配置**：配置简单，安全可靠
- ✅ **多种报告格式**：JSON、CSV、HTML
- ✅ **快速查看指标**：无需等待扫描完成

## 🔧 配置方式

### 方式 1: 使用 .env 文件（推荐）

在项目根目录创建 `.env` 文件（或使用现有的）：

```bash
# SonarCloud 配置
SONAR_TOKEN=your-sonarcloud-token
SONAR_ORGANIZATION=your-github-org
```

**配置步骤：**

1. **获取 SonarCloud Token**
   - 访问：https://sonarcloud.io/account/security
   - 登录你的 SonarCloud 账户
   - 点击 "Generate Token"
   - 输入名称（如：`ai-agent`）
   - 复制生成的 Token

2. **确定组织名**
   - 通常是你的 GitHub 用户名
   - 或 GitHub 组织名
   - 例如：`tianyehedashu` 或 `my-org`

3. **创建 .env 文件**
   ```bash
   # 在项目根目录
   cp env.example .env
   # 编辑 .env 文件，填写 SONAR_TOKEN 和 SONAR_ORGANIZATION
   ```

### 方式 2: 环境变量

**Linux/Mac:**
```bash
export SONAR_TOKEN=your-token
export SONAR_ORGANIZATION=your-org
```

**Windows PowerShell:**
```powershell
$env:SONAR_TOKEN = "your-token"
$env:SONAR_ORGANIZATION = "your-org"
```

## 📖 使用方法

### 1. 生成完整报告（HTML）

```bash
# 使用 .env 配置（推荐）
python scripts/sonarcloud_api.py report --format html

# 或指定组织名
python scripts/sonarcloud_api.py --org your-org report --format html
```

**输出：**
- `reports/sonarcloud_YYYYMMDD_HHMMSS/report.html` - 可视化 HTML 报告
- `reports/sonarcloud_YYYYMMDD_HHMMSS/report.json` - JSON 数据

### 2. 查看项目指标

```bash
python scripts/sonarcloud_api.py metrics
```

**输出示例：**
```
📊 项目指标概览

📦 Backend (Python)
   🐛 Bugs: 5
   🔓 漏洞: 2
   🧹 代码异味: 23
   📊 覆盖率: 78.5%
   📋 重复率: 3.2%
   📏 代码行数: 15234
   🎯 可靠性评级: A
   🔒 安全评级: B
   🔧 可维护性评级: A
   🚦 质量门禁: OK
```

### 3. 下载问题列表

```bash
# JSON 格式
python scripts/sonarcloud_api.py issues --format json

# CSV 格式（可用 Excel 打开）
python scripts/sonarcloud_api.py issues --format csv
```

### 4. 生成所有格式的报告

```bash
python scripts/sonarcloud_api.py report --format all
```

**输出：**
- `report.json` - JSON 数据
- `issues.csv` - CSV 表格
- `report.html` - HTML 可视化报告

### 5. 打开 SonarCloud 仪表板

```bash
python scripts/sonarcloud_api.py dashboard
```

会在浏览器中打开 SonarCloud 项目页面。

## 📊 报告格式说明

### HTML 报告

- **可视化指标卡片**：Bugs、漏洞、代码异味、覆盖率等
- **问题列表表格**：按严重程度和类型分类
- **响应式设计**：支持移动端查看
- **深色主题**：GitHub 风格

### JSON 报告

包含完整的项目数据：
- 项目信息
- 指标数据
- 问题列表（包含所有字段）

### CSV 报告

表格格式，包含以下列：
- Key - 问题唯一标识
- Severity - 严重程度（BLOCKER, CRITICAL, MAJOR, MINOR, INFO）
- Type - 类型（BUG, VULNERABILITY, CODE_SMELL）
- Component - 文件路径
- Line - 行号
- Message - 问题描述
- Status - 状态
- Effort - 修复工作量
- Tags - 标签

## 🔄 完整工作流程

### 场景 1: 首次使用

```bash
# 1. 配置 .env 文件
echo "SONAR_TOKEN=your-token" >> .env
echo "SONAR_ORGANIZATION=your-org" >> .env

# 2. 生成 HTML 报告
python scripts/sonarcloud_api.py report --format html

# 3. 打开报告查看
# Windows: start reports/sonarcloud_*/report.html
# Linux/Mac: open reports/sonarcloud_*/report.html
```

### 场景 2: 定期检查代码质量

```bash
# 快速查看指标
python scripts/sonarcloud_api.py metrics

# 如果发现问题，生成详细报告
python scripts/sonarcloud_api.py report --format html
```

### 场景 3: 导出问题列表用于修复

```bash
# 导出为 CSV，在 Excel 中打开
python scripts/sonarcloud_api.py issues --format csv

# 或导出为 JSON，用于脚本处理
python scripts/sonarcloud_api.py issues --format json
```

## 🆚 与 sonar-scanner 的对比

| 功能 | sonar-scanner | sonarcloud_api.py |
|------|---------------|-------------------|
| **需要本地扫描** | ✅ 是 | ❌ 否 |
| **需要安装工具** | ✅ 是 | ❌ 否 |
| **获取已分析结果** | ❌ 否 | ✅ 是 |
| **生成本地报告** | ❌ 否 | ✅ 是 |
| **速度** | 慢（需要扫描） | 快（直接下载） |
| **适用场景** | 首次分析、CI/CD | 查看结果、生成报告 |

**推荐使用场景：**

- **sonar-scanner**: 首次分析代码、CI/CD 流水线
- **sonarcloud_api.py**: 查看已有分析结果、生成报告、定期检查

## 🔍 故障排查

### 问题 1: `SONAR_TOKEN 未配置`

**原因：** `.env` 文件不存在或未正确配置

**解决：**
```bash
# 检查 .env 文件是否存在
ls -la .env

# 检查配置是否正确
cat .env | grep SONAR_TOKEN

# 确保 .env 文件在项目根目录或当前目录
```

### 问题 2: `组织名未配置`

**原因：** `SONAR_ORGANIZATION` 未设置

**解决：**
```bash
# 方式 1: 在 .env 中添加
echo "SONAR_ORGANIZATION=your-org" >> .env

# 方式 2: 使用命令行参数
python scripts/sonarcloud_api.py --org your-org report
```

### 问题 3: `API 请求失败`

**可能原因：**
- Token 无效或已过期
- 组织名不正确
- 网络连接问题

**解决：**
```bash
# 1. 验证 Token
# 访问 https://sonarcloud.io/account/security 检查 Token 状态

# 2. 验证组织名
# 访问 https://sonarcloud.io/ 查看你的组织名

# 3. 测试网络连接
curl https://sonarcloud.io/api/authentication/validate
```

### 问题 4: `项目不存在`

**原因：** 项目 Key 不正确（格式：`组织名_项目后缀`）

**解决：**
- 检查 `sonarcloud_api.py` 中的 `PROJECTS` 配置
- 确保项目已在 SonarCloud 中创建
- 检查组织名是否正确

## 📝 配置示例

### 完整的 .env 配置

```bash
# SonarCloud 配置
SONAR_TOKEN=abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
SONAR_ORGANIZATION=tianyehedashu
```

### 命令行使用示例

```bash
# 使用环境变量（不推荐，但可用于临时测试）
export SONAR_TOKEN=your-token
export SONAR_ORGANIZATION=your-org
python scripts/sonarcloud_api.py report

# 使用命令行参数覆盖组织名
python scripts/sonarcloud_api.py --org different-org report
```

## 🎯 最佳实践

1. **使用 .env 文件**
   - 安全：Token 不会出现在命令行历史
   - 方便：一次配置，多次使用
   - 版本控制：将 `.env` 添加到 `.gitignore`

2. **定期生成报告**
   - 每次代码审查前生成 HTML 报告
   - 每周查看一次指标变化
   - 修复问题后重新生成报告验证

3. **结合 CI/CD**
   - 在 CI 中运行 `sonar-scanner` 上传分析结果
   - 在 CD 中使用 `sonarcloud_api.py` 生成报告
   - 将报告作为构建产物保存

4. **问题跟踪**
   - 导出 CSV 格式用于问题跟踪
   - 按严重程度排序，优先修复 BLOCKER 和 CRITICAL
   - 定期检查代码异味数量变化

## 📚 相关文档

- [SonarCloud 官方文档](https://docs.sonarcloud.io/)
- [SonarCloud API 文档](https://sonarcloud.io/web_api)
- [Makefile SonarCloud 配置修复](./SONARCLOUD_MAKEFILE_FIX.md)

## 💡 提示

- HTML 报告会自动保存到 `reports/sonarcloud_YYYYMMDD_HHMMSS/` 目录
- 可以同时生成多种格式：`--format all`
- Token 不会在输出中完整显示，只显示后 4 位
- 如果项目很多，API 请求可能需要一些时间，请耐心等待
