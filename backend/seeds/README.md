# 数据种子（与 Alembic 迁移并列）

| 目录 | 职责 |
|------|------|
| `../alembic/versions/` | **Schema**：表结构变更（`upgrade head`） |
| `../alembic/sql/` | 生产运维用 DDL 脚本（与 versions 同名） |
| **本目录** | **数据种子**：幂等写入业务表，不由 Alembic 自动执行 |

## Gateway 模型目录

- 文件：`gateway-catalog.seed.json`
- 目标表：`system_gateway_models`、`system_provider_credentials`（经 `config_catalog_sync`）
- 运行时权威：**PostgreSQL**，JSON 仅为源

```bash
cd backend
make seed-gateway
# 或
uv run python scripts/run_seed_gateway.py
```

启动时可选：`GATEWAY_CATALOG_SYNC_ON_STARTUP=true`（开发方便，生产建议 `false` + 显式 seed）。

## 与迁移的区别

- 改表结构 → 新建 `alembic/versions` revision，**不要**把目录 JSON 塞进迁移。
- 改模型列表 → 编辑本目录 JSON 后重新 `seed-gateway` 或管理 API `reload-from-config`。
