# 测试数据库说明

本文档说明后端**测试专用数据库**的用途、表结构来源，以及为何会出现「列不存在」等表结构不一致问题及应对方式。新增迁移或模型字段时请按文末流程操作，可避免反复踩坑。

## 1. 测试数据库是专门的吗？

**是。** 测试使用**独立于开发/生产**的数据库：

- **URL 规则**：由 `bootstrap.config.settings.database_url` 派生，将库名改为 `test_` 前缀。
  - 例如：开发库 `ai_agent` → 测试库 `test_ai_agent`。
- **位置**：`tests/conftest.py` 中的 `TEST_DATABASE_URL`。
- **创建**：若不存在，conftest 会尝试用 `CREATE DATABASE` 创建测试库（需有连 `postgres` 库的权限）；若无权限则需手动建库。

测试数据与开发/生产完全隔离，不会互相影响。

## 2. 表结构从哪里来？

测试库里的表结构**不是**每次跑测试时从零建一次，而是：

1. **首次需要 `db_session` 时**（进程内第一次跑用到数据库的测试）：
   - 先尝试对测试库执行 **Alembic 迁移**（`alembic upgrade head`，子进程、`DATABASE_URL=TEST_DATABASE_URL`）。
   - 再执行 **`Base.metadata.create_all`**：只创建「当前模型里有、但库里还没有」的表，**不会修改已存在的表**。
   - 若有约定好的「补列」逻辑（见下），会再对指定表补缺失列。

2. **之后同进程内的测试**：不再重复跑迁移或 create_all（`_tables_created` 已为 True），直接复用已有表结构。

因此：**表结构 = 迁移 + create_all 的叠加；已存在的表不会被 create_all 更新。**

## 3. 为什么会出现「column xxx does not exist」？

典型情况：

- 你在**模型**里新增了字段（例如 `MCPServer.template_id`），并写了 **Alembic 迁移**。
- 开发/生产库：跑过 `alembic upgrade head`，表已包含新列。
- **测试库**：之前某次跑测试时，表是由**当时的** `create_all` 创建的（那时模型还没有新列），所以表里**没有**新列。
- `create_all` 只会「缺表就建」，**不会给已有表加列**。
- 子进程里的 `alembic upgrade head` 若未正确指向测试库或失败，测试库也不会被更新。
- 结果：测试里用到的 ORM 查询会带出新列，数据库报错「column xxx does not exist」。

也就是说：**表结构不一致 = 测试库曾用旧模型 create_all 建表，之后模型/迁移更新了，但测试库没被迁移或补列更新。**

## 4. 当前 conftest 的应对方式

在 `tests/conftest.py` 里目前有两层保障：

1. **对测试库跑迁移**  
   `_run_test_db_migrations()`：子进程执行 `alembic upgrade head`，环境变量 `DATABASE_URL=TEST_DATABASE_URL`，保证迁移在测试库上执行。若失败只打 warning，不阻断测试。

2. **补列兜底**  
   在 `create_all` 之后调用 `_ensure_mcp_servers_template_columns(conn)` 等，对「已知曾用 create_all 建过、又在新迁移里加了列」的表，用 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 补上缺失列，避免旧测试库缺列。

新增了「只加列」的迁移时，若希望测试库自动跟上，有两种做法（见下节）。

## 5. 新增迁移或模型字段时的推荐流程

为避免再次出现「测试库缺列」：

1. **先写 Alembic 迁移**  
   改完模型后立刻写迁移（`alembic revision`），并实现 `upgrade()` / `downgrade()`。

2. **本地开发库**  
   对开发库执行：`uv run alembic upgrade head`（或你平时的迁移命令）。

3. **测试库**  
   - **方式 A（推荐）**：跑一次全量集成测试前，对测试库执行一次迁移（与 conftest 使用同一测试库）：
     ```bash
     make db-upgrade-test
     ```
     或在 backend 目录下：`uv run python scripts/migrate_test_db.py`。  
     这样测试库与开发库结构一致，conftest 里的子进程迁移也会更容易成功。
   - **方式 B**：若某张表是「历史用 create_all 建的、本次只是加列」，且你希望测试不依赖迁移子进程，可在 conftest 里为该表增加一次性的「补列」逻辑（参考 `_ensure_mcp_servers_template_columns`），用 `ADD COLUMN IF NOT EXISTS` 补上新列。适合临时兜底，长期仍建议以迁移为主。

4. **CI**  
   若 CI 里测试库是每次新建或从空白库恢复的，确保 CI 在跑测试前对测试库执行 `alembic upgrade head`（使用测试库的 `DATABASE_URL`），这样表结构始终来自迁移，与模型一致。

## 6. 小结

| 问题 | 原因 | 应对 |
|------|------|------|
| 测试库是专门的吗？ | 是，独立库（如 `test_ai_agent`） | 无需改开发/生产库 |
| 表结构从哪来？ | 迁移 + create_all，且 create_all 不改已有表 | 依赖迁移更新表结构 |
| 为何报「column xxx does not exist」？ | 测试库曾用旧模型 create_all 建表，未跑新迁移或补列 | 对测试库跑迁移，或在 conftest 中为该表补列 |
| 新增字段后如何避免？ | 先写迁移，再对测试库执行迁移或补列 | 见第 5 节流程 |

文档位置：`backend/tests/TEST_DATABASE.md`。  
相关实现：`backend/tests/conftest.py`（`_run_test_db_migrations`、`_ensure_mcp_servers_template_columns`、`db_session` 中表初始化逻辑）。
