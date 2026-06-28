"""模型连通性探活：LiteLLM 调用归因 metadata（写入 gateway_request_logs）。"""

from __future__ import annotations

from typing import Any
import uuid

from domains.gateway.application.catalog.management.probe_target import ProbeTarget
from domains.gateway.domain.proxy.coding_agent_ua import apply_coding_agent_ua_litellm_params

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
        # route_name = 客户端调用名（GatewayModel.name），与真实代理请求语义一致；
        # 上游 real_model 经 gateway_real_model（见 probe_litellm_model_info）单独落库。
        "gateway_route_name": target.model_name,
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
        "gateway_model_id": str(target.model_id),
        # 注册别名快照 = 调用名；上游 canonical id 用 gateway_real_model。
        "gateway_model_name": target.model_name,
        "gateway_real_model": target.real_model,
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
    metadata = build_probe_gateway_metadata(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        target=target,
        credential_name=credential_name,
        user_email_snapshot=user_email_snapshot,
    )
    merged["metadata"] = metadata
    model_info = probe_litellm_model_info(target, credential_name)
    # LiteLLM 直连回调常只保留 litellm_params.metadata；与 Router 代理路径对齐双写。
    existing = merged.get("litellm_params")
    litellm_params = dict(existing) if isinstance(existing, dict) else {}
    litellm_params["model_info"] = model_info
    litellm_params["metadata"] = metadata
    merged["litellm_params"] = litellm_params
    return apply_coding_agent_ua_litellm_params(
        merged,
        credential_profile_id=credential_profile_id,
        provider=target.provider,
        real_model=target.real_model,
    )


__all__ = [
    "GATEWAY_PROBE_CLIENT_TYPE",
    "build_probe_gateway_metadata",
    "merge_probe_litellm_kwargs",
    "probe_litellm_model_info",
]
