# Gateway 专题文档

域架构权威文档：[AI_GATEWAY_DOMAIN_ARCHITECTURE.md](../AI_GATEWAY_DOMAIN_ARCHITECTURE.md)

## 阅读顺序

1. [AI_GATEWAY_DOMAIN_ARCHITECTURE.md](../AI_GATEWAY_DOMAIN_ARCHITECTURE.md) — DDD 分层、路由、鉴权、CQRS、数据模型
2. [LLM_GATEWAY_ARCHITECTURE.md](./LLM_GATEWAY_ARCHITECTURE.md) — LiteLLM 选型与 Gateway 抽象
3. [LITELLM_CAPABILITY_MATRIX.md](./LITELLM_CAPABILITY_MATRIX.md) — 能力矩阵（已用 / 未用）
4. [QUOTA_MANAGEMENT.md](./QUOTA_MANAGEMENT.md) — 三层配额概念、规则、两阶段热路径与 BYOK 豁免
5. [DEFERRED_WRITE_CONCURRENCY.md](./DEFERRED_WRITE_CONCURRENCY.md) — 延迟写入合并刷写、有界结算执行器与连接池治理
6. [UPSTREAM_EP_QUOTA.md](./UPSTREAM_EP_QUOTA.md) — 火山 `ep-*` 上游每日限额：日历重置、执法热路径、展示读与效率
7. 按需查阅下方运维与接入文档

## 接入与部署

| 文档 | 说明 |
|------|------|
| [GATEWAY_THIRDPARTY_CLIENT_GUIDE.md](./GATEWAY_THIRDPARTY_CLIENT_GUIDE.md) | 第三方客户端速查配置 |
| [GATEWAY_CURSOR_CLAUDE_CODE.md](./GATEWAY_CURSOR_CLAUDE_CODE.md) | Claude Code / Cursor 完整适配 |
| [GATEWAY_DEPLOYMENT_CHECKLIST.md](./GATEWAY_DEPLOYMENT_CHECKLIST.md) | 生产部署（SSE / 长连接） |

## 定价与模型

| 文档 | 说明 |
|------|------|
| [GATEWAY_PRICING_AND_LITELLM_COST.md](./GATEWAY_PRICING_AND_LITELLM_COST.md) | 定价与计费链路 |
| [LITELLM_SUPPORTED_MODELS.md](./LITELLM_SUPPORTED_MODELS.md) | 中国区实测模型列表 |

## 可靠性与性能

| 文档 | 说明 |
|------|------|
| [DEFERRED_WRITE_CONCURRENCY.md](./DEFERRED_WRITE_CONCURRENCY.md) | 响应后延迟写入：合并刷写、有界队列、背压与连接池隔离 |

## 归档

| 文档 | 说明 |
|------|------|
| [../archive/gateway/GATEWAY_COMPATIBILITY_CHECK.md](../archive/gateway/GATEWAY_COMPATIBILITY_CHECK.md) | 旧 `core/` 时代兼容性审计（已过时） |
