# Gateway 接入 Moonshot Kimi For Coding 的 User-Agent 白名单

## 问题现象

调用 Moonshot `kimi-for-coding` 模型时，上游返回 403：

```text
APIError: MoonshotException - Kimi For Coding is currently only available for Coding Agents
such as Kimi CLI, Claude Code, Roo Code, Kilo Code, etc.
```

## 根因

Moonshot 对 `kimi-for-coding` 所在的 Coding 端点（`https://api.kimi.com/coding/v1`）实施了 **User-Agent 白名单**。只有被认可的 Coding Agent 客户端才能访问，普通 OpenAI SDK / LiteLLM 默认请求会被拒绝。

Gateway 早期以 `moonshot.default` 等普通身份调用时，出站的 `User-Agent` 通常是 OpenAI Python SDK 默认值（如 `openai-python/2.24.0`），不在白名单内，因此触发 403。

## 解决方案

在 `UpstreamProfile` 中声明 `coding_agent_ua`，并在构造 LiteLLM 参数时把该值写入 `extra_headers["User-Agent"]`。

当前实测可用的 UA 为：

```text
User-Agent: claude-cli/2.1.161
```

### 注入路径

Gateway 通过 `domains.gateway.domain.coding_agent_ua` 模块解析 Coding Agent UA，支持三种命中方式：

1. **显式 profile**：`credential_profile_id == "moonshot.coding_plan"`
2. **api_base 兜底**：凭据的 `api_base` / `api_bases` 命中 Coding 端点 `https://api.kimi.com/coding/v1`
3. **模型名兜底**：上游真实模型名以 `kimi-for-coding` 开头

只要满足任一条件，就会注入白名单 UA。

### 关键代码位置

| 文件 | 作用 |
|---|---|
| `backend/domains/gateway/domain/upstream_profile_registry.py` | 声明 `moonshot.coding_plan` profile 及 `coding_agent_ua="claude-cli/2.1.161"` |
| `backend/domains/gateway/domain/coding_agent_ua.py` | 解析并回退 Coding Agent UA；把 UA 写入 `extra_headers` |
| `backend/domains/gateway/infrastructure/router_singleton.py` | Router deployment 构造时调用 `apply_coding_agent_ua_litellm_params` |
| `backend/domains/gateway/application/upstream_adapter.py` | 直连 LiteLLM 调用前注入 UA |
| `backend/domains/gateway/application/management/credential_upstream_catalog.py` | 拉取模型列表时也注入 UA |

### 调用链路覆盖

以下所有走 Gateway 出站的调用都会生效：

- OpenAI 兼容入口：`/v1/chat/completions`
- Anthropic 兼容入口：`/v1/messages`
- 内部 Agent 调用：通过 `GatewayBridge` / LiteLLM Router
- 管理面模型列表探活：`/v1/models` 拉取

## 配置建议

### 方式一：使用 Coding Plan profile（推荐）

在凭据/模型配置中选择：

```text
provider: moonshot
profile_id: moonshot.coding_plan
```

此时 `api_base` 会自动解析为 `https://api.kimi.com/coding/v1`，并注入 `User-Agent: claude-cli/2.1.161`。

### 方式二：自定义 api_base

如果出于业务原因使用 `moonshot.default` 等默认 profile，需把凭据的 `api_base` 显式设置为：

```text
https://api.kimi.com/coding/v1
```

Gateway 会按 api_base 兜底命中 Coding profile 的 UA。

### 方式三：模型名命中

若 profile 和 api_base 都是默认的，但上游真实模型名为 `kimi-for-coding`（或以此前缀），Gateway 也会按模型名兜底注入 UA。

## 验证

curl 实测：

```bash
curl -s -X POST "https://api.kimi.com/coding/v1/chat/completions" \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" \
  -H "User-Agent: claude-cli/2.1.161" \
  -H "Content-Type: application/json" \
  -d '{"model":"kimi-for-coding","messages":[{"role":"user","content":"hello"}]}'
```

返回 HTTP 200。

单元测试覆盖：

- `backend/tests/unit/gateway/domain/test_coding_agent_ua.py`
- `backend/tests/unit/gateway/test_router_litellm_api_base.py`
- `backend/tests/unit/gateway/test_upstream_adapter.py`

## 注意事项

- Moonshot 的白名单规则可能随时调整。若未来 `claude-cli/2.1.161` 失效，可更新 `upstream_profile_registry.py` 中的 `coding_agent_ua`。
- 该 UA 目前仅用于 Moonshot Coding 端点，不会污染其他 provider 或普通 Moonshot 请求。
- 后续可考虑把 `coding_agent_ua` 开放为 credential `extra` 字段或环境变量配置，便于运营快速调整。

## 相关 Issue / 参考

- [cline/cline#10307](https://github.com/cline/cline/issues/10307)
- [farion1231/cc-switch#3671](https://github.com/farion1231/cc-switch/pull/3671)
- [MoonshotAI/kimi-cli#2322](https://github.com/MoonshotAI/kimi-cli/issues/2322)
