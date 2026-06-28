"""LiteLLM Router deployment 归因字段提取（纯函数，无 I/O）。

全链路（pre_call 套餐匹配、callback 结算、请求日志落库）均以
``model_info.gateway_real_model`` 为上游模型身份 SSOT，与 ``router_singleton``
写入 deployment 的 ``GatewayModel.real_model`` 一致。
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any
import uuid


def litellm_model_info_from_kwargs(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    top = kwargs.get("model_info")
    if isinstance(top, dict):
        return top
    for container_key in ("litellm_params", "standard_logging_object"):
        container = kwargs.get(container_key)
        if not isinstance(container, dict):
            continue
        model_info = container.get("model_info")
        if isinstance(model_info, dict):
            return model_info
    return None


def gateway_deployment_real_model(kwargs: dict[str, Any]) -> str | None:
    model_info = litellm_model_info_from_kwargs(kwargs)
    if model_info is None:
        return None
    raw = model_info.get("gateway_real_model")
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped:
            return stripped
    return None


def gateway_deployment_credential_id(kwargs: dict[str, Any]) -> uuid.UUID | None:
    model_info = litellm_model_info_from_kwargs(kwargs)
    if model_info is None:
        return None
    raw = model_info.get("gateway_credential_id")
    if raw is None:
        return None
    with suppress(ValueError, TypeError):
        return uuid.UUID(str(raw))
    return None


def gateway_deployment_id(kwargs: dict[str, Any]) -> str | None:
    """从 LiteLLM callback kwargs 提取当前 deployment 的 stable 行 id（供 Router cooldown）。

    该 id 与 ``router_singleton._build_deployment`` 写入的 ``model_info.id``
    （``router_deployment_row_id(model_name, GatewayModel.id)``）一致：每条 deployment 行唯一，
    故 cooldown 只作用于被选中的那一行，不会跨 model_group/团队串台。模型身份（用量归因）
    另见 ``model_info.gateway_model_id``。
    """
    model_info = litellm_model_info_from_kwargs(kwargs)
    if model_info is None:
        return None
    raw = model_info.get("id")
    if raw is None:
        return None
    stripped = str(raw).strip()
    return stripped or None


def gateway_deployment_owner_user_id(kwargs: dict[str, Any]) -> uuid.UUID | None:
    model_info = litellm_model_info_from_kwargs(kwargs)
    if model_info is None:
        return None
    top_meta = kwargs.get("metadata")
    if isinstance(top_meta, dict):
        raw_meta = top_meta.get("gateway_credential_owner_user_id")
        if raw_meta is not None:
            with suppress(ValueError, TypeError):
                return uuid.UUID(str(raw_meta))
    raw = model_info.get("gateway_credential_owner_user_id")
    if raw is None:
        return None
    with suppress(ValueError, TypeError):
        return uuid.UUID(str(raw))
    return None


__all__ = [
    "gateway_deployment_credential_id",
    "gateway_deployment_id",
    "gateway_deployment_owner_user_id",
    "gateway_deployment_real_model",
    "litellm_model_info_from_kwargs",
]
