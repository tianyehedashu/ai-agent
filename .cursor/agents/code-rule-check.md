---
name: code-rule-check
model: composer-2
description: 对修改的代码进行全面检查,确保符合项目规范和质量标准。
---

# 代码规则检查清单

> **真源**：所有规则细节以下列文档为准；本清单只做可勾选项 + 锚点：
>
> - `backend/docs/CODE_STANDARDS.md`（结构 / 导入 / 反退化 / Gateway 分层 / 读路径）
> - `backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md`（Gateway 边界、ProxyUseCase 拆分）
> - 仓库根 `AGENTS.md`（导入路径速查）
>
> 如本清单与真源冲突，以真源为准；发现冲突立即在 PR 中指出。

## 1. 架构（DDD 4 层）

- [ ] 调用方向：Presentation → Application → Domain ← Infrastructure（→ CODE_STANDARDS §项目结构）
- [ ] `domain/` 不 import SQLAlchemy `Session` / ORM 实体 / Redis / LiteLLM / FastAPI / httpx（→ §DDD 反退化约束）
- [ ] `presentation/` 仅做 HTTP 适配 + 鉴权 + Schema；业务分支下沉到 application/domain
- [ ] `infrastructure/` 实现 `domain/` 与 `application/` 端口，禁止反向依赖 application
- [ ] ORM 模型不跨域 import 当 DTO；跨域用提供方 `application/ports.py`
- [ ] `bootstrap/` 只装配工厂、生命周期、回调；业务策略不放 bootstrap
- [ ] 跨域 FastAPI 依赖工厂落 `bootstrap/composition/<bc>_services.py`，不散落到各域 `presentation/deps.py`

## 2. 域与目录归属

- [ ] 现存域：`identity / session / tenancy / gateway / agent / evaluation`
      （`studio` 为历史占位空壳，**禁止**新增内容；listing studio 等子用例落 `agent/application/`）
- [ ] 启动 / 配置代码 → `bootstrap/`（`main.py` / `config.py` / `composition/`）
- [ ] Agent 引擎 / 工具 / 记忆 / 推理 → `domains/agent/infrastructure/{llm,tools,memory,reasoning}/`
- [ ] 团队/成员权威只在 `domains/tenancy/`；Gateway 管理面经 `TeamService` / 仓储访问，不复制规则
- [ ] ORM 模型 → `domains/*/infrastructure/models/`
- [ ] Pydantic Schema → `domains/*/presentation/schemas.py` 或 `presentation/schemas/` 分包
- [ ] 跨域 IAM 抽象（`MembershipPort` 等）落 `libs/iam/`；业务团队规则不进 `libs/`

## 3. 跨域应用端口（Protocol + DTO）

- [ ] 由**提供方域**在 `domains/<bc>/application/ports.py` 声明，**不放 `libs/`**
- [ ] Session：`SessionApplicationPort` @ `domains/session/application/ports.py`
- [ ] Identity：`MembershipPort` 等 @ `domains/identity/application/ports.py`
- [ ] Gateway：`GatewayProxyProtocol` / `GatewayCallContext` / `GatewayResponse` 等 @
      `domains/gateway/application/ports.py`；工厂 `get_gateway_proxy` @ `gateway_proxy_factory.py`
- [ ] **禁止**在 `libs/llm/` 与 `libs/gateway/` 新增 `.py`（两个目录已废弃）

## 4. 命名

- [ ] 模块：`snake_case.py`；类：`PascalCase`；常量：`UPPER_SNAKE`；私有：`_` 前缀
- [ ] 路由文件：单文件域用 `*_router.py`（如 `session_router.py`）；
      Gateway 这类大域走 `presentation/routers/<sub>.py` 分包（无 `_router` 后缀），在 `routers/__init__.py` 聚合
- [ ] 测试：`test_<scenario>_<expected>`；放在镜像 domain 路径的 `tests/unit|integration|e2e/` 下

## 5. 类型与风格（→ CODE_STANDARDS §类型安全 / §代码风格）

- [ ] 全量类型注解；通过 `uv run pyright`
- [ ] 禁止 `Any` / `dict` 无类型 / `# type: ignore`（除非必要并写明原因）
- [ ] 字符串注解类型已通过全局 `from __future__ import annotations` 失效，**不要**再加引号
- [ ] 业务类型从 `domains.*.domain.types` 导入；通用类型从 `libs.types` 导入
- [ ] 行宽 ≤ 100；用 `pathlib.Path` 与 f-string；通过 `uv run ruff check .`

## 6. 错误处理（→ CODE_STANDARDS §错误处理）

- [ ] 可失败操作返回 `Result[T]`（来自 `libs.types`）
- [ ] 业务异常继承 `libs.exceptions.AIAgentError`（或 `HttpMappableDomainError`），
      **不在 application 内**重新定义业务异常类型
- [ ] 复用既有：`ValidationError` / `NotFoundError` / `PermissionDeniedError` /
      `AuthenticationError` / `TokenError` / `ToolExecutionError` / `ExternalServiceError`
- [ ] 异步操作有合适的异常处理 + 取消传播

## 7. DDD 反退化（→ CODE_STANDARDS §DDD 反退化约束）

- [ ] 新增「不变量 / 白名单 / 策略选择 / 计划生成」纯逻辑落在 `domains/<bc>/domain/`，
      不允许只写在 application 私有方法里
- [ ] application 中出现 ≥3 个对同一概念的 `if scope == ... / elif ...` 分支 → 抽成 domain policy
- [ ] 单个 `*UseCase` 不同时承担「校验 + 限流 + 预算 + metadata + 外部 SDK + 响应适配 + 结算」；
      按变化原因拆 `*_metadata_builder` / `*_litellm_client` / `*_response_adapter` / `*_deferred_tasks` 等
- [ ] application 文件 > 800 行 或 类的私有方法 > 15 个 → PR 给出拆分说明或 follow-up todo
- [ ] application 服务之间禁止 import 对方 `_` 前缀符号；公开 API 显式 `__all__` 或不带前缀

## 8. Gateway 热路径专项（→ CODE_STANDARDS §Gateway 热路径分层约束）

> 每条 Gateway 改动须在 PR 描述里答：「新增规则落在了 domain 还是 application？为什么不下沉？」

- [ ] 模型 / 能力 / 预算 / 套餐 / 限流 / 归因 等纯规则先落 `domains/gateway/domain/proxy_policy.py`（或同类 domain 模块）
- [ ] `proxy_use_case.py` 仅作 `/v1/*` 编排门面，不包含业务分支
- [ ] 应用协作模块按职责落位：`proxy_metadata_builder` / `proxy_litellm_client` /
      `proxy_response_adapter` / `proxy_deferred_tasks` / `proxy_chat_pipeline` / `proxy_stream_settlement`
- [ ] **禁止**在 `proxy_use_case.py` 顶层重新加兼容再导出别名（`_settle_usage` / `_enrich_*` 等）

## 9. 读路径 / 字段扩展（CQRS）（→ CODE_STANDARDS §读路径 / 字段扩展）

- [ ] 同一资源的 list / detail / dashboard 共用 repository 或 `*ReadMixin` 入口；
      不复制 `select(...)` 列清单到多处
- [ ] 加字段链路收敛为：`migration → ORM → ReadModel/端口 DTO → *_read_mappers.py → Schema → 测试`
- [ ] 禁止在 router 直接 `{"new_field": row.new_field}` 拼 response dict
- [ ] 业务过滤（可见性 / team axis / scope）在 domain policy 决策；application 按 plan 查一次
- [ ] 跨域消费方依赖端口 DTO，不复制字段结构
- [ ] 集成测试断言新字段；前端 `@/types` 或 `features/<bc>/*` 内单一 adapter 同步

## 10. 遗留与重复

- [ ] 不再引入 `libs/gateway` / `libs/llm` 等已废弃路径
- [ ] 兼容分支有明确**到期条件**或被立即清理；不允许在兼容里又写新逻辑
- [ ] 同一行为不跨域重复实现（团队解析 / 租户 provisioning / Session 写入只能有一个权威）

## 11. 测试

- [ ] 行为变更补 `tests/unit/<bc>/` 或 `tests/integration/`
- [ ] domain policy 必须有**纯函数**单测（不连 DB / Redis / HTTP）
- [ ] `monkeypatch.setattr` 指向真正实现所在模块，不指向再导出 facade

## 12. 性能与安全

- [ ] DB 查询走索引字段；批量用批量 API；避免 N+1
- [ ] 输入用 Pydantic Schema 校验；敏感操作用 `check_session_ownership` / `check_tenant_access`
- [ ] 用 ORM 防 SQL 注入；用 `pathlib` 规范化路径防遍历

## 13. 前端（TypeScript）

- [ ] 全量类型注解；禁止 `any` / `as any` / `@ts-ignore`；禁止直接操作 `localStorage`
- [ ] 业务类型从对应 feature 模块或 `@/types` 导入；项目内用 `@/` 别名
- [ ] API 调用经单一 hook / adapter（如 `features/gateway-*`），不在多处重写 fetch / 字段映射
- [ ] BYOK 凭据 / 个人模型 UI 在 `/gateway/*` 与 `frontend/src/features/gateway-*`，**不**回到 `pages/settings`

## 14. 静态检查命令（`backend/` 下）

```powershell
uv run ruff check .
uv run pyright <相关包路径>
uv run pytest tests/unit/<相关目录> -q --tb=short
uv run pytest tests/integration/ -q --tb=short  # 涉及 HTTP/DB
```

---

**检查原则**：先看真源，本清单只是 reviewer 的 keystroke 入口；发现条目过时 → 改清单 + 真源同步。
