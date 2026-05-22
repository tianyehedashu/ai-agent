# 执行环境配置架构重构方案

## 当前问题

### 1. ExecutionConfigLoader 职责过重 (God Class)

```
当前 ExecutionConfigLoader:
├── 配置加载
├── 配置合并
├── 环境变量解析
├── 配置验证
├── 工具定义加载
├── MCP 配置加载
├── 工具确认检查 (重复!)
└── Schema 导出
```

### 2. 缺少扩展性

- 配置源硬编码为 TOML 文件
- 无法支持远程配置中心
- 无法支持数据库存储

### 3. 职责重叠

- `ExecutionConfigLoader.requires_confirmation()` vs `ConfiguredToolRegistry.requires_confirmation()`
- `ExecutionConfigLoader.get_effective_tools()` vs `ConfiguredToolRegistry._filter_enabled_tools()`

---

## 重构后的架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Execution Config System                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐     ┌──────────────────┐     ┌─────────────────┐  │
│  │  ConfigSource    │     │  ConfigValidator │     │  ConfigMerger   │  │
│  │  (Interface)     │     │  (Interface)     │     │  (静态工具类)    │  │
│  └────────┬─────────┘     └────────┬─────────┘     └─────────────────┘  │
│           │                        │                                     │
│  ┌────────┼────────────────────────┼──────────────────┐                 │
│  │        │                        │                  │                 │
│  ▼        ▼                        ▼                  ▼                 │
│ TomlSource  DatabaseSource    SecurityValidator   SchemaValidator       │
│             RemoteSource      ToolValidator                             │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    ExecutionConfigService                         │   │
│  │                                                                   │   │
│  │  职责：                                                            │   │
│  │  - 协调配置源、验证器、合并器                                        │   │
│  │  - 实现分层加载逻辑                                                 │   │
│  │  - 提供缓存管理                                                    │   │
│  │                                                                   │   │
│  │  不包含：                                                          │   │
│  │  - 具体的 TOML 解析 (委托给 TomlSource)                            │   │
│  │  - 验证逻辑 (委托给 Validators)                                    │   │
│  │  - 工具确认检查 (保留在 ConfiguredToolRegistry)                     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 具体实现

### 1. 定义 ConfigSource 接口

```python
# core/config/sources/base.py
from abc import ABC, abstractmethod
from typing import Any
from pathlib import Path

class ConfigSource(ABC):
    """配置源抽象基类"""

    @abstractmethod
    def load(self, identifier: str) -> dict[str, Any] | None:
        """加载配置"""
        pass

    @abstractmethod
    def exists(self, identifier: str) -> bool:
        """检查配置是否存在"""
        pass

    @abstractmethod
    def list_available(self) -> list[str]:
        """列出所有可用配置"""
        pass
```

### 2. 实现具体配置源

```python
# core/config/sources/toml_source.py
class TomlConfigSource(ConfigSource):
    """TOML 文件配置源"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def load(self, identifier: str) -> dict[str, Any] | None:
        path = self.base_dir / f"{identifier}.toml"
        if not path.exists():
            return None
        with path.open("rb") as f:
            return tomli.load(f)

    def exists(self, identifier: str) -> bool:
        return (self.base_dir / f"{identifier}.toml").exists()

    def list_available(self) -> list[str]:
        return [p.stem for p in self.base_dir.glob("*.toml")]


# core/config/sources/database_source.py (未来扩展)
class DatabaseConfigSource(ConfigSource):
    """数据库配置源"""

    def __init__(self, db_session):
        self.db = db_session

    def load(self, identifier: str) -> dict[str, Any] | None:
        # 从数据库加载
        pass


# core/config/sources/remote_source.py (未来扩展)
class RemoteConfigSource(ConfigSource):
    """远程配置中心 (Consul/Nacos/Apollo)"""

    def __init__(self, url: str, namespace: str):
        self.url = url
        self.namespace = namespace

    def load(self, identifier: str) -> dict[str, Any] | None:
        # 从远程获取
        pass
```

### 3. 定义 ConfigValidator 接口

```python
# core/config/validators/base.py
from abc import ABC, abstractmethod

class ConfigValidator(ABC):
    """配置验证器抽象基类"""

    @abstractmethod
    def validate(self, config: ExecutionConfig) -> tuple[bool, list[str], list[str]]:
        """
        验证配置

        Returns:
            (是否有效, 错误列表, 警告列表)
        """
        pass
```

### 4. 实现具体验证器

```python
# core/config/validators/security_validator.py
class SecurityValidator(ConfigValidator):
    """安全配置验证器"""

    def validate(self, config: ExecutionConfig) -> tuple[bool, list[str], list[str]]:
        errors = []
        warnings = []

        if not config.sandbox.security.read_only_root:
            warnings.append("read_only_root is disabled")

        if not config.sandbox.security.no_new_privileges:
            warnings.append("no_new_privileges is disabled")

        return len(errors) == 0, errors, warnings


# core/config/validators/sandbox_validator.py
class SandboxValidator(ConfigValidator):
    """沙箱配置验证器"""

    def validate(self, config: ExecutionConfig) -> tuple[bool, list[str], list[str]]:
        errors = []
        warnings = []

        if config.sandbox.mode == SandboxMode.DOCKER:
            if not config.sandbox.docker.image:
                errors.append("Docker mode requires image")

        return len(errors) == 0, errors, warnings


# core/config/validators/composite_validator.py
class CompositeValidator(ConfigValidator):
    """组合验证器 - 聚合多个验证器"""

    def __init__(self, validators: list[ConfigValidator]):
        self.validators = validators

    def validate(self, config: ExecutionConfig) -> tuple[bool, list[str], list[str]]:
        all_errors = []
        all_warnings = []

        for validator in self.validators:
            is_valid, errors, warnings = validator.validate(config)
            all_errors.extend(errors)
            all_warnings.extend(warnings)

        return len(all_errors) == 0, all_errors, all_warnings
```

### 5. 重构 ExecutionConfigService

```python
# core/config/service.py
class ExecutionConfigService:
    """
    执行环境配置服务

    职责：
    - 协调配置源、验证器
    - 实现分层加载逻辑
    - 管理缓存

    不包含：
    - 具体的文件解析
    - 验证逻辑
    - 工具确认检查
    """

    def __init__(
        self,
        system_source: ConfigSource,
        template_source: ConfigSource,
        agent_source: ConfigSource,
        validator: ConfigValidator | None = None,
        env_resolver: EnvVarResolver | None = None,
    ):
        self.system_source = system_source
        self.template_source = template_source
        self.agent_source = agent_source
        self.validator = validator or CompositeValidator([
            SandboxValidator(),
            SecurityValidator(),
        ])
        self.env_resolver = env_resolver or EnvVarResolver()

        # 缓存
        self._cache: dict[str, ExecutionConfig] = {}

    def load_for_agent(
        self,
        agent_id: str,
        runtime_overrides: dict[str, Any] | None = None,
        *,
        validate: bool = False,
    ) -> ExecutionConfig:
        """为 Agent 加载配置"""

        # 1. 加载系统默认
        config = self._load_and_resolve("execution", self.system_source)

        # 2. 加载 Agent 配置
        agent_config = self._load_and_resolve(agent_id, self.agent_source)

        if agent_config:
            # 3. 如果 Agent 指定了模板，先合并模板
            if agent_config.extends:
                template = self._load_and_resolve(agent_config.extends, self.template_source)
                if template:
                    config = config.merge_with(template)

            # 4. 合并 Agent 配置
            config = config.merge_with(agent_config)

        # 5. 合并运行时参数
        if runtime_overrides:
            resolved = self.env_resolver.resolve(runtime_overrides)
            runtime_config = ExecutionConfig.model_validate(resolved)
            config = config.merge_with(runtime_config)

        # 6. 可选验证
        if validate:
            is_valid, errors, warnings = self.validator.validate(config)
            if not is_valid:
                raise ValueError(f"Invalid configuration: {'; '.join(errors)}")

        return config

    def _load_and_resolve(self, identifier: str, source: ConfigSource) -> ExecutionConfig | None:
        """加载并解析配置"""
        data = source.load(identifier)
        if data is None:
            return None
        resolved = self.env_resolver.resolve(data)
        return ExecutionConfig.model_validate(resolved)

    def clear_cache(self) -> None:
        """清理缓存"""
        self._cache.clear()
```

### 6. 删除 ConfiguredToolRegistry 中的重复逻辑

`requires_confirmation()` 方法只保留在 `ConfiguredToolRegistry` 中，
因为它与工具执行强相关。

---

## 重构后的目录结构

```
core/config/
├── __init__.py
├── execution_config.py      # 配置模型 (不变)
├── merger.py                # ConfigMerger (从 execution_config.py 分离)
├── service.py               # ExecutionConfigService (新)
├── env_resolver.py          # 环境变量解析器 (新)
├── sources/
│   ├── __init__.py
│   ├── base.py              # ConfigSource 接口
│   ├── toml_source.py       # TOML 实现
│   ├── database_source.py   # 数据库实现 (预留)
│   └── remote_source.py     # 远程配置实现 (预留)
└── validators/
    ├── __init__.py
    ├── base.py              # ConfigValidator 接口
    ├── sandbox_validator.py
    ├── security_validator.py
    ├── tool_validator.py
    └── composite.py         # 组合验证器
```

---

## 改进效果

| 维度 | 改进前 | 改进后 |
|------|--------|--------|
| **SRP** | ExecutionConfigLoader 7+ 职责 | 每个类 1 个职责 |
| **OCP** | 新增配置源需改源码 | 实现 ConfigSource 接口即可 |
| **DIP** | 硬编码依赖 TOML | 依赖抽象 ConfigSource |
| **重复代码** | requires_confirmation 2 处 | 1 处 |
| **可测试性** | 难以 mock | 接口易 mock |
| **可扩展性** | 无法支持远程配置 | 实现接口即可支持 |

---

## 实施步骤

1. **Phase 1**: 提取接口 (低风险)
   - 创建 `ConfigSource` 接口
   - 创建 `ConfigValidator` 接口
   - 原 `ExecutionConfigLoader` 实现这些接口

2. **Phase 2**: 分离实现 (中风险)
   - 分离 `TomlConfigSource`
   - 分离各个 Validator
   - 创建 `ExecutionConfigService`

3. **Phase 3**: 清理冗余 (低风险)
   - 删除 `ExecutionConfigLoader` 中的重复方法
   - 更新调用方

4. **Phase 4**: 增强 (可选)
   - 添加 `DatabaseConfigSource`
   - 添加 `RemoteConfigSource`
   - 添加配置变更监听
