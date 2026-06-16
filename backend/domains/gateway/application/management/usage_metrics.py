"""Gateway 管理面用量指标纯函数（读侧聚合复用）。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def merge_gateway_usage_slices(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """合并两段用量（如 route_name 直连 + deployment 归因），费用按 Decimal 相加。"""
    ca = a.get("cost_usd", 0)
    cb = b.get("cost_usd", 0)
    da = ca if isinstance(ca, Decimal) else Decimal(str(ca or 0))
    db = cb if isinstance(cb, Decimal) else Decimal(str(cb or 0))
    return {
        "requests": int(a.get("requests", 0)) + int(b.get("requests", 0)),
        "input_tokens": int(a.get("input_tokens", 0)) + int(b.get("input_tokens", 0)),
        "output_tokens": int(a.get("output_tokens", 0)) + int(b.get("output_tokens", 0)),
        "cached_tokens": int(a.get("cached_tokens", 0)) + int(b.get("cached_tokens", 0)),
        "cache_creation_tokens": int(a.get("cache_creation_tokens", 0))
        + int(b.get("cache_creation_tokens", 0)),
        "cost_usd": da + db,
    }


def _decimal_add(a: object, b: object) -> Decimal:
    da = a if isinstance(a, Decimal) else Decimal(str(a or 0))
    db = b if isinstance(b, Decimal) else Decimal(str(b or 0))
    return da + db


def _weighted_avg(avg_a: float, weight_a: int, avg_b: float, weight_b: int) -> float:
    total = weight_a + weight_b
    if total <= 0:
        return 0.0
    return (avg_a * weight_a + avg_b * weight_b) / total


def merge_summary_slices(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """合并 dashboard summary 两段（hourly 冷段 + logs 热尾）。"""
    success_a = int(a.get("success", 0))
    success_b = int(b.get("success", 0))
    merged = {
        "total": int(a.get("total", 0)) + int(b.get("total", 0)),
        "input_tokens": int(a.get("input_tokens", 0)) + int(b.get("input_tokens", 0)),
        "output_tokens": int(a.get("output_tokens", 0)) + int(b.get("output_tokens", 0)),
        "cached_tokens": int(a.get("cached_tokens", 0)) + int(b.get("cached_tokens", 0)),
        "cache_creation_tokens": int(a.get("cache_creation_tokens", 0))
        + int(b.get("cache_creation_tokens", 0)),
        "cost_usd": _decimal_add(a.get("cost_usd"), b.get("cost_usd")),
        "success": success_a + success_b,
        "failure": int(a.get("failure", 0)) + int(b.get("failure", 0)),
        "avg_latency_ms": _weighted_avg(
            float(a.get("avg_latency_ms", 0)),
            success_a,
            float(b.get("avg_latency_ms", 0)),
            success_b,
        ),
        "avg_ttfb_ms": _weighted_avg(
            float(a.get("avg_ttfb_ms", 0)),
            success_a,
            float(b.get("avg_ttfb_ms", 0)),
            success_b,
        ),
    }
    by_client_a = a.get("by_client_type")
    by_client_b = b.get("by_client_type")
    if by_client_a is not None or by_client_b is not None:
        merged["by_client_type"] = merge_client_type_slices(
            by_client_a if isinstance(by_client_a, list) else [],
            by_client_b if isinstance(by_client_b, list) else [],
        )
    return merged


def merge_client_type_slices(
    a: list[dict[str, Any]],
    b: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in [*a, *b]:
        key = str(item.get("client_type", "unknown"))
        existing = merged.get(key)
        if existing is None:
            merged[key] = {
                "client_type": key,
                "requests": int(item.get("requests", 0)),
                "cost_usd": _decimal_add(item.get("cost_usd"), 0),
            }
            continue
        existing["requests"] = int(existing["requests"]) + int(item.get("requests", 0))
        existing["cost_usd"] = _decimal_add(existing["cost_usd"], item.get("cost_usd"))
    return sorted(merged.values(), key=lambda row: int(row["requests"]), reverse=True)


def merge_statistics_totals(
    a: dict[str, Any] | object,
    b: dict[str, Any] | object,
) -> dict[str, int | float | Decimal]:
    def _get(obj: dict[str, Any] | object, key: str) -> object:
        if isinstance(obj, dict):
            return obj.get(key, 0)
        return getattr(obj, key, 0)

    success_a = int(_get(a, "success_count"))
    success_b = int(_get(b, "success_count"))
    return {
        "requests": int(_get(a, "requests")) + int(_get(b, "requests")),
        "success_count": success_a + success_b,
        "failure_count": int(_get(a, "failure_count")) + int(_get(b, "failure_count")),
        "input_tokens": int(_get(a, "input_tokens")) + int(_get(b, "input_tokens")),
        "output_tokens": int(_get(a, "output_tokens")) + int(_get(b, "output_tokens")),
        "cached_tokens": int(_get(a, "cached_tokens")) + int(_get(b, "cached_tokens")),
        "cache_creation_tokens": int(_get(a, "cache_creation_tokens"))
        + int(_get(b, "cache_creation_tokens")),
        "cost_usd": _decimal_add(_get(a, "cost_usd"), _get(b, "cost_usd")),
        "avg_latency_ms": _weighted_avg(
            float(_get(a, "avg_latency_ms")),
            success_a,
            float(_get(b, "avg_latency_ms")),
            success_b,
        ),
        "avg_ttfb_ms": _weighted_avg(
            float(_get(a, "avg_ttfb_ms")),
            success_a,
            float(_get(b, "avg_ttfb_ms")),
            success_b,
        ),
        "cache_hit_count": int(_get(a, "cache_hit_count")) + int(_get(b, "cache_hit_count")),
    }


def _group_key_str(value: object) -> str:
    return "" if value is None else str(value)


def merge_statistics_items(
    rows_a: list[Any],
    rows_b: list[Any],
) -> list[Any]:
    """按 group_key 合并统计行（保留 rows_a 类型）。"""
    index: dict[str, Any] = {}
    order: list[str] = []

    def _ingest(row: Any) -> None:
        key = _group_key_str(getattr(row, "group_key", None))
        if key not in index:
            index[key] = row
            order.append(key)
            return
        existing = index[key]
        totals = merge_statistics_totals(existing, row)
        index[key] = type(existing)(
            group_key=existing.group_key,
            label_snapshot=existing.label_snapshot or getattr(row, "label_snapshot", None),
            group_key_parts=existing.group_key_parts,
            label_parts=existing.label_parts,
            requests=int(totals["requests"]),
            success_count=int(totals["success_count"]),
            failure_count=int(totals["failure_count"]),
            input_tokens=int(totals["input_tokens"]),
            output_tokens=int(totals["output_tokens"]),
            cached_tokens=int(totals["cached_tokens"]),
            cache_creation_tokens=int(totals["cache_creation_tokens"]),
            cost_usd=totals["cost_usd"] if isinstance(totals["cost_usd"], Decimal) else Decimal("0"),
            avg_latency_ms=float(totals["avg_latency_ms"]),
            avg_ttfb_ms=float(totals["avg_ttfb_ms"]),
            cache_hit_count=int(totals["cache_hit_count"]),
        )

    for row in rows_a:
        _ingest(row)
    for row in rows_b:
        _ingest(row)

    merged = [index[key] for key in order]
    merged.sort(key=lambda row: int(getattr(row, "requests", 0)), reverse=True)
    return merged


__all__ = [
    "merge_client_type_slices",
    "merge_gateway_usage_slices",
    "merge_statistics_items",
    "merge_statistics_totals",
    "merge_summary_slices",
]
