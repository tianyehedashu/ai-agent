# SessionManager 工厂模式重构说明

## 重构背景

### 原有问题

在 `session_manager.py:366-370` 发现以下设计问题：

```python
async def _create_session(...):
    """创建新会话"""
    # 延迟导入避免循环依赖
    # pylint: disable=import-outside-toplevel
    from core.sandbox.executor import SessionDockerExecutor
    
    executor = SessionDockerExecutor(...)
```

**问题分析**：
1. ❌ **注释误导**：实际上不存在循环依赖，延迟导入是不必要的
2. ❌ **紧耦合**：SessionManager 直接依赖具体的 SessionDockerExecutor 实现
3. ❌ **难以测试**：无法注入 Mock 执行器，测试必须依赖 Docker 环境
4. ❌ **违反 SOLID**：违反依赖倒置原则（DIP）和开闭原则（OCP）

## 重构方案：工厂模式 + 依赖注入

### 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        SessionManager                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  - executor_factory: SessionExecutorFactory | None        │  │
│  │  + __init__(policy, executor_factory=None)               │  │
│  │  + _create_session(...) -> SessionInfo                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────┬────────────────────────────────────────┘
                        │ 依赖注入
                        ▼
    ┌───────────────────────────────────────────────────┐
    │   SessionExecutorFactory (Protocol)               │
    │   + create_session_executor(...) -> Executor      │
    └───────────────────────────────────────────────────┘
                        △
                        │ 实现
        ┌───────────────┼───────────────┐
        │               │               │
┌───────┴────────┐ ┌────┴─────────┐ ┌──┴──────────────┐
│ Default        │ │ Mock         │ │ Custom          │
│ Factory        │ │ Factory      │ │ Factory         │
│ (生产环境)      │ │ (单元测试)    │ │ (用户自定义)    │
└────────────────┘ └──────────────┘ └─────────────────┘
```

### 核心变更

#### 1. 新增 `session_executor_factory.py`

定义工厂协议和实现：

```python
class SessionExecutorFactory(Protocol):
    """会话执行器工厂协议（用于依赖注入）"""
    def create_session_executor(
        self, max_idle_seconds: int, config=None
    ) -> SessionDockerExecutor:
        ...

class DefaultSessionExecutorFactory:
    """默认工厂（生产环境使用）"""
    def create_session_executor(...):
        return SessionDockerExecutor(...)

class MockSessionExecutorFactory:
    """模拟工厂（单元测试使用）"""
    def create_session_executor(...):
        # 返回模拟执行器，不启动真实容器
        executor = SessionDockerExecutor(...)
        executor._session_id = "mock-session-xxx"
        executor._container_id = "mock-container-xxx"
        return executor
```

#### 2. 修改 `SessionManager`

引入工厂依赖注入：

```python
class SessionManager:
    def __init__(
        self,
        policy: SessionPolicy | None = None,
        executor_factory: SessionExecutorFactory | None = None,  # 新增参数
    ):
        self.policy = policy or SessionPolicy()
        self.executor_factory = executor_factory  # 支持注入
        # ...
    
    async def _create_session(...):
        """创建新会话"""
        # 使用工厂创建执行器
        if self.executor_factory is None:
            # 延迟初始化默认工厂
            from core.sandbox.session_executor_factory import DefaultSessionExecutorFactory
            self.executor_factory = DefaultSessionExecutorFactory()
        
        executor = self.executor_factory.create_session_executor(
            max_idle_seconds=self.policy.idle_timeout,
            config=config,
        )
        # ...
```

#### 3. 更新导入

移除不必要的延迟导入：

```python
# 之前：TYPE_CHECKING 条件导入 + 函数内延迟导入
if TYPE_CHECKING:
    from core.sandbox.executor import SessionDockerExecutor

async def _create_session(...):
    from core.sandbox.executor import SessionDockerExecutor  # 延迟导入
    executor = SessionDockerExecutor(...)

# 之后：直接导入（因为不存在循环依赖）
from core.sandbox.executor import SessionDockerExecutor

async def _create_session(...):
    # 使用工厂，无需导入
    executor = self.executor_factory.create_session_executor(...)
```

## 重构优势

### ✅ 1. 解耦

- SessionManager 依赖抽象接口（Protocol），不依赖具体实现
- 可以轻松替换不同的执行器实现

### ✅ 2. 可测试性

**之前**：测试必须启动 Docker 容器

```python
@pytest.mark.integration
async def test_create_session(manager):
    session = await manager.get_or_create_session()  # 启动真实 Docker
    assert session.executor is not None  # 需要 Docker 环境
```

**之后**：可以使用 Mock 工厂进行单元测试

```python
def test_create_session_with_mock():
    mock_factory = MockSessionExecutorFactory()
    manager = SessionManager(executor_factory=mock_factory)
    
    session = await manager.get_or_create_session()
    assert len(mock_factory.created_executors) == 1  # 无需 Docker
```

### ✅ 3. 可扩展性

用户可以提供自定义工厂：

```python
class CustomFactory:
    def create_session_executor(self, max_idle_seconds, config=None):
        return SessionDockerExecutor(
            image="python:3.12-alpine",  # 自定义镜像
            workspace_path="/custom/path",
            max_idle_seconds=max_idle_seconds,
        )

manager = SessionManager(executor_factory=CustomFactory())
```

### ✅ 4. 向后兼容

不注入工厂时，自动使用默认工厂：

```python
# 原有代码无需修改
manager = SessionManager(policy=policy)
session = await manager.get_or_create_session()  # 使用默认工厂
```

### ✅ 5. 符合 SOLID 原则

- **S**ingle Responsibility：SessionManager 专注于会话管理，执行器创建委托给工厂
- **O**pen/Closed：对扩展开放（自定义工厂），对修改封闭
- **L**iskov Substitution：所有工厂都可以互相替换
- **I**nterface Segregation：工厂接口简洁明确
- **D**ependency Inversion：依赖抽象（Protocol），不依赖具体实现

## 测试验证

### 新增测试

创建 `test_session_executor_factory.py`，包含 8 个测试用例：

```bash
tests/unit/test_session_executor_factory.py::TestDefaultSessionExecutorFactory::test_create_executor PASSED
tests/unit/test_session_executor_factory.py::TestDefaultSessionExecutorFactory::test_create_with_config PASSED
tests/unit/test_session_executor_factory.py::TestMockSessionExecutorFactory::test_create_mock_executor PASSED
tests/unit/test_session_executor_factory.py::TestMockSessionExecutorFactory::test_track_created_executors PASSED
tests/unit/test_session_executor_factory.py::TestSessionManagerWithFactory::test_manager_uses_injected_factory PASSED
tests/unit/test_session_executor_factory.py::TestSessionManagerWithFactory::test_multiple_sessions_with_mock_factory PASSED
tests/unit/test_session_executor_factory.py::TestSessionManagerWithFactory::test_manager_without_factory_uses_default PASSED
tests/unit/test_session_executor_factory.py::TestCustomFactory::test_custom_factory_integration PASSED

8 passed in 18.75s
```

### 原有测试通过

所有 SessionManager 原有测试仍然通过，验证向后兼容性：

```bash
tests/unit/test_session_manager.py - 15 passed, 4 deselected (integration tests)
```

## 使用指南

### 生产环境（默认）

```python
# 方式 1：使用默认配置
manager = SessionManager()

# 方式 2：自定义默认工厂
from core.sandbox.session_executor_factory import DefaultSessionExecutorFactory

factory = DefaultSessionExecutorFactory(
    image="python:3.12",
    workspace_path="/data/workspaces",
)
manager = SessionManager(executor_factory=factory)
```

### 单元测试

```python
from core.sandbox import MockSessionExecutorFactory, SessionManager

def test_session_logic():
    # 使用 Mock 工厂，不启动真实容器
    mock_factory = MockSessionExecutorFactory()
    manager = SessionManager(executor_factory=mock_factory)
    
    await manager.start()
    session = await manager.get_or_create_session(
        user_id="test-user",
        conversation_id="test-conv",
    )
    
    # 验证逻辑，无需 Docker
    assert len(mock_factory.created_executors) == 1
    assert session.session_id.startswith("mock-session-")
```

### 自定义工厂

```python
from core.sandbox import SessionManager

class ProductionFactory:
    """生产环境工厂，带监控和日志"""
    
    def create_session_executor(self, max_idle_seconds, config=None):
        executor = SessionDockerExecutor(
            image="my-custom-image:latest",
            max_idle_seconds=max_idle_seconds,
        )
        # 注入监控
        self.monitor.track_executor(executor)
        return executor

manager = SessionManager(executor_factory=ProductionFactory())
```

## 文件清单

### 新增文件

- `backend/core/sandbox/session_executor_factory.py` - 工厂协议和实现
- `backend/tests/unit/test_session_executor_factory.py` - 工厂测试
- `backend/docs/SessionManager重构说明.md` - 本文档

### 修改文件

- `backend/core/sandbox/session_manager.py` - 引入工厂依赖注入
- `backend/core/sandbox/__init__.py` - 导出工厂接口

## 总结

本次重构通过引入**工厂模式**和**依赖注入**，解决了原有架构中的紧耦合问题，显著提升了代码的：

- 🎯 **可测试性**：单元测试无需 Docker 环境
- 🔧 **可维护性**：职责清晰，符合 SOLID 原则
- 🚀 **可扩展性**：轻松自定义执行器创建逻辑
- ✅ **向后兼容**：不影响现有代码

这是一个教科书级别的重构案例，展示了如何在不破坏现有功能的前提下，优雅地改进架构设计。
