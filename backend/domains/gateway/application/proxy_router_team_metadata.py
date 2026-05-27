"""LiteLLM Router 归因 metadata 双桶同步（``metadata`` + ``litellm_metadata``）。

Router ``_ageneric_api_call_with_fallbacks``（含 ``aanthropic_messages``）把日志写入
``litellm_metadata``，而 ``ProxyMetadataBuilder`` 默认只写 ``metadata``。
此前仅镜像 ``user_api_key_team_id``，导致 team 可查、user/vkey 在 callback 丢失。
"""

from __future__ import annotations

from typing import Any
import uuid

# LiteLLM StandardLoggingPayload / Router 回调较稳定保留的键
_ROUTER_ATTRIBUTION_MIRROR_KEYS: frozenset[str] = frozenset(
    {
        "user_api_key_team_id",
        "user_api_key_user_id",
        "user_api_key_auth_metadata",
    }
)


def _resolve_team_id(kwargs: dict[str, Any], team_id: uuid.UUID | None) -> str | None:
    if team_id is not None:
        return str(team_id)
    for bucket_key in ("metadata", "litellm_metadata"):
        bucket = kwargs.get(bucket_key)
        if not isinstance(bucket, dict):
            continue
        raw = bucket.get("user_api_key_team_id") or bucket.get("gateway_team_id")
        if raw is not None and str(raw).strip():
            return str(raw)
    return None


def _collect_attribution_from_metadata_bucket(meta: dict[str, Any]) -> dict[str, Any]:
    collected: dict[str, Any] = {}
    for key in _ROUTER_ATTRIBUTION_MIRROR_KEYS:
        value = meta.get(key)
        if value is not None:
            collected[key] = value
    if "user_api_key_auth_metadata" not in collected:
        gateway_snapshot = {
            key: value for key, value in meta.items() if str(key).startswith("gateway_")
        }
        if gateway_snapshot:
            collected["user_api_key_auth_metadata"] = gateway_snapshot
    if "user_api_key_user_id" not in collected:
        gateway_user = meta.get("gateway_user_id")
        if gateway_user is not None and str(gateway_user).strip():
            collected["user_api_key_user_id"] = str(gateway_user)
    return collected


def _canonical_router_attribution(kwargs: dict[str, Any]) -> dict[str, Any]:
    """以 ``metadata`` 为权威来源，合并 ``litellm_metadata`` 已有键。"""
    merged: dict[str, Any] = {}
    litellm_meta = kwargs.get("litellm_metadata")
    if isinstance(litellm_meta, dict):
        merged.update(_collect_attribution_from_metadata_bucket(litellm_meta))
    meta = kwargs.get("metadata")
    if isinstance(meta, dict):
        merged.update(_collect_attribution_from_metadata_bucket(meta))
    return merged


def _write_attribution_to_buckets(kwargs: dict[str, Any], attribution: dict[str, Any]) -> None:
    if not attribution:
        return
    for bucket_key in ("metadata", "litellm_metadata"):
        bucket = kwargs.get(bucket_key)
        if not isinstance(bucket, dict):
            bucket = {}
            kwargs[bucket_key] = bucket
        bucket.update(attribution)


def ensure_litellm_router_team_metadata(
    kwargs: dict[str, Any],
    team_id: uuid.UUID | None = None,
    *,
    user_id: uuid.UUID | None = None,
) -> None:
    """确保 Router 双桶 metadata 含团队/用户/vkey 归因（供 filter 与 CustomLogger）。"""
    attribution = _canonical_router_attribution(kwargs)
    tid = _resolve_team_id(kwargs, team_id)
    if tid is not None:
        attribution["user_api_key_team_id"] = tid
    if user_id is not None:
        uid = str(user_id)
        attribution["user_api_key_user_id"] = uid
        auth = attribution.get("user_api_key_auth_metadata")
        auth_dict: dict[str, Any] = dict(auth) if isinstance(auth, dict) else {}
        auth_dict["gateway_user_id"] = uid
        if tid is not None:
            auth_dict.setdefault("gateway_team_id", tid)
        attribution["user_api_key_auth_metadata"] = auth_dict
    _write_attribution_to_buckets(kwargs, attribution)


__all__ = ["ensure_litellm_router_team_metadata"]
