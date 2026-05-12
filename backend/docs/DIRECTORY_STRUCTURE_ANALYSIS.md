# 目录结构分析（已归档）

> **状态**：本文原载于 2026-01-12，描述的是**旧版** `backend/` 布局（`api/`、`app/`、`core/`、`services/` 等），与当前 **`domains/` + `bootstrap/` + `libs/`** 不一致。  
> **结论**：正文已移除，**请勿再按本文理解目录**；以下方权威文档与仓库实际目录为准。

---

## 现行结构以何为准

| 文档 | 用途 |
|------|------|
| [AGENTS.md](../../AGENTS.md) | 仓库根规范：域划分、导入约定 |
| [CODE_STANDARDS.md](./CODE_STANDARDS.md) | 后端 DDD 分层与目录说明 |
| [AI_GATEWAY_DOMAIN_ARCHITECTURE.md](./AI_GATEWAY_DOMAIN_ARCHITECTURE.md) | Gateway 域：UseCase、CQRS、依赖方向 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 后端能力总览（部分图示仍为历史风格时，以 `domains/` 为准） |

---

## 当前 backend 顶层（概要）

```
backend/
├── bootstrap/     # FastAPI 入口、生命周期、路由注册
├── domains/       # 业务域（identity, session, agent, gateway, studio, evaluation, …）
├── libs/          # 与业务无关的基础设施
├── alembic/       # 数据库迁移
├── utils/
└── tests/
```

若需新的「目录结构审视」，建议基于当前树另写短文或 PR 说明，避免与本归档文件名混淆。
