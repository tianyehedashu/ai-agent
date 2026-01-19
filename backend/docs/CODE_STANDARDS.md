# Backend 代码规范

## 核心原则

| 原则 | 说明 |
|------|------|
| **类型优先** | 所有代码必须有完整类型注解，通过 `pyright --strict` |
| **DRY** | 复用 `core/types.py`、`services/` 层，禁止重复逻辑 |
| **单一职责** | API 层处理 HTTP，Service 层处理业务，Model 层定义数据 |
| **显式优于隐式** | 明确声明类型和依赖，禁止 `from xxx import *` |

## 项目结构

```
backend/
├── api/v1/          # API 路由
├── app/             # FastAPI 入口、配置
├── core/            # 核心类型定义 (types.py)
├── models/          # SQLAlchemy ORM 模型
├── schemas/         # Pydantic 请求/响应
├── services/        # 业务逻辑层
├── db/              # 数据库连接
├── tools/           # Agent 工具
└── tests/           # 测试 (unit/integration/e2e)
```

| 层级 | 职责 | 依赖 |
|------|------|------|
| `api/` | HTTP 请求处理、参数验证 | services, schemas |
| `services/` | 业务逻辑、事务处理 | models, db |
| `models/` | 数据库模型、关系映射 | db |
| `schemas/` | 请求/响应数据结构 | - |
| `core/` | 核心类型、枚举、协议 | - |

## 类型安全

```python
# ✅ 使用项目类型
from core.types import Result, AgentConfig, EventType, ToolCall

# ✅ Pydantic 模型
class UserCreate(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    username: str = Field(min_length=3, max_length=50)

# ✅ SQLAlchemy 类型
username: Mapped[str] = mapped_column(String(50), unique=True)
avatar: Mapped[str | None] = mapped_column(nullable=True)

# ✅ 避免循环依赖
if TYPE_CHECKING:
    from models.user import User
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

