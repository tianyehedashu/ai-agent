# 权限系统架构文档

## 目录

- [概述](#概述)
- [实现状态](#实现状态)
- [架构设计](#架构设计)
- [核心组件](#核心组件)
- [数据权限处理流程](#数据权限处理流程)
- [使用指南](#使用指南)
- [最佳实践](#最佳实践)
- [常见问题](#常见问题)

## 概述

本系统实现了基于角色的访问控制（RBAC）和数据权限的统一管理，支持注册用户和匿名用户，并提供管理员权限绕过机制。

## 实现状态

### ✅ 已实现

1. **核心组件**
   - ✅ `OwnedMixin` 和 `OwnedProtocol` - 模型所有权协议
   - ✅ `PermissionContext` - 权限上下文
   - ✅ `OwnedRepositoryBase` - Repository 基类
   - ✅ `PermissionContextMiddleware` - 权限上下文中间件
   - ✅ `Principal` 和 `CurrentUser` 的 `role` 字段
   - ✅ 权限检查函数（`check_ownership`、`check_ownership_or_public`、`check_session_ownership`）
   - ✅ 角色依赖（`require_role`、`AdminUser`）

2. **模型层**
   - ✅ `Session` 模型继承 `OwnedMixin`
   - ✅ `Agent` 模型继承 `OwnedMixin`

3. **Presentation 层**
   - ✅ Studio 路由权限检查已修复
   - ✅ Agent 和 Memory 路由已适配新的权限检查函数

### ✅ 已完成迁移

1. **Repository 层迁移**
   - ✅ 会话仓储已继承 `OwnedRepositoryBase`，支持自动权限过滤
   - ✅ Agent 仓储已继承 `OwnedRepositoryBase`，支持自动权限过滤
   - ✅ `find_by_user` 和 `get_by_id` 方法已迁移使用 `find_owned` 和 `get_owned`

2. **权限上下文设置**
   - ✅ `get_current_user` 依赖已自动设置权限上下文
   - ✅ 权限上下文中间件已注册到 FastAPI 应用

### 设计目标

1. **统一数据权限处理**：在 Repository 层自动过滤数据，防止权限漏洞
2. **支持多种用户类型**：注册用户、匿名用户、管理员
3. **显式权限检查**：在 Presentation 层提供显式的所有权检查函数
4. **类型安全**：使用类型协议和混入类确保类型安全
5. **易于扩展**：通过基类和协议，便于添加新的资源类型

### 核心特性

- ✅ 自动数据过滤（Repository 层）
- ✅ 显式权限检查（Presentation 层）
- ✅ 管理员权限绕过
- ✅ 匿名用户支持
- ✅ 角色基础访问控制（RBAC）
- ✅ 类型安全的模型定义

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    HTTP 请求层                                │
│              (JWT Token / Anonymous Cookie)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    认证层                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ JWTStrategy  │→ │ User Model   │→ │ get_principal│      │
│  │              │  │ (with role)  │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                       │                                      │
│                       ▼                                      │
│              Principal(id, email, name, role)                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Presentation 层                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │get_current_  │→ │ CurrentUser  │→ │check_owner-  │      │
│  │   user()     │  │ (with role)  │  │   ship()     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  中间件层                                     │
│         PermissionContextMiddleware                          │
│              PermissionContext                               │
│         (user_id, anonymous_user_id, role)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Repository 层                                │
│         OwnedRepositoryBase                                  │
│    _apply_ownership_filter(query)                            │
│    ├─ 管理员 → 不过滤，返回所有数据                           │
│    ├─ 匿名用户 → WHERE anonymous_user_id = ?                 │
│    └─ 注册用户 → WHERE user_id = ?                           │
└─────────────────────────────────────────────────────────────┘
```

### 两层权限检查

系统采用两层权限检查机制：

| 层级 | 方法 | 职责 | 适用场景 |
|------|------|------|----------|
| **Repository 层** | `find_owned()` | 自动过滤列表数据 | 列表查询 |
| **Repository 层** | `get_owned()` | 获取单个实体并检查所有权 | 单条查询（可选） |
| **Presentation 层** | `check_ownership()` | 显式检查单个资源所有权 | 更新/删除操作 |

**为什么需要两层？**

- **Repository 层**：自动过滤，防止遗漏，适合列表查询
- **Presentation 层**：显式检查，用于 `get_by_id` 后的所有权验证（因为 `get_by_id` 不自动过滤）

## 核心组件

### 1. OwnedMixin 和 OwnedProtocol

**位置**：`backend/libs/orm/base.py`

提供所有权字段的类型协议和通用方法。

```python
@runtime_checkable
class OwnedProtocol(Protocol):
    """所有权协议 - 用于类型检查"""
    user_id: uuid.UUID | None
    anonymous_user_id: str | None

class OwnedMixin:
    """所有权混入类
    
    为模型提供所有权字段的类型声明和通用方法。
    各模型仍然自己定义字段（必填/可选），Mixin 只提供类型协议。
    """
    user_id: "Mapped[uuid.UUID | None]"
    anonymous_user_id: "Mapped[str | None] | None"
    
    def is_owned_by(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
    ) -> bool:
        """检查是否被指定用户拥有"""
        # ...
```

**使用示例**：

```python
# Agent 模型：user_id 必填
class Agent(BaseModel, OwnedMixin):
    user_id: Mapped[uuid.UUID] = mapped_column(...)  # 必填

# Session 模型：user_id 和 anonymous_user_id 可选
class Session(BaseModel, OwnedMixin):
    user_id: Mapped[uuid.UUID | None] = mapped_column(...)  # 可选
    anonymous_user_id: Mapped[str | None] = mapped_column(...)  # 可选
```

### 2. PermissionContext

**位置**：`backend/libs/db/permission_context.py`

封装当前请求的用户身份和权限信息，使用 `ContextVar` 在请求生命周期内传递。

```python
@dataclass(frozen=True)
class PermissionContext:
    """数据权限上下文"""
    user_id: uuid.UUID | None = None
    anonymous_user_id: str | None = None
    role: str = "user"
    
    @property
    def is_admin(self) -> bool:
        """是否为管理员"""
        return self.role == "admin"
    
    @property
    def is_anonymous(self) -> bool:
        """是否为匿名用户"""
        return self.anonymous_user_id is not None
```

**API**：

- `get_permission_context()`: 获取当前权限上下文
- `set_permission_context(ctx)`: 设置权限上下文
- `clear_permission_context()`: 清除权限上下文

### 3. OwnedRepositoryBase

**位置**：`backend/libs/db/base_repository.py`

带所有权过滤的 Repository 基类，自动根据 `PermissionContext` 过滤数据。

```python
class OwnedRepositoryBase(ABC, Generic[T]):
    """带所有权过滤的 Repository 基类
    
    自动根据 PermissionContext 过滤数据：
    - 管理员：可访问所有数据
    - 普通用户：只能访问自己的数据
    """
    
    @property
    @abstractmethod
    def model_class(self) -> type[T]:
        """返回模型类"""
        ...
    
    @property
    def anonymous_user_id_column(self) -> str | None:
        """匿名用户 ID 字段名，不支持匿名则返回 None"""
        return None
    
    def _apply_ownership_filter(self, query: Select) -> Select:
        """应用所有权过滤"""
        ctx = get_permission_context()
        if ctx is None:
            return query.where(False)  # 安全默认
        
        if ctx.is_admin:
            return query  # 管理员可访问所有数据
        
        # 根据用户类型过滤
        if ctx.is_anonymous and self.anonymous_user_id_column:
            return query.where(
                getattr(model, self.anonymous_user_id_column) == ctx.anonymous_user_id
            )
        elif ctx.user_id:
            return query.where(
                getattr(model, self.user_id_column) == ctx.user_id
            )
        
        return query.where(False)
    
    async def find_owned(self, skip: int = 0, limit: int = 20, **filters) -> list[T]:
        """查询当前用户拥有的数据（自动过滤）"""
        # ...
    
    async def get_owned(self, entity_id: uuid.UUID) -> T | None:
        """获取单个实体（自动检查所有权）"""
        # ...
```

**使用示例**：

```python
from domains.agent.domain.interfaces.session_repository import (
    SessionRepository as SessionRepositoryInterface,
)

class SessionRepository(OwnedRepositoryBase[Session], SessionRepositoryInterface):
    """会话仓储实现
    
    继承 OwnedRepositoryBase 提供自动权限过滤功能。
    """
    @property
    def model_class(self) -> type[Session]:
        return Session
    
    @property
    def anonymous_user_id_column(self) -> str:
        return "anonymous_user_id"  # 支持匿名用户
    
    # find_by_user 可以简化为调用 find_owned
    async def find_by_user(self, ...) -> list[Session]:
        return await self.find_owned(skip=skip, limit=limit, agent_id=agent_id)
```

### 4. PermissionContextMiddleware

**位置**：`backend/libs/middleware/permission.py`

在请求开始时从认证信息创建 `PermissionContext`，供 Repository 层使用。

```python
class PermissionContextMiddleware(BaseHTTPMiddleware):
    """权限上下文中间件"""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            ctx = None
            if hasattr(request.state, "current_user"):
                user = request.state.current_user
                # 解析用户身份
                ctx = PermissionContext(
                    user_id=...,
                    anonymous_user_id=...,
                    role=user.role,
                )
            set_permission_context(ctx)
            response = await call_next(request)
            return response
        finally:
            clear_permission_context()
```

### 5. Principal 和 CurrentUser

**位置**：
- `backend/domains/identity/domain/types.py` (Principal)
- `backend/domains/identity/presentation/schemas.py` (CurrentUser)

统一的身份主体，支持注册用户和匿名用户，包含角色信息。

```python
@dataclass(frozen=True, slots=True)
class Principal:
    """统一的身份主体"""
    id: str
    email: str
    name: str
    is_anonymous: bool = False
    role: str = "user"  # 用户角色：admin, user, viewer

class CurrentUser(BaseModel):
    """当前登录用户（用于依赖注入）"""
    id: str
    email: str
    name: str
    is_anonymous: bool = False
    role: str = "user"  # 用户角色：admin, user, viewer
```

### 6. 权限检查函数

**位置**：`backend/domains/identity/presentation/deps.py`

提供显式的权限检查函数，支持管理员绕过。

```python
def check_ownership(
    resource_user_id: str,
    current_user: CurrentUser,
    resource_name: str = "Resource",
) -> None:
    """检查资源所有权（管理员可访问所有资源）"""
    if current_user.role == ADMIN_ROLE:
        return  # 管理员绕过
    if str(resource_user_id) != current_user.id:
        raise PermissionDeniedError(...)

def check_ownership_or_public(
    resource_user_id: str,
    current_user: CurrentUser,
    is_public: bool,
    resource_name: str = "Resource",
) -> None:
    """检查资源所有权或是否公开（管理员可访问所有资源）"""
    if current_user.role == ADMIN_ROLE:
        return  # 管理员绕过
    if str(resource_user_id) != current_user.id and not is_public:
        raise PermissionDeniedError(...)

def check_session_ownership(
    session: SessionLike,
    current_user: CurrentUser,
) -> None:
    """检查会话所有权（支持注册用户和匿名用户，管理员可访问所有会话）"""
    if current_user.role == ADMIN_ROLE:
        return  # 管理员绕过
    # 检查逻辑...
```

### 7. 角色依赖

**位置**：`backend/domains/identity/presentation/deps.py`

提供基于角色的依赖注入。

```python
# 角色常量
ADMIN_ROLE = "admin"
USER_ROLE = "user"
VIEWER_ROLE = "viewer"

def require_role(*roles: str):
    """要求特定角色的依赖工厂"""
    async def dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role not in roles:
            raise PermissionDeniedError(...)
        return current_user
    return dependency

# 类型别名
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
RequiredAuthUser = Annotated[CurrentUser, Depends(require_auth)]
AdminUser = Annotated[CurrentUser, Depends(require_role(ADMIN_ROLE))]
```

**使用示例**：

```python
@router.get("/admin-only")
async def admin_only(user: AdminUser):
    """仅管理员可访问"""
    ...

@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    current_user: AuthUser,
) -> dict[str, Any]:
    workflow = await service.get(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=WORKFLOW_NOT_FOUND)
    
    # 显式检查所有权（管理员可访问所有）
    check_ownership(str(workflow.user_id), current_user, "Workflow")
    
    return {...}
```

## 数据权限处理流程

### 完整流程

```
HTTP 请求
    ↓
认证中间件 → JWT/Cookie → User 对象 (含 role)
    ↓
get_principal() → Principal(id, email, name, is_anonymous, role)
    ↓
get_current_user() → CurrentUser(id, email, name, is_anonymous, role)
    ↓
PermissionContextMiddleware → PermissionContext(user_id, anonymous_user_id, role)
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Repository 层自动过滤                                        │
│                                                             │
│ OwnedRepositoryBase._apply_ownership_filter(query)          │
│   ├─ ctx.is_admin → 不过滤，返回所有数据                      │
│   ├─ ctx.is_anonymous → WHERE anonymous_user_id = ?         │
│   └─ ctx.user_id → WHERE user_id = ?                        │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Presentation 层显式检查（单个资源操作时）                      │
│                                                             │
│ check_ownership(resource_user_id, current_user)             │
│   ├─ current_user.role == "admin" → 绕过                    │
│   └─ 比较 user_id                                           │
└─────────────────────────────────────────────────────────────┘
```

### 权限过滤逻辑

```python
def _apply_ownership_filter(self, query: Select) -> Select:
    ctx = get_permission_context()
    
    # 1. 无上下文：返回空结果（安全默认）
    if ctx is None:
        return query.where(False)
    
    # 2. 管理员：不过滤，返回所有数据
    if ctx.is_admin:
        return query
    
    # 3. 匿名用户：按 anonymous_user_id 过滤
    if ctx.is_anonymous and self.anonymous_user_id_column:
        return query.where(
            getattr(model, self.anonymous_user_id_column) == ctx.anonymous_user_id
        )
    
    # 4. 注册用户：按 user_id 过滤
    elif ctx.user_id:
        return query.where(
            getattr(model, self.user_id_column) == ctx.user_id
        )
    
    # 5. 无有效身份：返回空结果
    return query.where(False)
```

## 使用指南

### 1. 定义模型

```python
from libs.orm.base import BaseModel, OwnedMixin

class MyResource(BaseModel, OwnedMixin):
    """我的资源模型"""
    __tablename__ = "my_resources"
    
    # 定义所有权字段（根据业务需求选择必填/可选）
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,  # 必填
        index=True,
    )
    # 如果需要支持匿名用户
    anonymous_user_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,  # 可选
        index=True,
    )
    
    # 其他字段...
    name: Mapped[str] = mapped_column(String(255))
```

### 2. 实现 Repository

```python
from libs.db.base_repository import OwnedRepositoryBase
from domains.my_domain.domain.interfaces.my_resource_repository import (
    MyResourceRepository as MyResourceRepositoryInterface,
)

class MyResourceRepository(
    OwnedRepositoryBase[MyResource],
    MyResourceRepositoryInterface
):
    """资源仓储实现
    
    继承 OwnedRepositoryBase 提供自动权限过滤功能。
    接口和实现类同名，通过文件路径区分：
    - 接口：domain/interfaces/my_resource_repository.py
    - 实现：infrastructure/repositories/my_resource_repository.py
    """
    
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)  # 初始化 OwnedRepositoryBase
        self.db = db
    
    @property
    def model_class(self) -> type[MyResource]:
        return MyResource
    
    @property
    def anonymous_user_id_column(self) -> str | None:
        return "anonymous_user_id"  # 如果支持匿名用户
    
    # 使用 find_owned 自动过滤
    async def find_by_user(
        self,
        skip: int = 0,
        limit: int = 20,
        **filters,
    ) -> list[MyResource]:
        return await self.find_owned(skip=skip, limit=limit, **filters)
    
    # 使用 get_owned 自动检查所有权
    async def get_by_id(self, resource_id: uuid.UUID) -> MyResource | None:
        return await self.get_owned(resource_id)
```

### 3. 在路由中使用权限检查

```python
from domains.identity.presentation.deps import (
    AuthUser,
    check_ownership,
)

@router.get("/resources/{resource_id}")
async def get_resource(
    resource_id: str,
    current_user: AuthUser,
) -> dict[str, Any]:
    """获取资源"""
    resource = await service.get(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    # 显式检查所有权（管理员可访问所有）
    check_ownership(str(resource.user_id), current_user, "Resource")
    
    return {...}

@router.put("/resources/{resource_id}")
async def update_resource(
    resource_id: str,
    update_data: ResourceUpdate,
    current_user: AuthUser,
) -> dict[str, Any]:
    """更新资源"""
    resource = await service.get(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    # 显式检查所有权
    check_ownership(str(resource.user_id), current_user, "Resource")
    
    updated = await service.update(resource_id, update_data)
    return {...}

@router.delete("/resources/{resource_id}")
async def delete_resource(
    resource_id: str,
    current_user: AuthUser,
) -> dict[str, Any]:
    """删除资源"""
    resource = await service.get(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    # 显式检查所有权
    check_ownership(str(resource.user_id), current_user, "Resource")
    
    await service.delete(resource_id)
    return {"message": "Resource deleted"}
```

### 4. 权限上下文设置

权限上下文会在 `get_current_user` 依赖中自动设置，无需手动配置。中间件也已注册，作为备用机制。

**实现方式**：

1. **依赖注入中设置**（主要方式）：`get_current_user` 会自动设置权限上下文
2. **中间件设置**（备用方式）：`PermissionContextMiddleware` 已注册到 FastAPI 应用

```python
# backend/bootstrap/main.py
from libs.middleware.permission import PermissionContextMiddleware

app = FastAPI(...)

# 权限上下文中间件（已注册）
app.add_middleware(PermissionContextMiddleware)
```

**工作原理**：
- 当路由使用 `AuthUser` 或 `get_current_user` 依赖时，会自动设置权限上下文
- Repository 层的 `find_owned` 和 `get_owned` 方法会自动使用权限上下文进行过滤
- 无需在每个 Repository 方法中手动传递用户信息

### 5. 使用角色依赖

```python
from domains.identity.presentation.deps import AdminUser

@router.get("/admin/dashboard")
async def admin_dashboard(user: AdminUser):
    """仅管理员可访问"""
    return {"message": "Admin dashboard", "user": user}
```

## 最佳实践

### 1. 模型定义

- ✅ **继承 OwnedMixin**：所有需要权限控制的模型都应继承 `OwnedMixin`
- ✅ **明确字段类型**：根据业务需求明确 `user_id` 和 `anonymous_user_id` 的必填/可选
- ✅ **添加索引**：为所有权字段添加数据库索引以提高查询性能

```python
class MyResource(BaseModel, OwnedMixin):
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,  # 添加索引
    )
```

### 2. Repository 实现

- ✅ **继承 OwnedRepositoryBase**：自动获得数据过滤能力
- ✅ **实现 model_class**：必须实现 `model_class` 属性
- ✅ **配置匿名支持**：如果支持匿名用户，实现 `anonymous_user_id_column`
- ✅ **使用 find_owned/get_owned**：列表查询使用 `find_owned`，单条查询使用 `get_owned`

```python
class MyResourceRepository(OwnedRepositoryBase[MyResource], MyRepositoryInterface):
    """资源仓储实现"""
    
    @property
    def model_class(self) -> type[MyResource]:
        return MyResource
    
    @property
    def anonymous_user_id_column(self) -> str | None:
        return "anonymous_user_id"  # 如果支持
```

### 3. 路由权限检查

- ✅ **使用类型注解**：使用 `AuthUser`、`RequiredAuthUser`、`AdminUser` 等类型别名
- ✅ **显式检查所有权**：对于更新/删除操作，必须调用 `check_ownership`
- ✅ **处理 404**：先检查资源是否存在，再检查权限
- ✅ **管理员绕过**：权限检查函数已自动支持管理员绕过，无需额外处理

```python
@router.put("/resources/{resource_id}")
async def update_resource(
    resource_id: str,
    update_data: ResourceUpdate,
    current_user: AuthUser,  # 使用类型别名
) -> dict[str, Any]:
    resource = await service.get(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Not found")
    
    check_ownership(str(resource.user_id), current_user, "Resource")  # 显式检查
    # ...
```

### 4. 错误处理

- ✅ **统一错误类型**：使用 `PermissionDeniedError` 表示权限错误
- ✅ **清晰的错误消息**：提供清晰的错误消息和资源名称

```python
try:
    check_ownership(str(resource.user_id), current_user, "Resource")
except PermissionDeniedError as e:
    # 错误已自动转换为 HTTPException
    raise
```

### 5. 测试

- ✅ **测试权限过滤**：测试 Repository 层的数据过滤是否正确
- ✅ **测试权限检查**：测试 Presentation 层的权限检查是否正确
- ✅ **测试管理员绕过**：测试管理员是否可以访问所有资源
- ✅ **测试匿名用户**：测试匿名用户的权限是否正确

## 常见问题

### Q1: 为什么需要两层权限检查？

**A**: Repository 层自动过滤适合列表查询，防止遗漏；Presentation 层显式检查适合单个资源操作，提供更明确的错误信息。

### Q2: 什么时候使用 `find_owned` vs `get_owned`？

**A**: 
- `find_owned`: 用于列表查询，自动过滤当前用户的数据
- `get_owned`: 用于单条查询，自动检查所有权，如果无权限返回 `None`

### Q3: 什么时候需要显式调用 `check_ownership`？

**A**: 对于更新/删除操作，即使使用了 `get_owned`，也建议显式调用 `check_ownership` 以提供更清晰的错误信息。

### Q4: 如何支持新的资源类型？

**A**: 
1. 模型继承 `OwnedMixin`
2. Repository 继承 `OwnedRepositoryBase`
3. 在路由中使用 `check_ownership` 进行显式检查

### Q5: 匿名用户和注册用户的权限有什么区别？

**A**: 
- 匿名用户只能访问自己的数据（通过 `anonymous_user_id`）
- 注册用户可以访问自己的数据（通过 `user_id`）
- 管理员可以访问所有数据

### Q6: 如何添加新的角色？

**A**: 
1. 在 `backend/domains/identity/presentation/deps.py` 中添加角色常量
2. 在 `require_role` 中使用新角色
3. 在数据库 User 模型中设置角色

### Q7: 权限上下文什么时候被设置？

**A**: `PermissionContextMiddleware` 在请求开始时设置权限上下文，在请求结束时清除。上下文在整个请求生命周期内可用。

### Q8: 如果忘记继承 `OwnedMixin` 会怎样？

**A**: 类型检查会报错，因为 `OwnedRepositoryBase` 要求模型实现 `OwnedMixin`。这确保了类型安全。

## 相关文档

- [代码规范](CODE_STANDARDS.md)
- [架构设计](ARCHITECTURE.md)
- [身份认证域设计](../domains/identity/README.md)

## 目录结构

### Repository 分层

```
domains/agent/
├── domain/
│   └── interfaces/           # 接口（抽象）
│       ├── __init__.py
│       ├── session_repository.py    # SessionRepository 接口
│       ├── agent_repository.py      # AgentRepository 接口
│       └── message_repository.py    # MessageRepository 接口
└── infrastructure/
    └── repositories/         # 实现（具体）
        ├── __init__.py
        ├── session_repository.py    # SessionRepository 实现
        ├── agent_repository.py      # AgentRepository 实现
        └── message_repository.py    # MessageRepository 实现
```

### 命名约定

- **接口和实现同名**：通过文件路径区分
  - 接口：`domain/interfaces/session_repository.py` → `SessionRepository`
  - 实现：`infrastructure/repositories/session_repository.py` → `SessionRepository`
- **导入时使用别名**：避免命名冲突
  ```python
  from domains.agent.domain.interfaces.session_repository import (
      SessionRepository as SessionRepositoryInterface,
  )
  from domains.agent.infrastructure.repositories import SessionRepository
  ```

## 更新日志

- **2026-01-26**: 重构目录结构和命名约定
  - ✅ `domain/repositories/` → `domain/interfaces/`（更通用）
  - ✅ 去掉实现类的 `Postgres` 前缀（如 `PostgresSessionRepository` → `SessionRepository`）
  - ✅ 接口和实现同名，通过路径区分
  - ✅ 更新所有导入引用

- **2026-01-26**: 初始版本，实现完整的权限管理系统
  - ✅ 核心组件已实现（OwnedMixin、PermissionContext、OwnedRepositoryBase 等）
  - ✅ 模型层已迁移（Session、Agent 继承 OwnedMixin）
  - ✅ Presentation 层权限检查已修复
  - ✅ Repository 层已迁移（会话仓储和 Agent 仓储继承 OwnedRepositoryBase）
  - ✅ 权限上下文中间件已注册
  - ✅ `get_current_user` 依赖自动设置权限上下文
