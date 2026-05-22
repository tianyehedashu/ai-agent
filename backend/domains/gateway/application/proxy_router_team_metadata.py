"""LiteLLM Router 团队过滤所需的 request metadata 补齐。"""

from __future__ import annotations

from typing import Any
import uuid


def _resolve_team_id(kwargs: dict[str, Any], team_id: uuid.UUID | None) -> str | None:
    if team_id is not None:
        return str(team_id)
    meta = kwargs.get("metadata")
    if isinstance(meta, dict):
        raw = meta.get("user_api_key_team_id") or meta.get("gateway_team_id")
        if raw is not None and str(raw).strip():
            return str(raw)
    litellm_meta = kwargs.get("litellm_metadata")
    if isinstance(litellm_meta, dict):
        raw = litellm_meta.get("user_api_key_team_id")
        if raw is not None and str(raw).strip():
            return str(raw)
    return None


def ensure_litellm_router_team_metadata(
    kwargs: dict[str, Any],
    team_id: uuid.UUID | None = None,
) -> None:
    """确保 ``filter_team_based_models`` 能匹配 deployment ``model_info.team_id``。

    LiteLLM Router 的 async 路径会按 ``user_api_key_team_id`` 过滤带 ``team_id`` 的
    deployment；缺该字段时所有 team-scoped deployment 会被剔除。
    """
    tid = _resolve_team_id(kwargs, team_id)
    if tid is None:
        return
    for key in ("metadata", "litellm_metadata"):
        bucket = kwargs.get(key)
        if not isinstance(bucket, dict):
            bucket = {}
            kwargs[key] = bucket
        bucket.setdefault("user_api_key_team_id", tid)


__all__ = ["ensure_litellm_router_team_metadata"]
