"""模型连通性探活：LiteLLM 调用归因 metadata（写入 gateway_request_logs）。"""

from __future__ import annotations

from typing import Any
import uuid

from domains.gateway.application.management.write_modules.probe_target import ProbeTarget
from domains.gateway.domain.upstream_profile_registry import get_upstream_profile

GATEWAY_PROBE_CLIENT_TYPE = "model_connectivity_probe"


def build_probe_gateway_metadata(
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    target: ProbeTarget,
    credential_name: str,
    user_email_snapshot: str | None = None,
) -> dict[str, Any]:
    """与 ``ProxyMetadataBuilder`` 对齐的 Gateway 归因键，供 CustomLogger 落库。"""
    team_id_str = str(tenant_id)
    user_id_str = str(actor_user_id) if actor_user_id is not None else None
    meta: dict[str, Any] = {
        "gateway_team_id": team_id_str,
        "user_api_key_team_id": team_id_str,
        "gateway_user_id": user_id_str,
        "user_api_key_user_id": user_id_str,
        "gateway_credential_id": str(target.credential_id),
        "gateway_credential_name_snapshot": credential_name,
        "gateway_capability": target.capability,
        "gateway_provider": target.provider,
        "gateway_client_type": GATEWAY_PROBE_CLIENT_TYPE,
        "gateway_route_name": target.real_model,
    }
    if user_email_snapshot:
        meta["gateway_user_email_snapshot"] = user_email_snapshot
    gateway_snapshot = {key: value for key, value in meta.items() if key.startswith("gateway_")}
    if gateway_snapshot:
        meta["user_api_key_auth_metadata"] = gateway_snapshot
    return meta


def probe_litellm_model_info(target: ProbeTarget, credential_name: str) -> dict[str, Any]:
    """供 ``_deployment_from_model_info_kwargs`` / ``_credential_from_model_info_kwargs`` 解析。"""
    return {
        "id": str(target.model_id),
        "gateway_model_name": target.real_model,
        "gateway_credential_id": str(target.credential_id),
        "gateway_credential_name": credential_name,
    }


def merge_probe_litellm_kwargs(
    base: dict[str, Any],
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    target: ProbeTarget,
    credential_name: str,
    user_email_snapshot: str | None = None,
    credential_profile_id: str | None = None,
) -> dict[str, Any]:
    """在探活 LiteLLM kwargs 上合并 metadata、model_info 与 coding_agent_ua。"""
    merged = dict(base)
    merged["metadata"] = build_probe_gateway_metadata(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        target=target,
        credential_name=credential_name,
        user_email_snapshot=user_email_snapshot,
    )
    model_info = probe_litellm_model_info(target, credential_name)
    existing = merged.get("litellm_params")
    if isinstance(existing, dict):
        merged["litellm_params"] = {**existing, "model_info": model_info}
    else:
        merged["litellm_params"] = {"model_info": model_info}
    profile = get_upstream_profile(credential_profile_id, provider=target.provider)
    if profile.coding_agent_ua:
        headers = dict(merged.get("extra_headers") or {})
        headers["User-Agent"] = profile.coding_agent_ua
        merged["extra_headers"] = headers
    return merged


__all__ = [
    "GATEWAY_PROBE_CLIENT_TYPE",
    "build_probe_gateway_metadata",
    "merge_probe_litellm_kwargs",
    "probe_litellm_model_info",
]
