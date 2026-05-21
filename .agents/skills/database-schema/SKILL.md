---
name: database-schema
description: >-
  Designs PostgreSQL schema (table ownership, columns, indexes) and implements
  Alembic migrations for ai-agent. Use when designing new tables, reviewing
  data models, choosing tenant_id vs system_* vs target_kind, writing ORM
  models, or creating alembic/versions and alembic/sql revisions.
---

# 数据库 Schema 设计与迁移（ai-agent）

**先设计，后迁移。** 未通过设计评审前，不要写 `alembic revision`。

## 何时使用

| 阶段 | 场景 |
|------|------|
| **设计** | 新功能要落库、扩表、拆 `system_*`、定 tenant/索引/唯一约束 |
| **实现** | ORM、`alembic/versions`、`alembic/sql`、回填、`upgrade head` |
| **评审** | 对照守门测试、权限链、API 是否需 `tenant_id`/`team_id` 镜像 |

## 一、Schema 设计（迁移之前）

### 1.1 核心归属模型

```
User ──► gateway_team_members ──► gateway_teams.id (= tenant_id) ──► 业务行
```

| 表类型 | 判断 | 物理特征 |
|--------|------|----------|
| **租户业务表** | 按团队/工作区隔离 | `tenant_id UUID NOT NULL` → `gateway_teams` |
| **平台配置** | 全站一份 | 表名 `system_*`，**无** `tenant_id` |
| **策略挂载** | 挂在 vkey/计划等，与 tenant 正交 | `target_kind` + `target_id` |
| **身份根** | 用户账号 | `users`（无 tenant_id） |

**禁止**在新表用 `user_id` / `team_id` / `scope` / `scope_id` 表达「记录属于哪个工作区」。  
例外：`created_by_user_id`（创建者）、`api_keys.user_id`（所有者，与 `tenant_id` 并存且语义不同）。

详细决策树、列类型、索引/FK、反模式 → **[design.md](design.md)**。

### 1.2 设计工作流（勾选）

```
Schema 设计：
- [ ] 1. 回答 design.md §1 前置问题（隔离维度、生命周期、读路径）
- [ ] 2. 确定表归属：tenant / system_* / target_kind / 遗留 scope
- [ ] 3. 列清单：标准列 + 业务列 + 敏感字段存储方式
- [ ] 4. 索引与唯一约束（租户内 uq、部分索引、列表复合索引）
- [ ] 5. FK 与 ondelete（CASCADE vs RESTRICT）（不得使用外键）
- [ ] 6. ORM 落点：domains/<bc>/infrastructure/models/
- [ ] 7. 授权：TenantScopedRepositoryBase + PermissionContext.team_ids
- [ ] 8. API：是否 tenant_scoped_orm_dict / 读模型双字段
- [ ] 9. 设计评审清单（design.md §10）通过后再进入迁移
```

### 1.3 BaseModel 与相关字段

`libs.orm.base` 组合：

| 组件 | 自动建列 | 说明 |
|------|----------|------|
| `BaseModel` | `id`, `created_at`, `updated_at` | 几乎所有业务实体 |
| `TenantScopedMixin` | **`tenant_id`**（UUID NOT NULL，index，**无 DB FK**） | 继承即得列；子类一般无需重写 |
| `PolicyTargetMixin` | 仅类型协议 | 子类显式声明 `target_kind` / `target_id`（nullable/index 差异较大） |
| `AuditableMixin` | 仅类型协议 | 子类按需声明 `created_by` / `updated_by` |

**项目约定：** 全库 **零 DB `FOREIGN KEY`**（ORM 禁止 `ForeignKey(...)`，迁移 `20260602_dafk`）；租户表继承 `TenantScopedMixin`；引用完整性由 Service/Repository + `test_orm_metadata_has_no_db_foreign_keys` 保证。

**易混「相关字段」：** `created_by_user_id`（创建者）、`api_keys.user_id`（所有者）≠ 工作区归属；归属只看 `tenant_id`。

| 表类型 | 类声明 |
|--------|--------|
| 租户业务 | `class X(BaseModel, TenantScopedMixin)` — `tenant_id` 自动具备（无 FK） |
| 系统配置 | `class X(BaseModel)`，表名 `system_*` |
| 策略 | `class X(BaseModel, PolicyTargetMixin)` + `target_*` |

字段详解、实例对照、模板、误用 → **[basemodel.md](basemodel.md)**。

权威：`backend/docs/CODE_STANDARDS.md`、`backend/docs/PERMISSION_SYSTEM_ARCHITECTURE.md`。

---

## 二、迁移实施（设计定稿之后）

### 2.1 迁移工作流（勾选）

```
迁移实施：
- [ ] 1. uv run alembic revision -m "描述"（cd backend）
- [ ] 2. upgrade/downgrade 与 ORM 一致；数据迁移先 NULL → 回填 → NOT NULL
- [ ] 3. alembic/env.py 已 import 新 model
- [ ] 4. uv run alembic upgrade head
- [ ] 5. uv run python scripts/generate_alembic_sql_files.py
- [ ] 6. uv run python scripts/verify_ops_sql_files.py（至少本 stem）
- [ ] 7. pytest tests/architecture/test_orm_data_conventions.py + 域测试
```

### 2.2 revision 与数据迁移要点

- 文件：`alembic/versions/YYYYMMDD_<desc>.py`；`revision` 短 id，单链 `down_revision`
- 加 `tenant_id` 顺序：ADD NULL → INDEX → UPDATE 回填 → DELETE 孤儿 → SET NOT NULL → DROP 旧列
- 拆 `system_*`：CREATE → INSERT SELECT → 改 FK → DELETE 旧系统行
- 避免迁移内 `bind.execute().fetchall()`（离线 `--sql` / verify 会失败）

### 2.3 环境与 ops SQL（含生产权限）

| 环境 | 谁执行 | 数据库账号 | 做法 |
|------|--------|------------|------|
| 开发 / CI | 开发者 / CI | 本地超权或 `postgres` | `uv run alembic upgrade head` |
| 生产 | **运维 / DBA**（非日常开发） | **迁移专用账号**（DDL） | 顺序执行 `alembic/sql/<stem>.up.sql`，手工维护 `alembic_version` |
| 生产运行时 | 应用进程 | **应用账号**（仅 DML） | **禁止** DDL、`alembic upgrade`、改 `alembic_version` |

**权限原则（生产必守）：**

1. **账号分离**：`DATABASE_URL`（应用）≠ 迁移账号。应用账号只需业务表 `SELECT/INSERT/UPDATE/DELETE`；`CREATE/ALTER/DROP`、`alembic_version` 写入仅迁移账号。
2. **开发机不连生产 DDL**：开发者只提交 `versions/` + `sql/`；不在本机 `.env` 用 `pgroot`/超权连生产跑 `alembic upgrade`（核对版本可用只读账号或运维代查）。
3. **网络**：RDS 优先内网地址；公网端点仅运维堡垒机/应急，不写入应用 `DATABASE_URL`。
4. **与 `deploy.sh` 的关系**：若发版脚本里 `alembic upgrade head`，须使用**发版时注入的迁移凭据**，且与 7×24 应用 `DATABASE_URL` 分离；否则坚持 **方式 A（运维手工 SQL）**，避免容器内应用账号越权改表。
5. **发版窗口**：DDL 前短暂停写或只读；含 `DELETE` 回填/清孤儿的脚本需 DBA 评审 + 备份。

```bash
cd backend
uv run python scripts/generate_alembic_sql_files.py
uv run python scripts/verify_ops_sql_files.py
```

单条导出兜底：`ALEMBIC_SQL_GEN_MOCK=1` + `alembic upgrade <down>:<rev> --sql` → 见 [reference.md](reference.md) §生产权限。

---

## 三、速查表

| 类型 | 物理列 | ORM |
|------|--------|-----|
| 多租户业务表 | `id`, `created_at`, `updated_at`, **`tenant_id`** | `TenantScopedMixin` |
| 平台级 | 无 `tenant_id`，`system_*` | 仅 `BaseModel` |
| 策略挂载 | **`target_kind` / `target_id`** | `PolicyTargetMixin` |

---

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| 未设计直接写 migration | 先完成 design.md 评审清单 |
| 新业务表用 `team_id` 列 | `tenant_id`；API 可镜像 `team_id` |
| ORM 与 DDL 分 PR | 同 PR 同步 |
| 无 ops SQL | 生成 `sql/*.up.sql` / `*.down.sql` |
| 列表 API 直接 `model_validate(orm)` | Gateway 用 `tenant_scoped_orm_dict` |

## 延伸阅读

- **BaseModel / Mixin / 相关字段**：[basemodel.md](basemodel.md)
- **设计详解**：[design.md](design.md)
- **迁移模板、回填 SQL、迁移链**：[reference.md](reference.md)
