# 🔧 执行环境配置设计文档

> Agent 运行时执行环境、工具、Shell 的统一配置系统（与 `libs/config`、Agent 沙箱等一致）

---

## 一、概述

### 1.1 设计目标

为 Agent 运行时提供**完整的执行环境配置系统**，支持：

- **沙箱配置** - Docker/本地执行、资源限制、网络隔离
- **工具配置** - 内置工具启用/禁用、参数配置
- **Shell 环境** - 工作目录、环境变量、Shell 类型
- **MCP 服务器** - Model Context Protocol 工具服务器
- **安全策略** - 权限控制、敏感操作审批

### 1.2 设计原则

1. **Code-First** - 配置以 TOML 文件为主，UI 为可视化编辑器
2. **分层覆盖** - 系统默认 → 环境模板 → Agent配置 → 运行时参数
3. **安全优先** - 默认最小权限，危险操作需确认
4. **可扩展** - 支持自定义工具、MCP 服务器

### 1.3 配置层级

```
配置优先级 (从低到高)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌─────────────────────────────────────────────────┐
  │  Level 4: 运行时参数 (Runtime)                  │  ← API 调用时传入
  │  优先级最高，临时覆盖                            │
  └─────────────────────────────────────────────────┘
                         ▲ 覆盖
  ┌─────────────────────────────────────────────────┐
  │  Level 3: Agent 配置 (agent.toml)               │  ← 每个 Agent 独立
  │  工具选择、特定环境变量、自定义沙箱              │
  └─────────────────────────────────────────────────┘
                         ▲ 覆盖
  ┌─────────────────────────────────────────────────┐
  │  Level 2: 环境模板 (environments/*.toml)        │  ← 可复用模板
  │  如: python-dev, node-dev, data-science         │
  └─────────────────────────────────────────────────┘
                         ▲ 覆盖
  ┌─────────────────────────────────────────────────┐
  │  Level 1: 系统默认 (config/execution.toml)      │  ← 全局默认
  │  默认沙箱配置、默认工具、默认 MCP 服务器         │
  └─────────────────────────────────────────────────┘
```

---

## 二、目录结构

```
backend/
├── config/
│   ├── execution.toml              # Level 1: 系统默认执行环境配置
│   ├── tools.toml                  # 工具定义和默认配置
│   ├── mcp.toml                    # MCP 服务器配置
│   └── environments/               # Level 2: 环境模板
│       ├── python-dev.toml         # Python 开发环境
│       ├── node-dev.toml           # Node.js 开发环境
│       ├── data-science.toml       # 数据科学环境
│       └── minimal.toml            # 最小化环境
│
├── agents/                         # Level 3: Agent 独立配置
│   └── {agent_id}/
│       ├── agent.toml              # Agent 执行环境配置
│       ├── workflow.py             # 工作流代码
│       └── .env                    # Agent 敏感环境变量
│
├── core/
│   └── config/
│       ├── execution_config.py     # 配置模型定义
│       └── execution_loader.py     # 配置加载器
│
└── api/v1/
    └── execution.py                # 执行环境 API
```

---

## 三、配置文件格式

### 3.1 系统默认配置 (`config/execution.toml`)

```toml
# =============================================================================
# 执行环境系统默认配置
# =============================================================================

[metadata]
version = "1.0"
description = "系统默认执行环境配置"

# -----------------------------------------------------------------------------
# 沙箱配置
# -----------------------------------------------------------------------------
[sandbox]
# 执行模式: "docker" | "local" | "remote"
mode = "docker"
timeout_seconds = 30

[sandbox.resources]
memory_limit = "256m"
cpu_limit = 1.0
disk_limit = "1g"

[sandbox.network]
enabled = false
allowed_hosts = []

[sandbox.security]
read_only_root = true
no_new_privileges = true
drop_capabilities = ["ALL"]

# -----------------------------------------------------------------------------
# Shell 环境配置
# -----------------------------------------------------------------------------
[shell]
default_shell = "/bin/bash"
work_dir = "/workspace"

[shell.env]
LANG = "en_US.UTF-8"
TZ = "Asia/Shanghai"
PYTHONUNBUFFERED = "1"

# -----------------------------------------------------------------------------
# 工具配置
# -----------------------------------------------------------------------------
[tools]
enabled = [
    "read_file",
    "write_file",
    "list_directory",
    "search_files",
    "run_python",
    "run_shell",
]

require_confirmation = [
    "write_file",
    "delete_file",
    "run_shell",
    "http_request",
]

auto_approve_patterns = [
    "read_*",
    "list_*",
    "search_*",
]

# -----------------------------------------------------------------------------
# MCP 服务器配置
# -----------------------------------------------------------------------------
[mcp.servers]
# 示例配置
# filesystem = { url = "http://localhost:3000", enabled = true }

# -----------------------------------------------------------------------------
# 日志配置
# -----------------------------------------------------------------------------
[logging]
level = "info"
retention_days = 7
log_tool_calls = true
```

### 3.2 环境模板示例 (`config/environments/python-dev.toml`)

```toml
# =============================================================================
# Python 开发环境模板
# =============================================================================

[metadata]
name = "python-dev"
description = "Python 开发环境，预装常用库"
tags = ["python", "development", "data"]

extends = ""  # 继承系统默认

# -----------------------------------------------------------------------------
# 沙箱配置覆盖
# -----------------------------------------------------------------------------
[sandbox]
timeout_seconds = 60

[sandbox.docker]
image = "python:3.11-slim"
packages = [
    "pandas",
    "numpy",
    "requests",
    "beautifulsoup4",
]

[sandbox.resources]
memory_limit = "512m"
cpu_limit = 2.0

[sandbox.network]
enabled = true
allowed_hosts = [
    "pypi.org",
    "files.pythonhosted.org",
]

# -----------------------------------------------------------------------------
# Shell 环境覆盖
# -----------------------------------------------------------------------------
[shell.env]
PYTHONPATH = "/workspace/src"
PIP_NO_CACHE_DIR = "1"

# -----------------------------------------------------------------------------
# 工具配置覆盖
# -----------------------------------------------------------------------------
[tools]
enabled = [
    "read_file",
    "write_file",
    "list_directory",
    "search_files",
    "run_python",
    "run_shell",
    "http_request",
    "install_package",
]
```

### 3.3 Agent 配置 (`agents/{agent_id}/agent.toml`)

```toml
# =============================================================================
# Agent 执行环境配置
# =============================================================================

[metadata]
agent_id = "research-assistant"
name = "研究助手"
description = "支持网络搜索、数据分析的研究助手"

# 继承环境模板
extends = "python-dev"

# -----------------------------------------------------------------------------
# Agent 级别配置覆盖
# -----------------------------------------------------------------------------
[sandbox]
timeout_seconds = 120

[sandbox.resources]
memory_limit = "1g"

[sandbox.network]
enabled = true
allowed_hosts = [
    "api.search.com",
    "arxiv.org",
    "github.com",
]

# -----------------------------------------------------------------------------
# Agent 特定环境变量
# -----------------------------------------------------------------------------
[shell.env]
SEARCH_API_KEY = "${SEARCH_API_KEY}"
RESEARCH_OUTPUT_DIR = "/workspace/output"

# -----------------------------------------------------------------------------
# 工具配置
# -----------------------------------------------------------------------------
[tools]
enabled = [
    "web_search",
    "fetch_url",
    "save_artifact",
]

[tools.config.web_search]
provider = "tavily"
max_results = 10

# -----------------------------------------------------------------------------
# MCP 服务器配置
# -----------------------------------------------------------------------------
[mcp.servers]
browser = { url = "http://localhost:3001", enabled = true }

# -----------------------------------------------------------------------------
# Human-in-the-Loop 配置
# -----------------------------------------------------------------------------
[hitl]
require_confirmation = [
    "write_file",
    "http_request",
]

auto_approve_patterns = [
    "read_*",
    "fetch_url",
]
```

---

## 四、工具定义 (`config/tools.toml`)

```toml
# =============================================================================
# 工具定义与配置
# =============================================================================

[metadata]
version = "1.0"

# =============================================================================
# 文件操作工具
# =============================================================================
[tools.read_file]
name = "read_file"
description = "读取文件内容"
category = "file"
requires_confirmation = false
enabled_by_default = true

[tools.read_file.parameters]
path = { type = "string", description = "文件路径", required = true }
encoding = { type = "string", default = "utf-8" }

[tools.read_file.constraints]
max_file_size = "10m"
blocked_paths = ["/etc/passwd", "/etc/shadow", "**/.env"]

# -----------------------------------------------------------------------------
[tools.write_file]
name = "write_file"
description = "写入文件内容"
category = "file"
requires_confirmation = true
enabled_by_default = true

[tools.write_file.constraints]
max_file_size = "5m"
workspace_only = true

# =============================================================================
# 代码执行工具
# =============================================================================
[tools.run_python]
name = "run_python"
description = "执行 Python 代码"
category = "code"
requires_confirmation = false
enabled_by_default = true

[tools.run_python.config]
blocked_imports = [
    "subprocess",
    "os.system",
]

# -----------------------------------------------------------------------------
[tools.run_shell]
name = "run_shell"
description = "执行 Shell 命令"
category = "code"
requires_confirmation = true
enabled_by_default = true

[tools.run_shell.config]
blocked_commands = [
    "rm -rf /",
    "dd if=",
    "chmod 777",
]

# =============================================================================
# 网络工具
# =============================================================================
[tools.http_request]
name = "http_request"
description = "发送 HTTP 请求"
category = "network"
requires_confirmation = true
enabled_by_default = false

[tools.http_request.config]
auto_approve_methods = ["GET", "HEAD"]

[tools.http_request.constraints]
blocked_hosts = ["localhost", "127.0.0.1", "*.internal"]
```

---

## 五、MCP 服务器配置 (`config/mcp.toml`)

```toml
# =============================================================================
# MCP 服务器配置
# =============================================================================

[settings]
connection_timeout = 10
tool_timeout = 60
max_retries = 3
cache_tools = true
cache_ttl = 300

# -----------------------------------------------------------------------------
# 预定义 MCP 服务器
# -----------------------------------------------------------------------------

[servers.filesystem]
name = "Filesystem"
description = "文件系统操作工具"
url = "stdio://npx -y @anthropic/mcp-server-filesystem"
transport = "stdio"
enabled = true
auto_start = true

[servers.filesystem.config]
allowed_directories = ["${WORKSPACE}"]

# -----------------------------------------------------------------------------
[servers.git]
name = "Git"
description = "Git 版本控制操作"
url = "stdio://npx -y @anthropic/mcp-server-git"
transport = "stdio"
enabled = true

# -----------------------------------------------------------------------------
[servers.browser]
name = "Browser"
description = "浏览器自动化工具"
url = "http://localhost:3001"
transport = "http"
enabled = false
api_key_env = "BROWSER_MCP_KEY"

[servers.browser.config]
headless = true
timeout = 30
```

---

## 六、API 接口

### 6.1 端点列表

```
/api/v1/execution
│
├── GET    /templates                    # 列出环境模板
├── GET    /templates/{name}             # 获取模板详情
├── GET    /agents/{id}/config           # 获取 Agent 配置
├── PUT    /agents/{id}/config           # 更新 Agent 配置
├── POST   /validate                     # 验证配置
├── POST   /agents/{id}/preview          # 预览合并后配置
├── GET    /tools                        # 列出工具定义
└── GET    /mcp/servers                  # 列出 MCP 服务器
```

### 6.2 使用示例

**获取 Agent 合并后的完整配置：**

```bash
GET /api/v1/execution/agents/research-assistant/config?resolve=true
```

**预览运行时覆盖效果：**

```bash
POST /api/v1/execution/agents/research-assistant/preview
Content-Type: application/json

{
  "sandbox": {
    "timeout_seconds": 180
  },
  "shell": {
    "env": {
      "DEBUG": "true"
    }
  }
}
```

**验证配置：**

```bash
POST /api/v1/execution/validate
Content-Type: application/json

{
  "sandbox": {
    "mode": "docker",
    "timeout_seconds": 60
  }
}
```

---

## 七、配置加载流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           配置加载流程                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ExecutionConfigLoader.load_for_agent(agent_id, runtime_overrides)         │
│                                                                             │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. 加载系统默认配置                                                 │   │
│  │     config/execution.toml                                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  2. 加载 Agent 配置                                                  │   │
│  │     agents/{agent_id}/agent.toml                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  3. 检查 extends 字段，加载环境模板                                   │   │
│  │     config/environments/{template}.toml                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  4. 分层合并配置                                                     │   │
│  │     系统默认 → 环境模板 → Agent配置 → 运行时参数                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  5. 解析环境变量                                                     │   │
│  │     ${VAR} → os.environ.get("VAR")                                   │   │
│  │     ${VAR:default} → os.environ.get("VAR", "default")                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  6. 返回 ExecutionConfig 对象                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 八、与现有系统集成

### 8.1 沙箱执行器

```python
from core.config.execution_loader import ExecutionConfigLoader

# 加载配置
loader = ExecutionConfigLoader()
config = loader.load_for_agent("research-assistant")

# 创建执行器
from core.sandbox.executor import ExecutorFactory
executor = ExecutorFactory.create(config)

# 执行代码
result = await executor.execute_python("print('Hello')")
```

### 8.2 工具注册表

```python
from domains.runtime.infrastructure.tools.registry import ConfiguredToolRegistry

# 创建配置化的工具注册表
registry = ConfiguredToolRegistry(config)

# 获取启用的工具
tools = registry.list_all()

# 检查是否需要确认
if registry.requires_confirmation("write_file"):
    # 请求用户确认
    pass
```

### 8.3 MCP 管理器

```python
from domains.runtime.infrastructure.tools.mcp.client import ConfiguredMCPManager

# 创建 MCP 管理器
mcp_manager = ConfiguredMCPManager(config)
await mcp_manager.initialize()

# 列出所有可用工具
tools = await mcp_manager.list_all_tools()

# 调用工具
result = await mcp_manager.call_tool("browser", "screenshot", {"url": "..."})
```

---

## 九、安全考虑

### 9.1 默认安全策略

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `sandbox.mode` | `docker` | 使用容器隔离 |
| `sandbox.network.enabled` | `false` | 默认禁用网络 |
| `sandbox.security.read_only_root` | `true` | 只读根文件系统 |
| `sandbox.security.no_new_privileges` | `true` | 禁止提权 |
| `tools.require_confirmation` | 危险操作列表 | 需人工确认 |

### 9.2 危险操作清单

以下操作默认需要人工确认：

- `write_file` - 写入文件
- `delete_file` - 删除文件
- `run_shell` - 执行 Shell 命令
- `http_request` (POST/PUT/DELETE) - 写操作的 HTTP 请求
- `query_database` (非 SELECT) - 数据库写操作

### 9.3 命令黑名单

```toml
blocked_commands = [
    "rm -rf /",
    "dd if=",
    "mkfs",
    ":(){ :|:& };:",   # Fork 炸弹
    "chmod 777",
    "curl * | bash",
    "wget * | bash",
]
```

---

## 十、扩展指南

### 10.1 添加新的环境模板

1. 在 `config/environments/` 创建新文件，如 `rust-dev.toml`
2. 定义 `[metadata]` 包含 name, description, tags
3. 设置 `extends = ""` 或继承其他模板
4. 配置沙箱、Shell 环境、工具

### 10.2 添加新的工具

1. 在 `config/tools.toml` 添加工具定义
2. 在 `tools/` 目录实现工具类
3. 使用 `@register_tool` 装饰器注册

### 10.3 添加新的 MCP 服务器

1. 在 `config/mcp.toml` 添加服务器配置
2. 或在 Agent 配置中添加 `[mcp.servers.xxx]`
3. 指定 transport 类型和连接参数

---

## 十一、FAQ

### Q: 如何在开发环境使用本地执行器？

创建 `config/environments/local-dev.toml`：

```toml
[metadata]
name = "local-dev"
description = "本地开发环境（不使用 Docker）"

[sandbox]
mode = "local"  # 使用本地执行器

[sandbox.security]
# 本地模式下这些配置不生效，但建议保留
read_only_root = false
```

### Q: 如何为特定 Agent 添加自定义 MCP 服务器？

在 Agent 配置中添加：

```toml
[mcp.servers.my_custom_server]
name = "My Custom Server"
url = "http://my-server:8080"
transport = "http"
enabled = true
api_key_env = "MY_SERVER_API_KEY"
```

### Q: 如何临时覆盖配置进行测试？

使用 API 的 runtime_overrides 参数：

```python
config = loader.load_for_agent(
    "my-agent",
    runtime_overrides={
        "sandbox": {"timeout_seconds": 300},
        "shell": {"env": {"DEBUG": "1"}},
    }
)
```

---

<div align="center">

**Code-First · 分层覆盖 · 安全优先**

*文档版本: v1.0 | 最后更新: 2026-01-17*

</div>
