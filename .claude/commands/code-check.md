对当前改动做 **规范 + DDD 分层 + 重复/遗留** 审核，输出可执行建议。

> 规则真源：
>
> - `backend/docs/CODE_STANDARDS.md`（结构 / 反退化 / Gateway 分层 / 读路径）
> - `docs/PAGINATION.md`（列表 API 分页 envelope）
> - `docs/API_RESPONSE.md`（API 成功/错误响应 + 异常处理）
> - `backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md`（Gateway 边界 / `ProxyUseCase` 拆分）
> - `backend/docs/ARCHITECTURE.md`、仓库根 `AGENTS.md`
>
> 可勾选 checklist：`.cursor/agents/code-rule-check.md`
>
> 本命令只规定**流程、专项问法与输出格式**，不再重复罗列所有规则。

## 审查流程（按顺序）

1. **改动盘点**：列出本次新增/修改的文件，标出归属域与层（presentation / application / domain / infrastructure / bootstrap / libs）。
2. **应用 checklist**：对每个改动文件勾选 `.cursor/agents/code-rule-check.md` §1–§16，记录违反项。
3. **专项问法**（按改动类型分流，至少回答触发的那一类）：

   - **Gateway `/v1/*` 代理改动** → 回答 §A
   - **新增/扩展业务规则** → 回答 §B
   - **API / 读路径 / 字段扩展** → 回答 §C
   - **跨域调用 / 端口** → 回答 §D
   - **前端 BYOK / 模型 UI** → 回答 §E
   - **新增/改动 list endpoint 或分页 UI** → 回答 §F，并勾选 checklist **§15**
   - **异常处理 / 错误响应格式** → 回答 §G，并勾选 checklist **§16**

4. **静态与测试**：在 `backend/` 下跑：

   ```powershell
   uv run ruff check .
   uv run pyright <相关包路径>
   uv run pytest tests/unit/<相关目录> -q --tb=short
   uv run pytest tests/integration/ -q --tb=short  # 涉及 HTTP/DB
   ```

5. **输出**：按「问题 → 依据（真源锚点）→ 建议修改」分条列出；无问题时简要说明已核对项。

## 专项问法

### §A. Gateway 热路径

每条 Gateway 改动**必须**显式回答（→ CODE_STANDARDS §Gateway 热路径分层约束）：

- 新规则落在了 **domain 还是 application**？为什么不下沉到 `domains/gateway/domain/proxy_policy.py`（或同类 domain 模块）？
- 是否触碰 `proxy_use_case.py`？只允许编排顺序变化；其他原因（换 SDK、改字段映射、改归因来源）说明拆分不到位。
- 是否在 `proxy_use_case.py` 顶层加了兼容再导出别名（`_settle_usage` / `_enrich_*` 等）？必须删除，调用方改到正确模块。
- 应用协作模块是否落到对应职责文件：`proxy_metadata_builder` / `proxy_litellm_client` / `proxy_response_adapter` / `proxy_deferred_tasks` / `proxy_chat_pipeline` / `proxy_stream_settlement`？

### §B. Domain 反退化

（→ CODE_STANDARDS §DDD 反退化约束）

- 新「不变量 / 白名单 / 策略选择 / 计划生成」是否在 `domains/<bc>/domain/`？
- application 中是否出现 ≥3 个 `if scope == "team" / elif scope == "user"` 同概念分支？若是，说明为什么没抽成 domain policy。
- domain 模块是否误 import SQLAlchemy `Session` / ORM 实体 / Redis / LiteLLM / FastAPI / httpx？
- application 文件 > 800 行 或 类私有方法 > 15 个 → 必须给拆分说明或 follow-up todo。

### §C. API / 读路径 / 字段扩展

（→ CODE_STANDARDS §读路径 / 字段扩展）

- 加字段是否走标准链路 `migration → ORM → ReadModel/端口 DTO → *_read_mappers.py → Schema → 测试`？多出一处即偏离。
- list / detail / dashboard 是否复用同一 repository 或 `*ReadMixin` 入口，仅 projection / 过滤参数不同？
- 是否在 router 直接 `{"new_field": row.new_field}` 拼 response？需改走 mapper。
- 业务过滤（可见性 / team axis / scope）是否在 domain policy 决策（如 `usage_log_visibility`、`pricing_visibility`）？
- 集成测试是否断言新字段？前端调用是否经单一 adapter 而非每个调用点各拼一份？

### §D. 跨域调用 / 端口

- 是否依赖了**提供方**的 `application/ports.py` 而非具体实现 / ORM？
- 是否在 `libs/` 新增了业务 Protocol（**禁止**）？业务端口必须落 `domains/<bc>/application/ports.py`。
- 是否新增 `libs/llm/` 或 `libs/gateway/` 的 `.py`（**禁止**，两个目录已废弃）。

### §E. 前端 BYOK / 模型 UI

- 凭据 / 模型 Tab 是否回流到 `pages/settings`？必须停留在 `/gateway/*` + `features/gateway-*`（→ AGENTS.md「前端」原则）。
- 是否使用 `@/types` 已有类型而非 `any` 重写？

### §F. 列表分页

（→ `docs/PAGINATION.md`、checklist §15）

- Query 是否为 `page` + `page_size`（非 `skip/limit`）？响应是否含 `items/total/page/page_size/has_next/has_prev`？
- 是否使用 `libs.api.pagination`（`PageParams` / `build_page` / `slice_page`）而非 router 手拼 envelope？
- SQL 分页是否经 repository，application 是否避免直接列表 SQL？
- 前端是否经 `@/lib/pagination` + `@/components/pagination-controls`？批量 id 是否处理 `truncated`？
- 集成测试是否断言 envelope 字段？

### §G. API 响应 / 异常处理

（→ `docs/API_RESPONSE.md`、checklist §16）

- 成功响应是否为 Schema 直出（非 `{ code, message, data }`）？
- 错误是否走 `AIAgentError` + 全局 RFC 7807 handler（非 router 手写 HTTPException）？
- 新错误码是否登记 `libs/exceptions/codes.py`？
- OpenAI/Anthropic `/v1/*` 是否仍走各自 compat mapper（未包 Problem Details）？
- 前端是否经 `parseApiErrorBody` / 结构化 `ApiError`？

## 遗留与重复（每次必检）

- 是否引入已移除路径（`libs/gateway`、`libs/llm`、`domains/studio`）？
- 兼容分支是否有明确到期条件？「兼容里又写新逻辑」直接拒绝。
- 同一行为是否跨域重复实现（团队解析 / 租户 provisioning / Session 写入只有一个权威）？

## 输出格式示例

```
[问题] domains/gateway/application/foo_use_case.py:42 出现 5 处 if scope == ... 分支
[依据] CODE_STANDARDS §DDD 反退化约束 §拒绝 Domain 退化（Anemic Domain Model）
[建议] 抽成 domains/gateway/domain/foo_scope_policy.py 中的枚举驱动 policy；
      use case 仅按 plan 调度 IO；补 tests/unit/gateway/domain/test_foo_scope_policy.py
```

无问题时简要列出已核对的 checklist 与专项问法编号即可。
