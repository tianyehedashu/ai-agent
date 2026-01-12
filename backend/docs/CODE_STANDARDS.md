# 🔧 AI Agent Backend 代码规范

> **版本**: 1.0.0
> **更新日期**: 2026-01-12
> **适用范围**: backend/ 目录下所有 Python 代码

---

## 📋 目录

1. [核心原则](#核心原则)
2. [项目结构](#项目结构)
3. [类型安全](#类型安全)
4. [代码风格](#代码风格)
5. [命名规范](#命名规范)
6. [注释与文档](#注释与文档)
7. [错误处理](#错误处理)
8. [异步编程](#异步编程)
9. [数据库规范](#数据库规范)
10. [API 设计](#api-设计)
11. [测试规范](#测试规范)
12. [质量检测工具](#质量检测工具)
13. [Git 工作流](#git-工作流)

---

## 核心原则

### 1. 类型优先 (Type-First)

所有代码必须有完整的类型注解，通过 `pyright --strict` 检查。

```python
# ✅ 正确
def process_data(items: list[dict[str, Any]], limit: int = 10) -> Result[ProcessedData]:
    ...

# ❌ 错误
def process_data(items, limit=10):
    ...
```

### 2. 不重复造轮子 (DRY)

- 优先使用现有抽象和工具类
- 复用 `core/types.py` 中定义的类型
- 使用 `services/` 层封装业务逻辑
- 禁止在多处重复相同的逻辑

### 3. 单一职责 (SRP)

- 每个模块/类/函数只做一件事
- API 层只处理 HTTP 请求/响应
- Service 层处理业务逻辑
- Model 层只定义数据结构

### 4. 显式优于隐式 (Explicit over Implicit)

```python
# ✅ 显式声明
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.user import User

# ❌ 隐式导入
from models import *
```

---

## 项目结构

```
backend/
├── api/                    # API 层 (路由、请求处理)
│   ├── v1/                 # API 版本
│   │   ├── router.py       # 路由聚合
│   │   ├── agent.py        # Agent 相关 API
│   │   ├── chat.py         # 对话 API
│   │   └── session.py      # 会话 API
│   └── deps.py             # 依赖注入
│
├── app/                    # 应用核心
│   ├── main.py             # FastAPI 应用入口
│   └── config.py           # 配置管理
│
├── core/                   # 核心定义
│   └── types.py            # 类型定义 (枚举、协议、TypedDict)
│
├── models/                 # 数据模型 (SQLAlchemy ORM)
│   ├── base.py             # 模型基类
│   ├── user.py             # 用户模型
│   ├── agent.py            # Agent 模型
│   └── session.py          # 会话模型
│
├── schemas/                # Pydantic Schema (请求/响应)
│   └── message.py          # 消息 Schema
│
├── services/               # 业务服务层
│   ├── agent.py            # Agent 服务
│   ├── chat.py             # 对话服务
│   └── session.py          # 会话服务
│
├── db/                     # 数据库
│   ├── database.py         # 数据库连接
│   └── redis.py            # Redis 连接
│
├── tools/                  # Agent 工具
│   ├── base.py             # 工具基类
│   ├── registry.py         # 工具注册中心
│   └── file_tools.py       # 文件操作工具
│
└── tests/                  # 测试
    ├── unit/               # 单元测试
    ├── integration/        # 集成测试
    └── conftest.py         # Pytest 配置
```

### 各层职责

| 层级 | 职责 | 依赖 |
|------|------|------|
| `api/` | HTTP 请求处理、参数验证、响应格式化 | services, schemas |
| `services/` | 业务逻辑、事务处理、跨模型操作 | models, db |
| `models/` | 数据库模型定义、关系映射 | db |
| `schemas/` | 请求/响应数据结构、验证规则 | - |
| `core/` | 核心类型、枚举、协议定义 | - |
| `tools/` | Agent 工具实现 | core |

---

## 类型安全

### 3.1 必须使用的类型注解

```python
from typing import Any, TypeVar, Generic, Protocol, TYPE_CHECKING
from collections.abc import Sequence, Mapping, AsyncGenerator

# 函数参数和返回值必须有类型
def get_user(user_id: str) -> User | None:
    ...

# 类属性必须有类型
class UserService:
    _cache: dict[str, User]

    def __init__(self) -> None:
        self._cache = {}
```

### 3.2 使用项目定义的类型

```python
# ✅ 使用 core/types.py 中定义的类型
from core.types import (
    Result,           # 结果类型
    ToolProtocol,     # 工具协议
    AgentConfig,      # Agent 配置
    MessageRole,      # 消息角色枚举
    EventType,        # 事件类型枚举
)

# 使用 Result 类型处理可能失败的操作
async def process_request(data: dict[str, Any]) -> Result[ProcessedData]:
    if not validate(data):
        return Result.err("Invalid data")
    return Result.ok(ProcessedData(...))
```

### 3.3 Pydantic 模型规范

```python
from pydantic import BaseModel, Field, ConfigDict

class UserCreate(BaseModel):
    """用户创建请求"""

    model_config = ConfigDict(
        strict=True,           # 严格类型检查
        frozen=True,           # 不可变 (值对象)
        extra="forbid",        # 禁止额外字段
    )

    username: str = Field(min_length=3, max_length=50)
    email: str = Field(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    password: str = Field(min_length=8)
```

### 3.4 SQLAlchemy 模型类型

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey

class User(BaseModel):
    """用户模型"""

    __tablename__ = "users"

    # 使用 Mapped 进行类型注解
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)

    # 可空字段
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 关系
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )
```

### 3.5 TYPE_CHECKING 惰性导入

```python
from typing import TYPE_CHECKING

# 仅在类型检查时导入，避免循环依赖
if TYPE_CHECKING:
    from models.user import User
    from services.auth import AuthService

class SessionService:
    async def get_user_sessions(self, user: "User") -> list[Session]:
        ...
```

---

## 代码风格

### 4.1 Ruff 配置 (已在 pyproject.toml 中)

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM", "TCH", "PTH", "RUF"]
```

### 4.2 导入顺序

```python
# 1. 标准库
from datetime import datetime
from typing import Any

# 2. 第三方库
from fastapi import APIRouter, Depends
from pydantic import BaseModel

# 3. 本地模块
from api.deps import get_current_user
from core.types import Result
from models.user import User
```

### 4.3 字符串格式化

```python
# ✅ 使用 f-string
message = f"User {user.name} created successfully"

# ❌ 避免
message = "User {} created successfully".format(user.name)
message = "User %s created successfully" % user.name
```

### 4.4 路径处理

```python
from pathlib import Path

# ✅ 使用 pathlib
config_path = Path(__file__).parent / "config.yaml"

# ❌ 避免 os.path
import os
config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
```

---

## 命名规范

### 5.1 通用规则

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | snake_case | `user_service.py` |
| 类 | PascalCase | `UserService`, `AgentConfig` |
| 函数/方法 | snake_case | `get_user_by_id()` |
| 变量 | snake_case | `user_count`, `is_active` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| 类型变量 | PascalCase + 后缀 T | `StateT`, `ResponseT` |
| 私有成员 | 前缀 `_` | `_internal_state` |

### 5.2 特定命名约定

```python
# API 路由函数: 动词_名词
async def list_sessions(...): ...
async def create_agent(...): ...
async def get_session(...): ...
async def update_agent(...): ...
async def delete_session(...): ...

# Service 类: 名词 + Service
class SessionService: ...
class AgentService: ...

# Repository 类: 名词 + Repository
class UserRepository: ...

# 异步函数: 普通命名 (不加 async_ 前缀)
async def process_message(...): ...  # ✅
async def async_process_message(...): ...  # ❌

# 布尔变量: is_, has_, can_ 前缀
is_active: bool
has_permission: bool
can_execute: bool
```

---

## 注释与文档

### 6.1 模块文档

```python
"""
Session Service - 会话服务

提供会话的创建、查询、更新、删除功能。

主要功能:
- 会话生命周期管理
- 消息历史记录
- Token 统计

使用示例:
    service = SessionService()
    session = await service.create(user_id="xxx")
"""
```

### 6.2 函数文档 (Google 风格)

```python
async def create_session(
    user_id: str,
    agent_id: str | None = None,
    title: str | None = None,
) -> Session:
    """创建新会话。

    Args:
        user_id: 用户 ID
        agent_id: 关联的 Agent ID (可选)
        title: 会话标题 (可选)

    Returns:
        创建的 Session 对象

    Raises:
        ValueError: 当 user_id 无效时
        DatabaseError: 当数据库操作失败时

    Example:
        >>> session = await create_session("user-123", title="测试会话")
        >>> print(session.id)
    """
```

### 6.3 类文档

```python
class SessionService:
    """会话服务类。

    管理用户会话的完整生命周期，包括创建、查询、更新和删除。

    Attributes:
        _cache: 会话缓存字典
        _db: 数据库会话工厂

    Example:
        >>> service = SessionService()
        >>> sessions = await service.list_by_user("user-123")
    """
```

### 6.4 行内注释

```python
# ✅ 解释为什么，而不是是什么
# 使用 UUID 而不是自增 ID，避免并发竞争
session_id = str(uuid.uuid4())

# ❌ 无意义的注释
# 设置 session_id
session_id = str(uuid.uuid4())
```

---

## 错误处理

### 7.1 使用 Result 类型

```python
from core.types import Result

async def process_file(path: Path) -> Result[FileContent]:
    """处理文件，返回 Result 类型。"""
    if not path.exists():
        return Result.err(f"File not found: {path}")

    try:
        content = path.read_text()
        return Result.ok(FileContent(content))
    except PermissionError:
        return Result.err(f"Permission denied: {path}")

# 使用方
result = await process_file(Path("data.txt"))
if result.is_ok:
    content = result.unwrap()
else:
    logger.error(result.error)
```

### 7.2 自定义异常

```python
# exceptions.py
class AIAgentError(Exception):
    """AI Agent 基础异常"""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class ValidationError(AIAgentError):
    """验证错误"""
    pass


class NotFoundError(AIAgentError):
    """资源不存在"""
    pass


class PermissionDeniedError(AIAgentError):
    """权限不足"""
    pass
```

### 7.3 API 异常处理

```python
from fastapi import HTTPException, status

# 在 API 层转换异常
@router.get("/{session_id}")
async def get_session(session_id: str) -> SessionResponse:
    session = await session_service.get_by_id(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionResponse.model_validate(session)
```

---

## 异步编程

### 8.1 异步数据库操作

```python
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user(db: AsyncSession, user_id: str) -> User | None:
    """异步获取用户。"""
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    return result.scalar_one_or_none()
```

### 8.2 上下文管理器

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """提供数据库会话上下文。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### 8.3 并发控制

```python
import asyncio

# 限制并发数
semaphore = asyncio.Semaphore(10)

async def process_with_limit(item: Item) -> Result:
    async with semaphore:
        return await process(item)

# 批量处理
results = await asyncio.gather(
    *[process_with_limit(item) for item in items],
    return_exceptions=True,
)
```

### 8.4 流式响应

```python
from collections.abc import AsyncGenerator
from core.types import AgentEvent

async def stream_response(
    session_id: str,
    message: str,
) -> AsyncGenerator[AgentEvent, None]:
    """流式生成 Agent 响应。"""
    async for event in agent.run_stream(session_id, message):
        yield event
```

---

## 数据库规范

### 9.1 模型基类

```python
# models/base.py
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseModel(DeclarativeBase):
    """模型基类，提供通用字段。"""

    id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
```

### 9.2 查询规范

```python
# ✅ 使用 select() 构建查询
from sqlalchemy import select

query = (
    select(Session)
    .where(Session.user_id == user_id)
    .order_by(Session.created_at.desc())
    .limit(20)
)
result = await db.execute(query)
sessions = result.scalars().all()

# ❌ 避免使用旧式 query API
db.query(Session).filter(...).all()
```

### 9.3 事务处理

```python
async def transfer_funds(
    from_account: str,
    to_account: str,
    amount: Decimal,
) -> None:
    """转账操作（事务）。"""
    async with get_session_context() as db:
        # 所有操作在同一个事务中
        from_acc = await get_account(db, from_account)
        to_acc = await get_account(db, to_account)

        from_acc.balance -= amount
        to_acc.balance += amount

        # 上下文管理器自动提交或回滚
```

---

## API 设计

### 10.1 路由命名

```python
from fastapi import APIRouter

router = APIRouter(prefix="/sessions", tags=["sessions"])

# RESTful 风格
@router.get("/")                    # 列表
@router.post("/")                   # 创建
@router.get("/{session_id}")        # 获取详情
@router.put("/{session_id}")        # 完整更新
@router.patch("/{session_id}")      # 部分更新
@router.delete("/{session_id}")     # 删除

# 子资源
@router.get("/{session_id}/messages")
@router.post("/{session_id}/messages")
```

### 10.2 请求/响应模型

```python
from pydantic import BaseModel, Field

# 请求模型: xxxCreate, xxxUpdate
class SessionCreate(BaseModel):
    """创建会话请求"""
    agent_id: str | None = None
    title: str | None = Field(default=None, max_length=200)


# 响应模型: xxxResponse
class SessionResponse(BaseModel):
    """会话响应"""
    id: str
    user_id: str
    title: str | None
    created_at: datetime

    class Config:
        from_attributes = True  # 支持 ORM 对象转换
```

### 10.3 分页参数

```python
from typing import Annotated
from fastapi import Query

@router.get("/")
async def list_items(
    skip: Annotated[int, Query(ge=0, description="跳过记录数")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="返回记录数")] = 20,
) -> list[ItemResponse]:
    ...
```

### 10.4 依赖注入

```python
# api/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

security = HTTPBearer()


async def get_current_user(
    token: str = Depends(security),
) -> User:
    """获取当前认证用户。"""
    user = await verify_token(token.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return user


# 在路由中使用
@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)
```

---

## 测试规范

### 11.1 测试结构

```
tests/
├── conftest.py           # 共享 fixtures
├── unit/                 # 单元测试
│   ├── test_services/
│   └── test_utils/
├── integration/          # 集成测试
│   ├── test_api/
│   └── test_db/
└── e2e/                  # 端到端测试
```

### 11.2 测试命名

```python
# 测试文件: test_<module>.py
# 测试类: Test<Class>
# 测试方法: test_<scenario>_<expected_result>

class TestSessionService:
    async def test_create_session_with_valid_data_succeeds(self):
        ...

    async def test_create_session_with_invalid_user_raises_error(self):
        ...

    async def test_get_session_returns_none_when_not_found(self):
        ...
```

### 11.3 Fixtures

```python
# conftest.py
import pytest
from collections.abc import AsyncGenerator

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """提供测试数据库会话。"""
    async with async_test_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_user() -> User:
    """创建测试用户。"""
    return User(
        username="testuser",
        email="test@example.com",
    )
```

### 11.4 测试异步代码

```python
import pytest

# pytest.mark.asyncio 由 pytest-asyncio 自动添加 (asyncio_mode = "auto")

async def test_create_session(db_session: AsyncSession):
    """测试创建会话。"""
    service = SessionService(db_session)
    session = await service.create(user_id="user-123")

    assert session.id is not None
    assert session.user_id == "user-123"
```

### 11.5 标记测试类型

```python
import pytest

@pytest.mark.unit
async def test_validate_input():
    """单元测试"""
    ...

@pytest.mark.integration
async def test_database_operations(db_session):
    """集成测试"""
    ...

@pytest.mark.e2e
async def test_full_workflow(client):
    """端到端测试"""
    ...
```

---

## 质量检测工具

### 12.1 工具链

| 工具 | 用途 | 命令 |
|------|------|------|
| Ruff | 代码检查 + 格式化 | `make lint` / `make format` |
| Pyright | 类型检查 (推荐) | `make typecheck` |
| MyPy | 类型检查 (备用) | `make typecheck-mypy` |
| Bandit | 安全检查 | `make security` |
| pytest | 测试框架 | `make test` |
| pytest-cov | 覆盖率 | `make test-cov` |
| pre-commit | Git hooks | `pre-commit run` |

### 12.2 快速检查命令

```bash
# 安装开发依赖
make install-dev

# 运行所有检查
make check

# 自动修复问题
make fix

# 运行测试
make test

# 运行测试 (带覆盖率)
make test-cov
```

### 12.3 Pre-commit 配置

```yaml
# .pre-commit-config.yaml 已配置:
# - trailing-whitespace: 移除行尾空白
# - end-of-file-fixer: 确保文件以换行符结尾
# - ruff: 代码检查和格式化
# - pyright: 类型检查 (pre-push)
# - bandit: 安全检查
# - commitizen: 提交信息规范
```

### 12.4 CI 检查

```bash
# CI 环境运行 (严格模式)
make check-ci
```

---

## Git 工作流

### 13.1 分支命名

```
main                    # 主分支
develop                 # 开发分支
feature/xxx             # 功能分支
fix/xxx                 # 修复分支
docs/xxx                # 文档分支
refactor/xxx            # 重构分支
```

### 13.2 提交信息规范 (Conventional Commits)

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型 (type):**

| 类型 | 说明 |
|------|------|
| feat | 新功能 |
| fix | Bug 修复 |
| docs | 文档变更 |
| style | 代码格式 (不影响功能) |
| refactor | 重构 (不是新功能也不是修复) |
| perf | 性能优化 |
| test | 测试相关 |
| build | 构建相关 |
| ci | CI 配置 |
| chore | 杂项 |
| revert | 回滚 |

**示例:**

```
feat(agent): 添加检查点持久化功能

- 实现 CheckpointService
- 支持 Redis 和 PostgreSQL 存储
- 添加时间旅行调试 API

Closes #123
```

### 13.3 代码审查清单

- [ ] 类型注解完整，通过 `pyright --strict`
- [ ] 遵循项目结构和命名规范
- [ ] 有必要的文档和注释
- [ ] 错误处理完善
- [ ] 有对应的测试用例
- [ ] 通过所有质量检查 (`make check`)

---

## 附录

### A. 常用类型速查

```python
from typing import (
    Any,                    # 任意类型
    TypeVar,                # 类型变量
    Generic,                # 泛型
    Protocol,               # 协议/接口
    TypedDict,              # 字典类型约束
    Literal,                # 字面量类型
    TYPE_CHECKING,          # 类型检查时导入
)

from collections.abc import (
    Sequence,               # 序列
    Mapping,                # 映射
    Callable,               # 可调用
    Awaitable,              # 可等待
    AsyncGenerator,         # 异步生成器
)
```

### B. 项目核心类型

```python
from core.types import (
    # 枚举
    AgentMode,              # Agent 模式
    ToolCategory,           # 工具分类
    MessageRole,            # 消息角色
    EventType,              # 事件类型

    # Pydantic 模型
    ToolCall,               # 工具调用
    ToolResult,             # 工具结果
    AgentConfig,            # Agent 配置
    AgentState,             # Agent 状态
    Checkpoint,             # 检查点

    # Protocol
    ToolProtocol,           # 工具协议
    CheckpointerProtocol,   # 检查点协议
    LLMProviderProtocol,    # LLM 提供商协议

    # 泛型
    Result,                 # 结果类型 (类似 Rust)

    # 类型别名
    JSONObject,             # dict[str, Any]
    SessionId,              # str
)
```

### C. 相关文档

- [Python 类型注解指南](https://docs.python.org/3/library/typing.html)
- [Pydantic V2 文档](https://docs.pydantic.dev/latest/)
- [FastAPI 最佳实践](https://fastapi.tiangolo.com/tutorial/)
- [SQLAlchemy 2.0 异步指南](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Ruff 规则文档](https://docs.astral.sh/ruff/rules/)

---

<div align="center">

**代码质量是团队效率的基石**

*文档版本: v1.0.0 | 最后更新: 2026-01-12*

</div>
