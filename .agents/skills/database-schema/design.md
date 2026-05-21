# Schema 设计参考（ai-agent）

设计阶段产出物：**表归属结论 + 列清单 + 索引/约束 + 与现有表关系**。通过评审后再写 Alembic。

## 1. 设计前置问题（必答）

| 问题 | 选项 | 影响 |
|------|------|------|
| 数据按谁隔离？ | 租户 / 全平台 / 用户级 BYOK | `tenant_id` vs `system_*` vs `scope='user'` |
| 生命周期？ | 随 tenant 删 / 随 session 删 / 独立保留 | `ondelete`、是否软删 |
| 读路径？ | 列表按 tenant、按 id 点查、日志式追加 | 索引设计 |
| 是否覆盖系统默认？ | 是（同名覆盖）/ 否 | 是否进 `gateway_models` 租户表 vs 仅 `system_*` |
| 敏感字段？ | API Key、凭据密文 | 加密列、禁止日志明文 |

授权链（业务行归属）：`User → gateway_team_members → gateway_teams.id (= tenant_id)`。  
**不要**在新业务表用 `user_id` 表达「这条记录属于哪个工作区」——用 `tenant_id`。

## 2. 表归属决策树

```
新实体需要持久化？
├─ 全平台一份配置、所有租户共享同一套定义
│   └─ 表名 system_<domain>_<entity>，无 tenant_id
│       例：system_gateway_models, system_provider_credentials, system_mcp_servers
├─ 每个团队/工作区各一份（含 personal team）
│   └─ 业务表 + tenant_id NOT NULL → gateway_teams.id
│       例：sessions, agents, gateway_models（租户行）, gateway_virtual_keys
├─ 用户个人 BYOK、不随团队共享
│   └─ provider_credentials：scope='user' + scope_id=user_id（遗留维度，非 tenant 归属）
└─ 策略挂在某对象上（与 tenant 正交）
    └─ target_kind + target_id
        例：gateway_budgets, entitlement_plans
```

### 合并 vs 拆表

| 倾向拆表 | 倾向单表 |
|----------|----------|
| 系统行与租户行字段/约束不同 | 字段高度一致，仅 `tenant_id` 有无 |
| 系统配置需平台管理员独立演进 | 查询总是 `UNION` 系统+租户且结构相同 |
| 无外键混用（系统凭据 vs 租户凭据） | 数据量小、迁移成本高 |

本项目 Gateway 模型/路由/告警已采用 **system_* + 租户表** 双表，应用层 `list_system()` + `list_for_tenant()` 合并。

## 3. 标准列清单

> `BaseModel` / `TenantScopedMixin` / `PolicyTargetMixin` 字段分工与继承模板见 **[basemodel.md](basemodel.md)**。

### 多租户业务表（默认）

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | `UUID` | PK, default uuid4 | `BaseModel` 已含 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, server now | `TimestampMixin` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, onupdate | `TimestampMixin` |
| `tenant_id` | `UUID` | NOT NULL, INDEX，**无 DB FK** | 继承 `TenantScopedMixin` **自动建列**（`@declared_attr`）；无需子类重写 |

### 平台表 `system_*`

同上，但 **无** `tenant_id`。FK 指向其他 `system_*` 或全局字典表。

### 可选列

| 列 | 场景 |
|----|------|
| `created_by_user_id` | 虚拟 Key、需知创建者（非 tenant 归属） |
| `created_by` / `updated_by` | 管理面审计（`AuditableMixin`） |
| `is_active` / `enabled` | 软禁用，保留历史 |
| `deleted_at` | 仅当产品明确要求软删；否则用 `is_active` |

### 禁止作为「归属维度」的新列名

`user_id`、`team_id`、`scope`、`scope_id`（后两者仅 `provider_credentials` 等遗留表在迁移期存在；新表勿仿）。

`api_keys` 等可同时有 `tenant_id`（数据作用域）与 `user_id`（创建者/所有者 UUID），二者语义不同，勿混淆。

## 4. 命名

| 对象 | 规则 | 示例 |
|------|------|------|
| 表名 | 复数 snake_case；域前缀可选 | `gateway_models`, `product_info_jobs` |
| 系统表 | 前缀 `system_` | `system_gateway_models` |
| 索引 | `ix_<table>_<column(s)>` | `ix_sessions_tenant_id` |
| 唯一约束 | `uq_<table>_<语义>` | `uq_gateway_models_tenant_name` |
| FK 约束 | `fk_<table>_<column>` 或 Alembic 生成名 | — |
| ORM 类 | PascalCase 单数 | `GatewayModel` → `gateway_models` |
| 文件路径 | `domains/<bc>/infrastructure/models/<entity>.py` | 与限界上下文一致 |

## 5. 类型与 PostgreSQL 习惯

| 用途 | 推荐类型 |
|------|----------|
| 主键 / 引用 ID 列 | `UUID` (`as_uuid=True`)（逻辑关联；**不**等于必须有 DB `FOREIGN KEY` 约束） |
| 时间 | `DateTime(timezone=True)` → `TIMESTAMPTZ` |
| 短枚举/状态 | `String(20~50)` + 应用层校验（非 PG ENUM，便于迁移） |
| 结构化配置 | `JSONB`，`server_default='{}'` |
| 字符串列表 | `ARRAY(String)`，`server_default='{}'` |
| 金额 | `Numeric` / `Decimal`（应用层），勿 `float` |
| 长文本 | `Text`；短标签 `String(n)` |
| 密文 | `String(512+)` + comment 标明 Fernet/哈希 |

布尔列：`Boolean`, `server_default='true'/'false'`, `nullable=False`。

## 6. 索引与唯一性

**必索引：**

- 所有 `tenant_id`（过滤几乎总是 `WHERE tenant_id = ?`）
- 跨表引用列（`credential_id`, `session_id`, `agent_id` 等）——**无论是否在 DB 建 FK 约束都应索引**
- 高频过滤：`is_active`, `enabled`, `capability`

**组合唯一（租户内）：**

```python
UniqueConstraint("tenant_id", "name", name="uq_gateway_models_tenant_name")
```

**部分唯一（PostgreSQL）：**

```python
Index(
    "uq_provider_credentials_tenant_provider_name",
    "tenant_id", "provider", "name",
    unique=True,
    postgresql_where=sa.text("tenant_id IS NOT NULL"),
)
```

列表查询避免仅对低基数列单独索引；按实际 `EXPLAIN` 再加复合索引 `(tenant_id, created_at DESC)` 等。

## 7. DB 外键（`FOREIGN KEY`）策略 — **全库禁止**

**硬规则：** `public` schema **不得**存在 PostgreSQL `FOREIGN KEY` 约束；ORM `mapped_column` **不得**使用 `ForeignKey(...)`。迁移 `20260602_drop_all_db_foreign_keys` 已删除历史全部 FK。

**逻辑引用仍允许：** 列名 `credential_id`、`session_id`、`user_id` 等照常使用 `UUID` 存关联主键，在列 `comment` 标明 `refs <table>.id (no DB FK)`，并**必须索引**（见 §6）。

**引用完整性由应用层负责：**

| 场景 | 应用层处理 |
|------|------------|
| `tenant_id` 工作区归属 | `TenantScopedMixin` + `DataScopeEnforcer` + `TenantScopedRepositoryBase` |
| 删凭据前仍有 `gateway_models` 引用 | Service/Repository 显式校验（原 DB RESTRICT 语义） |
| 删 session / agent | UseCase 内 SET NULL 或级联删子表（原 `ondelete` 语义） |
| 删 user / team | Tenancy/Identity 服务编排顺序删除或软删 |

**守门：** `test_orm_metadata_has_no_db_foreign_keys` 扫描 `Base.metadata` 全部表。

**理由（业界常见）：** 降低锁竞争、便于分片与蓝绿迁移、避免 ORM/迁移与 FK 顺序耦合；代价是删除/迁移路径须在代码里写清。

## 8. 域边界与 ORM 放置

| 域 | 典型表 |
|----|--------|
| `identity` | `users`, `api_keys` |
| `tenancy` | `gateway_teams`, `gateway_team_members` |
| `session` | `sessions`, `messages` |
| `agent` | `agents`, `memories`, `mcp_servers`, `video_gen_tasks`, … |
| `gateway` | `gateway_*`, `provider_credentials`, `system_*`, `downstream_model_pricing` |

新表 ORM **必须**落在所属 `domains/<bc>/infrastructure/models/`，并在 `alembic/env.py` import，否则元数据与守门测试漏表。

## 9. 从设计到实现的映射

```
设计评审通过
    → ORM Model（BaseModel + TenantScopedMixin 自动建 tenant_id，见 basemodel.md）
    → Repository（TenantScopedRepositoryBase 或专用）
    → Alembic revision（DDL 与 ORM 一致）
    → sql/*.up.sql / *.down.sql
    → test_orm_data_conventions + 域单测
```

ORM 与迁移 **同一 PR**；禁止「先迁库、后补 ORM」跨版本部署（除非运维脚本与代码同步发布）。

## 10. 设计评审清单

```
Schema 设计评审：
- [ ] 表归属（tenant / system_* / target / user-scope）已写明
- [ ] 未引入 user_id/team_id 作为工作区归属
- [ ] 含 created_at/updated_at（守门表除外）
- [ ] 租户表通过继承 TenantScopedMixin 获得 tenant_id（无需在子类重写）；system 表无 tenant_id
- [ ] ORM 与 DB 均无 `FOREIGN KEY`；删除/级联语义在 Service/Repository 文档化
- [ ] 唯一约束在正确维度（租户内 vs 全局）
- [ ] 敏感字段存储方式（hash/encrypt）已对齐 identity/gateway 先例
- [ ] 查询路径有对应索引
- [ ] 与 PermissionContext / DataScopeEnforcer 过滤一致
- [ ] API 若暴露：tenant_id + 可选 team_id 镜像策略已约定
```

## 11. 反模式

| 反模式 | 原因 |
|--------|------|
| 在 `libs/` 放带业务语义的表 | 违反 DDD；放 `domains/` |
| `tenant_id` 可 NULL 的业务表 | 授权链无法过滤；仅迁移过渡期允许 |
| 系统配置写进租户表且 `tenant_id NULL` | 用 `system_*` |
| 双写 `team_id` + `tenant_id` | 已完成迁移；API 层镜像即可 |
| JSONB 存大 blob / 全文 | 用对象存储 + URL 列 |
| PG ENUM 类型 | 改值需 DDL；用 String + 域常量 |
