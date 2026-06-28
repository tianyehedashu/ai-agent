"""合并 plan quota 桶：按 label upsert，保留其它桶。"""

from __future__ import annotations

from typing import Any


def merge_plan_quotas_by_label(
    existing_quotas: list[Any],
    label: str,
    quota_payload: dict[str, object],
    *,
    extra_fields: tuple[str, ...] = (),
) -> list[dict[str, object]]:
    """将 ``quota_payload`` 写入 label 对应桶；其它桶原样保留。

    ``extra_fields`` 用于 downstream entitlement 桶的单价字段等扩展列。
    """
    merged: list[dict[str, object]] = []
    for q in existing_quotas:
        if q.label == label:
            continue
        row: dict[str, object] = {
            "label": q.label,
            "window_seconds": q.window_seconds,
            "reset_strategy": q.reset_strategy,
            "reset_timezone": getattr(q, "reset_timezone", "UTC"),
            "reset_time_minutes": getattr(q, "reset_time_minutes", 0),
            "reset_day_of_month": getattr(q, "reset_day_of_month", 1),
            "limit_usd": q.limit_usd,
            "limit_tokens": q.limit_tokens,
            "limit_requests": q.limit_requests,
            "enabled": getattr(q, "enabled", True),
            "valid_from": getattr(q, "valid_from", None),
            "valid_until": getattr(q, "valid_until", None),
        }
        for field in extra_fields:
            row[field] = getattr(q, field, None)
        merged.append(row)
    merged.append(quota_payload)
    return merged
