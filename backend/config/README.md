# 配置文件说明

> **完整文档**：请参阅 [docs/CONFIGURATION.md](../docs/CONFIGURATION.md)

## 文件结构

```
config/
├── app.toml                    # 应用基础配置
├── app.development.toml        # 开发环境覆盖
├── app.staging.toml            # 预发环境覆盖
├── app.production.toml         # 生产环境覆盖
├── execution.toml              # 执行环境系统默认配置
├── tools.toml                  # 工具配置
├── mcp.toml                    # MCP 服务器配置
├── litellm_models.yaml         # LiteLLM 模型配置
├── environments/               # 环境模板目录
│   ├── docker-dev.toml         # Docker 开发环境（网络已启用）
│   ├── network-enabled.toml    # 完全网络访问
│   ├── network-restricted.toml # 受限网络访问（生产推荐）
│   ├── local-dev.toml          # 本地开发环境
│   ├── python-dev.toml         # Python 开发环境
│   ├── node-dev.toml           # Node.js 开发环境
│   ├── data-science.toml       # 数据科学环境
│   └── minimal.toml            # 最小化环境
├── NETWORK_CONFIG_GUIDE.md     # 网络配置详细指南
└── README.md                   # 本文件
```

## 配置优先级

```
环境变量 > .env > app.{env}.toml > app.toml > 代码默认值
```

## 多环境配置

通过 `APP_ENV` 环境变量切换环境：

```bash
# 开发环境（默认）
export APP_ENV=development

# 预发环境
export APP_ENV=staging

# 生产环境
export APP_ENV=production
```

## 快速开始

### 1. 设置环境变量

```bash
# 复制示例配置
cp config/env.example .env

# 编辑 .env，填写 API Keys
```

### 2. 修改配置（可选）

编辑 `app.toml` 或对应环境的配置文件：

```toml
[simplemem]
enabled = true
extraction_model = "gpt-4o-mini"
```

### 3. 环境变量覆盖

```bash
# 任何配置都可以通过环境变量覆盖
export SIMPLEMEM_ENABLED=false
```

## 配置分类

| 类型 | 存放位置 | 示例 |
|------|---------|------|
| 敏感信息 | `.env` | API Keys、数据库密码 |
| 环境相关 | `.env` | DATABASE_URL、APP_ENV |
| 功能开关 | `app.toml` | simplemem.enabled |
| 模型配置 | `app.toml` | models.available |
| 环境特定 | `app.{env}.toml` | logging.level |
| 执行环境 | `execution.toml` | 沙箱、网络、资源限制 |
| 环境模板 | `environments/*.toml` | 预定义的执行环境 |

---

## 🌐 沙箱网络配置

### 快速启用网络

**方法 1：使用环境模板（推荐）**

在 Agent 配置中引用模板：

```toml
# agents/my-agent/config.toml
extends = "docker-dev"  # 网络已启用 + 基础白名单
```

**方法 2：修改默认配置**

编辑 `execution.toml`：

```toml
[sandbox.network]
enabled = true              # 启用网络
allowed_hosts = [           # 白名单（可选）
    "pypi.org",
    "api.openai.com",
]
```

### 可用的网络环境模板

| 模板 | 网络状态 | 适用场景 |
|------|---------|---------|
| `docker-dev` | ✅ 启用（白名单） | 本地开发 |
| `network-enabled` | ✅ 完全访问 | 需要访问多个 API |
| `network-restricted` | ✅ 严格白名单 | 生产环境（推荐） |
| `local-dev` | ❌ 禁用 | 离线开发 |

### 详细文档

📖 **完整网络配置指南**：[NETWORK_CONFIG_GUIDE.md](./NETWORK_CONFIG_GUIDE.md)

包含：
- ✅ 配置层次说明
- ✅ 使用方法（4 种）
- ✅ 安全建议
- ✅ 常见问题
- ✅ 配置示例
- ✅ 测试方法

### 测试网络配置

```bash
cd backend

# 运行网络配置测试
uv run python scripts/test_network_config.py
```

---

## 🔧 执行环境配置

执行环境配置支持**分层覆盖**：

```
系统默认 (execution.toml)
    ↓
环境模板 (environments/*.toml)
    ↓
Agent 配置 (agents/*/config.toml)
    ↓
运行时参数
```

### 配置内容

- **沙箱配置**：执行模式（Docker/本地）、资源限制、网络
- **Shell 环境**：工作目录、环境变量
- **工具配置**：启用/禁用工具、确认策略
- **MCP 集成**：外部服务连接
- **HITL 配置**：人机交互策略
- **日志配置**：日志级别、保留策略