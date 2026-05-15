"""将 app.toml ``models.available`` 幂等同步到 ``GatewayModel``（team_id NULL）与 system 凭据。"""

from __future__ import annotations

import logging
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from bootstrap.config_loader import ModelInfo, app_config
from domains.agent.application.ports.model_catalog_port import ModelCapabilitySnapshot
from domains.gateway.application.catalog_capability import infer_catalog_capability
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from libs.crypto import derive_encryption_key, encrypt_value

logger = logging.getLogger(__name__)

MANAGED_BY_KEY = "managed_by"
MANAGED_CONFIG = "config"
SYSTEM_CREDENTIAL_NAME = "app-config-default"


def _provider_api_key_and_base(provider: str) -> tuple[str | None, str | None]:
    """从 Settings 读取明文 API Key 与 base（无则返回 None）。"""
    if provider == "openai":
        key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
        return key, settings.openai_api_base
    if provider == "deepseek":
        key = settings.deepseek_api_key.get_secret_value() if settings.deepseek_api_key else None
        return key, settings.deepseek_api_base
    if provider == "anthropic":
        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
        return key, None
    if provider == "dashscope":
        key = settings.dashscope_api_key.get_secret_value() if settings.dashscope_api_key else None
        return key, settings.dashscope_api_base
    if provider == "zhipuai":
        key = settings.zhipuai_api_key.get_secret_value() if settings.zhipuai_api_key else None
        return key, settings.zhipuai_api_base
    if provider == "volcengine":
        key = (
            settings.volcengine_api_key.get_secret_value() if settings.volcengine_api_key else None
        )
        return key, settings.volcengine_api_base
    if provider == "custom":
        return None, None
    logger.warning("Unknown provider %s for gateway catalog sync", provider)
    return None, None


def _volcengine_extra() -> dict[str, Any] | None:
    chat_id = settings.volcengine_chat_endpoint_id or settings.volcengine_endpoint_id
    if chat_id:
        return {"endpoint_id": chat_id}
    return None


async def _ensure_system_credential(
    session: AsyncSession,
    *,
    provider: str,
    encryption_key: str,
) -> uuid.UUID | None:
    """每个 provider 一条 system 默认凭据；无 API Key 时返回 None。"""
    repo = ProviderCredentialRepository(session)
    plain_key, api_base = _provider_api_key_and_base(provider)
    if not plain_key:
        return None

    existing = await repo.find_system_by_provider_and_name(provider, SYSTEM_CREDENTIAL_NAME)
    encrypted = encrypt_value(plain_key, encryption_key)
    extra = _volcengine_extra() if provider == "volcengine" else None
    if existing is not None:
        await repo.update(
            existing.id,
            api_key_encrypted=encrypted,
            api_base=api_base,
            extra=extra,
            is_active=True,
        )
        return existing.id

    created = await repo.create(
        scope="system",
        scope_id=None,
        provider=provider,
        name=SYSTEM_CREDENTIAL_NAME,
        api_key_encrypted=encrypted,
        api_base=api_base,
        extra=extra,
        is_active=True,
    )
    return created.id


def _build_tags_from_model_info(model: ModelInfo) -> dict[str, Any]:
    tags: dict[str, Any] = {
        MANAGED_BY_KEY: MANAGED_CONFIG,
        "display_name": model.name,
        "context_window": model.context_window,
        "supports_vision": model.supports_vision,
        "supports_tools": model.supports_tools,
        "supports_reasoning": model.supports_reasoning,
        "supports_json_mode": model.supports_json_mode,
        "supports_image_gen": model.supports_image_gen,
        # 旧字段：单位混乱（¥/千tokens 或 $/1M tokens），保留只供前端展示用。
        "input_price": model.input_price,
        "output_price": model.output_price,
        "description": model.description,
        "recommended_for": list(model.recommended_for),
    }
    if model.supports_image_gen:
        tags["supports_txt2img"] = model.supports_txt2img
        tags["supports_img2img"] = model.supports_img2img
    if model.supports_video_gen:
        tags["supports_video_gen"] = True
    if model.supports_image_to_video:
        tags["supports_image_to_video"] = True
    if int(model.max_reference_images or 0) > 0:
        tags["max_reference_images"] = int(model.max_reference_images)

    # 与 LiteLLM 对齐的 USD/token 价格。仅在显式配置为正数时透传，
    # 避免把默认 0 写入 tags 后误抑制 LiteLLM 内置 model_cost_map 的价目。
    input_cpt = getattr(model, "input_cost_per_token", 0.0) or 0.0
    output_cpt = getattr(model, "output_cost_per_token", 0.0) or 0.0
    if input_cpt > 0:
        tags["input_cost_per_token"] = float(input_cpt)
    if output_cpt > 0:
        tags["output_cost_per_token"] = float(output_cpt)
    return tags


def _infer_model_types_from_tags(tags: dict[str, Any], capability: str) -> list[str]:
    """结合网关 capability 与 tags 推断 user-model 选择器 ``model_types``。"""
    cap = (capability or "").strip().lower()
    if cap in (
        "embedding",
        "audio_transcription",
        "audio_speech",
        "rerank",
        "moderation",
    ):
        return []
    out: list[str] = []
    if tags.get("supports_video_gen"):
        out.append("video")
    if cap == "image":
        out.append("image_gen")
    elif cap == "video_generation":
        if "video" not in out:
            out.append("video")
    elif cap == "chat":
        out.append("text")
        if tags.get("supports_vision"):
            out.append("image")
        if tags.get("supports_image_gen"):
            out.append("image_gen")
    if not out:
        out.append("text")
        if tags.get("supports_vision"):
            out.append("image")
    return out


def model_types_for_gateway_registration(tags: dict[str, Any], capability: str) -> list[str]:
    """管理 API / 文档用：与 ``gateway_model_to_selector_item`` 的 ``model_types`` 推导一致。"""
    return _infer_model_types_from_tags(tags, capability)


def selector_capabilities_from_tags(tags: dict[str, Any]) -> dict[str, Any]:
    """扁平特性字典，与选择器 ``capabilities`` 字段对齐。"""
    return _selector_capabilities_payload(tags)


def _selector_capabilities_payload(tags: dict[str, Any]) -> dict[str, Any]:
    """供前端展示与校验的扁平能力（与 ``ModelCapabilitySnapshot`` 对齐）。"""
    snap = tags_to_capability_snapshot(tags)
    return {
        "supports_vision": snap.supports_vision,
        "supports_tools": snap.supports_tools,
        "supports_reasoning": snap.supports_reasoning,
        "supports_json_mode": snap.supports_json_mode,
        "supports_image_gen": snap.supports_image_gen,
        "supports_txt2img": snap.supports_txt2img,
        "supports_img2img": snap.supports_img2img,
        "supports_video_gen": snap.supports_video_gen,
        "supports_image_to_video": snap.supports_image_to_video,
        "max_reference_images": snap.max_reference_images,
    }


async def sync_app_config_gateway_catalog(session: AsyncSession) -> dict[str, int]:
    """将 ``app_config.models.available`` 同步到全局 ``GatewayModel``。

    Returns:
        统计字段：upserted, disabled, skipped_no_credential, vkeys_pruned
    """
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    models_repo = GatewayModelRepository(session)
    desired_ids = {m.id for m in app_config.models.available if m.litellm_model or m.id}
    upserted = 0
    skipped = 0

    for model in app_config.models.available:
        if not (model.litellm_model or model.id):
            continue
        cred_id = await _ensure_system_credential(
            session, provider=model.provider, encryption_key=encryption_key
        )
        if cred_id is None:
            logger.info(
                "Gateway catalog sync: skip model %s (no API key for provider %s)",
                model.id,
                model.provider,
            )
            skipped += 1
            continue
        real_model = model.litellm_model or model.id
        capability = infer_catalog_capability(model)
        tags = _build_tags_from_model_info(model)
        existing = await models_repo.get_by_name(None, model.id)
        if existing is None:
            await models_repo.create(
                team_id=None,
                name=model.id,
                capability=capability,
                real_model=real_model,
                credential_id=cred_id,
                provider=model.provider,
                weight=1,
                rpm_limit=None,
                tpm_limit=None,
                tags=tags,
            )
            upserted += 1
            continue

        if (existing.tags or {}).get(MANAGED_BY_KEY) != MANAGED_CONFIG:
            skipped += 1
            continue

        merged_tags = tags
        if not settings.gateway_catalog_config_overwrites_managed:
            merged_tags = {**(existing.tags or {}), **tags}
            merged_tags[MANAGED_BY_KEY] = MANAGED_CONFIG

        await models_repo.update(
            existing.id,
            capability=capability,
            real_model=real_model,
            credential_id=cred_id,
            provider=model.provider,
            enabled=True,
            tags=merged_tags,
        )
        upserted += 1

    disabled = 0
    newly_disabled_names: list[str] = []
    global_rows = await models_repo.list_for_team(None, only_enabled=False)
    for row in global_rows:
        row_tags = row.tags or {}
        if row_tags.get(MANAGED_BY_KEY) != MANAGED_CONFIG:
            continue
        if row.name in desired_ids:
            continue
        if row.enabled:
            await models_repo.update(row.id, enabled=False)
            disabled += 1
            newly_disabled_names.append(row.name)

    vkeys_pruned = 0
    if settings.gateway_catalog_prune_vkey_allowed_models and newly_disabled_names:
        vkey_repo = VirtualKeyRepository(session)
        vkeys_pruned = await vkey_repo.remove_model_names_from_all_allowed_lists(
            frozenset(newly_disabled_names)
        )

    await session.flush()
    logger.info(
        "Gateway catalog sync finished: upserted=%s disabled=%s skipped_no_credential=%s vkeys_pruned=%s",
        upserted,
        disabled,
        skipped,
        vkeys_pruned,
    )
    return {
        "upserted": upserted,
        "disabled": disabled,
        "skipped_no_credential": skipped,
        "vkeys_pruned": vkeys_pruned,
    }


def gateway_model_to_selector_item(row: GatewayModel) -> dict[str, Any]:
    """将 ORM 行转为 user-models 选择器条目。"""
    tags = row.tags or {}
    display_name = str(tags.get("display_name") or row.name)
    raw_vendor = tags.get("video_vendor_model_id") or tags.get("giikin_video_model")
    video_vendor_model_id = (
        str(raw_vendor).strip() if isinstance(raw_vendor, str) and str(raw_vendor).strip() else None
    )
    video_durations = tags.get("video_durations")
    return {
        "id": row.name,
        "display_name": display_name,
        "provider": row.provider,
        "model_id": row.name,
        "model_types": _infer_model_types_from_tags(tags, row.capability),
        "capabilities": _selector_capabilities_payload(tags),
        "video_vendor_model_id": video_vendor_model_id,
        "video_durations": video_durations if isinstance(video_durations, list) else None,
        "is_system": True,
        "config": {
            "context_window": tags.get("context_window", 0),
            "supports_vision": bool(tags.get("supports_vision", False)),
            "supports_tools": bool(tags.get("supports_tools", True)),
            "supports_reasoning": bool(tags.get("supports_reasoning", False)),
            "input_price": tags.get("input_price", 0.0),
            "output_price": tags.get("output_price", 0.0),
            "description": tags.get("description", ""),
        },
    }


def tags_to_capability_snapshot(tags: dict[str, Any]) -> ModelCapabilitySnapshot:
    supports_image_gen = bool(tags.get("supports_image_gen", False))
    default_txt2 = supports_image_gen
    default_img2 = supports_image_gen
    return ModelCapabilitySnapshot(
        supports_tools=bool(tags.get("supports_tools", True)),
        supports_reasoning=bool(tags.get("supports_reasoning", False)),
        supports_json_mode=bool(tags.get("supports_json_mode", True)),
        supports_vision=bool(tags.get("supports_vision", False)),
        supports_image_gen=supports_image_gen,
        supports_txt2img=bool(tags.get("supports_txt2img", default_txt2)),
        supports_img2img=bool(tags.get("supports_img2img", default_img2)),
        supports_video_gen=bool(tags.get("supports_video_gen", False)),
        supports_image_to_video=bool(tags.get("supports_image_to_video", False)),
        max_reference_images=int(tags.get("max_reference_images", 0) or 0),
    )


__all__ = [
    "MANAGED_BY_KEY",
    "MANAGED_CONFIG",
    "gateway_model_to_selector_item",
    "model_types_for_gateway_registration",
    "selector_capabilities_from_tags",
    "sync_app_config_gateway_catalog",
    "tags_to_capability_snapshot",
]
