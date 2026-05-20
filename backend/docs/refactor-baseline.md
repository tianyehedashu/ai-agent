# Agent–Gateway 解耦：测试基线（T1）

记录日期：**2026-05-19**（本机 `uv sync --all-extras` 后执行）

## 命令与结果

| 命令 | 结果 |
|------|------|
| `cd backend && uv run pytest tests/ -m "not e2e" -q --tb=no` | **1347 passed**, 6 skipped（约 170s） |
| `cd frontend && npm run typecheck` | **通过** |
| `cd frontend && npm run lint` | **通过** |

## 解耦专项子集（必须通过）

```bash
cd backend
uv run pytest \
  tests/architecture/ \
  tests/unit/gateway/test_upstream_adapter.py \
  tests/unit/gateway/test_upstream_policy.py \
  tests/unit/gateway/test_prompt_cache_middleware.py \
  tests/unit/gateway/domain/ \
  tests/unit/agent/test_message_formatter.py \
  tests/unit/agent/infrastructure/test_langchain_messages.py \
  tests/unit/agent/test_agent_llm_facade.py \
  tests/unit/gateway/test_litellm_payload.py \
  -q
```

**2026-05-19：52 passed**（含 T2–T7 对齐计划后的用例）

CI：`.github/workflows/backend-architecture.yml` 跑架构 + gateway domain/adapter 子集。

## E2E 说明

`tests/e2e/` 中 Chat/SimpleMem/Execution 用例依赖：

1. 本机 `http://localhost:8000`（或 `E2E_API_BASE_URL`）
2. 环境变量 `E2E_USER_EMAIL` / `E2E_USER_PASSWORD`（Gateway 桥接需注册用户归因）

未配置凭据时相关用例 **skip**，不计入失败。见 `tests/e2e/conftest.py`。

## 计划 T1–T7 对齐清单

| ID | 交付物 | 状态 |
|----|--------|------|
| T1 | 本文件 + 全量/pytest 与前端 check 记录 | ✅ |
| T2 | `test_upstream_adapter.py` + `test_upstream_policy.py`（5 类 quirks） | ✅ |
| T3 | `test_prompt_cache_middleware.py`（含 `cache_control`） | ✅ |
| T4 | `test_message_formatter.py` + `test_langchain_messages.py`（非 `libs/llm`） | ✅ |
| T5 | `test_agent_llm_facade.py`（含流式 ToolCall） | ✅ |
| T6 | `test_agent_llm_facade.py`（含原 core 用例） | ✅ |
| T7 | `test_agent_no_litellm_import.py`、`test_agent_no_provider_settings.py`、`test_gateway_no_agent_import.py` | ✅ |

## 架构约定（复查）

- 无 `libs/llm/`：LiteLLM 规则在 `domains/gateway/domain/`
- Agent 消息：`domains/agent/infrastructure/llm/message_formatter.py`、`langchain_messages.py`
- 跨域契约：`domains/gateway/application/ports.py`、`model_catalog_port.py`
