# 配置管理

## 概述

本项目采用 **TOML + .env 统一配置** 方案：
- `.env` 只存放敏感信息（API Keys、密码）
- `app.toml` 通过 `${VAR}` 语法引用 `.env` 变量
- 在 TOML 中可以看到**所有配置的全貌**

## 配置架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        统一配置架构                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  .env (敏感信息)                                                         │
│  ├── OPENAI_API_KEY=sk-xxx                                              │
│  ├── DATABASE_URL=postgresql://...                                      │
│  └── ...                                                                │
│         ↓                                                               │
│  config/app.toml (统一管理)                                              │
│  ├── [llm.openai]                                                       │
│  │   api_key = "${OPENAI_API_KEY:}"    ← 引用 .env 变量                 │
│  ├── [infra]                                                            │
│  │   database_url = "${DATABASE_URL:...}"                               │
│  └── [simplemem]                                                        │
│      enabled = true                     ← 应用逻辑配置                   │
│         ↓                                                               │
│  config/app.{env}.toml (环境覆盖)                                        │
│  └── 开发/预发/生产 环境特定配置                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 环境变量插值语法

在 TOML 文件中可以使用以下语法引用环境变量：

```toml
# 引用环境变量，不存在则为空
api_key = "${OPENAI_API_KEY}"

# 引用环境变量，不存在则使用默认值
database_url = "${DATABASE_URL:postgresql://localhost/ai_agent}"
```

## 文件结构

```
backend/
├── .env                        # 敏感信息（不入版本控制）
├── .env.example                # .env 模板（入版本控制）
├── config/
│   ├── app.toml               # 基础配置（默认值）
│   ├── app.development.toml   # 开发环境覆盖（可选）
│   ├── app.staging.toml       # 预发环境覆盖（可选）
│   ├── app.production.toml    # 生产环境覆盖（可选）
│   └── README.md              # 配置说明
└── app/
    ├── config.py              # Pydantic Settings（统一入口）
    └── config_loader.py       # TOML 加载器
```

## 配置分类

### 1. 敏感信息 → `.env`

**绝对不能入版本控制**，通过环境变量或 K8s Secret 注入：

```bash
# API Keys
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
DEEPSEEK_API_KEY=sk-xxx

# 数据库密码
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/db

# JWT 密钥
JWT_SECRET_KEY=your-secret-key
```

### 2. 环境相关 → `.env` 或环境变量

不同环境值不同，但不敏感：

```bash
# 开发环境
APP_ENV=development
DEBUG=true
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent

# 生产环境
APP_ENV=production
DEBUG=false
DATABASE_URL=postgresql+asyncpg://user:xxx@prod-db:5432/ai_agent
```

### 3. 应用逻辑 → `config/app.toml`

功能开关、业务参数，**可以入版本控制**：

```toml
[simplemem]
enabled = true
extraction_model = "gpt-4o-mini"

[agent]
max_iterations = 20
timeout_seconds = 600
```

### 4. 环境特定覆盖 → `config/app.{env}.toml`

仅覆盖特定环境需要修改的配置：

```toml
# config/app.production.toml
# 生产环境：关闭调试、使用更强的模型

[simplemem]
extraction_model = "gpt-4o"  # 生产用更好的模型

[logging]
level = "WARNING"  # 生产减少日志

[monitoring]
tracing_enabled = true
```

## 多环境配置

### 环境识别

通过 `APP_ENV` 环境变量识别当前环境：

| APP_ENV | 说明 | 配置文件 |
|---------|------|---------|
| `development` | 本地开发 | app.toml + app.development.toml |
| `staging` | 预发测试 | app.toml + app.staging.toml |
| `production` | 生产环境 | app.toml + app.production.toml |

### 配置合并规则

```python
# 加载顺序（后面覆盖前面）
base_config = load("config/app.toml")
env_config = load(f"config/app.{APP_ENV}.toml")  # 如果存在
final_config = merge(base_config, env_config)
```

### 典型环境差异

| 配置项 | 开发环境 | 生产环境 |
|--------|---------|---------|
| `logging.level` | DEBUG | WARNING |
| `simplemem.extraction_model` | gpt-4o-mini | gpt-4o |
| `monitoring.tracing_enabled` | false | true |
| `agent.max_iterations` | 20 | 50 |

## 使用方式

### 代码中读取配置

```python
# 方式 1：Pydantic Settings（支持环境变量覆盖）
from app.config import settings

if settings.simplemem_enabled:
    model = settings.simplemem_extraction_model

# 方式 2：直接读取 TOML（获取完整结构）
from app.config_loader import app_config

for model in app_config.models.available:
    print(f"{model.name}: ${model.input_price}/1M tokens")
```

### 环境变量覆盖

任何 TOML 配置都可以通过环境变量覆盖：

```bash
# TOML 路径转换为环境变量名
# [simplemem].enabled → SIMPLEMEM_ENABLED
# [simplemem.window].size → SIMPLEMEM_WINDOW_SIZE

export SIMPLEMEM_ENABLED=false
export SIMPLEMEM_EXTRACTION_MODEL=deepseek-chat
```

### Docker 部署

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - APP_ENV=production
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DATABASE_URL=postgresql+asyncpg://...
    volumes:
      - ./config:/app/config:ro  # 挂载配置目录
```

### Kubernetes 部署

```yaml
# ConfigMap - 非敏感配置
apiVersion: v1
kind: ConfigMap
metadata:
  name: ai-agent-config
data:
  APP_ENV: "production"
  SIMPLEMEM_ENABLED: "true"

---
# Secret - 敏感信息
apiVersion: v1
kind: Secret
metadata:
  name: ai-agent-secrets
type: Opaque
stringData:
  OPENAI_API_KEY: "sk-xxx"
  DATABASE_URL: "postgresql+asyncpg://..."
```

## 配置格式选型

### 为什么选择 TOML + .env？

| 格式 | 优点 | 缺点 | 本项目用途 |
|------|------|------|-----------|
| **.env** | 安全、容器友好 | 不支持嵌套 | 敏感信息 |
| **TOML** | 类型明确、支持注释 | 深层嵌套冗长 | 应用配置 |
| YAML | 嵌套优雅 | 缩进敏感、类型歧义 | K8s 配置 |
| JSON | 解析快 | 无注释 | API 响应 |

### TOML vs YAML 对比

```yaml
# YAML - 缩进敏感，容易出错
simplemem:
  enabled: true
  window:
    size: 10  # 缩进错误很难发现
```

```toml
# TOML - 类型明确，不依赖缩进
[simplemem]
enabled = true

[simplemem.window]
size = 10
```

## 最佳实践

### ✅ 推荐

1. **敏感信息永远不入版本控制**
2. **使用环境变量覆盖生产配置**
3. **TOML 文件添加详细注释**
4. **提供 `.env.example` 模板**
5. **不同环境使用不同的配置文件**

### ❌ 避免

1. **在代码中硬编码配置**
2. **在 TOML 中写敏感信息**
3. **生产环境使用 DEBUG=true**
4. **忽略配置验证**

## 配置项速查

### SimpleMem

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `simplemem.enabled` | bool | true | 启用会话内长程记忆 |
| `simplemem.extraction_model` | str | gpt-4o-mini | 记忆提取模型 |
| `simplemem.window.size` | int | 10 | 滑动窗口大小 |
| `simplemem.filter.novelty_threshold` | float | 0.35 | 新颖度阈值 |

### Agent

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `agent.max_iterations` | int | 20 | 最大迭代次数 |
| `agent.timeout_seconds` | int | 600 | 超时时间（秒） |
| `agent.hitl.enabled` | bool | true | Human-in-the-Loop |

### 日志

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `logging.level` | str | INFO | 日志级别 |
| `logging.format` | str | json | 日志格式 |

完整配置项请参考 `config/app.toml`。
