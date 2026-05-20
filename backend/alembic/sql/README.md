# 运维 SQL（与 `versions/` 一一对应）

## `up.sql` / `down.sql` 是什么？

| 文件 | 含义 | 何时用 |
|------|------|--------|
| **`<name>.up.sql`** | **升级**：把库从「上一版 revision」迁到「本 revision」 | 生产发版、向前升级 |
| **`<name>.down.sql`** | **回滚**：从「本 revision」退回「上一版 revision」 | 生产事故回滚（若支持） |

命名与 `alembic/versions/<name>.py` **同名**（不含 `.py`）。  
例如 `20260520_add_system_storage_config.up.sql` 对应 `versions/20260520_add_system_storage_config.py`。

## 两套环境，不要混用

| 环境 | 做法 |
|------|------|
| **本地 / 开发 / CI** | `uv run alembic upgrade head` → 只执行 `versions/*.py` 里的 Python |
| **生产（运维手工）** | 按迁移链顺序用 `psql` 执行本目录的 `.up.sql`；**Alembic 不会自动读这些文件** |

## 命名规则

```
alembic/versions/<name>.py     ← 本地 Alembic 用
alembic/sql/<name>.up.sql      ← 运维升级用
alembic/sql/<name>.down.sql    ← 运维回滚用
```

## 生产执行注意

1. 确认当前 `alembic_version.version_num` 与脚本假设的 `down_revision` 一致。  
2. 按迁移链顺序执行各 revision 的 `.up.sql`（不是随便挑文件）。  
3. 每步成功后**手工**更新 `alembic_version`（与 Alembic 链一致）。  
4. 含「不可回滚」注释的 `.down.sql` 仅作记录，不要在生产执行。

## 重新生成 SQL（开发侧）

从当前 `versions/*.py` 导出运维脚本（覆盖 `sql/`）：

```bash
cd backend
uv run python scripts/generate_alembic_sql_files.py --force
```

导出仅供初稿；条件分支类迁移请人工核对后再发给运维。

## 新表 DDL 约定（20260521 起）

- 多租户业务表：`tenant_id UUID NOT NULL`（勿再新增物理列名 `user_id` / `team_id` / `scope` / `scope_id`）。
- 平台级配置：写入 `system_*` 表（无 `tenant_id`）。
- 策略挂载：另加 `target_kind` / `target_id`（与 tenant 正交）。
