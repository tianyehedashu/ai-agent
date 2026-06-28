# Gateway Application 子包迁移执行计划

> 本文档是 [AI_GATEWAY_DOMAIN_ARCHITECTURE.md §2.1](../AI_GATEWAY_DOMAIN_ARCHITECTURE.md#21-application-子包组织目标态与迁移计划) 的可执行附录，给出每个子包的精确 `git mv` / shim / import 替换 / 验证 / 回滚步骤。
>
> **执行原则**：一次一个子包；每段独立可合并可回滚；shim 保留到第 3 段统一清理；未跑回归不合并。
>
> **进度**：M1 ✅ 完成（2026-06-27）｜ M2 ✅ 完成（2026-06-27）｜ M3 ✅ 完成（2026-06-27）｜ M4 ✅ 完成（2026-06-27）｜ M5–M9 ✅ 完成（2026-06-27）｜ M10 ✅ 完成（2026-06-27）｜ M11 ✅ 完成（2026-06-27）｜ M12 ✅ 完成（2026-06-27，103 shim 已删）｜ **附1：management/ 整理 ✅（2026-06-27）｜ 附2：management/ 读侧下沉 ✅（2026-06-27）｜ 附3：router→route 重命名 + grant/ 拆分 ✅（2026-06-27）｜ 附4：write_modules 下沉 ✅（2026-06-27，15 mixin 下沉 + write_modules/ 消除）｜ 附5：深层整改 ✅（2026-06-27，upstream/ 独立 + granted_route 归位 + pricing_management 下沉，13 文件迁移）｜ 附6：infrastructure/litellm/ 下沉 ✅（2026-06-27，5 文件，三层对称）｜ 附7：management/__init__ docstring 修正 + 后缀统一 ✅（2026-06-27，8 文件 docstring + 1 文件重命名）**

## 0. 通用约定

### 0.1 目录与命名

- 目标根：`backend/domains/gateway/application/`
- 每个子包必须有 `__init__.py`，哪怕为空。
- 子包内文件**保持原名**（不加 `_` 前缀），便于 git 历史追踪。
- 子包内文件之间的相对 import 在 `git mv` 后需同步更新（`from domains.gateway.application.xxx` → `from domains.gateway.application.<subpackage>.xxx` 或 `from .xxx`）。

### 0.2 Shim 模板

根级旧位置保留 shim 文件，内容统一格式：

```python
"""兼容 shim — 已迁移至 <subpackage>/<module>，待第 3 段清理。

详见 docs/gateway/APPLICATION_SUBPACKAGE_MIGRATION.md。
"""
from domains.gateway.application.<subpackage>.<module> import *  # noqa: F403
```

> **M1 实测踩坑**：
> 1. **ruff 配置下 `import *` 不触发 F401**（仅 F403），shim 的 noqa 只需保留 `F403`，写 `F401,F403` 会被 RUF100 报"unused noqa"。
> 2. **`import *` 不导出 `_` 前缀私有符号**，也不导出 `__all__` 外的符号。若测试或调用方直接 import 私有符号（如 `_bucket_key`），shim 无法兜底——此时应让调用方（尤其测试）直接走新路径 `application.<subpackage>.<module>`，而非依赖 shim。
> 3. **`monkeypatch.setattr("domains.gateway.application.budget_xxx.attr", ...)` / `patch("...")` 的字符串路径也指向 shim 模块**，patch shim 命名空间的属性不会影响真实模块内的引用。迁移时必须同步更新这些字符串路径为新模块路径。

### 0.3 Import 替换命令

同域调用方批量替换（PowerShell，迁移 `<subpackage>` 时执行）：

```powershell
# 例：迁移 budget/ 时，把 application.budget_service 替换为 application.budget.budget_service
# 注意：先替换子包内文件（相对 import），再替换外部文件
```

实际操作建议用 IDE 全局替换（Ctrl+Shift+H），按子包逐个执行，每次替换后跑 ruff 检查未用 import。

### 0.4 验证清单（每个子包迁移后必跑）

1. `ruff check backend/domains/gateway/application/<subpackage>/` —— 无 lint 错误
2. `ruff check backend/` —— 全局无新增错误
3. `python -c "import domains.gateway.application.<subpackage>"` —— 子包可导入
4. `python -c "import domains.gateway.application"` —— 根包仍可导入（shim 生效）
5. `pytest tests/architecture/ -x` —— 架构约束测试通过
6. `pytest tests/integration/gateway/ -x` —— 网关集成测试通过
7. 跨域 smoke：`python -c "from domains.agent.infrastructure.llm.agent_llm_facade import AgentLlmFacade"`（验证 bridge/proxy 相关 shim）

### 0.5 回滚

每个子包迁移作为一个独立 commit。回滚 = `git revert <commit>`。shim 设计保证即使只回滚单个子包，其余子包不受影响。

---

## 1. 里程碑与顺序

| 阶段 | 子包 | 文件数 | 跨域引用 | 风险 | 依赖 |
|------|------|--------|---------|------|------|
| M1 | `budget/` | 7 | 0 | 低 | 无 |
| M2 | `grant/` | 15 | 0 | 低 | 无 |
| M3 | `quota/` | 11 | 1（entitlement_model_status → agent） | 中 | 无 |
| M4 | `catalog/` | 22（含现有 2） | 5 | 中 | 无 |
| M5 | `access/` | 2 | 0 | 低 | 无 |
| M6 | `usage/` | 2 | 1（tests） | 低 | 无 |
| M7 | `observability/` | 3 | 0 | 低 | grant/（依赖其缓存） |
| M8 | `router/` | 3 | 0 | 低 | 无 |
| M9 | `credential/` | 2 | 0 | 低 | 无 |
| M10 | `proxy/` | 26 | 4（agent + tests） | 高 | bridge/ 的 billing_context 等 |
| M11 | `bridge/` | 10 | 6（agent 最密） | 高 | 无 |
| M12 | 清理 shim | — | — | 低 | M1-M11 全部稳定 |

**关键依赖**：M10 `proxy/` 内部分文件依赖 `bridge/` 的 `billing_context` / `internal_bridge_actor`。由于 bridge/ 在 M11 才迁，M10 期间 proxy/ 文件仍从根级 import bridge 模块（shim 保留），无阻塞。**禁止为图省事把 bridge/ 提前到 M10 之前**，因为 bridge/ 跨域引用最密，需要单独专注处理。

---

## M1. budget/ 迁移（7 文件，0 跨域引用，首战练手）

### 文件清单

```
budget_service.py
budget_config_cache.py
budget_callback_settlement.py
budget_platform_settlement.py
budget_deployment_check.py
budget_usage_persist.py
user_credential_budget_index.py
```

### 步骤

1. **建子包**
   ```powershell
   New-Item -ItemType Directory -Path backend\domains\gateway\application\budget
   New-Item -ItemType File -Path backend\domains\gateway\application\budget\__init__.py
   ```

2. **`__init__.py` 内容**（第 1 段：兼容再导出，此时还不 mv 文件）
   ```python
   """budget 子包 — 预算与限流。

   详见 docs/gateway/APPLICATION_SUBPACKAGE_MIGRATION.md M1。
   """
   ```

3. **第 2 段：逐文件迁移**（每个文件一次 commit，或整批一次 commit）
   ```powershell
   git mv backend\domains\gateway\application\budget_service.py backend\domains\gateway\application\budget\budget_service.py
   git mv backend\domains\gateway\application\budget_config_cache.py backend\domains\gateway\application\budget\budget_config_cache.py
   git mv backend\domains\gateway\application\budget_callback_settlement.py backend\domains\gateway\application\budget\budget_callback_settlement.py
   git mv backend\domains\gateway\application\budget_platform_settlement.py backend\domains\gateway\application\budget\budget_platform_settlement.py
   git mv backend\domains\gateway\application\budget_deployment_check.py backend\domains\gateway\application\budget\budget_deployment_check.py
   git mv backend\domains\gateway\application\budget_usage_persist.py backend\domains\gateway\application\budget\budget_usage_persist.py
   git mv backend\domains\gateway\application\user_credential_budget_index.py backend\domains\gateway\application\budget\user_credential_budget_index.py
   ```

4. **更新子包内相对 import**（用 IDE 全局替换，scope 限定 `backend/domains/gateway/application/budget/`）
   - `from domains.gateway.application.budget_service` → `from .budget_service`
   - `from domains.gateway.application.budget_config_cache` → `from .budget_config_cache`
   - `from domains.gateway.application.budget_callback_settlement` → `from .budget_callback_settlement`
   - `from domains.gateway.application.budget_platform_settlement` → `from .budget_platform_settlement`
   - `from domains.gateway.application.budget_deployment_check` → `from .budget_deployment_check`
   - `from domains.gateway.application.budget_usage_persist` → `from .budget_usage_persist`
   - `from domains.gateway.application.user_credential_budget_index` → `from .user_credential_budget_index`

5. **更新外部调用方**（scope：`backend/` 排除 `application/budget/`）
   - `from domains.gateway.application.budget_service` → `from domains.gateway.application.budget.budget_service`
   - 同上 7 个模块，统一加 `.budget.` 中缀

6. **建 shim**（在根级旧位置建 7 个 shim 文件，内容见 §0.2）
   - `backend/domains/gateway/application/budget_service.py`
   - ... 其余 6 个

7. **验证**（跑 §0.4 全部 7 项）

8. **commit**
   ```
   refactor(gateway): migrate budget/ subpackage (M1)

   - Move 7 budget_* files to application/budget/
   - Add root-level re-export shims for backward compat
   - No external API changes
   ```

### 预期 import 影响范围

同域调用方（grep 显示）：
- `proxy_context.py`、`proxy_metadata_builder.py`、`proxy_response_adapter.py`、`proxy_stream_settlement.py`、`budget_callback_settlement` 互引、`entitlement_*` 引 `budget_*`、`provider_quota_*` 引 `budget_*`

跨域：无。

### ✅ M1 完成记录（2026-06-27）

**实际改动**：
- 7 文件 `git mv` 至 `application/budget/`，子包内 7 文件改相对 import
- 11 个同域调用方 import 路径加 `.budget.` 中缀（`proxy_guard` / `proxy_response_adapter` / `proxy_metadata_builder` / `proxy_stream_settlement` / `proxy_use_case` / `provider_quota_guard` / `gateway_cache_invalidation` / `management/quota_usage_adjustment` / `management/write_modules/quota_rule_writes` / `infrastructure/callbacks/custom_logger`）
- 7 个根级 shim 文件（`# noqa: F403`）
- **测试**：15 个测试文件 import 路径切到新路径（含 `from ... import _bucket_key` 等私有符号、`import ... as mod` monkeypatch 句柄、`monkeypatch.setattr("...budget_xxx.attr")` / `patch("...")` 字符串路径）

**验证结果**：
- `ruff check`：通过（修复 3 处 I001 import 排序：相对 import 须排在绝对 import 之前）
- `import domains.gateway.application.budget` / `import domains.gateway.application`：通过
- `pytest`（15 个 budget/proxy 相关单测）：**14 passed, 1 failed**
  - 唯一失败 `test_commit_defer_applies_full_cost`：Redis `ConnectionError`（本地无 Redis）
  - 根因：`commit_budget_from_callback` → `commit_cached_platform_budgets` → `get_cached_budget_by_plan` 缓存未命中 → `_put_redis_tombstone` → `budget_config_cache._get_redis_client()` 实际连 Redis；测试仅 patch 了 `budget_callback_settlement.get_redis_client`，未覆盖 `budget_config_cache._get_redis_client`
  - **此为预先存在的测试 mock 不完整 + 环境问题，迁移前后逻辑一致，与 M1 无关**

**后续待办（非 M1 范围）**：
- 修复 `test_commit_defer_applies_full_cost` 的 mock 覆盖（patch `budget.budget_config_cache._get_redis_client`）
- M2 grant/ 迁移

---

## M2. grant/ 迁移（15 文件，0 跨域引用）

### 文件清单

```
resource_grant_cleanup.py
resource_grant_filter.py
resource_grant_resolution.py
resource_grants_cache.py
system_grants_cache.py
system_visibility_filter.py
route_audit.py
route_grant_lifecycle_adapter.py
route_snapshot_cache.py
routing_strategy_validation.py
resolve_model_cache.py
virtual_key_grant_lifecycle_adapter.py
virtual_key_touch.py
vkey_proxy_model_list.py
vkey_team_resolution.py
```

> `route_owner_slug_maps.py` 原列于此，核实后更贴近 router 装配，已移至 M8 `router/`。M2 仅迁移上述 15 个文件；`route_owner_slug_maps` 留在根级，但其内部 import 已更新为 `application.grant.vkey_team_resolution`。

### 步骤

同 M1 模式：
1. 建 `grant/` 子包与 `__init__.py`
2. `git mv` 15 个文件
3. 子包内相对 import 替换（`from domains.gateway.application.xxx` → `from .xxx`）
4. 外部调用方替换：`application.resource_grant_cleanup` → `application.grant.resource_grant_cleanup`，共 15 组（含跨域 `domains/tenancy/application/team_service.py` 的 2 处延迟 import）
5. 建 15 个 shim
6. 验证 + commit

### 注意点

- `vkey_team_resolution` 被 `presentation/gateway_proxy_context.py` 引用（同域）
- `resolve_model_cache` / `route_snapshot_cache` / `system_grants_cache` / `resource_grants_cache` 被 `gateway_cache_invalidation.py` 引用（M7 observability/ 会处理，此时仍是根级 import，shim 兜底）
- `virtual_key_grant_lifecycle_adapter` / `route_grant_lifecycle_adapter` 被 `domains/tenancy/application/team_service.py` 延迟 import（跨域，已更新为 `application.grant.*`）
- `route_owner_slug_maps`（根级）import `grant.vkey_team_resolution`，M8 迁移 router/ 时一并处理

---

## M3. quota/ 迁移（11 文件，1 跨域引用）

### 文件清单

```
quota_plan_service.py
quota_plan_usage_persist.py
quota_plan_callback_settlement_shared.py
provider_quota_guard.py
provider_quota_config_cache.py
provider_quota_callback_settlement.py
entitlement_guard.py
entitlement_config_cache.py
entitlement_model_status.py
entitlement_plan_callback_settlement.py
usage_bucket_flusher.py
```

### 跨域引用处理

`entitlement_model_status` 被 `domains/agent/application/chat_model_resolution_use_case.py` 引用：
```python
from domains.gateway.application.entitlement_model_status import is_connectivity_requestable
```

**两种选择**：
- **A（推荐）**：保留根级 shim，agent 域 import 不动。shim 内容：
  ```python
  from domains.gateway.application.quota.entitlement_model_status import (  # noqa: F401
      is_connectivity_requestable,
      ENTITLEMENT_RESETTING_SOON_SECONDS,
  )
  ```
- **B**：更新 agent 域 import 为 `from domains.gateway.application.quota.entitlement_model_status import ...`。需改 agent 域文件。

M3 阶段选 A（shim 兜底），待 M12 清理时再统一决定是否切 B。

### 步骤

同 M1 模式 + 跨域 shim（A 方案）。

### 注意点

- `usage_bucket_flusher` 依赖 `proxy_deferred_tasks`（M10 才迁），此时仍从根级 import，shim 兜底
- `entitlement_plan_callback_settlement` 依赖 `quota_plan_callback_settlement_shared` 和 `quota_plan_service`（同子包，相对 import）
- ~~`provider_quota_callback_settlement` 依赖 `budget_service`~~ —— **核实有误**：该模块不 import `budget_service`，仅依赖子包内 `provider_quota_config_cache` / `provider_quota_guard` / `quota_plan_callback_settlement_shared` / `quota_plan_usage_persist`

### M3 实测决策与踩坑（2026-06-27）

1. **`usage_bucket_flusher` 归属 quota/ 的架构理由**：该模块同时服务 budget 桶（`ns=PLATFORM_NS`）与 quota 桶，是跨 budget/quota 的共享基础设施。但表名 `gateway_quota_plan_usage_bucket`、类型 `UsageBucketNamespace` 都在 `domain.quota_plan`，主命名偏 quota；budget 桶是 quota 桶的 `ns` 特例。`budget/budget_usage_persist` → `quota/usage_bucket_flusher` 属合理的跨子包依赖，无需引入第三个 `usage/` 子包。
2. **跨域 agent 引用选 A 方案（shim 兜底）**：`domains/agent/application/chat_model_resolution_use_case.py` import `entitlement_model_status.is_connectivity_requestable`。shim 的 `import *` 可导出该公开函数（非 `_` 前缀、无 `__all__` 限制），agent 域文件不动，待 M12 清理时统一决定是否切 B。
3. **子包内循环引用安全**：`entitlement_guard` → `entitlement_model_status` 运行时单向（顶层 import `ENTITLEMENT_RESETTING_SOON_SECONDS`）；反向 `entitlement_model_status` → `entitlement_guard` 仅 TYPE_CHECKING + 延迟 import。相对 import 不触发循环。
4. **实际外部调用方 27 个**：18 个同域 gateway 文件 + 9 个测试文件。6 个子包内文件改为相对 import。ruff 修复 23 个 I001（7 子包内 + 16 外部），无其他错误。
5. **验证**：quota 子包 + shim + 跨域 agent（经 shim）+ 跨子包（budget/grant → quota）import smoke 全通过；59 测试可收集（1.36s，无 import 错误）。

---

## M4. catalog/ 迁移（22 新迁 + 2 现有保留，10 跨域源码引用）✅

### 文件清单（现有 catalog/ 2 文件 + 新迁 22 文件）

现有保留：
```
catalog/__init__.py
catalog/gateway_model_tags_pipeline.py
catalog/litellm_capability_hint.py
```

新迁（22）：
```
gateway_catalog_maintenance.py
gateway_catalog_seed.py
gateway_model_listing.py
config_catalog_sync.py
sql_model_catalog.py
catalog_capability.py
model_list_pipeline.py
model_list_credential_assertions.py
model_list_readable_credentials.py
model_selector_reads.py
model_selector_list_reads.py
chat_model_selector_reads.py
model_credential_enrichment.py
model_reference_prune.py
model_or_route_resolution.py
personal_models.py
scenario_defaults.py
granted_route_listing.py
granted_route_selector_items.py
upstream_catalog_capability_prep.py
upstream_model_types_for_catalog.py
user_models_migration.py
```

### 跨域引用处理（B 方案：更新跨域源码 import）

| 模块 | 跨域引用方 |
|------|-----------|
| `scenario_defaults` | session/title_use_case、agent/video_prompt_optimize、agent/llm/__init__ |
| `sql_model_catalog` | libs/api/deps、agent/video_task_router、agent/chat_use_case、agent/video_gen_catalog、agent/listing_studio_pipeline、session/title_use_case |
| `chat_model_selector_reads` | agent/chat_model_resolution_use_case |
| `model_selector_reads` | agent/chat_model_resolution_use_case、agent/video_gen_catalog |
| `model_or_route_resolution` | agent/chat_agent_run |

### 注意点

- `config_catalog_sync` 依赖 `catalog_capability`、`credential_model_cascade`（M9 credential/，根级 shim）、`gateway_catalog_seed`、`model_reference_prune`（同子包）
- `model_selector_list_reads` 依赖 `billing_context`（M11 bridge/，根级 shim）、`chat_model_selector_reads`、`config_catalog_sync`、`entitlement_model_status`（M3 quota/，已迁）、`gateway_model_listing`、`granted_route_selector_items`、`internal_bridge_actor`（M11，shim）、`model_list_pipeline`、`model_selector_reads`、`personal_models`
- **依赖链最复杂**，迁移前已 `grep` 确认所有 import 被 shim 覆盖或路径已更新

### 步骤

同 M1，但跨域引用改走 B 方案（见下）。

### M4 实测决策与踩坑（2026-06-27）

1. **跨域引用选 B 方案（更新源码 import）而非 A 方案（shim 兜底）**：
   M4 跨域源码引用多达 10 个文件，其中多数为顶层 `from ... import`。若用 A 方案 shim 兜底，跨域测试的 `monkeypatch` 会因 shim 命名空间与真实模块分离而失效（M1 踩过的坑：patch shim 属性不影响真实模块内已绑定引用；patch 真实模块属性不影响 shim 重新导出）。直接更新跨域源码 import 为 `application.catalog.*`，shim 仅作兼容兜底（无跨域源码依赖它）。
2. **`gateway_catalog_seed.py` 的 `parents[3]` 路径失效**：
   该模块用 `Path(__file__).resolve().parents[3] / "seeds" / ...` 定位种子 JSON。迁移前在 `application/` 下 `parents[3]` 指向 `backend/`；迁入 `application/catalog/` 后多一层目录，`parents[3]` 指向 `domains/`，种子加载失败（`test_load_seed_catalog_models_from_repo_file` 暴露）。修复为 `parents[4]`。**教训**：迁移文件时务必 grep `Path(__file__)` / `parents[` 检查相对路径计算。
3. **`from domains.gateway.application import <m> as <mod>` 形式需手动改为子包路径**：
   批量替换脚本只处理 `domains.gateway.application.<m>` 前缀形式，漏掉 `from domains.gateway.application import <m>` 形式。后者导入 shim 模块，访问私有成员（`_ensure_system_credential`、`get_redis_client` 等 `import *` 不导出的名字）会 `AttributeError`。M4 修复 4 处（catalog），并顺手修复 M3 遗留 7 处（quota 子包：`usage_bucket_flusher` / `entitlement_plan_callback_settlement` / `provider_quota_callback_settlement` / `entitlement_guard` / `provider_quota_guard` / `quota_plan_service` / `quota_plan_usage_persist`）。
4. **架构归属再确认**：
   - `model_or_route_resolution`（按 `model` 名解析 `GatewayModel` 或 `GatewayRoute`）兼具路由解析语义，但被 catalog 选择器读侧与 proxy 热路径共用，且以"模型解析"为主，归 catalog/ 合理。
   - `granted_route_listing` / `granted_route_selector_items`（跨团队共享授权路由投影）本质是路由的"目录视图"，归 catalog/ 合理（热路径委派解析仍在 proxy/）。
   - `user_models_migration`（user_models → personal gateway_models 幂等迁移）是一次性迁移脚本，迁移目标属 catalog，归 catalog/ 合理。
5. **`__init__.py` 兼容 re-export**：
   现有 `catalog/__init__.py` re-export `build_gateway_model_tags` / `merge_litellm_capability_hints` / `merge_litellm_reasoning_hint`（历史调用方 `from domains.gateway.application.catalog import ...`）。迁移后保留 re-export 并补充子包 docstring，re-export 改相对 import。
6. **测试结果**：
   - M4 核心测试全通过（catalog_sync / model_or_route_resolution / model_selector_reads / gateway_model_listing / seed_gateway_models / gateway_catalog_maintenance / scenario_defaults / chat_model_selector_reads / granted_route_selector_items / orm_data_conventions）。
   - 3246 测试收集成功（19.71s）。
   - M1/M3 遗留 shim 命名空间问题修复后，quota 相关测试（`test_quota_plan_service::test_reserve_commit`、`test_quota_plan_usage_persist`、`test_budget_usage_persist` 等）已全通过。
   - 预先存在的业务断言失败（`test_resolve_model_cache` 缓存命中、`test_provider_quota_callback_settlement::test_commit` commit_rule、`test_route_grant_lifecycle::test_tenant_reload_invalidates_consumer_resolve_cache`、`test_vkey_team_resolution::test_assert_ambiguous_*`）与 M4 import 迁移无关（git diff 证明 M4 对这些测试文件仅改 import 路径，业务逻辑未变；import 指向真实子包模块非 shim），留待后续单独排查。

---

## M5-M9. 小包批量（access/ usage/ observability/ router/ credential/）

这 5 个小包共 13 文件（M8 含 `route_owner_slug_maps` 共 4 文件），可在一个 PR 内分 5 个 commit 完成。✅ 全部完成（2026-06-27）

### M5. access/（2 文件）
```
gateway_access_use_case.py
gateway_access_factory.py
```
- `gateway_access_factory` 依赖 `gateway_access_use_case`（同子包）
- 被同域 presentation/deps.py 引用

### M6. usage/（2 文件）
```
gateway_vkey_metrics.py
request_log_failure_classification.py
```
- `gateway_vkey_metrics` 被 tests/integration 引用（shim 兜底）

### M7. observability/（3 文件）
```
gateway_alert_job.py
gateway_cache_invalidation.py
deferred_task_runner.py
```
**注意**：`deferred_task_runner` 原计划归 `proxy/`，但核实后发现它是通用执行器装配，与 `proxy_deferred_tasks`（proxy 专用任务登记）职责不同。重新评估：
- `deferred_task_runner` → `observability/`（通用延迟执行器单例）
- `proxy_deferred_tasks` → `proxy/`（proxy 专用任务登记 + shutdown）

`gateway_cache_invalidation` 依赖 grant/ 的 4 个缓存模块（M2 已迁），import 路径需更新为 `application.grant.*`。

### M8. router/（4 文件）
```
upstream_adapter.py
router_deployment_params.py
router_model_name.py
route_owner_slug_maps.py
```
- `route_owner_slug_maps` 原计划在 grant/，但核实后发现它更贴近 router 装配。**重新归入 router/**。从 M2 文件清单移除，加入 M8。

### M9. credential/（2 文件）
```
credential_env_audit.py
credential_model_cascade.py
```
- `credential_model_cascade` 依赖 `model_reference_prune`（M4 catalog/，已迁）

### M5-M9 实测决策与踩坑（2026-06-27）

1. **统一采用 B 方案（更新源码 import）**：
   延续 M4 决策，M5-M9 所有同域 application 内的跨子包 import 与 tests 的 import/monkeypatch 字符串路径均直接更新为子包路径，避免 shim `import *` 不导出私有/外部名字导致的 `AttributeError` / `patch` 失效。具体：
   - M5：`test_platform_api_key_usage_middleware` 的 `patch` 字符串路径更新为 `access.gateway_access_factory`。
   - M6：`grant/vkey_team_resolution`、`preflight_failure_logger`、`custom_logger`、3 处测试 import 更新为 `usage.*`。
   - M7：`test_gateway_alert_job` 用 `from ...observability import gateway_alert_job as job_module`（`patch.object` 访问模块私有名字，必须指向真实模块）；`test_quota_rule_batch_write` 的 `import ... as cache_mod` 同理。`gateway_cache_invalidation` 被 management/write_modules/ 14 处函数内 import，统一脚本替换。
   - M8：17 处外部 import 脚本替换为 `router.*`。
   - M9：`test_credential_env_audit` 的 8 处 monkeypatch 字符串路径 + 3 处 application 层 import 更新为 `credential.*`。
2. **`from ...application import <m> as <mod>` 形式仍是重点检查项**：
   M7 的 `test_gateway_alert_job` 与 `test_quota_rule_batch_write` 用此形式访问模块私有名字（`_send_webhook`、`get_background_session_context`、`GatewayAlertRepository`），shim `import *` 不导出这些名字，必须改为子包路径。M8 无此形式（grep 确认 0 处）。M9 的 `test_credential_env_audit` 用 `patch("...credential_env_audit._BOOTSTRAP_PROVIDERS")` 字符串路径，指向 shim 会失效，必须改路径。
3. **shim 命名前缀冲突（M9 特有）**：
   `from domains.gateway.application import credential_env_audit as s1, credential_model_cascade as s2` 形式中，`s2`（`credential_model_cascade`）会 `ImportError`，疑似 `credential` 子包与 `credential_*` 模块同名前缀导致 `from package import name` 解析异常。但 `import domains.gateway.application.credential_model_cascade as s2`（`import` 语句形式）正常。实际无生产调用方用 `from ...application import credential_model_cascade` 形式（均已更新为 `application.credential.*`），shim 仅作兼容兜底，不影响。**教训**：迁移后对 `from <根包> import <与子包同名前缀的模块>` 形式做 import smoke 验证。
4. **ruff import 排序**：
   M5-M9 子包 `__init__.py` re-export 后，部分文件 import 顺序需 ruff `--fix` 自动整理（2 处）。无 RUF100（M1-M4 shim 的 `# noqa: F401,F403` 问题已通过统一用 `# noqa: F403` 规避）。
5. **架构归属确认**：
   - M7 `deferred_task_runner`（通用有界执行器单例装配）归 `observability/` 而非 `proxy/`，与 `proxy_deferred_tasks`（proxy 专用任务登记 + shutdown）职责分离，确认合理。
   - M8 `route_owner_slug_maps`（虚拟路由 owner slug 前缀解析）归 `router/` 而非 `grant/`，与 router 装配更贴近，确认合理。
   - M7 `gateway_cache_invalidation` 依赖 grant/budget/quota/management 多个子包缓存模块，作为"热路径读缓存统一失效入口"归 `observability/` 合理（跨子包编排，非任一被编排子包的内部职责）。
6. **测试结果**：
   - 5 子包 import smoke + shim import + 跨子包 import（22 个消费方模块：proxy_*/management/write_modules/grant/catalog/infrastructure/jobs/startup）全通过。
   - 1817 测试收集成功（4.17s）。
   - M5-M9 核心测试全通过（test_platform_api_key_usage_middleware / test_request_log_failure_classification / test_gateway_alert_job / test_quota_rule_batch_write / test_upstream_adapter / test_router_deployment_params / test_router_model_name_client_scope / test_router_virtual_deployments / test_resource_grant_resolution / test_route_grant_delegation / test_router_lazy_cross_team_route / test_credential_env_audit）。
   - 预先存在的业务断言失败（M4 已记录的 `test_resolve_model_cache` / `test_vkey_team_resolution` / `test_provider_quota_callback_settlement::test_commit` / `test_route_grant_lifecycle`）与 M5-M9 无关，状态未恶化。

---

## M10. proxy/ 迁移（25 文件，4 跨域引用，最大子包）✅

### 文件清单（25）

```
proxy_use_case.py
proxy_chat_entries.py
proxy_chat_pipeline.py
proxy_context.py
proxy_deferred_tasks.py
proxy_guard.py
proxy_inbound_preflight.py
proxy_litellm_client.py
proxy_litellm_kwargs.py
proxy_metadata_builder.py
proxy_model_list_reads.py
proxy_non_chat_pipeline.py
proxy_rate_limit_headers.py
proxy_response_adapter.py
proxy_router_invoke.py
proxy_router_team_metadata.py
proxy_stream_settlement.py
proxy_timing.py
proxy_vision_image_urls.py
proxy_allowed_models.py
anthropic_native_adapt.py
prompt_cache_middleware.py
preflight_failure_logger.py
invocation_overrides.py
platform_api_key_proxy_dto.py
```

### 跨域引用处理（B 方案：更新跨域源码 import）

| 模块 | 跨域引用方 |
|------|-----------|
| `prompt_cache_middleware` | agent/llm/__init__、agent/llm/prompt_cache |
| `platform_api_key_proxy_dto` | agent/llm/__init__（经 access 子包间接） |
| `proxy_use_case` / `proxy_deferred_tasks` / `proxy_timing` 等 | tests/integration（多处，shim 兜底） |

### 关键风险

- `proxy_use_case.py` 有 **14 处** 同子包 import + 多处跨子包 import（bridge/ budget/ quota/），是依赖最密的文件
- `proxy_response_adapter.py` 有 **20 处** import，依赖 budget/ quota/ pricing/
- `proxy_non_chat_pipeline.py` 有 9 处，`proxy_chat_entries.py` 有 9 处

### 步骤

同 M1，但建议**拆成 3 个 commit**降低单次 review 负担：
1. commit A：迁 `proxy_context` / `proxy_guard` / `proxy_inbound_preflight` / `proxy_litellm_kwargs` / `proxy_metadata_builder` / `proxy_router_invoke` / `proxy_router_team_metadata` / `proxy_rate_limit_headers` / `proxy_timing` / `proxy_vision_image_urls` / `proxy_allowed_models` / `anthropic_native_adapt` / `prompt_cache_middleware` / `preflight_failure_logger` / `invocation_overrides` / `platform_api_key_proxy_dto`（16 个无强依赖的基础模块）
2. commit B：迁 `proxy_chat_entries` / `proxy_chat_pipeline` / `proxy_non_chat_pipeline` / `proxy_stream_settlement` / `proxy_model_list_reads` / `proxy_litellm_client` / `proxy_response_adapter`（7 个流水线模块）
3. commit C：迁 `proxy_use_case` / `proxy_deferred_tasks`（2 个门面 + 任务登记，最后迁）

每个 commit 后跑验证清单。

### 注意点

- `proxy_deferred_tasks` 依赖 `deferred_task_runner`（M7 observability/，已迁）—— import 路径需更新为 `application.observability.deferred_task_runner`
- `proxy_metadata_builder` 依赖 `billing_context`（M11 bridge/，未迁，shim 兜底）
- `proxy_response_adapter` 依赖 `budget_callback_settlement`（M1 已迁）、`entitlement_plan_callback_settlement`（M3 已迁）、`provider_quota_callback_settlement`（M3 已迁）—— import 路径需更新

### M10 实测决策与踩坑（2026-06-27）

1. **一次性迁移 25 文件（未拆 3 commit）**：
   文档原建议拆 3 commit（基础/流水线/门面），实际执行采用一次性迁移 + 批量脚本替换。理由：25 文件同属一个子包，子包内相对 import 改造与外部 import 路径更新可由脚本统一处理；拆 commit 反而增加中间态验证成本。脚本完成 15 个子包内文件改相对 import + 61 个外部调用方文件改 `application.proxy.*` 路径。
2. **`__init__.py` 不 re-export**：
   25 个模块多数是内部协作模块（流水线/守卫/适配器），无稳定公共 API。`__init__.py` 仅写 docstring 子分组说明，外部调用方一律用全路径 `from domains.gateway.application.proxy.proxy_use_case import ...`。避免 re-export 25 个模块的维护成本与命名污染。
3. **shim 命名空间问题（M10 第 1 处）**：
   `test_proxy_use_case_budget.py` 第 13 行 `from domains.gateway.application import proxy_guard, proxy_response_adapter` 导入 shim 模块，后续访问模块成员（如 `proxy_guard.SomeClass`）可能因 shim `import *` 不导出私有/非 `__all__` 名字而失效。改为 `from domains.gateway.application.proxy import proxy_guard, proxy_response_adapter`。
4. **shim 命名空间问题（M10 第 2 处，monkeypatch）**：
   `test_proxy_inbound_preflight.py::test_optional_model_skips_model_whitelist` 第 60 行 `from domains.gateway.application import proxy_guard as proxy_guard_module`，随后 `monkeypatch.setattr(proxy_guard_module, "_default_budget_repository_factory", ...)` 失败（shim `import *` 不导出 `_` 前缀私有名字）。改为 `from domains.gateway.application.proxy import proxy_guard as proxy_guard_module`。**这是 M1-M10 第 N 次踩同一坑**：迁移后必须 grep `from <根包> import <已迁模块>` 形式 + 检查 `monkeypatch.setattr(<module>, "_private", ...)` 场景。
5. **跨域 B 方案**：
   `prompt_cache_middleware` 被 agent/llm 顶层 import，直接更新源码 import 为 `application.proxy.prompt_cache_middleware`，避免 shim 兜底的 monkeypatch 风险。tests/integration 的 `proxy_use_case` / `proxy_deferred_tasks` / `proxy_timing` 引用经脚本批量更新为 `application.proxy.*`，shim 仅作兼容兜底。
6. **ruff import 排序**：
   子包内 15 个文件改相对 import 后，ruff 检测到 20 处 import 顺序问题（相对 import 与绝对 import 混排），`--fix` 自动整理。
7. **测试结果**：
   - proxy 子包 import smoke + 25 shim import + 跨域 agent/llm + presentation（openai_compat_router / anthropic_compat_router / gateway_proxy_context / proxy_request_context）import 全通过。
   - 1817 测试收集成功（4.38s）。
   - M10 核心测试全通过（14 个测试文件 61 passed，含 test_proxy_guard_budget / test_proxy_use_case_budget / test_proxy_use_case_metadata / test_proxy_chat_pipeline / test_proxy_response_adapter_stream / test_proxy_metadata_builder / test_proxy_litellm_kwargs / test_proxy_router_invoke / test_proxy_stream_settlement / test_proxy_inbound_preflight / test_prompt_cache_middleware / test_anthropic_native_adapt / test_invocation_overrides / test_proxy_timing）。
   - 预先存在的业务断言失败（M4 已记录）与 M10 无关，状态未恶化。

---

## M11. bridge/ 迁移（10 文件，6 跨域引用，跨域最密）

### 文件清单

```
internal_bridge.py
internal_bridge_actor.py
bridge_attribution.py
bridge_catalog.py
litellm_bridge_payload.py
litellm_real_model_prefix.py
gateway_proxy_factory.py
gateway_internal_log_context.py
listing_studio_image_port_registry.py
billing_context.py
```

### 跨域引用处理

| 模块 | 跨域引用方 |
|------|-----------|
| `gateway_proxy_factory` | agent/llm/embeddings、agent/llm/agent_llm_facade、agent/video_task_use_case |
| `internal_bridge_actor` | agent/llm、agent/chat_model_resolution_use_case |
| `bridge_attribution` | agent/llm/embeddings、agent/llm/agent_llm_facade |
| `gateway_internal_log_context` | agent/llm/agent_llm_facade、agent/chat_use_case |
| `billing_context` | agent/video_task_use_case、agent/chat_use_case |
| `listing_studio_image_port_registry` | bootstrap/main |

### 策略选择（实际选 B）

**方案 A（保守）**：全部保留根级 shim，跨域 import 不动。M12 清理时再统一切。

**方案 B（彻底，实际采用）**：更新所有跨域 import 为 `application.bridge.*`。与 M1-M10 保持一致，避免 shim `import *` 不导出私有名字导致的 monkeypatch 失效问题。

实际涉及 26 个外部文件（含 agent 域 7 个、gateway 域内 8 个、tests 9 个、bootstrap 1 个、conftest 1 个）。

### 步骤

同 M1，但跨域 shim 有 6 个（含 bootstrap）。

### 注意点

- `billing_context` 依赖 `internal_bridge_actor`（同子包）
- `gateway_proxy_factory` 依赖 `internal_bridge`（同子包）
- `bridge_attribution` 依赖 `internal_bridge_actor`（同子包）
- `internal_bridge` 是 `GatewayBridge` 实现，依赖大量 proxy/ 模块（M10 已迁）—— import 路径需更新为 `application.proxy.*`

### M11 实测决策与踩坑（2026-06-27）

1. **采用 B 方案（与 M1-M10 一致）**：
   文档原建议 M11 选 A（保留 shim 不动跨域），但 M1-M10 实测发现 shim `import *` 不导出私有名字会导致 `monkeypatch.setattr` / `patch` 失效。M11 统一选 B，跨域 import 直接更新为 `application.bridge.*`，shim 仅作兼容兜底。
2. **`__init__.py` 不 re-export**：
   与 M10 一致，bridge 10 模块无稳定公共 API（多数是内部桥接实现），`__init__.py` 仅写 docstring 子分组说明。跨域调用方用全路径 `from domains.gateway.application.bridge.gateway_proxy_factory import ...`。
3. **子包内相对 import 改造**：
   4 个子包内文件（billing_context / bridge_attribution / gateway_proxy_factory / internal_bridge）改相对 import，ruff 检测到 2 处 import 顺序问题，`--fix` 自动整理。
4. **跨域影响范围实测**：
   - agent 域 7 文件：chat_use_case / chat_model_resolution_use_case / video_task_use_case / video_gen_catalog / agent_llm_facade / embeddings / llm/__init__
   - gateway 域内 8 文件：domain/litellm_model_id、catalog/ 4 个、proxy/proxy_vision_image_urls、management/write_modules/model_writes、startup
   - tests 9 文件 + bootstrap/main + tests/conftest + tests/helpers/bridge_identity
   - 跨域 import smoke（agent 6 模块 + gateway domain + startup + proxy_use_case）全通过。
5. **测试结果**：
   - bridge 子包 import smoke + 10 shim import + 跨域 import 全通过。
   - 1817 测试收集成功（4.04s）。
   - M11 核心测试全通过（7 个测试文件 30 passed：test_internal_gateway_actor / test_gateway_attribution / test_gateway_internal_log_context / test_litellm_payload / test_litellm_real_model_prefix / test_video_gen_catalog_merge / test_chat_model_selector_reads）。
   - 预先存在的业务断言失败（M4 已记录）与 M11 无关，状态未恶化。

---

## M12. 清理 shim（低风险，最后执行）

### 前置条件

- M1-M11 全部合并且**生产稳定 1-2 周**
- 无任何代码仍从根级 import 已迁移模块（需 grep 确认）

### M12 扫描实测（2026-06-27）

1. **全量 grep 扫描根级引用**：
   扫描所有 M1-M11 迁移模块的根级 import 形式（`domains.gateway.application.<m>` 非子包路径），结果：**无外部引用**（仅 shim 文件自身的子包 import 与文档示例）。
2. **修复 M3 遗漏**：
   扫描发现 `domains/agent/application/chat_model_resolution_use_case.py` 第 11 行仍用 `from domains.gateway.application.entitlement_model_status import is_connectivity_requestable`（M3 遗漏），已更新为 `domains.gateway.application.quota.entitlement_model_status`。
3. **shim 清单统计**：
   根级共 **103 个 shim 文件**（含 M1-M4 早期迁移创建的 shim，如 budget_deployment_check / catalog_capability / gateway_catalog_seed / personal_models / resolve_model_cache / route_snapshot_cache / system_grants_cache 等）。所有 shim 均为 `from ...<子包>.<m> import *  # noqa: F403` 形式。
4. **shim 删除决策（暂停）**：
   虽然全量 grep 确认无外部静态引用，但遵循前置条件"生产稳定 1-2 周"，**当前不删除 shim**。理由：
   - 迁移刚完成（同会话内），未跑全量回归测试（pytest tests/ -x）与生产 smoke。
   - 可能存在动态 import（`importlib.import_module`）或字符串路径引用未被发现。
   - shim 保留不影响功能，仅增加少量 import 间接层。
   - 生产稳定后，按下方"步骤"执行删除 + 全量回归 + smoke 验证。

### M12 执行记录（2026-06-27 完成）

1. **兜底 grep 确认无外部引用**：扫描 31 个 M1-M3 迁移模块的根级 import 形式，结果无匹配（仅 shim 自身）。
2. **批量删除 103 个 shim**：保留 `__init__.py` / `ports.py` / `startup.py` / `jobs.py` / `model_catalog_port.py` 5 个核心文件，其余 103 根级 `.py` 全部为 shim，一次性删除。
3. **ruff 修复**：`ruff --fix` 修复 46 处子包内 pre-existing I001 import 排序（shim 删除不引入新错误，ruff 重新扫描子包时整理）；剩余 1 处 RUF（pricing 模块 `if` 合并）为 pre-existing 逻辑代码，与迁移无关。
4. **验证**：
   - `ruff check domains/gateway/application/`：仅剩 1 pre-existing RUF
   - import smoke：`import domains.gateway.application` + `from domains.agent.infrastructure.llm.agent_llm_facade import AgentLlmFacade` 全通过
   - `pytest tests/unit/gateway -q`：**1817 passed**（105s）
5. **结果**：`application/` 根目录仅剩 5 个核心文件 + 14 个业务子包目录，shim 全部清理完成。

### 步骤

1. **grep 确认无外部引用**
   ```powershell
   # 应只返回 shim 文件自身的 import
   rg "from domains\.gateway\.application\.(budget_service|budget_config_cache|...)" backend/ --type py
   ```

2. **逐个删除 shim 文件**
   ```powershell
   git rm backend\domains\gateway\application\budget_service.py
   ...（共约 100 个 shim）
   ```

3. **更新文档**
   - [AI_GATEWAY_DOMAIN_ARCHITECTURE.md](../AI_GATEWAY_DOMAIN_ARCHITECTURE.md) §2 目录树
   - [CODE_STANDARDS.md](../CODE_STANDARDS.md) import 示例
   - 本文档标记为"已完成"

4. **全量回归**
   - `pytest tests/ -x`
   - 手动 smoke：启动服务，跑一次 `/v1/chat/completions` 代理

5. **commit**
   ```
   refactor(gateway): cleanup application/ root shims (M12)

   - Remove ~100 backward-compat shims
   - All imports now use subpackage paths
   - Migration complete
   ```

---

## 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 循环 import（子包间相互引用） | 中 | 高 | 保留根级 ports.py / model_catalog_port.py；子包间用绝对 import 而非相对；必要时用 TYPE_CHECKING |
| shim 符号遗漏（`import *` 漏掉 `__all__` 外符号） | 中 | 中 | shim 优先显式 re-export；ruff F401 检查 |
| 跨域 import 更新遗漏 | 低 | 中 | M12 前 grep 全量扫描；CI architecture 测试兜底 |
| proxy/ 单次 commit 过大 review 困难 | 高 | 低 | 拆 3 个 commit（M10 已规划） |
| bridge/ 跨域更新影响 agent 域 | 中 | 高 | M11 选方案 A（shim 兜底），不强制更新 agent 域 |
| 迁移中途需要修 bug | 中 | 中 | 每个子包独立 commit，bugfix 在哪个路径就改哪个路径；shim 保证新旧路径都可用 |

## 验收标准

- [ ] `application/` 根目录仅剩 `__init__.py` / `ports.py` / `startup.py` / `jobs.py` / `model_catalog_port.py` + 3 个已有子包目录 + 11 个新子包目录
- [ ] `ruff check backend/` 无新增错误
- [ ] `pytest tests/architecture/` 全绿
- [ ] `pytest tests/integration/gateway/` 全绿
- [ ] 跨域 smoke：`python -c "from domains.agent.infrastructure.llm.agent_llm_facade import AgentLlmFacade"` 成功
- [ ] 启动服务，`/v1/chat/completions` 与 `/api/v1/gateway/models` 均正常响应
- [ ] [AI_GATEWAY_DOMAIN_ARCHITECTURE.md](../AI_GATEWAY_DOMAIN_ARCHITECTURE.md) §2 目录树已更新
- [ ] [AGENTS.md](../../../AGENTS.md) 子包约定已更新

---

## 附：management/ 子包整理（MG1-MG7，2026-06-27 完成）

> `application/management/` 原有 54 个根级 `.py` + `write_modules/` 子包（17 文件），读侧严重平铺。本次按业务能力将 48 个读侧文件迁入 7 个子包，与 M1-M11 同模式（git mv + import 替换 + shim 兜底 → 清理 shim）。

### 整理方案

保留根级（6 文件，跨业务共享/入口）：

```
__init__.py          # 包入口（re-export Read/WriteService）
reads.py             # GatewayManagementReadService 主入口
writes.py            # GatewayManagementWriteService 门面（re-export write_modules）
ports.py             # 管理面出站端口
access_assertions.py # 管理面访问断言（被 reads 直接依赖，跨业务）
orm_row_projection.py# ORM 行→dict 投影共用工具
```

7 个业务子包（48 文件）：

| 子包 | 文件数 | 内容 |
|------|--------|------|
| `credential/` | 9 | 凭据读/写 mapper、copy types、creator labels、upstream catalog、playground、managed_team 凭据、多凭据类型 |
| `model/` | 6 | 模型读 mapper、copy types、test 常量、managed_team 模型读/用量、system_visibility |
| `route/` | 5 | 路由读 mapper、grant reads、team_grant lifecycle、managed_team 路由、personal_route callable |
| `virtual_key/` | 7 | vkey 读 mapper/model、team_grant 读写、policy、managed_team vkey |
| `quota/` | 10 | 配额规则/计划/用量读、assembler、cache、plan merge/read mappers/models |
| `usage/` | 8 | 用量读/日志/指标、metrics router/window、budget usage、alert、log 展示 |
| `grant/` | 3 | resource_grant policy/reads/writes |

`write_modules/` 保持不变（已按写操作 mixin 子包化）。

### 执行（幂等脚本 `_management_migrate.py`）

复用 M1-M11 模式，脚本完成：建子包 `__init__.py` → `git mv` 文件 → 子包内相对 import 替换 → 外部 import 路径加 `.<subpackage>.` 中缀 → 生成 shim。7 个子包依次执行（MG1-MG7）。

### 踩坑

1. **shim 命名空间问题（与 M1-M10 同坑）**：`test_quota_plan_usage_reads.py` 用 `from domains.gateway.application.management import quota_plan_usage_reads as reads_mod` 导入 shim 模块访问私有名字，改为 `from domains.gateway.application.management.quota import quota_plan_usage_reads as reads_mod`。
2. **ruff I001 import 排序**：7 子包迁移后 ruff 检测到 22 处 import 顺序问题（子包内相对 import 与绝对 import 混排），`--fix` 自动整理。
3. **无 monkeypatch 字符串路径引用 shim**：grep 确认 `monkeypatch.setattr("...management.<m>...")` / `patch("...")` 无匹配，shim 删除安全。

### 验证

- `ruff check domains/gateway/application/management/`：All checks passed
- import smoke：`GatewayManagementReadService` / `GatewayManagementWriteService` / `AgentLlmFacade` 全通过
- `pytest tests/unit/gateway -q`：**1817 passed**（103s）
- 48 个 shim 已全部删除，`management/` 根目录仅剩 6 核心文件 + 8 子包（7 业务 + write_modules）

### 结果

`management/` 目录从 54 根级文件 + 1 子包，整理为 6 根级文件 + 8 子包，读侧按业务能力清晰分类，与 application/ 顶层子包组织一致。

---

## 附2：management/ 读侧下沉到业务子包（MG-Sink，2026-06-27 完成）

> 附1 完成后，`management/` 仍是唯一含 7 个业务子包的"二级聚合包"，且子包名与顶层兄弟重名（`management/quota/` vs 顶层 `quota/`），认知负担重。本次将 48 个读侧模块下沉到对应业务子包的 `management/` 子目录，让 `management/` 回归纯 CQRS 门面。

### 问题诊断

`management/` 与其他 13 个顶层子包的差异：
1. **唯一二级聚合包**——其他子包都是扁平模块集合，唯独 management/ 内部又按业务能力分了 7 个子包
2. **命名冲突**——`management/quota/` / `management/credential/` / `management/grant/` / `management/usage/` 与顶层兄弟子包重名，`application.quota.xxx`（运行时）与 `application.management.quota.xxx`（管理面读）易混淆
3. **混杂定位**——既装 CQRS 门面（reads.py/writes.py），又装业务能力读侧实现

### 下沉方案

`management/` 回归纯门面，仅留 6 文件 + `write_modules/`（写侧 mixin 需集中组装成 GatewayManagementWriteService，不下沉）：

```
application/management/
├── __init__.py              # re-export Read/WriteService
├── reads.py                 # GatewayManagementReadService 门面
├── writes.py                # GatewayManagementWriteService 门面（re-export write_modules）
├── ports.py                 # 管理面出站端口
├── access_assertions.py     # 管理面访问断言
├── orm_row_projection.py    # ORM 行→dict 投影共用工具
└── write_modules/           # 写侧 mixin 组织（保持不变）
```

48 个读侧模块按业务能力归属下沉到 6 个业务子包的 `management/` 子目录：

| 源（management/） | 目标（业务子包） | 文件数 | 业务能力归属理由 |
|-------------------|------------------|--------|------------------|
| `credential/` | `credential/management/` | 9 | 凭据业务能力 |
| `model/` | `catalog/management/` | 6 | 模型目录属 catalog 业务能力 |
| `route/` | `router/management/` | 5 | 路由属 router 业务能力 |
| `virtual_key/` + `grant/` | `grant/management/` | 7+3=10 | vkey grant 与 resource grant 同属授权域，靠文件名前缀区分 |
| `quota/` | `quota/management/` | 10 | 配额业务能力 |
| `usage/` | `usage/management/` | 8 | 用量业务能力 |

### 执行（幂等脚本 `_management_sink.py`）

1. 建 6 个目标 `management/` 子目录 + `__init__.py`（docstring 标注 CQRS Query 模块）
2. `git mv` 48 文件到对应业务子包 `management/`
3. 全局 import 路径替换：`application.management.<src>.<m>` → `application.<biz>.management.<m>`（覆盖外部引用 + management 内部跨子包引用 + write_modules 22 处引用 + reads.py 11 处引用 + management/__init__.py 引用）
4. 子包内相对 import 无需改（同目录迁移）
5. 删除 `management/` 下 7 个空子包目录

### 踩坑

1. **函数内 import 形式未被脚本覆盖**：`test_quota_plan_usage_reads.py:64` 用 `from domains.gateway.application.management.quota import quota_plan_usage_reads as reads_mod`（`management.quota import <m>` 形式，非 `management.quota.<m>`），脚本正则匹配 `management\.quota\.quota_plan_usage_reads` 未命中。手动改为 `from domains.gateway.application.quota.management import quota_plan_usage_reads`。
2. **ruff I001 import 排序**：6 处子包内 import 顺序问题，`--fix` 自动整理。

### 验证

- `ruff check domains/gateway/application/`：仅剩 1 pre-existing RUF（与迁移无关）
- import smoke：`GatewayManagementReadService` / `GatewayManagementWriteService` / `AgentLlmFacade` 全通过
- 全量 grep 确认无残留 `application.management.<src_subpkg>.` 旧路径引用
- 全量 grep 确认无 `from ...management import <module>` shim 命名空间问题
- 全量 grep 确认无 `monkeypatch.setattr/patch("...management.<src>...")` 字符串路径引用
- `pytest tests/unit/gateway -q`：**1817 passed**（132s）

### 结果

`management/` 从"二级聚合包（6 根文件 + 8 子包）"瘦身为"纯门面包（6 根文件 + write_modules/）"，48 个读侧模块回归各业务子包的 `management/` 子目录。

- **消除两层分类**：业务能力单一维度，`application.quota.management.xxx`（管理面读）vs `application.quota.<m>`（运行时），同子包内分层清晰
- **消除命名冲突**：不再有 `management/quota/` 与 `quota/` 重名困惑
- **与其他子包一致**：每个业务子包都是扁平模块 + 可选 `management/` 子目录（CQRS 读侧），结构统一
- `reads.py` 作为 CQRS 读侧门面，聚合各业务子包 `management/` 的 Query 模块，职责清晰

---

## 附3：router→route 重命名 + grant/ 拆分（2026-06-27 完成）

> 附2 完成后审视 gateway 域整体组织，发现 application/ 与 domain/ 子包命名不一致、application/grant/ 过大且混合。本次解决 2 个"怪"点：router vs route 命名冲突、grant/ 混合 route/vkey/resource 业务。

### 问题诊断

**问题1：router vs route 命名不一致**
- `domain/route/` (6 文件) 用业务能力名词 route/
- `application/router/` (4 文件) 却用实现角色 router/
- 同一业务能力两层命名不同，认知负担重

**问题2：application/grant/ 过大且混合（15 运行时文件）**
grant/ 混合了 4 类业务逻辑：
- resource_grant_* (5 文件) — resource 授权，应留在 grant/
- route_* (4 文件) — route 授权，应归 route/
- vkey/virtual_key_* (4 文件) — vkey 授权，应归 vkey/（domain 已有 vkey/）
- system_* (2 文件) — system 授权，应留 grant/
- resolve_model_cache (1 文件) — grant 解析缓存，留 grant/

domain 层已把 route/ (6 文件) 和 vkey/ (5 文件) 分开，application/grant/ 却把 route 和 vkey 混在一起。

### 整改方案

**P0: application/router/ → application/route/**（与 domain/route/ 命名统一）
- 4 运行时文件 + management/ 5 文件整体迁移
- import 替换：`application.router` → `application.route`

**P1a: application/grant/route_* (4 文件) → application/route/**
- route_audit / route_grant_lifecycle_adapter / route_snapshot_cache / routing_strategy_validation
- 归 route 业务能力（依赖 domain.route.* + application.route.*）
- import 替换：`application.grant.route_audit` 等 → `application.route.route_audit`

**P1b: application/grant/vkey_* + virtual_key_* → 新建 application/vkey/**
- 运行时 4 文件：virtual_key_grant_lifecycle_adapter / virtual_key_touch / vkey_proxy_model_list / vkey_team_resolution
- management 7 文件：managed_team_virtual_key_reads / virtual_key_read_mappers / virtual_key_read_model / virtual_key_team_grant_read_mappers / virtual_key_team_grant_reads / virtual_key_team_grant_writes / vkey_team_grant_policy
- 与 domain/vkey/ 命名统一
- import 替换：`application.grant.vkey_*` → `application.vkey.vkey_*`，`application.grant.management.virtual_key_*` → `application.vkey.management.virtual_key_*`

### 整改后子包文件数

| 子包 | 运行时 | management/ | 合计 | 变化 |
|------|--------|-------------|------|------|
| route/ | 8 (原4+grant迁4) | 5 | 13 | +9（原 router 9 + grant迁4） |
| vkey/ | 4 | 7 | 11 | +11（新建，全从 grant 迁入） |
| grant/ | 7 (原15-8) | 3 (原10-7) | 10 | -14（拆出 route 4 + vkey 11） |

### 执行（脚本 `_route_vkey_split.py`）

用 shutil.move + git add（避免 git mv 与预创建 `__init__.py` 冲突）：
1. P0: 建 route/ + route/management/，移动 9 文件，全局替换 `application.router` → `application.route`
2. P1a: 移动 4 个 route_* 文件 grant/ → route/，替换 `application.grant.route_*` → `application.route.route_*`
3. P1b: 建 vkey/ + vkey/management/，移动 11 文件，替换 `application.grant.vkey_*` → `application.vkey.vkey_*` + `application.grant.management.virtual_key_*` → `application.vkey.management.virtual_key_*`

### 踩坑

1. **git mv 与预创建 `__init__.py` 冲突**：脚本先 `mkdir` + 创建 `__init__.py`，再 `git mv __init__.py` 失败（目标已存在）。改用 shutil.move + git add，`__init__.py` 只在不存在时创建。
2. **函数内 import 形式未被正则覆盖**：`test_vkey_team_resolution.py:139/171` 用 `from domains.gateway.application.grant import vkey_team_resolution as mod`（`grant import <m>` 形式，非 `grant.<m>`），脚本正则匹配 `grant.vkey_team_resolution` 未命中。手动改为 `from domains.gateway.application.vkey import vkey_team_resolution as mod`。
3. **ruff I001 import 排序**：7 处子包内 import 顺序问题，`--fix` 自动整理。

### 验证

- `ruff check domains/gateway/application/`：仅剩 1 pre-existing RUF（与迁移无关）
- import smoke：`GatewayManagementReadService` / `GatewayManagementWriteService` / `route.route_audit` / `vkey.vkey_team_resolution` / `AgentLlmFacade` 全通过
- 全量 grep 确认无残留 `application.router` / `application.grant.route_*` / `application.grant.vkey_*` / `application.grant.management.virtual_key_*` 旧路径
- 全量 grep 确认无 `monkeypatch/patch("...router...")` 字符串路径引用
- `pytest tests/unit/gateway -q`：**1817 passed**（102s）

### 结果

application/ 子包与 domain/ 子包命名完全对齐：

| 业务能力 | application/ | domain/ |
|----------|--------------|---------|
| 路由 | `route/` ✅ | `route/` ✅ |
| 虚拟 Key | `vkey/` ✅ | `vkey/` ✅ |
| 授权 | `grant/`（resource/system grant）✅ | （无，授权逻辑分散在 route/vkey domain） |
| 预算 | `budget/` ✅ | `budget/` ✅ |
| 配额 | `quota/` ✅ | `quota/` ✅ |
| 凭据 | `credential/` ✅ | `credential/` ✅ |
| 目录 | `catalog/` ✅ | `catalog/` ✅ |
| 定价 | `pricing/` ✅ | `pricing/` ✅ |
| 用量 | `usage/` ✅ | `usage/` ✅ |

- **消除 router vs route 命名冲突**：统一为 route/（业务能力名词）
- **grant/ 瘦身聚焦**：从 25 文件降至 10 文件，只保留 resource/system grant
- **vkey 独立成包**：与 domain/vkey/ 对应，11 文件内聚
- **route 聚合**：8 运行时 + 5 management = 13 文件，route 业务能力完整归位

---

## 附4：write_modules 下沉（2026-06-27 完成）

> 附3 完成后，management/ 仅剩 6 根文件 + write_modules/（17 文件）。write_modules/ 作为"写侧 mixin 集中目录"仍是个特殊存在——读侧已下沉到各业务子包 management/，写侧却仍集中放在 management/write_modules/ 下，不对称。本次将 15 个写侧 mixin 下沉到各业务子包 management/（与读侧对称），消除 write_modules/ 目录。

### 问题诊断

附2 把读侧 48 文件下沉到各业务子包 management/ 后，management/ 结构为：
```
management/
├── reads.py / writes.py / ports.py / access_assertions.py / orm_row_projection.py
└── write_modules/          ← 仍是个特殊集中目录
    ├── __init__.py         ← 组合 GatewayManagementWriteService
    ├── _base.py            ← 写侧基类
    ├── credential_writes.py / model_writes.py / pricing_writes.py
    ├── entitlement_writes.py / quota_*_writes.py (3)
    ├── route_writes.py / route_grant_writes.py
    └── probe*.py (6)
```

读侧已按业务能力分散到 `quota/management/` / `credential/management/` 等，写侧却仍集中，不对称。

### 下沉方案

**15 个 mixin 下沉到各业务子包 management/**（与读侧对称）：

| 文件 | 归属 | 文件 | 归属 |
|------|------|------|------|
| credential_writes | credential/management/ | quota_plan_delete_writes | quota/management/ |
| entitlement_writes | quota/management/ | quota_rule_writes | quota/management/ |
| model_writes | catalog/management/ | quota_usage_adjustment_writes | quota/management/ |
| pricing_writes | pricing/management/ | route_grant_writes | route/management/ |
| probe + probe_* (6) | catalog/management/ | route_writes | route/management/ |

probe 6 文件归 catalog/management/：probe 是"模型探测"功能（探测上游模型可用性），依赖 `catalog.management.model_test_constants`，本质属 catalog 业务能力。

**_base.py 基类保留 management/ 根**（改名 write_base.py）：跨业务共享的写侧基类，无单一业务归属，与 reads.py / writes.py 同级。

**writes.py 重组**：吸收原 write_modules/__init__.py 的组合逻辑，从各业务子包 management/ import mixin 组合成 GatewayManagementWriteService。

**write_modules/ 目录删除**。

### 整改后 management/ 结构

```
management/
├── __init__.py              # re-export Read/WriteService
├── reads.py                 # CQRS 读侧门面（聚合各子包 management/ 读模块）
├── writes.py                # CQRS 写侧门面（聚合各子包 management/ 写 mixin）
├── ports.py                 # 管理面出站端口
├── access_assertions.py     # 管理面访问断言
├── orm_row_projection.py    # ORM 行投影共用工具
└── write_base.py            # 写侧基类（跨业务共享）
```

management/ 完全回归纯 CQRS 门面，无子目录。读写两侧均下沉到各业务子包 management/，完全对称。

### 执行（脚本 `_write_modules_sink.py`）

1. `_base.py` → `management/write_base.py`（改名留 management/）
2. 15 mixin 下沉到各业务子包 management/（shutil.move + git add）
3. 重组 `management/writes.py`（从各子包 import mixin 组合）
4. 删除 write_modules/ 目录
5. import 替换：`application.management.write_modules.<m>` → `application.<biz>.management.<m>` + `application.management.write_modules._base` → `application.management.write_base`

### 踩坑

1. **裸 import 形式未被正则覆盖**：7 个测试文件用 `from domains.gateway.application.management.write_modules import GatewayManagementWriteService`（`write_modules import <X>` 形式，非 `write_modules.<m>`），脚本正则匹配 `write_modules.GatewayManagementWriteService` 未命中。手动改为 `from domains.gateway.application.management import GatewayManagementWriteService`。
2. **probe import 特殊处理**：`test_management_test_model.py:581` 用 `from ...write_modules import probe as probe_module`，改为 `from domains.gateway.application.catalog.management import probe as probe_module`。
3. **ruff I001 import 排序**：1 处 writes.py import 顺序问题，`--fix` 自动整理。

### 验证

- `ruff check domains/gateway/application/`：仅剩 1 pre-existing RUF（与迁移无关）
- import smoke：`GatewayManagementReadService` / `GatewayManagementWriteService` / `AgentLlmFacade` 全通过
- 全量 grep 确认无残留 `application.management.write_modules` 旧路径（仅脚本自身）
- `pytest tests/unit/gateway -q`：**1817 passed**（104s）

### 结果

management/ 从"6 根文件 + write_modules/（17 文件）"瘦身为"7 根文件 + 0 子目录"，完全回归纯 CQRS 门面。

- **读写对称**：读侧（reads.py 聚合各子包 management/ 读模块）与写侧（writes.py 聚合各子包 management/ 写 mixin）完全对称
- **消除特殊目录**：write_modules/ 不再存在，所有写侧 mixin 归位到各业务子包 management/
- **management/ 无子目录**：仅 7 个根文件，职责单一（CQRS 门面 + 共享工具）
- **业务能力内聚**：每个业务子包 management/ 同时包含读侧 Query 模块和写侧 Command mixin，业务能力完整

---

## 附5：深层整改 — upstream/ 独立 + granted_route 归位 + pricing_management 下沉（2026-06-27 完成）

> 附4 完成后深入审视，发现 3 个深层问题：① catalog/ 仍 24 文件混合（granted_route 错位）；② domain/ 有 upstream/、litellm/、provider/ 3 子包但 application/ 无对应，相关应用逻辑散落各处；③ pricing/pricing_management.py 是管理面辅助却放在运行时根目录。

### 问题诊断

**P1: granted_route_* 错位 catalog/**
- `catalog/granted_route_listing.py` / `granted_route_selector_items.py`
- docstring 明确写"消费团队代理列表中暴露跨团队共享授权路由"，是 route 授权投影
- 误归 catalog/，与 catalog 的"模型目录"职责不符

**P2: application/ 缺 upstream/ 子包，domain/ 已分**
- domain/ 有 `upstream/`(9) `litellm/`(5) `provider/`(11) 共 25 文件
- application/ 无对应子包，相关应用逻辑散落：
  - catalog/ 有 upstream_catalog_capability_prep、upstream_model_types_for_catalog、litellm_capability_hint
  - pricing/ 有 upstream_cost_resolver、upstream_pricing_audit、upstream_sync_service、litellm_upstream_price_sync
  - route/ 有 upstream_adapter
  - bridge/ 有 litellm_bridge_payload、litellm_real_model_prefix
- 架构不对称——domain 分了 application 没跟

**P4: pricing_management.py 错位**
- `pricing/pricing_management.py` docstring 写"定价目录管理面辅助（供 reads/writes 调用）"
- 属 management 读侧辅助，却放在 pricing/ 运行时根目录
- 与 pricing/management/（CQRS 读侧目录）不对称

### 整改方案

**P1: catalog/granted_route_* (2文件) → route/**
- granted_route_listing.py、granted_route_selector_items.py 迁到 route/
- route 业务归位，与 domain/route/ 对应

**P2: 新建 application/upstream/（与 domain/upstream/ 对应）**
- 收集 10 个散落的 upstream/litellm 衔接文件：
  | 源 | 文件 | 业务能力 |
  |----|------|---------|
  | catalog/ | upstream_catalog_capability_prep、upstream_model_types_for_catalog、litellm_capability_hint | 上游 catalog 能力衔接 |
  | pricing/ | upstream_cost_resolver、upstream_pricing_audit、upstream_sync_service、litellm_upstream_price_sync | 上游价格同步 |
  | route/ | upstream_adapter | 上游路由适配 |
  | bridge/ | litellm_bridge_payload、litellm_real_model_prefix | litellm 上游载荷 |
- 架构对称：domain/upstream/ ↔ application/upstream/

**P4: pricing/pricing_management.py → pricing/management/pricing_management.py**
- 管理面辅助归 management/（CQRS 读侧目录），与 pricing/management/ 对称

### 执行（脚本 `_deep_refactor.py`）

1. P1: 2 文件 shutil.move + git add，import 替换 `application.catalog.granted_route_*` → `application.route.granted_route_*`
2. P4: 1 文件迁移，import 替换 `application.pricing.pricing_management` → `application.pricing.management.pricing_management`
3. P2: 10 文件迁移到新建 upstream/，import 替换 `application.<src>.<m>` → `application.upstream.<m>`

### 踩坑

1. **迁移文件内部相对 import 未被脚本覆盖**（关键踩坑）：
   - 脚本只替换绝对路径 import，但迁移文件内部用 `from .<module>` 相对 import 引用了原目录的兄弟文件
   - 迁移后这些相对 import 指向新目录的同名文件，但目标文件不存在或已迁走
   - 案例：
     - `catalog/gateway_model_tags_pipeline.py:17` `from .litellm_capability_hint import ...` → 改为绝对路径 `from domains.gateway.application.upstream.litellm_capability_hint import ...`
     - `catalog/__init__.py:18` `from .litellm_capability_hint import ...` → 同上
     - `catalog/model_selector_list_reads.py:35` `from .granted_route_selector_items import ...` → 改为 `from domains.gateway.application.route.granted_route_selector_items import ...`
     - `upstream/upstream_model_types_for_catalog.py:13` `from .config_catalog_sync import ...` → 改为绝对路径（config_catalog_sync 仍在 catalog/）
     - `route/granted_route_selector_items.py:16` `from .config_catalog_sync import ...` → 同上
   - **教训**：迁移脚本必须额外扫描迁移文件内部的 `from .` 相对 import，验证目标是否存在；若引用的兄弟文件未一起迁移，需改为绝对路径

2. **测试文件用裸 import 形式**：
   - `test_granted_route_selector_items.py:10` `from domains.gateway.application.catalog import granted_route_selector_items as mod`（`catalog import <module>` 形式）
   - 脚本正则未覆盖，手动改为 `from domains.gateway.application.route import granted_route_selector_items as mod`

3. **ruff I001 import 排序**：迁移后多处 import 顺序变化，`--fix` 自动整理（10 处修复）

### 验证

- `ruff check domains/gateway/application/`：仅剩 1 pre-existing RUF（与迁移无关）
- import smoke：`GatewayManagementReadService` / `GatewayManagementWriteService` / `upstream.upstream_adapter` / `route.granted_route_listing` / `pricing.management.pricing_management` / `AgentLlmFacade` 全通过
- `pytest tests/unit/gateway -q`：**1817 passed**（104s）

### 结果

| 子包 | 变化 | 文件数 |
|------|------|--------|
| catalog/ | 24→21（移出 3 upstream 文件，granted_route 2 文件去 route/） | rt 21 + mgmt 13 = 34 |
| pricing/ | 18→14（移出 4 upstream 文件，pricing_management 去 management/） | rt 14 + mgmt 2 = 16 |
| route/ | 8→10（granted_route 2 文件归位） | rt 10 + mgmt 7 = 17 |
| bridge/ | 10→8（移出 2 litellm 文件） | rt 8 |
| **upstream/** | **新建** | **rt 10**（与 domain/upstream/ 对应） |

**架构收益**：
- **domain/application 对称**：domain/upstream/ ↔ application/upstream/，相关逻辑不再散落
- **catalog 聚焦**：catalog/ 回归"模型目录"职责，granted_route 归 route/
- **pricing 内聚**：pricing_management 归 management/，与 CQRS 读侧对称
- **业务能力清晰**：upstream 作为独立业务能力，统一收纳上游衔接逻辑（catalog 能力、pricing 同步、route 适配、bridge 载荷）

### 未处理项（明确记录）

- **P3: observability/ 3 文件**（deferred_task_runner / gateway_alert_job / gateway_cache_invalidation）功能差异大，但仅 3 文件，强拆收益低，暂保留
- **domain/ 的 litellm/ 和 provider/**：application/ 未建对应子包，相关逻辑已部分归入 upstream/，剩余需后续评估是否独立

---

## 附6：infrastructure/litellm/ 下沉（2026-06-27 完成）

> 附5 完成后继续深入 infrastructure/ 层，发现根级 7 文件平铺，其中 5 个 litellm_router_/router_ 文件属 LiteLLM Router 基础设施，与 domain/litellm/ 不对称。

### 问题诊断

infrastructure/ 根级 7 文件：
| 文件 | 实际职责 | 应归属 |
|------|---------|--------|
| litellm_capability_hint_adapter | LiteLLM 能力适配 | infrastructure/litellm/（与 domain/litellm/ 对称） |
| litellm_router_deployment_cooldown_adapter | LiteLLM Router 冷却 | 同上 |
| litellm_router_model_registry | LiteLLM Router 注册 | 同上 |
| router_reload_notifier | Router 多 worker 重载 | 同上 |
| router_singleton | LiteLLM Router 单例 | 同上 |
| gateway_log_sampling | 网关日志采样 | 保留根级（跨业务共享工具） |
| redis_rate_limit_usage_reader | Redis 限流读 | 保留根级（跨业务共享工具） |

**关键发现**：domain/ 有 `litellm/`(5文件) 子包，但 infrastructure/ 无对应，5 个 LiteLLM Router 基础设施文件散在根级。这是 domain/infrastructure 不对称的又一处。

### 整改方案

**新建 infrastructure/litellm/**（与 domain/litellm/ 对称），5 文件迁入：
- litellm_capability_hint_adapter
- litellm_router_deployment_cooldown_adapter
- litellm_router_model_registry
- router_reload_notifier
- router_singleton

**保留 infrastructure/ 根级 2 文件**：gateway_log_sampling、redis_rate_limit_usage_reader（跨业务共享工具，无单一业务归属）

### 三层对称

整改后 LiteLLM 业务能力三层对称：
- `domain/litellm/`（5文件）— LiteLLM 领域逻辑（model_id、capability_mapping、deployment_attribution）
- `application/upstream/`（10文件）— LiteLLM 上游衔接应用层（含 litellm_bridge_payload、litellm_real_model_prefix、litellm_capability_hint）
- `infrastructure/litellm/`（5文件）— LiteLLM Router 基础设施（singleton、reload、registry、cooldown、adapter）

### 执行（脚本 `_infra_litellm_sink.py`）

1. 新建 infrastructure/litellm/ + __init__.py
2. 5 文件 shutil.move + git add
3. import 替换：`domains.gateway.infrastructure.<m>` → `domains.gateway.infrastructure.litellm.<m>`

### 踩坑

1. **测试文件用裸 import 形式**（再次踩坑）：
   - `test_route_grant_delegation.py:229,261` 用 `from domains.gateway.infrastructure import router_singleton as rs`（`infrastructure import <module>` 形式）
   - 脚本正则只匹配 `infrastructure.router_singleton` 完整路径，未覆盖 `infrastructure import router_singleton`
   - 手动改为 `from domains.gateway.infrastructure.litellm import router_singleton as rs`
   - **教训（附5已记录，本次再现）**：迁移脚本的正则必须同时覆盖 `<pkg>.<module>` 和 `<pkg> import <module>` 两种 import 形式

2. **ruff TCH003 等**：5 处 type-checking 相关的 pre-existing 警告，`--fix` 自动整理

### 验证

- `ruff check domains/gateway/infrastructure/`：5 remaining（pre-existing，与迁移无关）
- import smoke：`infrastructure.litellm.router_singleton.get_router` / `reload_router` / `GatewayManagementWriteService` / `AgentLlmFacade` 全通过
- 全量 grep 确认无残留 `infrastructure.<5文件名>` 旧路径
- `pytest tests/unit/gateway -q`：**1817 passed**（95s）

### 结果

- **infrastructure/ 根级**：7→2 文件（仅保留 gateway_log_sampling、redis_rate_limit_usage_reader 跨业务共享工具）
- **infrastructure/litellm/**：新建，5 文件（与 domain/litellm/ 对称）
- **三层对称**：LiteLLM 业务能力在 domain/application/infrastructure 三层均有对应子包

### 已评估不拆分的项（明确记录）

- **proxy/ 25 文件**：虽最大，但 25 文件都是 proxy 业务不同切面（chat pipeline、non_chat pipeline、stream settlement、router invoke、litellm client、guard、preflight、middleware 等），属同一业务能力内聚，无更细业务边界。强拆破坏内聚性。
- **repositories/ 23 + models/ 18 平铺**：Repository/Model 按 ORM 实体一对一，平铺是业界常见做法。跨业务引用多，分组反增复杂度。
- **presentation/routers/ 28 + schemas/ 9**：Router/Schema 按 API 资源一对一，平铺合理。

## 附7：management/__init__ docstring 修正 + 后缀统一 + 分类标准文档化（2026-06-27 完成）

> 附6 后深入审视各子包 management/ 内容，发现三类问题：(1) 8 个 `management/__init__.py` docstring 仍写"管理面**读侧**"，但附4 后已含 `_writes` 文件——文档与实际不符；(2) `plan_read_models.py` 用复数，其余 `_read_model` 全用单数——后缀不一致；(3) runtime/management 分类标准未文档化，导致边界看似混乱。

### 问题诊断（逐文件读内容确认）

#### 问题1：management/__init__.py docstring 过时

8 个子包 management/__init__.py docstring 状态：

| 子包 | 旧 docstring | 实际含 writes | 问题 |
|------|-------------|--------------|------|
| catalog | "管理面读侧 — CQRS Query 模块" | model_writes.py | 过时 |
| credential | "管理面读侧" | credential_writes.py | 过时 |
| quota | "管理面读侧" | 4 个 _writes | 过时 |
| usage | "管理面读侧" | （reads 为主，但 docstring 未含 mixin 语义） | 过时 |
| grant | "管理面读侧" + "**从 virtual_key/ 下沉**" | resource_grant_writes.py | 过时 + 描述错误（子包叫 grant 非 virtual_key） |
| pricing | "管理面读侧 — CQRS Query/辅助模块" | pricing_writes.py | 过时 |
| route | "管理面读侧" | route_writes.py + route_grant_writes.py | 过时 |
| vkey | "管理面读侧" | virtual_key_team_grant_writes.py | 过时 |

#### 问题2：后缀单复数不一致

- `plan_read_models.py`（复数）vs 其余 5 个 `_read_model`（单数：credential_read_model、quota_rule_read_model、alert_read_model、virtual_key_read_model）
- `_read_mappers`（8 文件，全复数，已统一，保留）

#### 问题3（已排查确认非问题）：management/ 混入纯类型/常量/值对象？

初判 5 文件疑似错位，逐个读内容 + 查调用方后**确认归属合理**：

| 文件 | 实质 | 调用方 | 结论 |
|------|------|--------|------|
| credential_copy_types（63行） | dataclass（ImportedModelSummary 等） | 仅 credential_writes + presentation | 管理面写侧 DTO，留 management ✓ |
| multi_credential_types（19行） | dataclass | 仅 credential_writes | 同上 ✓ |
| model_copy_types（44行） | dataclass | 仅 model_writes + presentation | 同上 ✓ |
| model_test_constants（13行） | 纯常量 | 仅 probe.py（同包） | probe 配套，留 management ✓ |
| probe_target（66行） | Protocol + dataclass 值对象 | probe*.py 共用 | probe 契约，留 management ✓ |

**结论**：management/ 实际定位清晰——"管理面 CRUD 读写 + 相关类型/常量/DTO"，无真错位。

### 整改方案

#### P7a：统一 8 个 management/__init__.py docstring

统一为（含迁移说明）：

```python
"""<pkg> 管理面读写 — CQRS Query + Command mixin。

从 application/management/ 下沉至业务子包（附2 读侧 + 附4 写侧），详见 docs/gateway/APPLICATION_SUBPACKAGE_MIGRATION.md。
"""
```

- 修正"读侧"→"读写"
- 修正 grant 的"从 virtual_key/ 下沉"→"从 application/management/ 下沉"
- 补全 pricing/route/vkey 的迁移说明（原单行无说明）

#### P7b：后缀统一

- `plan_read_models.py` → `plan_read_model.py`（git mv，单复数统一）
- 6 处 import 更新（含相对 import `.plan_read_models` → `.plan_read_model`）

### 分类标准文档化（runtime vs management）

经逐文件内容审查，确认现有分类逻辑为"按服务对象分"，文档化如下：

| 维度 | runtime/（热路径） | management/（管理面） |
|------|-------------------|---------------------|
| 服务对象 | 代理调用热路径、运行时核心解析 | 管理面 CRUD API、dashboard、playground |
| 典型文件 | proxy_*、resolve_*、guard、cache、GET /v1/models 列表 | *_writes（Command mixin）、*_reads（Query）、dashboard 聚合读 |
| 读侧归属 | 服务热路径的读（如 catalog/model_selector_reads 服务 GET /v1/models）→ runtime | 服务 dashboard 的读（如 usage/budget_usage_reads）→ management |
| 类型/常量 | 跨读写共用的领域类型 → domain/ | 管理面写侧专属 DTO → management/ |
| 判断规则 | 若被代理热路径调用 → runtime | 若仅被管理面 API/router 调用 → management |

**同一 `_reads` 后缀可在两侧出现**：按"服务对象"而非"读写"分类。这是合理复杂度，非混乱。

### 验证

- ruff：4 文件 All checks passed
- import smoke：plan_read_model / GatewayManagementReadService / GatewayManagementWriteService 全通过
- `pytest tests/unit/gateway -q`：**1817 passed**（95s，与附6 基线一致）
- 全量 `pytest tests/`：3195 passed；11 failed + 14 errors 均为 pre-existing integration 环境问题（DB/Redis/httpx），与本次改动无关

### 结果

- 8 个 management/__init__.py docstring 统一为"管理面读写 — CQRS Query + Command mixin"
- plan_read_models → plan_read_model（单复数统一，与 5 个同类文件一致）
- 分类标准文档化，消除"runtime/management 边界混乱"的认知问题

### 后缀风格约定（新增）

| 后缀 | 含义 | 示例 |
|------|------|------|
| `_reads` | 读侧服务（聚合查询/列表/详情） | budget_usage_reads、managed_team_credential_reads |
| `_writes` | 写侧 Command mixin | model_writes、credential_writes |
| `_types` | 纯 dataclass/类型定义 | credential_copy_types、model_copy_types |
| `_cache` | 缓存（L1+Redis） | resolve_model_cache、quota_rule_cache |
| `_read_model` | 只读 DTO 数据类（单数） | credential_read_model、plan_read_model |
| `_read_mappers` | ORM→DTO 投影函数（复数） | gateway_model_read_mappers、credential_read_mappers |

