# Backend 代码规范

## 核心原则

| 原则 | 说明 |
|------|------|
| **类型优先** | 所有代码必须有完整类型注解，通过 `pyright --strict` |
| **DRY** | 复用 `domains.*.domain.types`、UseCase 层，禁止重复逻辑 |
| **DDD 分层** | Presentation → Application → Domain ← Infrastructure |
| **显式优于隐式** | 明确声明类型和依赖，禁止 `from xxx import *` |

## 项目结构 (DDD 4层架构)

```
backend/
├── libs/                   # 纯技术基础设施（非业务）
│   ├── types/              # 通用工具类型 (Result[T])
│   ├── config/             # 配置管理
│   ├── db/                 # 数据库组件
│   ├── api/                # 共享 API 工具（服务工厂、错误常量）
│   ├── middleware/         # 通用中间件（日志、限流、错误处理）
│   ├── observability/      # 可观测性
│   └── orm/                # ORM 基类
├── domains/                # 业务领域
│   ├── identity/           # 身份认证域
│   │   ├── domain/types.py # Principal, ANONYMOUS_*
│   │   └── presentation/   # 认证依赖、中间件、Schema
│   ├── agent/              # Agent 域（核心业务域）
│   │   ├── domain/
│   │   │   ├── types.py    # Message, AgentEvent, ToolCall
│   │   │   ├── entities/   # AgentEntity, SessionDomainService
│   │   │   └── repositories/ # 仓储接口
│   │   ├── application/    # AgentUseCase, ChatUseCase, SessionUseCase
│   │   └── infrastructure/
│   │       ├── llm/        # LLM 网关
│   │       ├── memory/     # 记忆系统
│   │       ├── tools/      # 工具系统
│   │       ├── reasoning/  # 推理策略
│   │       └── models/     # ORM 模型
│   ├── evaluation/         # 评估领域
│   └── studio/             # 工作室领域
├── bootstrap/              # 启动层
│   ├── main.py             # FastAPI 入口
│   └── config.py           # 应用配置
├── utils/                  # 工具函数
└── tests/                  # 测试目录
```

**目录说明**：
- `libs/` - 纯技术基础设施，与业务无关的通用组件
- `domains/identity/` - 身份认证域，包含认证依赖、中间件、用户相关类型
- `domains/agent/` - Agent 域，包含 Agent 配置、会话、执行、记忆、工具等核心功能
- 每个域有自己的 `types.py` 放域特有类型

| 层级 | 职责 | 依赖 |
|------|------|------|
| `presentation/` | HTTP 路由、Schema、参数验证 | application |
| `application/` | UseCase 业务编排、事务处理 | domain |
| `domain/` | 实体、领域服务、仓储接口、域类型 | libs.types |
| `infrastructure/` | 仓储实现、ORM 模型、外部适配 | domain (接口) |

## 共享组件库 (libs/)

| 子模块 | 职责 |
|--------|------|
| `libs/types/` | 通用工具类型 (Result[T]) |
| `libs/config/` | 配置管理 |
| `libs/db/` | 数据库组件 |
| `libs/api/` | 服务工厂（get_*_service）、错误常量 |
| `libs/middleware/` | 通用中间件（日志、限流、错误处理）|

**注意**：认证相关依赖已移至 `domains/identity/presentation/`

## 类型安全

```python
# ✅ 从 identity 域导入身份类型
from domains.identity.domain.types import Principal, ANONYMOUS_ID_PREFIX

# ✅ 从 identity 域导入认证依赖
from domains.identity.presentation.deps import AuthUser, RequiredAuthUser, check_session_ownership
from domains.identity.presentation.schemas import CurrentUser

# ✅ 从 agent 域导入消息/事件类型
from domains.agent.domain.types import Message, AgentEvent, EventType, AgentConfig, ToolCall

# ✅ 从 agent 域导入基础设施组件
from domains.agent.infrastructure.llm import LLMGateway
from domains.agent.infrastructure.tools import ConfiguredToolRegistry
from domains.agent.application import ChatUseCase, SessionUseCase, AgentUseCase

# ✅ 从 libs 导入纯技术基础设施
from libs.config import ExecutionConfig
from libs.types import Result
from libs.api.deps import get_db, get_session_service  # 服务工厂

# ✅ Pydantic 模型
class UserCreate(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    username: str = Field(min_length=3, max_length=50)

# ✅ SQLAlchemy 类型
username: Mapped[str] = mapped_column(String(50), unique=True)
avatar: Mapped[str | None] = mapped_column(nullable=True)

# ✅ 避免循环依赖
if TYPE_CHECKING:
    from domains.identity.infrastructure.models.user import User
```

## 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | snake_case | `user_service.py` |
| 类 | PascalCase | `UserService`, `AgentConfig` |
| 函数/变量 | snake_case | `get_user_by_id`, `is_active` |
| 常量 | UPPER_SNAKE | `MAX_RETRY_COUNT` |
| 私有成员 | 前缀 `_` | `_internal_state` |
| API 函数 | 动词_名词 | `list_sessions`, `create_agent` |
| 布尔变量 | is_/has_/can_ | `is_active`, `has_permission` |

## 代码风格

# 使用 f-string
message = f"User {user.name} created"

# 使用 pathlib
config_path = Path(__file__).parent / "config.yaml"
```

## 错误处理

```python
# ✅ 使用 Result 类型
async def process_file(path: Path) -> Result[FileContent]:
    if not path.exists():
        return Result.err(f"File not found: {path}")
    return Result.ok(FileContent(path.read_text()))

# ✅ API 层异常
if not session:
    raise HTTPException(status_code=404, detail="Session not found")
```

## 异步编程

```python
# 异步数据库
async def get_user(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

# 并发控制
semaphore = asyncio.Semaphore(10)
async with semaphore:
    return await process(item)
```

## API 设计

```python
# RESTful 路由
router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.get("/")                    # 列表
@router.post("/")                   # 创建
@router.get("/{id}")                # 详情
@router.put("/{id}")                # 更新
@router.delete("/{id}")             # 删除

# 分页参数
skip: Annotated[int, Query(ge=0)] = 0
limit: Annotated[int, Query(ge=1, le=100)] = 20
```

## 测试规范

```python
# 命名: test_<场景>_<预期结果>
class TestSessionService:
    async def test_create_with_valid_data_succeeds(self): ...
    async def test_create_with_invalid_user_raises_error(self): ...

# 标记
@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.e2e
```

