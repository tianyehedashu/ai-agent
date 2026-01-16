# 依赖注入重构总结

## 一、重构目标

修复 Core 层直接依赖应用层配置的问题，使用依赖注入模式，符合依赖倒置原则。

## 二、主要改动

### 2.1 创建配置接口 (`core/config.py`)

创建了 `LLMConfig` Protocol，定义 Core 层需要的配置接口：

```python
class LLMConfig(Protocol):
    """LLM 配置接口"""
    anthropic_api_key: SecretStr | None
    openai_api_key: SecretStr | None
    # ... 其他配置
```

### 2.2 修改 LLMGateway (`core/llm/gateway.py`)

**改动前**：
```python
class LLMGateway:
    def __init__(self) -> None:
        # 直接使用全局 settings
        if settings.anthropic_api_key:
            ...
```

**改动后**：
```python
class LLMGateway:
    def __init__(self, config: LLMConfig) -> None:
        """
        初始化 LLM Gateway

        Args:
            config: LLM 配置（通过依赖注入传入）
        """
        self.config = config
        if config.anthropic_api_key:
            ...
```

### 2.3 修改其他 Core 模块

1. **AgentEngine** (`core/engine/agent.py`)
   - `llm_gateway` 参数改为必需（移除默认值）
   - 通过依赖注入传入

2. **MemoryManager** (`core/memory/manager.py`)
   - `llm` 参数改为必需（移除默认值）
   - 移除对 `app.config` 的导入

3. **CodeFixer** (`core/quality/fixer.py`)
   - `llm` 参数改为必需（移除默认值）
   - 移除对 `app.config` 的导入

### 2.4 更新应用层代码

所有创建 LLMGateway 的地方都改为传递配置：

```python
# 应用层（services, api, workers）
from app.config import settings
llm_gateway = LLMGateway(config=settings)
```

## 三、依赖关系改进

### 3.1 改进前

```
Core Layer
    ↓ (直接依赖)
app.config.settings
```

### 3.2 改进后

```
Core Layer
    ↑ (依赖注入)
app.config.settings (实现 LLMConfig Protocol)
```

## 四、修改的文件清单

### Core 层
- ✅ `core/config.py` (新建)
- ✅ `core/llm/gateway.py`
- ✅ `core/llm/__init__.py` (添加工厂函数)
- ✅ `core/engine/agent.py`
- ✅ `core/memory/manager.py`
- ✅ `core/quality/fixer.py`

### 应用层
- ✅ `services/chat.py`
- ✅ `api/v1/quality.py`
- ✅ `api/v1/evaluation.py`
- ✅ `workers/tasks.py`

### 测试
- ✅ `tests/integration/test_llm_providers.py`
- ✅ `tests/unit/core/test_llm_gateway.py`

## 五、优势

1. **符合依赖倒置原则**
   - Core 层不再依赖应用层
   - 通过 Protocol 定义接口，实现解耦

2. **易于测试**
   - 可以轻松注入 Mock 配置
   - 不需要设置全局环境变量

3. **灵活性**
   - 可以为不同场景使用不同配置
   - 支持多租户场景

4. **类型安全**
   - 使用 Protocol 确保类型正确
   - IDE 可以提供更好的代码提示

## 六、注意事项

1. **向后兼容性**
   - 所有调用方都已更新
   - 测试文件已更新

2. **配置传递**
   - 应用层负责创建和传递配置
   - Core 层只接受配置，不创建

3. **Protocol vs ABC**
   - 使用 Protocol（结构化类型）
   - 不需要显式继承，更灵活

## 七、验证

运行以下命令验证修改：

```bash
# 验证导入
python -c "from core.llm.gateway import LLMGateway; from app.config import settings; gateway = LLMGateway(config=settings); print('OK')"

# 运行测试
pytest tests/unit/core/test_llm_gateway.py -v
```

## 八、后续优化建议

1. **依赖注入容器**（可选）
   - 考虑使用 `dependency-injector` 等库
   - 统一管理依赖关系

2. **配置验证**
   - 在应用启动时验证配置完整性
   - 提供清晰的错误信息

3. **配置分层**
   - 区分开发/生产配置
   - 支持配置热更新（如需要）
