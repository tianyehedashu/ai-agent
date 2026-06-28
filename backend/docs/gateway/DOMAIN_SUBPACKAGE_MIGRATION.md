# Gateway Domain 子包迁移计划

> 本文档是 [AI_GATEWAY_DOMAIN_ARCHITECTURE.md §2.2](../AI_GATEWAY_DOMAIN_ARCHITECTURE.md) 的可执行附录，给出 `domains/gateway/domain/` 按业务能力子包化的迁移步骤。
>
> **执行原则**：与 application 子包迁移一致（git mv + shim + import 替换）；一次一个子包；policies/ 解散并入对应业务子包；保留 types.py / errors.py 在根级。
>
> **进度**：D1–D14 全部完成 ✅（109 文件迁入 14 子包；根级 shim 与 policies/ 已清理）

## 0. 现状与目标

### 0.1 现状（109 文件，平铺严重）
- 根级 70 文件（含 types/errors 通用），跨 12+ 业务能力平铺
- `policies/` 39 文件，按"策略"技术关注点聚合，未按业务能力二次分组

### 0.2 目标态（按业务能力子包，与 application 子包对齐）

| 子包 | 文件数 | 含 policies/ | 说明 |
|------|--------|-------------|------|
| `budget/` | 5 | ✅ | 平台预算窗口、豁免、scope、upsert |
| `quota/` | 5 | ✅ | 套餐配额、周期锚点、窗口执法 |
| `credential/` | 10 | ✅ | 凭据 display/persist/probe/sync、团队访问、跨团队聚合 |
| `catalog/` | 16 | ✅ | 模型目录种子、能力、选择、注册表、deployment_weight |
| `route/` | 6 | ✅ | 路由 fallback、retry、snapshot、跨团队授权 |
| `upstream/` | 9 | — | 上游 profile/endpoint/policy、模型名规范化 |
| `vkey/` | 5 | — | 虚拟 Key 生成/访问、grant slug、proxy list、team prefix |
| `usage/` | 6 | — | 用量 axis/read_model、normalized_usage、margin、request_log_provider |
| `alert/` | 3 | ✅ | 告警聚合、规则快照、评估 |
| `pricing/` | 4 | ✅ | 定价计算、money、non_token_cost、visibility |
| `visibility/` | 6 | ✅ | 系统/资源/日志可见性、managed_team、gateway_admin |
| `proxy/` | 16 | ✅ | 代理策略、guardrail、PII、cache_hit、UA、header、stream、温度、思考、cooldown、invocation、anthropic_fields、vision |
| `provider/` | 11 | ✅ | 厂商适配：api_base/env/inference、agnes/dashscope/moonshot/volcengine、message_sanitize_base |
| `litellm/` | 5 | — | LiteLLM 适配：capability_mapping/credential_extra/deployment_attribution/model_id/router_registry |
| 根级保留 | 2 | — | types.py、errors.py（领域通用类型与错误层次） |
| **合计** | **109** | | |

### 0.3 通用约定

- **shim**：根级 `<m>.py` 保留 `from domains.gateway.domain.<子包>.<m> import *  # noqa: F403`；policies/ 下文件不建 shim（直接迁移，grep 确认无外部 `from ...domain.policies.<m>` 引用后删除）
- **import 更新（B 方案）**：跨域/同域外部引用直接更新为 `domain.<子包>.<m>`，避免 shim `import *` 不导出私有名字的 monkeypatch 失效问题（M1-M11 已验证）
- **相对 import**：子包内文件互相引用改为 `from .<m> import`
- **`__init__.py`**：仅 docstring 子分组说明，不 re-export（与 M10/M11 一致）
- **policies/ 解散**：`policies/<m>.py` → `<子包>/<m>.py`，policies/ 目录最终删除（D14）

## 1. 文件清单与归属

### D1. budget/（5 文件）
```
platform_budget_display.py
platform_budget_window.py
policies/budget_exemption_policy.py
policies/budget_scope_policy.py
policies/platform_budget_upsert_policy.py
```

### D2. quota/（5 文件）
```
quota_plan.py
period_reset_anchor.py
policies/quota_window_enforcement.py
policies/plan_quota_reset_anchor_policy.py
policies/quota_rule_visibility.py
```

### D3. credential/（10 文件）
```
credential_display.py
credential_persist.py
credential_probe.py
credential_sync_policy.py
team_credential_access.py
team_registry_credential_display.py
policies/credential_copy_policy.py
policies/credential_scope.py
policies/credential_model_cascade.py
policies/managed_team_credentials_policy.py
```

### D4. catalog/（16 文件）
```
catalog_seed_model.py
client_model_aliases.py
client_type.py
model_capability.py
model_selection_policy.py
model_types_tags.py
registry_model_types.py
scenario_defaults_policy.py
policies/model_copy_policy.py
policies/model_list_policy.py
policies/model_registry_scope.py
policies/model_selection.py
policies/chat_model_readiness.py
policies/team_model_access.py
policies/deployment_weight.py
policies/catalog_provider_availability.py
```

### D5. route/（6 文件）
```
fallback_chain.py
route_model_ref.py
route_retry_policy.py
route_snapshot.py
router_model_name.py
policies/route_grant_access.py
```

### D6. upstream/（9 文件）
```
upstream_call_shape_policy.py
upstream_catalog_policy.py
upstream_endpoint.py
upstream_model_name_normalize.py
upstream_policy.py
upstream_profile.py
upstream_profile_registry.py
upstream_registration_match.py
upstream_type_inference.py
```

### D7. vkey/（5 文件）
```
virtual_key_access.py
virtual_key_service.py
vkey_grant_slug_policy.py
vkey_proxy_list_policy.py
vkey_team_prefix_policy.py
```

### D8. usage/（6 文件）
```
usage_axis.py
usage_read_model.py
usage_statistics_breakdown.py
normalized_usage.py
margin_read_model.py
request_log_provider.py
```

### D9. alert/（3 文件）
```
alert_metric_aggregates.py
alert_rule_snapshot.py
policies/alert_evaluation.py
```

### D10. pricing/（4 文件）
```
pricing_calculator.py
money.py
policies/non_token_cost.py
policies/pricing_visibility.py
```

### D11. visibility/（6 文件）
```
visibility.py
policies/system_visibility.py
policies/resource_grant_visibility.py
policies/usage_log_visibility.py
policies/managed_team_resource_policy.py
policies/gateway_admin.py
```

### D12. proxy/（16 文件）
```
proxy_policy.py
proxy_rate_limit_port.py
proxy_ratelimit_headers.py
guardrail_policy.py
pii_redaction_policy.py
cache_hit_flag.py
coding_agent_ua.py
http_header_merge.py
stream_utils.py
temperature_policy.py
thinking_param.py
deployment_cooldown_port.py
policies/invocation_policy.py
policies/anthropic_only_request_fields.py
policies/vision_image_mime.py
policies/vision_image_url.py
```

### D13. provider/ + litellm/（16 文件）
```
# provider/（11）
provider_api_base.py
provider_env_catalog.py
provider_inference.py
policies/agnes_image.py
policies/dashscope_embedding.py
policies/moonshot_message_sanitize.py
policies/volcengine_direct.py
policies/volcengine_image.py
policies/volcengine_video.py
policies/volcengine_message_sanitize.py
policies/message_sanitize_base.py

# litellm/（5）
litellm_capability_mapping.py
litellm_credential_extra_keys.py
litellm_deployment_attribution.py
litellm_model_id.py
litellm_router_model_registry.py
```

### D14. policies/ 目录清理 + 根级 shim 清理 ✅
- 删除空的 `policies/` 目录（含 `__init__.py` 与 39 个 policy shim）
- 删除根级 68 个 shim 文件（grep 确认无 `from ...domain.<shim> import` / `from ...domain.policies.<m>` 引用）
- 根级保留 `types.py`、`errors.py`、`__init__.py`

## 4. 完成总结

| 项 | 结果 |
|----|------|
| 迁移文件 | 109（root 70 + policies 39）→ 14 子包 |
| 根级保留 | `types.py`、`errors.py`、`__init__.py` |
| shim 清理 | 68 根级 shim + 39 policies shim 全部删除 |
| 子包 smoke | 107 模块 import 通过 |
| 跨域 smoke | agent/gateway application/infrastructure import 通过 |
| 单元测试 | 1807 通过 / 10 失败（均 pre-existing 逻辑/mock 问题，非迁移引入） |
| 迁移引入修复 | 2 处测试 mock 路径（shim → 子包真实路径）：`test_vkey_team_resolution`、`test_proxy_entitlement_bucket_upsert` |

**最终目录结构**：
```
domains/gateway/domain/
├── __init__.py
├── types.py            # 领域通用类型
├── errors.py           # 领域错误层次
├── alert/              # 3 文件
├── budget/             # 5 文件
├── catalog/            # 16 文件
├── credential/         # 10 文件
├── litellm/            # 5 文件
├── pricing/            # 4 文件
├── provider/           # 11 文件
├── proxy/              # 16 文件
├── quota/              # 5 文件
├── route/              # 6 文件
├── upstream/           # 9 文件
├── usage/              # 6 文件
├── visibility/         # 6 文件
└── vkey/               # 5 文件
```

## 2. 执行顺序与风险

**顺序**：D1 → D2 → ... → D14（按业务能力逐步迁移）

**关键风险**：
- domain 被全代码库引用（application/infrastructure/presentation/agent 域），import 更新量大
- policies/ 解散后，`from domains.gateway.domain.policies.<m> import` 形式的引用需全量更新
- 部分文件名跨子包冲突（如 `credential_model_cascade` 在 application/credential 和 domain/policies 都有，迁移后 domain 侧为 `domain/credential/credential_model_cascade`，需注意区分）

**每个里程碑验证清单**：
1. `ruff check domains/gateway/domain/<子包>` 通过
2. 子包 import smoke：`importlib.import_module('domains.gateway.domain.<子包>.<m>')`
3. shim import smoke：`importlib.import_module('domains.gateway.domain.<m>')`
4. 跨域 import smoke：被 application/infrastructure/agent 引用的关键模块
5. `pytest tests/unit/gateway -q --co` 收集成功
6. 子包核心测试通过

## 3. 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| policies/ 解散后遗漏 `from ...domain.policies.<m>` 引用 | 中 | 中 | D14 前 grep 全量扫描；shim 不建（policies 直接迁移） |
| domain 被跨域引用量大，更新遗漏 | 中 | 中 | 批量脚本替换 + grep 验证 + CI 兜底 |
| 子包间循环 import | 低 | 高 | 子包间用绝对 import；必要时 TYPE_CHECKING |
| litellm/ 子包与 application 侧 litellm 引用混淆 | 低 | 低 | 命名清晰：domain.litellm.* vs application.proxy.litellm_* |
