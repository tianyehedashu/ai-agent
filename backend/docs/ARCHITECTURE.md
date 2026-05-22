# AI Agent 后端架构

> **版本**: 2.0  
> **更新**: 2026-05-14  
> **适用范围**: `backend/` 现行实现与目录事实。

本文已替换早期基于 `api/`、`core/`、`services/` 等**旧目录**的长篇叙述；能力说明以 **`domains/` + `bootstrap/` + `libs/`** 为准。

---

## 系统定位与能力

基于 FastAPI 的智能体后端，主要提供：

- **Agent 执行**：对话、工具、记忆、检查点、流式输出（SSE）
- **工具与 MCP**：内置工具、MCP 服务与动态工具
- **沙箱**：隔离执行环境（Docker 等，见 Agent 基础设施）
- **会话与身份**：用户、JWT、API Key、会话归属
- **AI Gateway**：多模型路由（LiteLLM）、团队/虚拟 Key、凭据与预算、**根路径 `/v1/*` 双协议对外代理**（OpenAI 兼容 + Anthropic `POST /v1/messages`）
- **评估**：基准与评估接口（`domains/evaluation/`）

---

## 分层与目录（现行）

### 顶层目录

```
backend/
├── bootstrap/          # FastAPI 入口、生命周期、全局中间件、路由挂载
├── domains/            # 业务域（DDD：presentation / application / domain / infrastructure）
│   ├── identity/       # 认证、用户、API Key
│   ├── session/        # 会话、标题
│   ├── agent/          # Agent 核心（引擎、LLM、工具、记忆、沙箱、垂直任务等）
│   ├── gateway/        # AI Gateway（/api/v1/gateway/*；/v1/* OpenAI 兼容 + Anthropic Messages）
│   └── evaluation/     # 评估
├── libs/               # 与业务无关的基础设施（db、config、middleware、observability 等）
├── alembic/            # 数据库迁移
├── utils/              # 通用工具
└── tests/              # 单元与集成测试
```

### 依赖方向（DDD）

```
presentation → application → domain
infrastructure 实现持久化与外部系统，由 application 调用；domain 不依赖 infrastructure。
```

- **Presentation**：各域 `presentation/` 下的 FastAPI 路由、Pydantic Schema、依赖注入。
- **Application**：UseCase、应用服务、后台任务编排（如 `domains/gateway/application/jobs.py`）。
- **Domain**：实体、领域类型、领域错误、纯算法。
- **Infrastructure**：ORM、仓储、外部 API 适配、沙箱、LiteLLM Router 单例等。

更细的导入与边界约定见仓库根 **[AGENTS.md](../../AGENTS.md)** 与 **[CODE_STANDARDS.md](./CODE_STANDARDS.md)**。

---

## 核心模块与代码位置

| 能力 | 主要位置 |
|------|-----------|
| HTTP 入口与路由注册 | `bootstrap/main.py` |
| Agent 对话与编排 | `domains/agent/application/`、`domains/agent/presentation/chat_router.py` 等 |
| Agent 引擎（LangGraph 等） | `domains/agent/infrastructure/engine/` |
| LLM（Agent 经 Gateway 桥接） | `domains/agent/infrastructure/llm/agent_llm_facade.py`（`AgentLlmFacade`） |
| 工具与 MCP | `domains/agent/infrastructure/tools/`、`presentation/mcp_*.py` |
| 记忆 | `domains/agent/infrastructure/memory/` |
| 沙箱 | `domains/agent/infrastructure/sandbox/` |
| AI Gateway（LiteLLM、团队、凭据、日志） | `domains/gateway/`；设计说明见 [AI_GATEWAY_DOMAIN_ARCHITECTURE.md](./AI_GATEWAY_DOMAIN_ARCHITECTURE.md) |
| Gateway 与 Agent 解耦协议 | `domains/gateway/application/ports.py`（`GatewayProxyProtocol` 等） |
| 会话域 | `domains/session/` |
| 身份域 | `domains/identity/` |
| 评估 | `domains/evaluation/` |
| Listing Studio（Listing 创作垂直任务） | `domains/agent/application/listing_studio_*`、`presentation/listing_studio_router.py` |
| 全局配置 | `bootstrap/config.py`（及环境变量） |

领域类型（如 `Message`、`AgentEvent`）位于各域 `domain/types.py` 或 `domain/entities/`，**不要**与旧文档中的 `core/types.py` 混淆。

---

## 技术栈

| 类别 | 技术 |
|------|------|
| Web | FastAPI、Uvicorn、SSE |
| 数据 | PostgreSQL、SQLAlchemy 2.0 异步、Alembic |
| 缓存 / 队列 | Redis |
| 向量 | Qdrant / Chroma（`VECTOR_DB_TYPE`）；`libs/db/vector.py` 纯向量 IO → `VectorIndexPort`；编排 `MemoryIndexingService`；策略 `domain/memory_index_policy.py` |
| LLM 统一 | LiteLLM（Agent 与 Gateway 场景） |
| 类型与质量 | Pyright、Ruff |

---

## 请求与数据流（概要）

典型对话请求：`Client → bootstrap 挂载的 chat 路由 → ChatUseCase 等 → Session/Agent 仓储与引擎 → LLM/工具 → 流式或 JSON 响应`。

Gateway 外部调用：`Client → /v1/* 或管理 API → Gateway 应用层与 LiteLLM Router → Provider`；内部模块可走 `GatewayProxyProtocol` 经网关归因，详见 Gateway 架构文档。

---

## 部署与安全要点

- **配置**：敏感项经环境变量与 `bootstrap/config.py` 注入，勿硬编码密钥。
- **认证**：JWT、API Key、Gateway 虚拟 Key 等分场景见 identity 与 gateway 的 `presentation/deps`。
- **权限**：`libs/db/permission_context.py` 与各领域 RBAC；详见 [PERMISSION_SYSTEM_ARCHITECTURE.md](./PERMISSION_SYSTEM_ARCHITECTURE.md)。
- **健康检查**：以 `bootstrap/main.py` 中实际注册的路由为准（如 `/health`）。

---

## 可观测性

| 能力 | 位置 |
|------|------|
| 日志、指标、Tracing、Sentry 集成 | `libs/observability/` |
| 应用日志初始化 | `bootstrap/main.py` 与 `utils/logging` |

---

## 扩展与性能

- **水平扩展**：无状态 API 多实例 + 共享 Redis/DB；注意 Gateway LiteLLM Router 单例与 Redis 计数的一致性。
- **异步**：路由与 UseCase 以 `async` 为主；阻塞调用应隔离或线程池。
- **数据库**：合理索引、分页、避免 N+1（`selectinload` 等）。

---

## Listing Studio 限界上下文（BC）

**决策（2026-05）**：Listing Studio（原 product-info）继续作为 **Agent 域内的垂直任务子模块**，与 `video-tasks` 并列；API 主路径 `/api/v1/listing-studio`，旧 `/api/v1/product-info` 短期 alias（`Deprecation` / `Link` 响应头）。

| 层级 | 职责 |
|------|------|
| `domains/agent/domain/listing_studio/` | 能力常量、`job_status_policy`、`pipeline_policy`、状态类型 |
| `domains/agent/application/listing_studio_*` | Job/Step CRUD、流水线编排、Capability Runner |
| `domains/gateway/domain/model_selection_policy` | 默认模型选取（配置 ID ∈ 可见集，否则首个可见） |
| Gateway `ModelCatalogPort` | 运行时模型真源（`list_visible_models`），禁止 app.toml 假默认 |

**模型解析**：Chat / Listing Studio 文本与视觉步骤经 `ChatModelResolutionUseCase`；8 图生图经 `resolve_image_gen_model_for_chat`。无可见模型时返回明确 `ValidationError`，引导配置 Gateway 凭据并同步目录。

**独立拆域触发条件**（暂不执行）：

1. 垂直电商场景 ≥3 且共享编排逻辑 <30%
2. 出现平台 Listing API、合规、SKU 等独立变更轴
3. 需独立产品线发布/计费

**演进路径**：

- **路径 A（电商为主）**：新建 `domains/commerce/` 收拢 Listing Studio 及后续电商工作流；Agent 保留执行引擎
- **路径 B（通用平台 + 垂直）**：维持现状，场景增多后再迁出

无论 A/B，Agent 域保留 Chat/LangGraph/工具/记忆，跨域依赖仍经 Gateway 端口与 Identity/Session。

---

## Agent 记忆向量索引（P3）

| 层级 | 模块 | 职责 |
|------|------|------|
| Domain | `domain/memory_index_policy.py` | collection 名、session 过滤、LangGraph namespace |
| Application | `MemoryIndexingService` | 嵌入 + 向量索引编排 |
| Application Ports | `TextEmbeddingPort`、`VectorIndexPort` | 依赖倒置 |
| Infrastructure | `vector_store_factory`、`vector_index_bridge` | Qdrant/Chroma 选择与 libs 桥接 |
| libs | `libs/db/vector.py` | 纯向量 IO（无 domains 依赖） |

`LongTermMemoryStore` 仅负责 LangGraph 元数据与调用 `MemoryIndexingService`；RAG 知识库后续复用 `VectorIndexPort` + `purpose="knowledge"` policy。

---

## 附录

### A. API 文档

启动后端后：

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### B. 相关文档

| 文档 | 说明 |
|------|------|
| [AGENTS.md](../../AGENTS.md) | 仓库级域划分与导入规范 |
| [CODE_STANDARDS.md](./CODE_STANDARDS.md) | 后端代码规范与 DDD 目录 |
| [AI_GATEWAY_DOMAIN_ARCHITECTURE.md](./AI_GATEWAY_DOMAIN_ARCHITECTURE.md) | Gateway 域与 CQRS |
| [LLM_GATEWAY_ARCHITECTURE.md](./gateway/LLM_GATEWAY_ARCHITECTURE.md) | LiteLLM 选型说明 |
| [archive/README.md](./archive/README.md) | 历史/过时文档归档目录 |
| [archive/refactor-baseline.md](./archive/refactor-baseline.md) | Agent–Gateway 解耦测试基线（快照） |
| [DEVELOPMENT.md](./DEVELOPMENT.md) | 本地开发与提交约定 |

[docs/](../../docs/README.md) 下产品/需求文档与 [archive/](../../docs/archive/README.md) 早期架构为参考材料，**实现以本仓库 `domains/` 代码为准**。

---

*文档版本: v2.0 | 最后更新: 2026-05-12*
