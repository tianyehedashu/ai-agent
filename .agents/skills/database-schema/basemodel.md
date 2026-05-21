# BaseModel 与相关字段（`libs.orm.base`）

源码：`backend/libs/orm/base.py`。多数情况下**直接继承 Mixin 即得列**，仅在需要差异化时由子类显式覆盖。

## 继承层次

```
libs.db.database.Base          # SQLAlchemy DeclarativeBase（元数据根）
    └── TimestampMixin         # created_at, updated_at（自动建列）
            └── BaseModel      # + id (UUID PK)（自动建列）
```

| 类 / Mixin | 是否抽象 | 实际写入表的列 |
|------------|----------|----------------|
| `BaseModel` | 是 | `id`, `created_at`, `updated_at` |
| `TenantScopedMixin` | 是 | **`tenant_id`**：UUID NOT NULL，index=True，**无 DB FK**（`@declared_attr`） |
| `PolicyTargetMixin` | 是（标记） | **无** — 子类显式声明 `target_kind`, `target_id`（细节差异多） |
| `AuditableMixin` | 是（标记） | **无** — 子类按需声明 `created_by`, `updated_by` |

> `TenantScopedMixin` 采用 SQLAlchemy `declared_attr`：每个子类得到独立的 `Column` 实例，子类可定义同名 `mapped_column` 覆盖默认 nullable / index 或叠加 FK。这是 SQLAlchemy 官方推荐的"可配置 Mixin"模式。
>
> **本项目全库零 DB 外键**（含 `tenant_id` 与所有 `*_id` 引用列）。ORM 禁止使用 `ForeignKey(...)`；守门 `test_orm_metadata_has_no_db_foreign_keys`。完整性由 Service/Repository + `DataScopeEnforcer` 保证。

## 字段说明

### `BaseModel` 自带

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | `UUID` PK | `default=generate_uuid` |
| `created_at` | `TIMESTAMPTZ` | Python `default` + DB `server_default=now()` |
| `updated_at` | `TIMESTAMPTZ` | 同上；Python `onupdate` 刷新 |

架构守门：除 `users`、`system_*`、`gateway_request_logs`（仅要求 `created_at`）外，业务表须有 `created_at` + `updated_at`（`test_business_tables_have_timestamps`）。

### `tenant_id`（租户业务表）

| 属性 | 默认（继承 Mixin 即得） |
|------|--------------------------|
| 语义 | 行归属 `gateway_teams.id`（personal / shared 工作区） |
| 类型 | `UUID(as_uuid=True)` |
| 空值 | `nullable=False` |
| 索引 | `index=True` |
| FK | **无**（应用层保证完整性） |
| 仓储 | `TenantScopedRepositoryBase` + `DataScopeEnforcer` 按 `PermissionContext.team_ids` 过滤 |

**何时需要在子类覆盖 `tenant_id`？**

- 迁移过渡期允许 `nullable=True`（应当短命，尽快回填后恢复 NOT NULL）

> **禁止**为新表引入 `tenant_id → gateway_teams.id` DB FK。

**相关但不同语义的列：**

| 列 | 用途 | 与 tenant_id 关系 |
|----|------|-------------------|
| `created_by_user_id` | 谁创建了该行（如 vkey） | 不表示归属；可见性策略用 |
| `user_id`（`api_keys`） | Key 所有者 | 与 `tenant_id` 并存；**不是**工作区归属列 |
| `scope` / `scope_id` | 仅 `provider_credentials` BYOK | 与 `tenant_id` 互斥；**新表勿仿** |

### `target_kind` / `target_id`（策略挂载）

| 属性 | 约定 |
|------|------|
| 语义 | 预算、权益计划等挂在 system/tenant/vkey/user 等对象上，**与 tenant 正交** |
| 示例表 | `gateway_budgets`, `entitlement_plans` |
| Mixin | `PolicyTargetMixin`（推荐）或仅 `BaseModel` + 自行声明列 |
| `target_kind` 字面量 | 仅出现在 **domain**（如 `vkey`, `apikey_grant`, `tenant`）；禁止写在 `libs/` |

`GatewayBudget`：`BaseModel` + 自声明 `target_kind`/`target_id`（未继承 `PolicyTargetMixin`，字段等价）。

### `AuditableMixin`（可选）

| 列 | 说明 |
|----|------|
| `created_by` | 操作人 UUID，**不参与**行级 tenant 过滤 |
| `updated_by` | 同上 |

项目内使用较少；需要管理面审计时再引入。

## 推荐继承组合

| 场景 | 类声明 | 必写列（除 BaseModel 外） |
|------|--------|---------------------------|
| 标准租户业务（唯一推荐） | `class X(BaseModel, TenantScopedMixin)` | **零** — `tenant_id` 自动具备（无 FK） |
| 平台配置 | `class X(BaseModel)` | 无 `tenant_id`；表名 `system_*` |
| 策略/预算 | `class X(BaseModel, PolicyTargetMixin)` | `target_kind`, `target_id` |
| 租户 + 策略 | `BaseModel, TenantScopedMixin, PolicyTargetMixin` | `target_*`（少见） |
| 仅追加型日志子表 | `class X(BaseModel)` | 无 tenant；如 `gateway_alert_events` |
| 分区/特殊主键 | `class X(Base)` | 不用 `BaseModel`；见 `gateway_request_logs` |

## 项目内实例对照

| 模型 | 继承 | `tenant_id` 来源 |
|------|------|------------------|
| 全部 13 张租户业务表（`sessions`/`agents`/`gateway_models`/`gateway_virtual_keys`/`api_keys` 等） | `BaseModel`, `TenantScopedMixin` | **Mixin 默认**（无 DB FK） |
| `GatewayVirtualKey` | 同上 | Mixin + `created_by_user_id`（创建者，与归属正交） |
| `ApiKey` | 同上 | Mixin + `user_id`（所有者，与归属正交） |
| `ProviderCredential` | `BaseModel` | `tenant_id` 可空 **或** `scope`+`scope_id`（BYOK） |
| `SystemGatewayModel` 等 `system_*` | `BaseModel` | 无 tenant |
| `GatewayBudget` | `BaseModel` | `target_kind`, `target_id` |
| `EntitlementPlan` | `BaseModel`, `PolicyTargetMixin` | `target_kind`, `target_id` |
| `User` | `SQLAlchemyBaseUserTableUUID`, `TimestampMixin`, `Base` | 无 `tenant_id`；**不是** `BaseModel` |

## 新表模板

**标准租户业务（推荐，无 DB FK）：**

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, TenantScopedMixin


class MyEntity(BaseModel, TenantScopedMixin):
    """tenant_id 由 TenantScopedMixin 默认提供（无 DB FK）。"""

    __tablename__ = "my_entities"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
```

**系统表：** 去掉 `TenantScopedMixin`，表名 `system_my_entities`。

策略表：

```python
from libs.orm.base import BaseModel, PolicyTargetMixin

class MyPolicy(BaseModel, PolicyTargetMixin):
    __tablename__ = "my_policies"

    target_kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
```

## 工具方法

```python
record.to_dict()  # BaseModel：所有列 → dict（不含 relationship）
```

列表 API 勿在 async 会话中对 ORM 随意 `getattr` 未加载列；Gateway 用 `tenant_scoped_orm_dict`（`domains/gateway/presentation/tenant_scoped_response.py`）。

## 与迁移 DDL 对齐

| ORM | Alembic / SQL |
|-----|----------------|
| `BaseModel.id` | `UUID PRIMARY KEY` |
| `TimestampMixin` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `tenant_id` | `UUID NOT NULL REFERENCES gateway_teams(id)` + `CREATE INDEX` |
| `target_*` | `VARCHAR(20)` + `UUID` + 业务唯一索引 |

`alembic/script.py.mako` 头部注释已嵌入新表约定，revision 应与 ORM 列名一致。

## 常见误用

| 误用 | 后果 |
|------|------|
| 在子类重复写一个**与默认完全一致**的 `tenant_id` | 不出错但冗余；删掉让 Mixin 接管 |
| `system_*` 表加 `tenant_id` | `test_system_tables_have_no_tenant_id_column` 失败 |
| 租户表 `tenant_id` 可空长期存在 | 授权链漏洞 |
| 用 `OwnedMixin` / `OwnedRepositoryBase` | 已移除；用 `TenantScoped*` |
| 直接用 `Mapped[uuid.UUID]` 注解（无 `mapped_column`）想"覆盖"Mixin | 不会覆盖 `declared_attr`；要用 `mapped_column` 同名声明 |
