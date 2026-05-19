对当前改动做 **规范 + DDD 分层 + 重复/遗留** 审核，并给出可执行建议。

## 必读

- `backend/docs/CODE_STANDARDS.md`（目录、`libs` vs `domains`、**应用端口**在 `application/` 不在 `libs`）
- 仓库根 `AGENTS.md`（导入路径与分层）
- 架构补充：`backend/docs/ARCHITECTURE.md`、`backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md`（Gateway 边界 / `ProxyUseCase` 门面拆分）

## 检查维度

### 1. 架构（DDD 分层）

- 调用方向严格 `Presentation → Application → Domain ← Infrastructure`；同层之间禁止环依赖。
- 跨域契约（**Protocol / DTO**）由 **提供方域** 的 `application/ports.py` 声明（如
  `SessionApplicationPort`、`GatewayProxyProtocol`、`UpstreamModelListPort`），**禁止**
  在 `libs/` 堆业务契约或在消费方临时复刻。
- `presentation/` 只做 HTTP 适配 + 鉴权 + Schema 校验；任何分支判断只要涉及业务概念，
  必须下沉到 `application/` 或 `domain/`。
- `infrastructure/` 实现 `domain/ports` 与 `application/ports`，禁止反向依赖
  application；ORM 模型不得跨域被直接 import 用作 DTO。
- `bootstrap/` 只装配工厂、生命周期、回调；任何 `if env == ...` 类业务策略要回到 domain。

### 2. 拒绝 Domain 退化（Anemic Domain）

- 新增「业务规则 / 不变量 / 策略」必须落在 `domains/<域>/domain/`：值对象、领域服务、
  policy 函数、错误类型；不允许只在 application 私有方法里写裸 `if/elif` 判定。
- Domain 模块**禁止**导入 SQLAlchemy `Session`、ORM 实体（除非该域定义的 `domain/types.py`
  里的纯数据类）、Redis、LiteLLM、FastAPI、httpx 等基础设施符号。如果策略需要这些数据，
  Application 层先查出**纯值快照**，再传入 Domain policy 函数。
- 「该查哪些 budget 行 / 该限流哪个 token / 该走哪个套餐」这种**计划性**逻辑要做成
  domain 的纯函数（如 `build_budget_check_plan`、`rate_limit_target`、
  `assert_registered_model_capability`），让 application 只负责**按计划执行 IO**。
- 当一个 application 方法出现 ≥3 个重复的 `if scope == "team" / elif scope == "user"`
  分支时，多半应抽成 domain 值对象或 policy；写 PR 描述时显式说明「为什么没下沉」。

### 3. 拒绝 Application 层加重（Fat Use Case）

- 单个 `*UseCase` 类不应同时承担：白名单校验、限流、预算、metadata 拼装、外部 SDK 调用、
  响应适配、结算 —— 这些应**按变化原因**拆成独立 application 模块（`*_metadata_builder`
  / `*_litellm_client` / `*_response_adapter` / `*_deferred_tasks` 等），UseCase 只做编排。
- UseCase 内部允许的「变化原因」是**编排顺序**变化；如果是「换 LLM SDK / 换响应字段 /
  换归因 metadata 来源」这类变化触发 UseCase 修改，说明拆分不到位。
- 一个 application 文件超过 800 行、或一个类的私有方法超过 15 个，必须在 PR 中给出
  拆分说明或 follow-up todo；不允许用「以后再拆」无限延期。
- Application 服务之间**禁止跨模块调用 `_` 前缀方法**；公开行为必须有显式 `__all__`
  或不带前缀的命名。

### 4. Gateway 热路径专项（`/v1/*` 代理）

- `ProxyUseCase` 只能是 `/v1/*` 代理编排门面；新增模型 / 能力 / 预算 / 套餐 / 限流 /
  归因策略一律先加到 `domains/gateway/domain/proxy_policy.py`（或同类 domain 模块）。
- 应用协作模块按职责落位：
  - `proxy_metadata_builder.py` —— Gateway metadata、归因、下游定价 kwargs。
  - `proxy_litellm_client.py` —— LiteLLM Router / 直连技术适配。
  - `proxy_response_adapter.py` —— 响应适配、`response_cost` 注入、预算/套餐结算。
  - `proxy_deferred_tasks.py` —— fire-and-forget 结算任务登记与 shutdown 收口。
  - `proxy_chat_pipeline.py` / `proxy_stream_settlement.py` —— Chat/Anthropic 共享流水线。
- 禁止在 `proxy_use_case.py` 顶层重新加「兼容再导出」别名（如 `_settle_usage`
  `_enrich_*`）；旧调用方一律改到正确模块。

### 5. 遗留与重复

- 禁止再引入已移除路径（如历史 `libs/gateway`、旧 `proxy_use_case` 内部下划线再导出）。
- 兼容分支必须有明确**到期条件**或被立即清理；不允许「兼容里又写新逻辑」。
- 同一行为禁止跨域重复实现（典型：团队解析、租户 provisioning、Session 写入只能有一个权威）。

### 6. 类型与风格

- 与 `pyproject.toml` 中 Ruff / Pyright 约定一致；禁止无必要的 `Any`、`# type: ignore`、
  字符串包裹的类型注解（已通过 `from __future__ import annotations` 全局生效）。
- 公开领域错误从 `libs/exceptions` 或域 `domain/errors.py` 复用，禁止在 application
  内部重新定义业务异常类型。

### 7. 测试

- 改动涉及行为时，补充或更新 `tests/unit/<域>/` 或 `tests/integration/`；
  domain policy 必须有**纯函数**单测（不连 DB / Redis / HTTP）。
- 单测的 `monkeypatch.setattr` 目标应指向**真正实现所在模块**，而不是经由再导出别名
  的 facade（避免拆分后测试失效却不暴露问题）。

## 建议本地命令（`backend/` 下）

```powershell
uv run ruff check .
uv run pyright <涉及的路径或包>
uv run pytest tests/unit/<相关目录> -q --tb=short
# 有 HTTP/DB 行为时：
uv run pytest tests/integration/ -q --tb=short
```

输出：按 **问题 → 依据（文档/原则）→ 建议修改** 列出；无问题时简要说明已核对项。
特别注意 §2 / §3 / §4：每条 Gateway 改动都要回答「新规则落在了 domain 还是 application」。
