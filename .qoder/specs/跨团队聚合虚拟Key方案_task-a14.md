# 跨团队聚合虚拟 Key 实施方案

> **状态（2026-06）**：后端 / 前端 / 单测与 `tests/integration/gateway/` 已落地；架构说明见 [AI_GATEWAY_DOMAIN_ARCHITECTURE.md §4.4.1](../../backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md)。P2：`GET /v1/models` 未合并 granted team 列表。

详细方案已写入 [.qoder/specs/multi-tenant-vkey.md](file:///e:/project/ai-agent/.qoder/specs/multi-tenant-vkey.md)，共 9 个 Task：

1. **数据库与迁移** — 新表 `gateway_virtual_key_team_grants`（仅 `(vkey_id, tenant_id)`，无 DB FK）+ 自洽 grant 回填 + Alembic `20260605_vkey_team_grants.py`
2. **鉴权链路接入 grants** — `VirtualKeyPrincipal` 加 `granted_team_ids`；`_gateway_principal_from_vkey_plain` 顺序 await 加载 grants；`assert_vkey_team_header_compatible` 放宽到"主属 ∪ grants"
3. **model 前缀派发（应用层纯函数）** — 新模块 `vkey_team_resolution.dispatch_vkey_model`，仅在 `slug ∈ vkey.granted_team_ids` 命中时识别 prefix，避免与 `vendor/model` 冲突；reserved slug 在 team_service 拦截
4. **Proxy 热路径接线（业务管线零侵入）** — dispatch 放 router 层（拿到 body 之后），重写 `proxy_body["model"]` + 设 `ctx.team_id = effective_team_id`；现有所有 `ctx.team_id` 调用点不动；关闭跨 grants 隐式 fallback
5. **管理 API（vkey owner 自助）** — 4 个 endpoints：list/grant/revoke/grantable-teams；权限严格私有（仅创建者本人）；system vkey 全拒
6. **离线清理任务** — `scripts/cleanup_stale_vkey_grants.py` set-based SQL + cron `*/5 * * * *`；`team_service.remove_member` 同步触发缩窗（热路径仍不查 membership）
7. **前端** — `VirtualKey.granted_team_ids` 类型扩展；列表页"跨 team 派发"列 + 抽屉；reveal 弹窗调用示例 hint；`features/gateway-keys/grants/` 子目录
7.5 **同名模型在多 team 的语义（本轮补强）** — [gateway_models](file:///e:/project/ai-agent/backend/domains/gateway/infrastructure/models/gateway_model.py#L102) `UniqueConstraint("tenant_id","name")` 保证同名模型在不同 team 是独立记录；无前缀=主属、显式 `slug/name` 消歧；隐式 fallback 已关；UI Banner 提示带 prefix；`gateway_vkey_ambiguous_model_invocations_total` 指标驱动 strict 模式切换
7.6 **模型自动导入边界声明（本轮补强）** — 本方案**不修改**导入路径；现有 7 道防线保留：probe support 四态 / 预检重名 / 唯一约束→409 / `normalize_upstream_model_id` / 领域异常可读化 / Exception 兑底 / 前端 50/个 chunk；reserved slug 只拦 team 创建/改名，不拦导入
8. **测试** — 单测 6 个文件 + 集成测试 6 个场景（dispatch / 审计落点 / 离线清理 / X-Team-Id 兼容 / system vkey / **多 team 同名模型**）
9. **部署与回滚** — schema → 后端 → 前端 → cron；自洽 grant 让旧客户端零回归；回滚顺序前端→后端→DB

## 关键架构判定（必读）

- **显式 Opt-In、默认不聚合**：主属 team 自洽 grant；其他 team **不会自动进**，需 vkey 创建者主动 `POST .../grants` 逐个选择（可多选）；`DELETE .../grants/{tenant_id}` 逐个撤销。“所属 5 个 team”不等于“一把 vkey 跨 5 个 team”。
- **dispatch 必须在 router 层**：FastAPI dependency 阶段尚未反序列化 body，前缀解析需要 body
- **业务管线零侵入**：通过让 `ctx.team_id == effective_team_id`，[proxy_litellm_client.py](file:///e:/project/ai-agent/backend/domains/gateway/application/proxy_litellm_client.py) / [proxy_metadata_builder.py](file:///e:/project/ai-agent/backend/domains/gateway/application/) / 审计 / 预算 / 限流全部不动
- **歧义解决**：仅当 slug ∈ vkey grants 时才识别为 team prefix；`openai/gpt-4o` 等 vendor 名字若不是某 team 的 slug 则继续走主属；reserved slug 列表硬编码兜底
- **创建者私有原则极致**：team owner/admin 不可见、不可撤销外来 grant，与现有 vkey 私有契约对齐
- **审计 tenant_id**：写入实际命中 team；额外加 `gateway_vkey_owner_team_id` 给"跨 team 流量分析"用

## 风险与未决项

1. reserved slug 列表（=主流 LiteLLM provider 名）需硬编码 + 单测固定
2. **建议禁止 Team.slug 变更**（仅改 name）— 待产品确认
3. 离线清理窗口期：cron + 同步触发压到秒级；建议加 `gateway_vkey_grant_stale_seconds` 指标
4. EntitlementPlan 仍按 vkey 维度（不做 per-grant，符合决策 #2）
5. `gateway_vkey_strict_team_prefix` 默认 False；按误用率切换
6. `gateway_route_name` 同时落 raw + normalized，避免 dashboard 高基数
7. **多 team 同名模型**（本轮补强）：DB 独立、路由显式、隐式 fallback 已关；非 strict 下仍有"忘加前缀→落主属"误用风险，靠 UI Banner + ambiguous 指标观察后切 strict（默认 false）

## 验证

- 单元/集成：`make test-unit -- tests/unit/gateway/test_vkey_team_*.py` + `make test-int -- tests/integration/gateway/test_multi_tenant_vkey_*.py`
- 端到端手测 6 步（详见 spec "Verification" 章节）：grant 创建 → prefix 派发 200 → 日志 tenant_id 验证 → fallback 关闭 422 → 移除 membership + cron → 派发降级
- Schema 检查：`alembic upgrade head && downgrade -1 && upgrade head` 全程绿色，自洽 grant count == active vkey count

## 兼容性矩阵

旧客户端 `sk-gw + model=gpt-4o` 行为完全不变；唯一行为变更是 `X-Team-Id=grant team` 从 400 变 200（放宽，非破坏性）。
