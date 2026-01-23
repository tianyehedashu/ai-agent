# 终局架构迁移方案（零功能回退）

> 目标：在一次性整理到“终局形态”的前提下，确保 **Agent / 对话（SSE）/ Session / Memory / Tools / HITL（检查点）/ 开发环境匿名用户** 等核心能力不丢失、行为正确、可回归验证。
>
> 重要约束：
> - **认证/登录对外契约不做硬要求**（前端尚未集成），但必须保留“开发环境匿名用户”以保证隔离正确性。
> - **SubAgent 并行调度不做强要求**（后续可能接 LangChain Deep Agent），本次仅预留扩展点。

---

## 1. 范围与不可回退清单（契约冻结）

### 1.1 必须保持可用的对外 API（路径维持 `/api/v1/*`）

- **Chat（SSE + HITL）**
  - `POST /api/v1/chat`（SSE，最后输出 `[DONE]`，headers/序列化行为保持）
  - `POST /api/v1/chat/resume`
  - `GET /api/v1/chat/checkpoints/{session_id}`
  - `GET /api/v1/chat/checkpoints/{checkpoint_id}/state`
  - `POST /api/v1/chat/checkpoints/diff`
- **Agents**
  - `GET/POST/GET/PUT/DELETE /api/v1/agents/*`（权限/公开逻辑保持）
- **Sessions**
  - `GET/POST/GET/PATCH/DELETE /api/v1/sessions/*`
  - `GET /api/v1/sessions/{session_id}/messages`
  - `POST /api/v1/sessions/{session_id}/generate-title`
- **Memory**
  - `GET/POST/DELETE /api/v1/memory/*`
  - `POST /api/v1/memory/search`
  - `POST /api/v1/memory/import`
- **Tools**
  - `GET /api/v1/tools`
  - `GET /api/v1/tools/{tool_name}`
  - `POST /api/v1/tools/{tool_name}/test`
- **Studio / System / Evaluation**
  - 现有接口保持可用（不作为本次 P0 主链路，但不允许“跑不起来”）

### 1.2 必须保持的运行时行为（关键语义）

- **开发环境匿名用户**
  - 无 `Authorization` 时仍可访问（dev）
  - 自动下发 `anonymous_user_id` Cookie
  - 匿名用户隔离：不同 Cookie 不串会话/记忆/Agent 数据
- **SSE 行为**
  - `text/event-stream`，保持现有 headers（如 `X-Accel-Buffering: no`）
  - 事件序列化逻辑不回退（处理 LiteLLM/Pydantic 序列化）
- **HITL/检查点**
  - resume/checkpoints/state/diff 行为正确

---

## 2. 终局架构（DDD + 四层，厚薄有别）

### 2.1 Bounded Context（终局边界）

固定为 5 个上下文（避免过度拆分）：

- **Identity**：用户、认证（未来 FastAPI Users）、权限、匿名策略
- **AgentCatalog**：Agent 定义/管理/版本/发布/安装（“下载并运行”的定义与分发在此）
- **Runtime**：对话、会话、工具、沙箱、检查点、上下文管理（包含 memory 作为 context 子系统）
- **Studio**：工作台/工作流
- **Evaluation**：评估/基准

> 说明：`memory` **不独立成域**，按当前定位归属 **Runtime 的上下文管理子系统**。

### 2.2 四层定义（强约束：依赖方向）

- **Presentation**：FastAPI router + Pydantic schema + 依赖注入（不写业务）
- **Application**：用例编排（事务/跨模块协调），是主要厚层
- **Domain**：承载真实业务规则（能抽则抽，不强求“满配”）
- **Infrastructure**：数据库/Redis/向量库/外部下载源/沙箱容器等实现细节

依赖方向硬规则：

```text
presentation → application → domain
infrastructure → domain（只实现 domain 定义的接口/协议）
shared/kernel：只放通用类型/异常/少量契约，严控体积
```

---

## 3. 终局目录规范（落地目录）

> 对外 API 仍按 `/api/v1/*` 暴露；内部实现归 `domains/*`。

```text
backend/
  app/
    main.py
    config.py
    lifespan.py

  api/
    router.py          # 汇总各 domain router（或继续使用 api/v1/router.py 作为外观层）
    deps.py            # 仅保留跨域通用依赖；身份相关逐步下沉到 Identity
    middleware/

  domains/
    identity/
      presentation/
        router.py
        middleware.py  # anonymous_user_id cookie 写入（由 Identity 管理）
        schemas.py
      application/
        principal_service.py  # 统一主体获取（含 dev 匿名策略）
      domain/
        policies.py
      infrastructure/
        authentication.py     # 未来 FastAPI Users 落点（本次不强制）
        repo.py

    agent_catalog/
      presentation/
        router.py             # /agents/*
        schemas.py
      application/
        service.py
      domain/
        models.py
        policies.py
      infrastructure/
        repo.py

    runtime/
      presentation/
        chat_router.py        # /chat*
        session_router.py     # /sessions*
        memory_router.py      # /memory*
        tools_router.py       # /tools*
        schemas.py
      application/
        chat_service.py
        session_service.py
        runtime_service.py
      domain/
        orchestration/        # 主Agent/扩展点（本次仅预留）
        engine/
        checkpoint/
        tools/
        sandbox/
        context/              # memory 归属：context_manager/retriever/summarizer
      infrastructure/
        llm_gateway.py
        vector_store.py
        repo.py

    studio/...
    evaluation/...

  shared/
    kernel/
      types.py
      exceptions.py
      contracts.py
    infrastructure/
      database.py
      redis.py
      observability/
```

---

## 4. 迁移策略（薄转发 + 分阶段验收）

核心手法：**入口不变、实现迁移**。旧文件先做薄转发，等新实现稳定后再清理遗留代码。

### 阶段 A：建立骨架（不切入口）

- 新增 `backend/domains/*` 与 `backend/shared/*` 目录结构
- 新增 `backend/api/router.py`（可选：先不启用）
- 不改现有 `backend/api/v1/router.py` include 结构

验收：服务能启动，现有 API 均可访问。

### 阶段 B：收拢匿名用户为 Identity 策略（不改对外行为）

- 将“匿名主体获取/创建”逻辑迁移到 `domains/identity/application/principal_service.py`
- 将 cookie 写入逻辑迁移到 `domains/identity/presentation/middleware.py`
- `backend/api/deps.py` 逐步变为薄适配：仍返回现有 `schemas.user.CurrentUser`/别名 `AuthUser` 等，确保其他 API 不改动即可继续工作

验收：dev 无 token 访问仍可用，cookie 下发与隔离正确。

### 阶段 C：Runtime 迁移 Chat + HITL（保持 SSE 行为不变）

- 新增 `domains/runtime/presentation/chat_router.py`，完全复刻 SSE headers/`[DONE]`/序列化语义
- `backend/api/v1/chat.py` 改为薄转发到新 router
- checkpointer/session_manager 生命周期不回退（仍由 app lifespan 初始化）

验收：chat/resume/checkpoints/state/diff 与现状一致。

### 阶段 D：AgentCatalog 迁移 Agents（CRUD 正确）

- `domains/agent_catalog/presentation/router.py` 暴露 `/agents/*`，内部复用/迁移现有逻辑
- `backend/api/v1/agent.py` 改为薄转发

验收：CRUD、权限、公开逻辑正确。

### 阶段 E：Runtime 接管 Sessions / Memory / Tools（保持路径不变）

- sessions：迁移 `/sessions/*`（含 messages、generate-title）
- memory：迁移 `/memory/*`（并明确其为 runtime/context 的管理面）
- tools：迁移 `/tools/*`
- 原 `backend/api/v1/session.py|memory.py|tool.py` 依次变薄转发

验收：Session/Memory/Tools 行为正确、匿名隔离正确。

### 阶段 F：Studio/Evaluation/System 归位（后置）

- 迁移或保持薄转发均可（不影响 P0 主链路）

验收：相关接口仍可用。

### 阶段 G：清理遗留代码（最后一步）

- 删除旧实现（auth/jwt/password/旧 middleware 等）
- 全局 import 清理，保证无“幽灵依赖”

验收：全量回归通过。

---

## 5. TODO 清单（按优先级）

### P0（必须：主链路零回退）

- **P0-01**：冻结核心对外契约并补齐最小回归用例（chat SSE/HITL、匿名隔离、agents/sessions/memory/tools）
- **P0-02**：建立终局目录骨架：`backend/domains/{identity,agent_catalog,runtime,studio,evaluation}` + `backend/shared/{kernel,infrastructure}`
- **P0-03**：匿名用户能力收拢到 Identity 策略（cookie + 落库隔离），对外行为不变
- **P0-04**：Runtime 迁移 Chat（保持 SSE headers、`[DONE]`、序列化语义）
- **P0-05**：Runtime 迁移 Checkpoint/HITL（resume/checkpoints/state/diff）
- **P0-06**：AgentCatalog 迁移 `/agents/*`（权限/公开逻辑正确）
- **P0-07**：Runtime 接管 `/sessions/*`（messages、generate-title）
- **P0-08**：Runtime 接管 `/memory/*`（仍按 user_id 隔离；定位为 context 子系统的管理面）
- **P0-09**：Runtime 接管 `/tools/*`（list/detail/test）

### P1（一致性与清理）

- **P1-01**：`backend/api/v1/*.py` 全部改为薄转发层（入口不变、实现归 domains）
- **P1-02**：清理遗留代码（最后做）：旧 auth/jwt/password、未使用中间件、重复 service 等
- **P1-03**：写入并执行依赖方向规则（文档 + lint/CI 约束）

### P2（为未来 subagent/deep agent 预留，不强制实现）

- **P2-01**：Runtime 预留 `orchestration` 扩展点（接口/抽象），先不实现并行调度
- **P2-02**：AgentCatalog 增加 manifest（tools 权限、能力标签、subagent 声明）为后续“下载并运行”铺路

---

## 6. 验收清单（每阶段必过）

### 6.1 匿名用户（dev）

- 无 token 请求可访问主链路 API
- 下发 `anonymous_user_id` Cookie
- A/B 两个 cookie 不串数据：session、memory、agents（若绑定 user_id）互相隔离

### 6.2 Chat SSE + HITL

- `POST /chat`：SSE 持续输出，最后 `[DONE]`，headers 保持（`Cache-Control/Connection/X-Accel-Buffering`）
- `POST /chat/resume`：SSE 输出正确
- checkpoints list/state/diff：字段与行为正确

### 6.3 Agent / Session / Memory / Tools

- Agents CRUD：权限/公开逻辑正确
- Sessions：列表/创建/更新/删除/消息历史/标题生成正确
- Memory：list/search/create/delete/import 正确（user 隔离正确）
- Tools：list/detail/test 正确

