# NormalizedUsage 统一重构

## Context

当前 gateway 域存在三条独立的 usage 提取路径，语义不一致是所有 cache/token bug 的根源：

| 路径 | 文件 | Anthropic input_tokens 语义 | 返回类型 |
|------|------|---------------------------|---------|
| `extract_usage_tokens` | `infrastructure/callbacks/cost_calculation.py` | 已膨胀 (+= cache_read + cache_creation) | `tuple[int,int,int]` |
| `_extract_usage_from_response` | `application/pricing/upstream_cost_resolver.py` | 原始值 (仅 non-cached) | `TokenUsage` |
| `anthropic_usage_total_tokens` | `application/anthropic_native_adapt.py` | N/A (只求总和) | `int` |

此外 `_persist_event` 有 272 行、10+ 职责；`settle_request_log_amounts` 构造 `TokenUsage` 时 `cache_creation_tokens` 永远为 0，导致 cache creation 费率漏计费。

---

## Task 1: 新建 `NormalizedUsage` 域值对象 + 提取函数

**新建文件**: `backend/domains/gateway/domain/normalized_usage.py`

```python
@dataclass(frozen=True)
class NormalizedUsage:
    input_tokens_raw: int = 0        # 上游原始值（Anthropic=non-cached, OpenAI=prompt_tokens-cached）
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    requests: int = 1

    @property
    def input_tokens_normalized(self) -> int:
        """与 OpenAI prompt_tokens 对齐（含所有 cache tokens）"""
        return self.input_tokens_raw + self.cache_read_tokens + self.cache_creation_tokens

    @property
    def total_tokens(self) -> int:
        return self.input_tokens_normalized + self.output_tokens

    def to_token_usage(self) -> TokenUsage:
        """转 pricing 层 TokenUsage（4 字段独立，用于 calculate_cost_from_rate）"""

    def to_db_tuple(self) -> tuple[int, int, int]:
        """DB 写入三元组: (input_normalized, output, cache_read)"""

    def with_slo_fallback(self, slo: dict | None) -> NormalizedUsage:
        """当 SLO 提供更完整 cache 信息时返回增强副本（仅原始值缺失时补齐）"""
```

**提取函数**（同文件）:
```python
def extract_normalized_usage(response_obj: Any, *, requests: int = 1) -> NormalizedUsage
def normalized_usage_from_raw(usage: Any, *, requests: int = 1) -> NormalizedUsage
```

**关键语义**:
- OpenAI 路径: `input_tokens_raw = max(0, prompt_tokens - cached_tokens)`, 使 `normalized = prompt_tokens`
- Anthropic 路径: `input_tokens_raw = input_tokens` (天然 non-cached)
- 两种格式下 `input_tokens_normalized` 和 `total_tokens` 均正确

**新建测试**: `backend/tests/unit/gateway/test_normalized_usage.py` — 18 个用例覆盖 OpenAI/Anthropic/dict/object/None/SLO fallback/to_token_usage/to_db_tuple

---

## Task 2: 低风险 shim 替换（外部行为不变）

### 2a. `extract_usage_tokens` → shim
**文件**: `backend/domains/gateway/infrastructure/callbacks/cost_calculation.py`
- 函数体改为 `return extract_normalized_usage(response_obj).to_db_tuple()`
- 签名/返回值不变，所有现有测试无需修改

### 2b. `anthropic_usage_total_tokens` → shim
**文件**: `backend/domains/gateway/application/anthropic_native_adapt.py`
- 函数体改为 `return normalized_usage_from_raw(usage).total_tokens`
- 签名/返回值不变

### 2c. `stream_usage_token_total` → 改用 domain 函数
**文件**: `backend/domains/gateway/application/proxy_stream_settlement.py`
- 改为 `return normalized_usage_from_raw(usage).total_tokens`
- 无需再检查 `total_tokens` key（`extract_normalized_usage` 内部处理）

每步验证: `test_cost_calculation.py` + `test_anthropic_native_adapt.py` + `test_proxy_stream_settlement.py` 全部通过

---

## Task 3: 修正 pricing 路径（中等风险 — 修正 bug）

### 3a. `_extract_usage_from_response` → shim
**文件**: `backend/domains/gateway/application/pricing/upstream_cost_resolver.py`
- 函数体改为 `return extract_normalized_usage(response_obj, requests=requests).to_token_usage()`
- **语义变化**: domain fallback 路径的 Anthropic `input_tokens` 现在包含 cache tokens（修正漏算 bug）

### 3b. `settle_request_log_amounts` 新增 `cache_creation_tokens` 参数
**文件**: `backend/domains/gateway/application/pricing/pricing_settlement.py`
```python
def settle_request_log_amounts(
    *, ..., cached_tokens: int,
    cache_creation_tokens: int = 0,  # 新增！修正 cache_creation 漏计费
) -> ...:
    usage = TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation_tokens,  # 之前永远为 0
        cache_read_tokens=cached_tokens,
    )
```

验证: `test_upstream_cost_resolver.py` + `test_pricing_calculator.py` + `test_custom_logger_pricing_settlement.py`

---

## Task 4: 拆分 `_persist_event`（高风险 — 逐步提取子函数）

**文件**: `backend/domains/gateway/infrastructure/callbacks/custom_logger.py`

从 272 行拆分为以下子函数（按独立性从高到低逐个提取）:

| 子函数 | 职责 | 原行号 |
|--------|------|--------|
| `_extract_attribution_ids(metadata, kwargs)` | team/user/vkey ID 提取 + 诊断日志 | 604-618 |
| `_normalize_route_model(metadata, kwargs, response_obj)` | route/model/provider 规范化 | 620-648 |
| `_resolve_time_latency(start_time, end_time, metadata)` | 时间/延迟计算 | 664-671 |
| `_resolve_client_info(metadata)` | client type/UA/快照字段 | 724-733 |
| `_build_log_previews(kwargs, response_obj, metadata)` | prompt/response 摘要 + 详细度配置 | 696-722 |
| `_make_sampling_decision(...)` | 采样判断 | 735-747 |
| `_resolve_usage_and_settlement(metadata, kwargs, response_obj, status)` | **核心**: NormalizedUsage + SLO + 成本结算 | 521-553 + 650-688 |
| `_write_log_to_db(session, ...)` | DB 写入块 | 749-804 |
| `_settle_budgets(status, ...)` | 预算 commit/release | 806-840 |
| `_post_persist_side_effects(...)` | Redis 计数 + 配额耗尽 | 842-863 |

重构后 `_persist_event` 骨架约 40 行：

```python
async def _persist_event(*, kwargs, response_obj, start_time, end_time, status, error_code, error_message):
    metadata = _extract_gateway_metadata(kwargs)
    attribution = _extract_attribution_ids(metadata, kwargs)
    route_model = _normalize_route_model(metadata, kwargs, response_obj)
    usage_settlement = _resolve_usage_and_settlement(metadata, kwargs, response_obj, status)
    time_info = _resolve_time_latency(start_time, end_time, metadata)
    previews = _build_log_previews(kwargs, response_obj, metadata)
    client_info = _resolve_client_info(metadata)
    sampling = _make_sampling_decision(...)
    if sampling.persist_row:
        await _write_log_to_db(...)
    await _settle_budgets(...)
    await _post_persist_side_effects(...)
```

**关键**: `_resolve_usage_and_settlement` 内部使用 `extract_normalized_usage()` + `.with_slo_fallback()` + 传递 `cache_creation_tokens` 到 `settle_request_log_amounts`。

验证: 每提取一个子函数后运行 `test_custom_logger_*.py` 全部 9 个测试文件

---

## Task 5: 全量回归 + 清理

- 运行 `pytest backend/tests/unit/gateway/ -x` 全部 gateway 单元测试（1067 个）
- 运行 `pytest backend/tests/integration/api/test_gateway_cache_and_token_stats.py` 集成测试
- 标记旧函数为 deprecated（注释说明，不删除）

---

## 涉及文件汇总

| 文件 | 操作 |
|------|------|
| `backend/domains/gateway/domain/normalized_usage.py` | **新建** |
| `backend/tests/unit/gateway/test_normalized_usage.py` | **新建** |
| `backend/domains/gateway/infrastructure/callbacks/cost_calculation.py` | 改 shim |
| `backend/domains/gateway/application/anthropic_native_adapt.py` | 改 shim |
| `backend/domains/gateway/application/proxy_stream_settlement.py` | 改用 domain 函数 |
| `backend/domains/gateway/application/pricing/upstream_cost_resolver.py` | 改 shim |
| `backend/domains/gateway/application/pricing/pricing_settlement.py` | 新增参数 |
| `backend/domains/gateway/infrastructure/callbacks/custom_logger.py` | 拆分 _persist_event |

---

## Task 6: 全链路添加 cache_creation_tokens 维度统计

### Context
当前 `cache_creation_tokens` 仅在内存中的 `NormalizedUsage`/`TokenUsage` 存在，未持久化到 DB。Dashboard Summary 不返回 `cached_tokens` 总计，Redis 实时计数只存 `tokens` 总计（不区分 input/output/cache）。

### 6a. DB Model + Alembic Migration
- `backend/domains/gateway/infrastructure/models/request_log.py`: GatewayRequestLog 添加 `cache_creation_tokens` 字段
- `backend/domains/gateway/infrastructure/models/metrics_hourly.py`: GatewayMetricsHourly 添加 `cache_creation_tokens` 字段
- 新建 alembic migration 添加两表列

### 6b. Repository 层
- `request_log_repository.py`:
  - `insert()` 添加 `cache_creation_tokens` 参数
  - `aggregate_summary_by_axis()` 添加 `cache_creation_tokens` 聚合
  - `aggregate_usage_statistics_by_axis()` 添加 `cache_creation_tokens` 聚合
  - `RequestLogUsageAggregateRow` / `RequestLogUsageTotals` 添加 `cache_creation_tokens`
  - `aggregate_by_route_names/deployment_ids/credential_global` 添加 `cache_creation_tokens`
- `metrics_rollup_repository.py`:
  - `_UPSERT_COLUMNS` 和 `rollup_window()` 添加 `cache_creation_tokens`

### 6c. Domain / Application 层
- `usage_reads.py`: `UsageStatisticsMetric`, `UsageLogReadModel`, `EntitlementUsageReadModel`, `ProviderPlanCostReadModel` 添加 `cache_creation_tokens`
- `usage_log_reads.py`: `_metric_from_totals()`, `_item_from_row()`, `_build_user_model_credential_items()`, `aggregate_gateway_model_route_usage()` 映射新字段
- `usage_metrics.py`: `merge_gateway_usage_slices()` 合并新字段

### 6d. Callback / Redis 层
- `custom_logger.py`:
  - `_write_log_to_db()` 加回 `cache_creation_tokens` 参数（DB schema 已支持）
  - `_bump_redis_counters()` 拆分 tokens 为独立维度（input/output/cached/cache_creation），保留旧 `tokens` 字段兼容
  - `_post_persist_side_effects()` 传入新参数

### 6e. Schema / API 层
- `common.py`:
  - `RequestLogResponse` 添加 `cache_creation_tokens`
  - `DashboardSummaryResponse` 添加 `total_cached_tokens`, `total_cache_creation_tokens`
  - `UsageStatisticsMetricResponse` 添加 `cache_creation_tokens`
  - `TimeSeriesPointResponse` 添加 `cached_tokens`, `cache_creation_tokens`
  - `GatewayModelRouteUsageSlice` 添加 `cached_tokens`, `cache_creation_tokens`

### 6f. Router 层
- `dashboard.py`:
  - `dashboard_summary()` 返回新字段
  - `_usage_stats_metric_response()` / `_usage_statistics_item_response()` 映射新字段

### 6g. 测试
- 更新 `test_gateway_cache_and_token_stats.py` 集成测试
- 新增/更新单元测试覆盖 rollup 和 Redis 计数

验证: `pytest backend/tests/unit/gateway/ -x` + `pytest backend/tests/integration/api/test_gateway_cache_and_token_stats.py -x`

---

**不变文件**: `pricing_calculator.py`（已完整支持 cache_creation 定价）
