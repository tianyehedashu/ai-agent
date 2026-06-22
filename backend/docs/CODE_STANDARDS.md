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
├── libs/                          # 纯技术基础设施（无业务规则、无「限界上下文」语义）
│   ├── types/                     # Result[T] 等通用代数类型
│   ├── config/                    # ExecutionConfig、校验器、多来源配置加载
│   ├── db/                        # AsyncSession 工厂、Redis、向量辅助（permission_context 见 libs/iam）
│   ├── api/                       # get_*_service 组合根、错误常量、共享 Query 参数
│   ├── exceptions/                # AIAgentError、HttpMappableDomainError 及子类层次
│   ├── iam/                       # TenantId、MembershipPort、团队错误 → HTTP 映射（跨域 IAM 抽象）
│   ├── middleware/                # 日志、trace、限流、匿名 Cookie、统一错误处理
│   ├── observability/             # 日志、Tracing、Metrics、Sentry
│   ├── orm/                       # DeclarativeBase 等 ORM 基类
│   ├── storage/                   # 本地文件/图片存储等纯 IO 适配
│   ├── mcp/                       # MCP 传输层共享工具（若存在）
│   # 无 libs/llm：LiteLLM/Provider 规则在 gateway/domain；Agent 消息适配在 agent/infrastructure/llm
│   ├── crypto.py                  # 加解密等扁平技术模块（按需增减）
│   └── background_tasks.py        # 通用后台任务辅助（若有）
│
├── domains/                       # 业务限界上下文（Bounded Context），每个子目录一个域
│   ├── identity/                  # 身份：Principal、JWT、API Key、User ORM
│   │   ├── domain/types.py        # Principal, ANONYMOUS_*
│   │   ├── application/
│   │   ├── infrastructure/        # User ORM、JWT、密码哈希
│   │   └── presentation/          # deps、schemas、auth 路由
│   │
│   ├── session/                   # 会话：Session、消息持久化、标题生成
│   │   ├── domain/
│   │   ├── application/
│   │   │   ├── ports.py           # SessionApplicationPort（供 Agent 等域依赖倒置）
│   │   │   └── ...                # SessionUseCase、TitleUseCase 等
│   │   ├── infrastructure/models/
│   │   └── presentation/          # /api/v1/sessions
│   │
│   ├── tenancy/                   # 团队/成员权威：Team、TeamMember、TeamService
│   │   ├── application/
│   │   ├── infrastructure/models/
│   │   └── presentation/          # 管理面团队解析（/teams/{team_id}/*）
│   │
│   ├── gateway/                   # AI Gateway、/v1 OpenAI + Anthropic、团队/预算/日志
│   │   ├── presentation/          # /api/v1/gateway/*、/v1/* 路由与 deps（不直连仓储）
│   │   ├── application/
│   │   │   ├── ports.py                    # GatewayProxyProtocol、GatewayCallContext 等（跨域内部桥接契约）
│   │   │   ├── gateway_proxy_factory.py    # get_gateway_proxy() → GatewayBridge
│   │   │   ├── internal_bridge.py          # GatewayBridge 实现（走 LiteLLM + 系统 vkey）
│   │   │   ├── internal_bridge_actor.py    # 内部调用 user_id / team_id 解析
│   │   │   ├── bridge_attribution.py       # GatewayBridgeAttribution
│   │   │   ├── litellm_bridge_payload.py   # acompletion / aembedding kwargs 拆分
│   │   │   ├── gateway_access_use_case.py
│   │   │   ├── proxy_use_case.py             # /v1 代理编排门面，不承载大块领域规则
│   │   │   ├── proxy_metadata_builder.py     # metadata / 定价 / 归因 kwargs 构建
│   │   │   ├── proxy_litellm_client.py       # LiteLLM Router / 直连技术适配
│   │   │   ├── proxy_response_adapter.py     # 响应适配、成本计算、预算结算
│   │   │   ├── proxy_deferred_tasks.py       # 代理异步结算任务收口
│   │   │   ├── jobs.py
│   │   │   └── management/        # reads / writes / usage_reads（管理面 CQRS）
│   │   ├── domain/                # VirtualKey、领域错误、UsageAggregation、proxy_policy 等
│   │   └── infrastructure/        # ORM、仓储、Router 单例、回调、护栏
│   │
│   ├── agent/                     # Agent 核心业务：对话、工具、记忆、LLM 编排
│   │   ├── domain/
│   │   │   ├── types.py           # Message, AgentEvent, ToolCall
│   │   │   ├── entities/
│   │   │   └── repositories/    # 仓储接口（若有）
│   │   ├── application/         # ChatUseCase、AgentUseCase（依赖 SessionApplicationPort 等）
│   │   ├── infrastructure/
│   │   │   ├── llm/               # AgentLlmFacade、embeddings、providers（可依赖 gateway.application.ports）
│   │   │   ├── memory/
│   │   │   ├── tools/
│   │   │   ├── reasoning/
│   │   │   └── models/
│   │   └── presentation/
│   │
│   └── evaluation/                # 评估
│
├── bootstrap/                     # 进程入口：FastAPI app、生命周期、路由挂载、全局中间件
│   ├── main.py
│   └── config.py                  # pydantic-settings；各域通过显式注入读取，避免散落 os.environ
│
├── utils/                         # 与域无关的纯函数（日志封装、字符串工具等）
├── alembic/                       # 数据库迁移版本
└── tests/                         # unit / integration / e2e；目录尽量镜像 domains 职责
    ├── unit/
    └── integration/
```

### 目录与依赖说明（细）

| 区域 | 放什么 | 不放什么 |
|------|--------|----------|
| **`libs/`** | DB 会话、配置加载、中间件、跨域 **IAM 抽象**、可观测性、ORM 基类、**无状态**工具函数 | 业务规则、虚拟 Key 策略、会话标题逻辑、Agent 编排 |
| **`domains/<bc>/domain/`** | 实体、值对象、领域服务、**本上下文**的类型与不变量 | HTTP、SQLAlchemy Session、第三方 SDK 细节 |
| **`domains/<bc>/application/`** | UseCase、事务边界、**对外暴露的应用端口（Protocol）**、后台任务编排 | Request/Response DTO（放 presentation） |
| **`domains/<bc>/infrastructure/`** | 仓储实现、ORM、外部 HTTP/SDK 适配 | 与 HTTP 绑定的参数校验 Schema |
| **`domains/<bc>/presentation/`** | FastAPI Router、Pydantic Schema、`Depends` 组装 | 复杂业务分支（下沉 application） |
| **`bootstrap/`** | 组装应用、挂载子路由、中间件顺序 | 具体业务用例 |

**跨域「应用端口」约定（与 `libs` 区分）**

- 由**提供能力的限界上下文**在 `application/` 下声明 **Protocol + DTO**，供其他域依赖倒置，**不要**放到 `libs/`（避免与「纯技术」混淆）。
- 示例：`domains/session/application/ports.py` 的 `SessionApplicationPort`；`domains/gateway/application/ports.py` 的 `GatewayProxyProtocol`、`GatewayCallContext`。
- 消费方（如 `domains/agent/infrastructure/llm`）`import` 上述端口类型；工厂函数（如 `get_gateway_proxy`）留在 **gateway 应用层**，内部再懒加载 `GatewayBridge`，避免应用层循环 import。

**目录说明（按域）**

- **`libs/`**：纯技术基础设施；可被任意域引用；不包含业务语言（不出现「虚拟 Key 业务规则」这类语义）。
- **`domains/identity/`**：认证主体、JWT、API Key、用户模型与登录相关 HTTP。
- **`domains/session/`**：会话生命周期、消息持久化、标题；对外端口 `SessionApplicationPort`。
- **`domains/tenancy/`**：团队与成员关系的**权威**数据与服务；Gateway 管理面通过 TeamService / 仓储访问团队，不复制团队规则。
- **`domains/gateway/`**：多模型路由、虚拟 Key、预算、日志与护栏；**内部 LLM 走 Gateway 桥接**的契约与实现均在 `application/` 上述文件中，与 **根路径 `/v1/*` 对外代理**（OpenAI 形与 Anthropic Messages）共用领域模型与 `ProxyUseCase`。
- **`domains/agent/`**：对话编排、工具、记忆、沙箱等；LLM 调用可通过端口走 Gateway 或直连 LiteLLM（由配置与归因决定）。
- **`bootstrap/`**：唯一进程入口侧组装；各域保持可测试的纯函数与可注入依赖。

| 层级 | 职责 | 典型依赖 |
|------|------|----------|
| `presentation/` | HTTP 路由、Schema、参数验证 | `application`（UseCase / 服务） |
| `application/` | 用例编排、事务、对外 **Ports** | `domain`、同域 `infrastructure`（经接口或工厂） |
| `domain/` | 实体、领域服务、仓储 **接口**、域类型 | `libs.types` 等极少通用类型 |
| `infrastructure/` | 仓储实现、ORM、外部系统适配 | `domain`（实现其接口） |

### DDD 反退化约束（适用于全部域）

> 适用于所有 `domains/*`；Gateway 是历史最重灾区，故另起小节列规则。

- **拒绝 Domain 退化（Anemic Domain Model）**：
  - 凡新增「不变量、白名单、策略选择、计划生成」一类纯逻辑，必须先落到
    `domains/<域>/domain/` 的值对象、领域服务或 policy 函数；不允许只写在 application
    私有方法里。
  - `domain/` 模块禁止 import SQLAlchemy `Session` / ORM 实体（不属于 `domain/types`
    的）/ Redis / LiteLLM / FastAPI / httpx；策略需要数据时由 application 先查出**纯值
    快照**再传给 domain 函数。
  - 出现 ≥3 个对同一概念的 `if scope == ... / elif ...` 分支时，应抽成 domain 值对象或
    枚举驱动的 policy。
- **拒绝 Application 加重（Fat Use Case / God Service）**：
  - 单个 `*UseCase` 不得同时承担「校验 + 限流 + 预算 + metadata + 外部 SDK 调用 + 响应
    适配 + 结算」；应按**变化原因**拆成独立 application 模块。
  - UseCase 内允许的变化原因仅为「编排顺序变化」；其它原因（换 SDK、换字段映射、
    换归因来源）触发的修改属于拆分不到位。
  - 单个 application 文件 > 800 行、或单类私有方法 > 15 个，PR 必须给出拆分说明或显式
    follow-up todo。
- **跨模块协作禁止依赖私有符号**：application 服务之间不得 import 对方的 `_` 前缀函数；
  如果某行为需要被复用，必须晋升为模块级公开函数 / 类并写入 `__all__`。
- **测试 monkeypatch 目标必须真实**：拆分后单测的 `monkeypatch.setattr` 应指向真正实现
  的模块路径，而不是经由再导出别名的 facade。

### Gateway 热路径分层约束

- `ProxyUseCase` 是 `/v1/*` 代理编排门面，只串联 preflight、metadata、LiteLLM 调用与
  响应结算；新增能力不得继续把完整业务分支直接塞回 `proxy_use_case.py`。
- **Domain 层**（`domains/gateway/domain/proxy_policy.py` 等）承载：
  - 模型/能力白名单 (`assert_model_allowed`、`assert_capability_allowed`)
  - 注册模型 capability 与 HTTP 入口匹配 (`assert_registered_model_capability`)
  - 预算 scope 选择与「该扫描哪些行」的 plan (`budget_scope_targets`、
    `build_budget_check_plan`、`BudgetCheckQuery`)
  - 限流 token 维度选择 (`rate_limit_target`)、错误文案的 `first_present_limit` 等纯函数
- **Application 层**按职责拆分协作模块：
  - `proxy_metadata_builder.py` —— Gateway metadata、归因、下游单价 kwargs
  - `proxy_litellm_client.py` —— LiteLLM Router / 直连技术适配
  - `proxy_response_adapter.py` —— 响应适配、`response_cost` 注入、预算/套餐结算
  - `deferred_task_runner.py` / `virtual_key_touch.py` / `usage_bucket_flusher.py` —— 响应后延迟写入（有界执行器 + 合并刷写，见 `docs/gateway/DEFERRED_WRITE_CONCURRENCY.md`）
  - `proxy_deferred_tasks.py` —— 后台任务登记 + shutdown 收口
  - `proxy_chat_pipeline.py` / `proxy_stream_settlement.py` —— Chat/Anthropic 流水线
- 禁止在 `proxy_use_case.py` 顶层加「兼容再导出」别名（如 `_settle_usage`、`_enrich_*`、
  `register_proxy_deferred_task` 等）；旧调用方一律改到正确模块。
- Code review / `code-check` 遇到 Gateway 代理改动时，必须显式回答：
  「新增规则落在了 domain 还是 application？为什么不下沉？」

### 读路径 / 字段扩展（CQRS）

> 适用于所有 `domains/*`；目标是「加一个字段不要改 5 处」「列表/详情不要写两套 SQL」。

- **读模型单点**：同一资源的 list / detail / dashboard / 大盘**共用** repository 或
  `*ReadMixin` / `*ReadService` 入口；仅 projection、过滤参数不同，禁止复制 `select(...)`
  列清单到多个 application 方法。
- **加字段最小改动面**：扩展字段时按下列固定链路改动，多一处即视为偏离：

  ```
  alembic migration → ORM 列 → application ReadModel / 端口 DTO
                     → *_read_mappers.py → presentation Schema → 测试
  ```

  不允许跳过 ReadModel 或 mapper 在 router 内直接 `{"new_field": row.new_field}` 拼装。
- **跨域只看端口 DTO**：消费方依赖提供方 `application/ports.py` 的 DTO，不复制字段结构；
  ORM 实体不得跨域 import 当作返回类型。
- **业务过滤下沉**：可见性 / team axis / scope 等过滤规则在 domain policy 决策（如
  `usage_log_visibility`、`pricing_visibility`、`system_visibility_filter`），application 按
  policy 计划查一次；禁止 presentation 为补字段再开第二条 IO。
- **测试同步**：新字段必须在 `tests/integration/api/` 断言；前端改 API 消费处时核对
  `@/types` 或 `frontend/src/features/<bc>/*` 内单一 adapter，避免每个调用点各拼一份。
- **典型参照（Gateway 管理面）**：`application/management/credential_read_mappers.py`、
  `application/management/*_read_model.py`、`application/management/reads.py` 已落地此模式，
  新代码遵循同形态。

## 共享组件库 (`libs/`)

| 子模块 | 职责 |
|--------|------|
| `libs/types/` | `Result[T]` 等通用类型 |
| `libs/config/` | 应用配置、校验器、多来源合并 |
| `libs/db/` | 异步引擎/会话、`permission_context`、Redis、向量辅助 |
| `libs/api/` | 组合根 `get_*_service`、`deps`、共享错误常量 |
| `libs/exceptions/` | 跨域异常基类与 HTTP 可映射错误 |
| `libs/iam/` | 租户/成员关系 **抽象**（Port）与 HTTP 映射，不含团队业务规则实现 |
| `libs/middleware/` | 日志、trace、限流、错误处理 |
| `libs/observability/` | Metrics、Tracing、Sentry 等 |

**注意**：认证 **依赖与路由** 在 `domains/identity/presentation/`；**团队实体与规则** 在 `domains/tenancy/`。

## 类型安全

```python
# ✅ 从 identity 域导入身份类型
from domains.identity.domain.types import Principal

# ✅ 从 identity 域导入认证依赖
from domains.identity.presentation.deps import AuthUser, RequiredAuthUser, check_tenant_access
from domains.identity.presentation.schemas import CurrentUser

# ✅ 从 agent 域导入消息/事件类型
from domains.agent.domain.types import Message, AgentEvent, EventType, AgentConfig, ToolCall

# ✅ 从 session 域导入会话相关（列表/详情/检查点鉴权用 SessionUseCase.assert_session_accessible）
# ✅ 租户资源显式鉴权用 identity.deps.check_tenant_access
from domains.session.application import SessionUseCase, TitleUseCase
from domains.session.application.ports import SessionApplicationPort
from domains.session.infrastructure.models import Session

# ✅ 从 gateway 域导入内部桥接端口（跨域调用 AI Gateway 时）
from domains.gateway.application.ports import (
    GatewayCallContext,
    GatewayProxyProtocol,
    GatewayResponse,
    GatewayStreamChunk,
)
from domains.gateway.application.gateway_proxy_factory import get_gateway_proxy

# ✅ 从 agent 域导入基础设施组件
from domains.agent.infrastructure.llm import AgentLlmFacade
from domains.agent.infrastructure.tools import ConfiguredToolRegistry
from domains.agent.application import ChatUseCase, AgentUseCase

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

## ORM 与多租户数据归属

- **多租户业务表**：`BaseModel` + `TenantScopedMixin`（物理列 `tenant_id UUID NOT NULL`）；系统级配置写入 `system_*` 表。
- **系统级配置**：`system_*` 表（无 `tenant_id`），如 `system_gateway_models`；查询时在应用层 `list_system()` + `list_for_tenant()` 合并（tenant 同名覆盖 system）。
- **个人用户**：归属 `personal` team（`TeamService.ensure_personal_team`）。
- **认证模式**：`auth_mode=local`（邮箱密码 + JWT）或 `auth_mode=sso`（HiGress(giikin-auth-bridge) 注入 `X-Giikin-*` 身份，校验 `X-Giikin-Internal-Key` 后按 `giikin_user_id` JIT 建本地用户）。**已移除匿名访问**：无有效身份一律 401。见 `domains/identity/application/principal_service.py`、`infrastructure/auth/giikin_gateway.py`。
- **授权链**：`User → team_members → tenant_id`；`PermissionContext.team_ids` + `DataScopeEnforcer`（libs 机制，不含 domain 字面量）。
- **策略挂载**：`PolicyTargetMixin`（`target_kind` / `target_id`），与 tenant 正交；字面量仅出现在各 domain（如 gateway `vkey`）。

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

```python
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

# 分页：见 docs/PAGINATION.md；错误：见 docs/API_RESPONSE.md
from libs.api.pagination import PageParams, PaginatedListResponse, build_page, page_query_params
from libs.api.problem_details import ProblemDetails, problem_response_from_agent_error
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

**集成测试**：需要 DB/Redis 等外部依赖时，在 `tests/integration/` 运行；与 Gateway 管理面、OpenAI 兼容相关的用例见 `tests/integration/api/test_gateway_management_api.py`、`test_openai_compat_api.py`、`test_gateway_bridge_attribution.py` 等。全量集成建议：

`uv run pytest tests/integration/ -q --tb=short`

**AsyncSession 长 I/O**（`libs/db/session_lifecycle.py`）：

| Helper | 场景 | 行为 |
|--------|------|------|
| `release_request_db_connection` | Gateway **代理** preflight 后 | rollback + **close**，连接还 pool（高并发 504 修复） |
| `release_session_before_blocking_io` | **管理面**探活、凭据上游列表探测 | rollback 或 commit 待写入；**不 close**，同请求后续仍写库 |

共用规则：**调用任一 helper 前**把仍需使用的 ORM 字段读入局部变量（如 `credential.name`）；rollback 后 lazy load 在 LiteLLM 同步路径会 `MissingGreenlet` / `xd2s`（探活 `probe.py` 曾踩坑）。

**Gateway 集成测 session 约定**（`tests/integration/conftest.py`，autouse）：

- `client` / `dev_client` 将**同一条** `db_session` 注入 `get_db`；生产路径在上游前会 `release_request_db_connection()`（`close()`），集成测对该调用 noop，避免 `DetachedInstanceError` / `MissingGreenlet`。
- 多 HTTP 请求串行时，`_finalize_dependency_session` 改为**仅 flush** 待写入行（不 commit），否则后续请求的 JWT `read_token` 会 401（`TOKEN_ERROR`）；回滚由 `db_session` fixture 收尾。

**Gateway 单元测 xdist**（`tests/unit/gateway/conftest.py`）：`pytestmark = xdist_group("gateway_db")`，配合 Makefile `--dist=loadgroup`，避免多 worker 并发写 `system_provider_credentials` 等全局表时死锁。团队凭据单测种子须带 `created_by_user_id`（见 `credential_test_helpers.create_tenant_test_credential`），与 `can_create_model_on_team_credential` 策略一致。

---

更完整的架构与 Gateway 边界说明见同目录 **[ARCHITECTURE.md](./ARCHITECTURE.md)**、**[AI_GATEWAY_DOMAIN_ARCHITECTURE.md](./AI_GATEWAY_DOMAIN_ARCHITECTURE.md)**；仓库根 **AGENTS.md** 为跨语言导入备忘。
