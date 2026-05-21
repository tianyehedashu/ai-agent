# 数据库 Schema 设计与迁移 — 参考

> **Schema 设计**（归属、列、索引、评审清单）见 [design.md](design.md)。本文侧重 **Alembic / ops SQL / 回填**。

## 目录与命名

```
backend/alembic/versions/<YYYYMMDD>_<desc>.py   # Alembic Python（开发/CI）
backend/alembic/sql/<同上 stem>.up.sql          # 运维升级
backend/alembic/sql/<同上 stem>.down.sql        # 运维回滚
```

`stem` = 文件名去掉 `.py` / `.up.sql`，三者必须一致。

revision 元数据示例：

```python
revision: str = "20260531_ort"
down_revision: str | None = "20260530_dps_tenant"
```

## 表分类决策树

```
需要按团队/工作区隔离数据？
├─ 否 → system_* 表（无 tenant_id）
└─ 是 → 业务表 + tenant_id NOT NULL
         还需挂在 vkey/计划等策略对象上？
         └─ 是 → 另加 target_kind + target_id（PolicyTargetMixin）
```

### system_* 表示例

- `system_gateway_models`, `system_provider_credentials`, `system_mcp_servers`
- 无 `tenant_id`；`test_system_tables_have_no_tenant_id_column` 守门

### 多租户业务表示例

- `gateway_models`, `gateway_routes`, `sessions`, `agents`, `gateway_virtual_keys`
- `provider_credentials`：租户行 `tenant_id` + `scope NULL`；用户 BYOK 仍 `scope='user'`

### 特殊表

| 表 | 说明 |
|----|------|
| `users` | 无 `tenant_id`；身份根 |
| `gateway_request_logs` | 可有 `tenant_id` 可选；时间戳守门例外 |
| `gateway_teams` / `gateway_team_members` | 租户与成员关系权威 |

## ORM 模板

```python
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, TenantScopedMixin


class ExampleEntity(BaseModel, TenantScopedMixin):
    __tablename__ = "example_entities"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gateway_teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # ... 业务列
```

系统表：仅 `BaseModel`，勿加 `TenantScopedMixin`。

## 回填 SQL 模板

### 注册用户 → personal tenant

```sql
UPDATE {table} x
SET tenant_id = t.id
FROM gateway_teams t
WHERE x.user_id IS NOT NULL
  AND x.tenant_id IS NULL
  AND t.owner_user_id = x.user_id
  AND t.kind = 'personal'
  AND t.is_active = TRUE;
```

### 匿名会话 → shadow user 的 personal tenant

```sql
UPDATE {table} x
SET tenant_id = t.id
FROM users u
JOIN gateway_teams t ON t.owner_user_id = u.id
    AND t.kind = 'personal'
    AND t.is_active = TRUE
WHERE x.anonymous_user_id IS NOT NULL
  AND x.tenant_id IS NULL
  AND u.role = 'anonymous'
  AND u.settings->>'anonymous_cookie_id' = x.anonymous_user_id;
```

### sessions 无 tenant 时补团队（迁移 20260525 模式）

先 `INSERT` 缺失的 personal `gateway_teams` / `gateway_team_members`，再 `UPDATE sessions`，最后 `DELETE FROM sessions WHERE tenant_id IS NULL`。

## Alembic revision 骨架

```python
"""简短说明

Revision ID: 20260599_xxx
Revises: <prev_rev>
"""

from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "20260599_xxx"
down_revision: str | None = "<prev_rev>"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("my_table", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_my_table_tenant_id", "my_table", ["tenant_id"])
    op.execute("""UPDATE ...""")
    op.execute("ALTER TABLE my_table ALTER COLUMN tenant_id SET NOT NULL")


def downgrade() -> None:
    op.drop_index("ix_my_table_tenant_id", table_name="my_table")
    op.drop_column("my_table", "tenant_id")
```

列重命名优先 `op.alter_column(..., new_column_name=...)`；枚举/值映射用 `UPDATE ... SET target_kind = 'tenant' WHERE target_kind = 'team'`。

## ops SQL 文件头（与生成脚本一致）

```sql
-- =============================================================================
-- 生产运维手工执行 | Alembic 运行时不会加载本文件
-- 本地/开发请用: uv run alembic upgrade head  （走 alembic/versions/*.py）
-- versions/<stem>.py
-- revision: <rev>
-- down_revision: <down_rev or base>
-- 方向: UPGRADE (up.sql)
-- ...
-- =============================================================================
```

## 应用层与 API

- 仓储：`libs.db.base_repository.TenantScopedRepositoryBase`
- 团队 id 解析：`domains.tenancy.application.team_membership_queries`（勿新建 `libs.db.team_ids_resolver`）
- Gateway 列表响应：`domains.gateway.presentation.tenant_scoped_response.tenant_scoped_orm_dict`
- Virtual Key 写路径返回 ORM 时：`virtual_key_from_orm` 再 `vkey_to_response`

## 测试命令

```bash
cd backend
uv run alembic upgrade head
uv run pytest tests/architecture/test_orm_data_conventions.py -q
uv run pytest tests/unit/libs/db/ tests/unit/gateway/ -q --tb=line -x  # 按需缩小范围
uv run python scripts/verify_ops_sql_files.py
```

## 近期迁移链（租户命名收尾，便于对照）

| stem | 要点 |
|------|------|
| `20260521_tenant_data_scope` | 引入 `system_gateway_*` |
| `20260522_tenant_phase3` | Gateway 表 `team_id` → `tenant_id` |
| `20260523_sessions_agents_tenant_id` | Session/Agent 加 `tenant_id` |
| `20260524_drop_agents_user_id` | 删 `agents.user_id` |
| `20260525_drop_sessions_owner_columns` | Session 仅 `tenant_id` |
| `20260526_provider_credentials_tenant_id` | 凭据 `tenant_id` |
| `20260527_provider_credentials_scope_nullable` | 租户行 `scope` 可空 |
| `20260528_system_gateway_models_credential_fk` | 系统凭据 FK |
| `20260529_gateway_budgets_rename_to_target` | `target_kind` / `target_id` |
| `20260530_downstream_pricing_scope_tenant` | 定价 scope 值 |
| `20260531_owned_resources_tenant_id` | Owned 表 + `system_mcp_servers` |

完整链：`uv run alembic history -v`（在 `backend/` 下）。

## 生产权限与账号（推荐）

### 角色分工

```
开发者 ──提交──► versions/*.py + sql/*.up.sql（PR 评审）
运维/DBA ──执行──► sql/*.up.sql + UPDATE alembic_version（迁移账号）
应用进程 ──仅──► DML on 业务表（应用账号，无 DDL）
```

### PostgreSQL 账号示例（由 DBA 在 RDS 落地）

| 角色 | 典型权限 | 用途 |
|------|----------|------|
| `ai_agent_app` | 业务表 DML；`alembic_version` 可选只读 | `DATABASE_URL`、运行时 |
| `ai_agent_migrate` | DDL + 全表 DML + `alembic_version` 读写 | 运维 `psql` / 发版迁移 Job |
| `ai_agent_readonly` | `SELECT` | 排障、核对 `version_num`、数据抽检 |

勿将 RDS 主账号（如 `pgroot`）写入应用 `.env` 或提交仓库。

### 运维执行清单（方式 A）

1. 备份 / 确认 `alembic_version` = 本批首个脚本的 `down_revision`。
2. 用 **迁移账号** 在堡垒机执行 `psql -f .../<stem>.up.sql`（按链顺序）。
3. `UPDATE alembic_version SET version_num = '<revision>';`（每步一条 revision）。
4. 用 **只读账号** 或运维脚本 spot-check（列是否存在、关键 `tenant_id` 无 NULL）。
5. 恢复应用写流量；应用仍用 **应用账号** 启动。

### 与 Alembic 自动升级（方式 B）的权限要求

`deploy.sh` / `docker compose run backend alembic upgrade head` 在运行时对 DB 用户要求 **DDL 权限**，等同于迁移账号。若生产坚持最小权限，应禁用方式 B，仅保留方式 A。

### 开发侧禁止项

- 本地 `alembic upgrade` 指向生产 `DATABASE_URL`（超权泄露风险）。
- 在应用迁移 Python 里写死生产连接串。
- 让 CI 用生产 DDL 账号跑迁移（除非专用 release pipeline + 密钥托管）。
