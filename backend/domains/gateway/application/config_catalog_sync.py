"""将 Gateway 目录种子（JSON）幂等同步到 ``GatewayModel``（team_id NULL）与 system 凭据。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from domains.gateway.application.catalog.gateway_model_tags_pipeline import build_gateway_model_tags
from domains.gateway.application.catalog_capability import infer_catalog_capability
from domains.gateway.application.credential_model_cascade import (
    sync_gateway_models_for_credential_is_active,
)
from domains.gateway.application.gateway_catalog_seed import resolve_catalog_seed_models
from domains.gateway.application.model_reference_prune import prune_gateway_model_name_references
from domains.gateway.domain.catalog_seed_model import CatalogSeedModel
from domains.gateway.domain.credential_persist import normalize_credential_write_fields
from domains.gateway.domain.credential_sync_policy import (
    credential_force_env_sync,
    resolve_bootstrap_api_base,
)
from domains.gateway.domain.model_capability import tags_to_capability_snapshot
from domains.gateway.domain.policies.catalog_provider_availability import (
    build_catalog_provider_retirement_plan,
)
from domains.gateway.domain.provider_env_catalog import (
    ProviderEnvSnapshot,
    provider_env_snapshot_from_settings,
    resolve_provider_credentials,
    volcengine_extra_from_snapshot,
)
from domains.gateway.domain.registry_model_types import infer_model_types_from_tags
from domains.gateway.domain.types import (
    CONFIG_MANAGED_BY,
    CONFIG_MANAGED_CREDENTIAL_NAME,
)
from domains.gateway.domain.upstream_endpoint import infer_profile_id_from_env_api_base
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from libs.crypto import derive_encryption_key, encrypt_value

if TYPE_CHECKING:
    from domains.gateway.application.gateway_model_listing import GatewayRegistryModelRow

logger = logging.getLogger(__name__)

MANAGED_BY_KEY = "managed_by"
MANAGED_CONFIG = CONFIG_MANAGED_BY
SYSTEM_CREDENTIAL_NAME = CONFIG_MANAGED_CREDENTIAL_NAME


def _provider_env_snapshot() -> ProviderEnvSnapshot:
    return provider_env_snapshot_from_settings(settings)


def _provider_api_key_and_base(provider: str) -> tuple[str | None, str | None]:
    """从 Settings 快照读取明文 API Key 与 base（无则 return None）。"""
    creds = resolve_provider_credentials(provider, _provider_env_snapshot())
    if creds is None:
        logger.warning("Unknown provider %s for gateway catalog sync", provider)
        return None, None
    return creds.api_key, creds.api_base


def _config_managed_credential_extra(provider: str) -> dict[str, Any]:
    extra: dict[str, Any] = {MANAGED_BY_KEY: MANAGED_CONFIG}
    if provider == "volcengine":
        ve = volcengine_extra_from_snapshot(_provider_env_snapshot())
        if ve:
            extra.update(ve)
    return extra


def _merge_config_managed_credential_extra(
    provider: str,
    existing_extra: dict[str, Any] | None,
) -> dict[str, Any]:
    """合并 sync 托管字段；保留 ``force_env_sync`` 等管理面写入的 extra 键。"""
    sync_extra = _config_managed_credential_extra(provider)
    if not existing_extra:
        return sync_extra
    return {**existing_extra, **sync_extra}


async def _ensure_system_credential(
    session: AsyncSession,
    *,
    provider: str,
    encryption_key: str,
) -> uuid.UUID | None:
    """每个 provider 一条 system 默认凭据；无 API Key 时返回 None。"""
    from bootstrap.config import settings
    from domains.gateway.domain.provider_api_base import get_default_api_base

    repo = SystemProviderCredentialRepository(session)
    plain_key, api_base = _provider_api_key_and_base(provider)
    if not plain_key and (
        settings.app_env != "production" or os.environ.get("PYTEST_VERSION")
    ):
        # 非生产 / pytest：占位凭据仍注册 seed 模型，便于集成测 Router 解析（上游由 mock 承接）
        plain_key = f"sk-gateway-catalog-placeholder-{provider.strip().lower()}"
        api_base = api_base or get_default_api_base(provider)
    if not plain_key:
        return None

    existing = await repo.find_config_managed(provider)
    encrypted = encrypt_value(plain_key, encryption_key)
    existing_extra = existing.extra if existing is not None else None
    extra = _merge_config_managed_credential_extra(provider, existing_extra)
    resolved_base = resolve_bootstrap_api_base(
        provider=provider,
        env_base=api_base,
        existing_base=existing.api_base if existing is not None else None,
        is_new_credential=existing is None,
        force_env_sync=credential_force_env_sync(existing_extra),
    )
    profile_id = (
        existing.profile_id
        if existing is not None and existing.profile_id
        else infer_profile_id_from_env_api_base(provider, api_base=resolved_base)
    )
    stored_base, stored_bases, stored_profile_id = normalize_credential_write_fields(
        provider=provider,
        profile_id=profile_id,
        api_base=resolved_base,
        existing_api_base=existing.api_base if existing is not None else None,
        existing_api_bases=(
            dict(existing.api_bases) if existing is not None and existing.api_bases else None
        ),
        existing_profile_id=existing.profile_id if existing is not None else None,
    )
    if existing is not None:
        await repo.update(
            existing.id,
            api_key_encrypted=encrypted,
            api_base=stored_base,
            api_bases=stored_bases,
            profile_id=stored_profile_id,
            extra=extra,
            is_active=True,
        )
        return existing.id

    created = await repo.create(
        provider=provider,
        name=SYSTEM_CREDENTIAL_NAME,
        api_key_encrypted=encrypted,
        api_base=stored_base,
        api_bases=stored_bases,
        profile_id=stored_profile_id,
        extra=extra,
        is_active=True,
    )
    return created.id


def build_tags_from_seed_model(model: CatalogSeedModel) -> dict[str, Any]:
    real_model = (model.litellm_model or model.id).strip()
    explicit_tp = getattr(model, "thinking_param", None)
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
    if isinstance(explicit_tp, str) and explicit_tp.strip():
        tags["thinking_param"] = explicit_tp.strip()
    if model.supports_image_gen:
        tags["supports_txt2img"] = model.supports_txt2img
        tags["supports_img2img"] = model.supports_img2img
    if model.supports_video_gen:
        tags["supports_video_gen"] = True
    if model.supports_image_to_video:
        tags["supports_image_to_video"] = True
    if int(model.max_reference_images or 0) > 0:
        tags["max_reference_images"] = int(model.max_reference_images)

    tags = build_gateway_model_tags(
        tags,
        provider=model.provider,
        real_model=real_model,
        skip_hints=True,
        on_hint_thinking_param=lambda hint_tp: logger.warning(
            "catalog seed %s: litellm hint thinking_param=%s (no explicit seed value)",
            model.id,
            hint_tp,
        ),
    )

    # 计费用单价写入 upstream_model_pricing（见 _upsert_upstream_pricing_from_model），不再写入 tags。
    return tags


async def _upsert_upstream_pricing_from_model(
    session: AsyncSession,
    *,
    model: CatalogSeedModel,
    real_model: str,
    capability: str,
) -> None:
    from decimal import Decimal

    from domains.gateway.infrastructure.repositories.pricing_repository import (
        UpstreamPricingRepository,
    )

    input_cpt = getattr(model, "input_cost_per_token", 0.0) or 0.0
    output_cpt = getattr(model, "output_cost_per_token", 0.0) or 0.0
    if input_cpt <= 0 or output_cpt <= 0:
        return
    repo = UpstreamPricingRepository(session)
    existing = await repo.get_active(
        provider=model.provider,
        upstream_model=real_model,
        capability=capability,
    )
    if existing is not None:
        return
    await repo.create(
        provider=model.provider,
        upstream_model=real_model,
        capability=capability,
        input_cost_per_token=Decimal(str(input_cpt)),
        output_cost_per_token=Decimal(str(output_cpt)),
        source="seed",
    )


def model_types_for_gateway_registration(tags: dict[str, Any], capability: str) -> list[str]:
    """管理 API / 文档用：与 ``gateway_model_to_selector_item`` 的 ``model_types`` 推导一致。"""
    return infer_model_types_from_tags(tags, capability)


def selector_capabilities_from_tags(
    tags: dict[str, Any],
    *,
    provider: str = "",
    real_model: str = "",
    credential_profile_id: str | None = None,
) -> dict[str, Any]:
    """扁平特性字典，与选择器 ``capabilities`` 字段对齐。"""
    return _selector_capabilities_payload(
        tags,
        provider=provider,
        real_model=real_model,
        credential_profile_id=credential_profile_id,
    )


def _selector_capabilities_payload(
    tags: dict[str, Any],
    *,
    provider: str = "",
    real_model: str = "",
    credential_profile_id: str | None = None,
) -> dict[str, Any]:
    """供前端展示与校验的扁平能力（与 ``ModelCapabilitySnapshot`` 对齐）。"""
    snap = tags_to_capability_snapshot(
        tags,
        provider=provider,
        real_model=real_model,
        credential_profile_id=credential_profile_id,
    )
    return {
        "supports_vision": snap.supports_vision,
        "supports_tools": snap.supports_tools,
        "supports_reasoning": snap.supports_reasoning,
        "thinking_param": snap.thinking_param,
        "temperature_policy": snap.temperature_policy,
        "temperature_default": snap.temperature_default,
        "supports_json_mode": snap.supports_json_mode,
        "supports_image_gen": snap.supports_image_gen,
        "supports_txt2img": snap.supports_txt2img,
        "supports_img2img": snap.supports_img2img,
        "supports_video_gen": snap.supports_video_gen,
        "supports_image_to_video": snap.supports_image_to_video,
        "max_reference_images": snap.max_reference_images,
    }


async def sync_gateway_catalog_from_seed(
    session: AsyncSession,
    *,
    seed_path: Path | None = None,
) -> dict[str, int]:
    """将 ``gateway-catalog.seed.json`` 同步到全局 ``GatewayModel``。"""
    models = resolve_catalog_seed_models(seed_path)
    return await _sync_catalog_models(session, models)


async def sync_app_config_gateway_catalog(session: AsyncSession) -> dict[str, int]:
    """兼容旧名：等同 ``sync_gateway_catalog_from_seed``（不含价目注册与审计）。"""
    return await sync_gateway_catalog_from_seed(session)


async def _sync_catalog_models(
    session: AsyncSession,
    models: list[CatalogSeedModel],
) -> dict[str, int]:
    """将模型列表幂等写入 system gateway_models。

    Returns:
        统计字段：upserted, disabled, skipped_no_credential, vkeys_pruned
    """
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    models_repo = GatewayModelRepository(session)
    creds_repo = SystemProviderCredentialRepository(session)
    desired_ids = {m.id for m in models if m.litellm_model or m.id}
    upserted = 0
    skipped = 0
    providers_without_key: set[str] = set()

    for model in models:
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
            providers_without_key.add(model.provider.strip().lower())
            skipped += 1
            continue
        raw_model = model.litellm_model or model.id
        real_model = raw_model  # 存储上游模型 ID，不加 LiteLLM provider 前缀
        capability = infer_catalog_capability(model)
        tags = build_tags_from_seed_model(model)
        existing = await models_repo.get_system_by_name(model.id)
        if existing is None:
            await models_repo.create_system(
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
            await _upsert_upstream_pricing_from_model(
                session, model=model, real_model=real_model, capability=capability
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

        await models_repo.update_system(
            existing.id,
            capability=capability,
            real_model=real_model,
            credential_id=cred_id,
            provider=model.provider,
            enabled=True,
            tags=merged_tags,
            # visibility / grants 由平台管理员维护，catalog reload 不覆盖
        )
        await _upsert_upstream_pricing_from_model(
            session, model=model, real_model=real_model, capability=capability
        )
        upserted += 1

    disabled = 0
    newly_disabled_names: list[str] = []
    global_rows = await models_repo.list_system(only_enabled=False)
    for row in global_rows:
        row_tags = row.tags or {}
        if row_tags.get(MANAGED_BY_KEY) != MANAGED_CONFIG:
            continue
        if row.name in desired_ids:
            continue
        if row.enabled:
            await models_repo.update_system(row.id, enabled=False)
            disabled += 1
            newly_disabled_names.append(row.name)

    credentials_deactivated = 0
    if providers_without_key:
        plan = build_catalog_provider_retirement_plan(
            providers_without_key=providers_without_key,
            system_models=global_rows,
            system_credentials=await creds_repo.list_all(),
        )
        for model_id in plan.model_ids_to_disable:
            await models_repo.update_system(model_id, enabled=False)
            disabled += 1

        for cred_id in plan.credential_ids_to_deactivate:
            await creds_repo.update(cred_id, is_active=False)
            credentials_deactivated += 1
            await sync_gateway_models_for_credential_is_active(
                session,
                models_repo,
                cred_id,
                is_active=False,
            )
        newly_disabled_names.extend(plan.affected_model_names)
        if plan.affected_model_names:
            logger.info(
                "Gateway catalog sync: retired %d config-managed models for providers %s",
                len(plan.affected_model_names),
                sorted(providers_without_key),
            )

    vkeys_pruned = 0
    routes_pruned = 0
    if settings.gateway_catalog_prune_vkey_allowed_models and newly_disabled_names:
        vkeys_pruned, routes_pruned = await prune_gateway_model_name_references(
            session, frozenset(newly_disabled_names)
        )

    await session.flush()
    logger.info(
        "Gateway catalog sync finished: upserted=%s disabled=%s skipped_no_credential=%s "
        "credentials_deactivated=%s vkeys_pruned=%s routes_pruned=%s",
        upserted,
        disabled,
        skipped,
        credentials_deactivated,
        vkeys_pruned,
        routes_pruned,
    )
    return {
        "upserted": upserted,
        "disabled": disabled,
        "skipped_no_credential": skipped,
        "credentials_deactivated": credentials_deactivated,
        "vkeys_pruned": vkeys_pruned,
        "routes_pruned": routes_pruned,
    }


def gateway_model_to_selector_item(row: GatewayRegistryModelRow) -> dict[str, Any]:
    """将 ORM 行转为模型选择器 system_models 条目（``GatewayModel`` 或 ``SystemGatewayModel``）。"""
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
        "real_model": row.real_model,
        "model_id": row.name,
        "model_types": infer_model_types_from_tags(tags, row.capability),
        "selector_capabilities": _selector_capabilities_payload(
            tags, provider=row.provider, real_model=row.real_model
        ),
        # Deprecated: 与 selector_capabilities 同义；计划 2026-Q3 前移除，请改用 selector_capabilities。
        "capabilities": _selector_capabilities_payload(
            tags, provider=row.provider, real_model=row.real_model
        ),
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


__all__ = [
    "MANAGED_BY_KEY",
    "MANAGED_CONFIG",
    "gateway_model_to_selector_item",
    "model_types_for_gateway_registration",
    "selector_capabilities_from_tags",
    "sync_app_config_gateway_catalog",
    "sync_gateway_catalog_from_seed",
]
