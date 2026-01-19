# 沙箱网络配置指南

本文档说明如何为 AI Agent 沙箱配置网络访问权限。

## 📋 目录

1. [配置层次](#配置层次)
2. [可用的环境模板](#可用的环境模板)
3. [使用方法](#使用方法)
4. [安全建议](#安全建议)
5. [常见问题](#常见问题)

---

## 配置层次

配置优先级从低到高：

```
系统默认配置 (execution.toml)
    ↓
环境模板 (environments/*.toml)
    ↓
Agent 配置 (agents/*/config.toml)
    ↓
运行时参数
```

---

## 可用的环境模板

### 1. `docker-dev` - Docker 开发环境

**特点**：
- ✅ 网络已启用
- ✅ 白名单模式（常用开发站点）
- ✅ 资源限制较宽松
- ✅ 会话模式启用

**适用场景**：本地开发、调试

**网络白名单**：
- `pypi.org`
- `files.pythonhosted.org`
- `github.com`
- `raw.githubusercontent.com`

### 2. `network-enabled` - 完全网络访问（新增）

**特点**：
- ✅ 完全网络访问（无白名单限制）
- ⚠️ 安全性较低
- ✅ 超时时间较长
- ✅ 内存限制较宽松

**适用场景**：
- 需要访问多个 API 的场景
- 数据爬取任务
- 集成测试

### 3. `network-restricted` - 受限网络访问（新增）

**特点**：
- ✅ 网络启用 + 严格白名单
- ✅ 安全性高
- ✅ 适合生产环境
- ✅ 自定义 DNS

**适用场景**：
- 生产环境
- 需要网络但注重安全的场景
- 企业内部部署

**网络白名单**：
- Python 包管理：`pypi.org`
- 代码托管：`github.com`, `gitlab.com`
- AI API：`api.openai.com`, `api.anthropic.com`
- 等等（详见配置文件）

### 4. 默认配置（已修改为启用网络）

**特点**：
- ✅ 网络已启用（修改后）
- ✅ 基础白名单
- ✅ 平衡安全与功能

---

## 使用方法

### 方法 1：在 Agent 配置中引用环境模板

创建或修改 Agent 配置文件（例如 `backend/agents/my-agent/config.toml`）：

```toml
[metadata]
name = "my-agent"

# 使用环境模板
extends = "network-enabled"  # 或 "docker-dev", "network-restricted"

# 如需覆盖特定配置
[sandbox.network]
allowed_hosts = [
    "api.custom-service.com",  # 添加自定义主机
]
```

### 方法 2：直接在 Agent 配置中设置

```toml
[metadata]
name = "my-agent"

[sandbox.network]
enabled = true
allowed_hosts = [
    "api.example.com",
    "data.example.com",
]
dns_servers = ["8.8.8.8"]
```

### 方法 3：通过环境变量

```bash
# 使用 Docker 开发环境
export SANDBOX_MODE=docker
export AGENT_TEMPLATE=docker-dev

# 启动后端
cd backend
uv run python -m app.main
```

### 方法 4：在代码中动态配置

```python
from core.config.execution_config import ExecutionConfig, SandboxConfig, NetworkConfig

config = ExecutionConfig(
    sandbox=SandboxConfig(
        network=NetworkConfig(
            enabled=True,
            allowed_hosts=["api.example.com"],
        )
    )
)

# 使用配置创建执行器
from core.sandbox.factory import ExecutorFactory
executor = ExecutorFactory.create(config)
```

---

## 安全建议

### ✅ 推荐做法

1. **生产环境**：使用 `network-restricted` 模板，维护严格的白名单
2. **开发环境**：使用 `docker-dev` 模板，平衡便利性与安全性
3. **定期审查**：定期检查和更新白名单
4. **最小权限原则**：只添加必需的主机到白名单

### ⚠️ 注意事项

1. **避免完全开放**：不要在生产环境使用 `network-enabled`（无白名单）
2. **DNS 安全**：使用可信的 DNS 服务器（如 `8.8.8.8`）
3. **日志监控**：启用网络日志，监控异常访问
4. **定期更新**：及时更新 Docker 镜像和依赖包

### ❌ 禁止做法

1. ❌ 不要在生产环境中设置 `allowed_hosts = []`（允许所有）
2. ❌ 不要添加不可信的第三方域名到白名单
3. ❌ 不要在网络启用时关闭其他安全措施
4. ❌ 不要在没有审查的情况下运行用户提交的网络代码

---

## 常见问题

### Q1: 网络请求失败，显示"网络不可用"？

**A**: 检查配置：
```bash
# 检查当前配置
cd backend
uv run python -c "
from core.config import get_execution_config
config = get_execution_config()
print(f'Network enabled: {config.sandbox.network.enabled}')
print(f'Allowed hosts: {config.sandbox.network.allowed_hosts}')
"
```

### Q2: 如何允许访问特定 API？

**A**: 添加到白名单：
```toml
[sandbox.network]
enabled = true
allowed_hosts = [
    "api.your-service.com",
]
```

### Q3: Docker 网络隔离如何工作？

**A**: 
- `network.enabled = false`：使用 `--network none`，完全禁用网络
- `network.enabled = true` + 白名单：需要在应用层实现（计划中）
- `network.enabled = true` + 空白名单：完全网络访问

### Q4: 白名单在 Docker 层面是否生效？

**A**: 当前版本的白名单配置主要用于：
1. 文档和审计目的
2. 应用层访问控制（需要在工具中实现）
3. Docker 层面仅控制启用/禁用

未来版本可能会添加 Docker 网络策略支持。

### Q5: 如何临时启用网络进行测试？

**A**: 使用环境变量：
```bash
# 临时启用网络
export SANDBOX_NETWORK_ENABLED=true

# 或在代码中
config = SandboxConfig(network_enabled=True)
```

### Q6: 性能影响？

**A**:
- **网络禁用**：无影响，性能最佳
- **网络启用**：轻微延迟（DNS 解析、网络 I/O）
- **建议**：根据实际需求选择，不需要网络时保持禁用

---

## 配置示例

### 示例 1：Web 爬虫 Agent

```toml
[metadata]
name = "web-crawler"
extends = "network-enabled"

[sandbox]
timeout_seconds = 120  # 网络请求需要更长时间

[sandbox.resources]
memory_limit = "1g"    # 处理网页需要更多内存

[sandbox.network]
allowed_hosts = []     # 爬虫需要访问各种网站
```

### 示例 2：API 集成 Agent

```toml
[metadata]
name = "api-integrator"
extends = "network-restricted"

[sandbox.network]
allowed_hosts = [
    "api.openai.com",
    "api.stripe.com",
    "api.sendgrid.com",
]
```

### 示例 3：离线数据处理 Agent

```toml
[metadata]
name = "data-processor"

[sandbox.network]
enabled = false        # 不需要网络，最安全

[sandbox.resources]
memory_limit = "2g"    # 数据处理需要更多内存
cpu_limit = 2.0
```

---

## 测试网络配置

### 测试脚本

创建 `test_network.py`：

```python
import asyncio
from core.config import get_execution_config
from core.sandbox.factory import ExecutorFactory
from core.sandbox.executor import SandboxConfig

async def test_network():
    """测试网络配置"""
    config = get_execution_config()
    executor = ExecutorFactory.create(config)
    
    # 测试网络访问
    code = """
import socket
try:
    socket.create_connection(("pypi.org", 80), timeout=5)
    print("✅ Network is enabled")
except Exception as e:
    print(f"❌ Network error: {e}")
"""
    
    result = await executor.execute_python(code)
    print(result.stdout)
    print(result.stderr)

if __name__ == "__main__":
    asyncio.run(test_network())
```

运行测试：
```bash
cd backend
uv run python test_network.py
```

---

## 相关文档

- [执行环境配置](./README.md)
- [沙箱安全设计](../docs/sandbox-security.md)
- [Docker 镜像构建](../docker/sandbox/README.md)

---

## 更新日志

- **2026-01-17**: 创建网络配置指南
  - 添加 `network-enabled` 环境模板
  - 添加 `network-restricted` 环境模板
  - 修改默认配置启用网络
  - 完善使用文档和安全建议
