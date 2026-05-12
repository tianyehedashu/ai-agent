# Agent「核心能力」与目录（已对齐 `domains/`）

> **说明**：旧版文档中的 `backend/core/`、`shared/`、`db/` 等顶层目录**已不存在**。执行引擎、LLM、工具、记忆、沙箱等能力现主要在 **`domains/agent/infrastructure/`**；统一多模型网关见 **`domains/gateway/`**。下文为理念 + **现行落点**，避免与历史路径混淆。

---

## 1. 为何单独强调「技术能力」

AI Agent 系统的「核心」不仅是业务规则，还包括**可插拔的智能与执行能力**（推理、工具、记忆、隔离执行）。这些在 DDD 中通常落在 **Infrastructure** 或 **Application 所调用的适配器**，与 CRUD 域模型并列演进。

---

## 2. 现行落点（对照）

| 能力 | 现行主要位置 |
|------|----------------|
| LLM 调用 / Agent 侧网关 | `domains/agent/infrastructure/llm/`（含 `LLMGateway`） |
| AI Gateway（OpenAI 兼容、团队、凭据） | `domains/gateway/`（见 [AI_GATEWAY_DOMAIN_ARCHITECTURE.md](./AI_GATEWAY_DOMAIN_ARCHITECTURE.md)） |
| 工具 / MCP | `domains/agent/infrastructure/tools/` 等 |
| 记忆 | `domains/agent/infrastructure/memory/` |
| 沙箱 | `domains/agent/infrastructure/` 下沙箱相关模块 |
| 推理策略 | `domains/agent/infrastructure/reasoning/` |
| 数据库访问 | `libs/db/`；各域 ORM 在 `domains/*/infrastructure/models/` |

---

## 3. 依赖方向（仍适用）

- `presentation` → `application`（UseCase）→ `domain`；技术实现放在 `infrastructure`。
- **避免** presentation 直接调用底层 HTTP/ORM/容器细节；由 UseCase 编排。

---

## 4. 何时再拆抽象

在需要替换实现（如换推理框架）、多租户隔离配置、或对单点做独立扩缩时再引入额外端口/适配器；当前以 **`domains/` 内聚实现 + 清晰分层** 为主。

**权威目录与导入约定**：根目录 [AGENTS.md](../../AGENTS.md)、[CODE_STANDARDS.md](./CODE_STANDARDS.md)。
