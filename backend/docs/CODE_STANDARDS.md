# Backend 代码规范

## 核心原则

| 原则 | 说明 |
|------|------|
| **类型优先** | 所有代码必须有完整类型注解，通过 `pyright --strict` |
| **DRY** | 复用 `shared/types.py`、UseCase 层，禁止重复逻辑 |
| **DDD 分层** | Presentation → Application → Domain ← Infrastructure |
| **显式优于隐式** | 明确声明类型和依赖，禁止 `from xxx import *` |

## 项目结构 (DDD 4层架构)

```
backend/
├── api/v1/                 # API 路由汇总（表现层入口）
├── bootstrap/              # 启动层：FastAPI 入口、配置
│   ├── main.py             # FastAPI 应用入口
│   ├── config.py           # 应用配置
│   └── config_loader.py    # TOML 配置加载器
├── domains/                # 业务领域
│   ├── agent_catalog/      # Agent 目录管理
│   ├── evaluation/         # 评估领域
│   ├── identity/           # 身份认证
│   ├── runtime/            # Agent 运行时（核心）
│   │   ├── application/    # UseCase 业务编排
│   │   ├── domain/         # 实体/领域服务
│   │   ├── infrastructure/ # 基础设施实现
│   │   │   ├── engine/     # LangGraph Agent
│   │   │   ├── memory/     # 记忆系统
│   │   │   ├── reasoning/  # 推理策略
│   │   │   ├── sandbox/    # 沙箱执行器
│   │   │   └── tools/      # 工具系统
│   │   └── presentation/   # 路由 + Schema
│   └── studio/             # 工作室领域
├── shared/                 # 共享层
│   ├── kernel/             # 内核类型 (Principal)
│   ├── infrastructure/     # 共享基础设施
│   │   ├── auth/           # 认证 (JWT/RBAC)
│   │   ├── db/             # 数据库连接
│   │   ├── llm/            # LLM 网关
│   │   └── orm/            # ORM 基类
│   ├── presentation/       # 共享表示层（deps, errors, schemas）
│   └── types.py            # 核心类型定义
├── utils/                  # 工具函数
└── tests/                  # 测试目录
```

**目录说明**：
- `api/v1/` - 表现层入口，路由聚合，导入 `shared.presentation` 的依赖
- `bootstrap/` - 启动层，负责初始化 FastAPI 应用、配置和生命周期管理
- `shared/presentation/` - 共享的表示层组件：依赖注入、错误常量、Schema

| 层级 | 职责 | 依赖 |
|------|------|------|
| `presentation/` | HTTP 路由、Schema、参数验证 | application |
| `application/` | UseCase 业务编排、事务处理 | domain |
| `domain/` | 实体、领域服务、仓储接口 | - |
| `infrastructure/` | 仓储实现、ORM 模型、外部适配 | domain (接口) |
| `shared/` | 跨领域共享组件 | - |

## 类型安全

```python
# ✅ 使用项目类型
from shared.types import Result, AgentConfig, EventType, ToolCall
from shared.kernel.types import Principal

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

