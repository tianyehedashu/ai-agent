"""凭据上游模型目录：探测与批量导入（Application 编排）。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, TypeVar
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.management.credential_read_model import CredentialReadModel
from domains.gateway.application.management.ports import (
    RawUpstreamListResult,
    UpstreamModelListPort,
)
from domains.gateway.application.upstream_model_types_for_catalog import (
    infer_upstream_model_types_for_catalog,
)
from domains.gateway.domain.credential_probe import (
    CredentialProbeResult,
    UpstreamModelItem,
)
from domains.gateway.domain.policies.credential_scope import (
    registry_target_for_credential_scope,
)
from domains.gateway.domain.upstream_catalog_policy import (
    resolve_openai_compatible_models_list_url,
)
from domains.gateway.domain.upstream_registration_match import (
    format_already_registered_reason,
    match_registered_names,
)
from domains.gateway.domain.upstream_type_inference import filter_valid_personal_model_types
from domains.gateway.infrastructure.upstream.openai_compatible_model_list_adapter import (
    OpenAICompatibleModelListAdapter,
)
from libs.crypto import decrypt_value, derive_encryption_key
from libs.exceptions import HttpMappableDomainError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)

_ImportItemT = TypeVar("_ImportItemT")


def _append_import_failure(
    failed: list[dict[str, str]], upstream_id: str, reason: str
) -> None:
    failed.append({"upstream_model_id": upstream_id, "reason": reason})


async def _run_batch_import_loop(
    items: list[_ImportItemT],
    *,
    provider_norm: str,
    registered_rows: list[tuple[str, str]],
    upstream_id_of: Callable[[_ImportItemT], str],
    import_one: Callable[[str, _ImportItemT], Awaitable[dict[str, Any] | None]],
    log_tag: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], bool]:
    created: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    reload_once = False
    for item in items:
        mid = upstream_id_of(item).strip()
        if not mid:
            continue
        existing = match_registered_names(provider_norm, mid, registered_rows)
        if existing:
            _append_import_failure(
                failed, mid, format_already_registered_reason(existing)
            )
            continue
        try:
            entry = await import_one(mid, item)
        except ValidationError as exc:
            _append_import_failure(failed, mid, exc.message)
            continue
        except HttpMappableDomainError as exc:
            _append_import_failure(failed, mid, exc.message)
            continue
        except Exception:
            logger.exception("%s unexpected error upstream_model_id=%s", log_tag, mid)
            _append_import_failure(
                failed, mid, "导入失败（内部错误），请稍后重试。"
            )
            continue
        if entry is None:
            continue
        created.append(entry)
        reload_once = True
    return created, failed, reload_once


def _encryption_key() -> str:
    from bootstrap.config import settings

    return derive_encryption_key(settings.secret_key.get_secret_value())


def _decrypt_api_key_for_probe(encrypted: str) -> str | None:
    """解密凭据 API Key；失败时返回 ``None``（禁止将密文当作密钥出站）。"""
    key = _encryption_key()
    try:
        return decrypt_value(encrypted, key)
    except Exception:  # pragma: no cover
        logger.warning("credential decrypt failed for upstream catalog probe")
        return None


class CredentialUpstreamCatalogService:
    """探测上游模型列表；批量导入个人/团队注册行。"""

    def __init__(
        self,
        session: AsyncSession,
        port: UpstreamModelListPort | None = None,
    ) -> None:
        self._session = session
        self._port: UpstreamModelListPort = port or OpenAICompatibleModelListAdapter()
        from domains.gateway.application.management.reads import GatewayManagementReadService
        from domains.gateway.application.management.writes import GatewayManagementWriteService

        self._reads = GatewayManagementReadService(session)
        self._writes = GatewayManagementWriteService(session)

    async def _registered_rows_for_credential(
        self, credential_id: uuid.UUID
    ) -> list[tuple[str, str]]:
        from domains.gateway.infrastructure.repositories.model_repository import (
            GatewayModelRepository,
        )

        return await GatewayModelRepository(
            self._session
        ).list_name_real_model_pairs_for_credential(credential_id)

    async def _enrich_probe_items(
        self,
        *,
        credential_id: uuid.UUID,
        provider: str,
        items: tuple[UpstreamModelItem, ...],
    ) -> tuple[UpstreamModelItem, ...]:
        if not items:
            return items
        rows = await self._registered_rows_for_credential(credential_id)
        if not rows:
            return items
        prov = provider.strip().lower()
        enriched: list[UpstreamModelItem] = []
        for item in items:
            names = match_registered_names(prov, item.id, rows)
            inferred = infer_upstream_model_types_for_catalog(prov, item.id, item.owned_by)
            enriched.append(
                UpstreamModelItem(
                    id=item.id,
                    owned_by=item.owned_by,
                    already_registered=bool(names),
                    registered_names=names,
                    inferred_model_types=inferred,
                )
            )
        return tuple(enriched)

    def _map_raw_to_probe_result(
        self,
        *,
        credential_id: uuid.UUID,
        raw: RawUpstreamListResult,
    ) -> CredentialProbeResult:
        now = datetime.now(UTC)
        if raw.ok:
            items = tuple(
                UpstreamModelItem(
                    id=mid,
                    owned_by=ob,
                    inferred_model_types=list(
                        infer_upstream_model_types_for_catalog("", mid, ob)
                    ),
                )
                for mid, ob in raw.items
            )
            return CredentialProbeResult(
                credential_id=credential_id,
                probe_at=now,
                support="full",
                upstream="openai_compatible",
                items=items,
                message=None,
                http_status=raw.http_status,
            )
        return CredentialProbeResult(
            credential_id=credential_id,
            probe_at=now,
            support="error",
            upstream="openai_compatible",
            items=(),
            message=raw.error_message or "上游列举失败",
            http_status=raw.http_status,
        )

    async def _probe_credential_row(
        self,
        *,
        credential_id: uuid.UUID,
        row: CredentialReadModel,
    ) -> CredentialProbeResult:
        if not row.is_active:
            return CredentialProbeResult(
                credential_id=credential_id,
                probe_at=datetime.now(UTC),
                support="error",
                upstream="none",
                items=(),
                message="凭据已禁用，无法探测。",
                http_status=None,
            )
        st, url, reason = resolve_openai_compatible_models_list_url(
            provider=row.provider, api_base=row.api_base
        )
        if st == "unsupported":
            return CredentialProbeResult(
                credential_id=credential_id,
                probe_at=datetime.now(UTC),
                support="unsupported",
                upstream="none",
                items=(),
                message=reason,
                http_status=None,
            )
        assert url is not None
        api_key = _decrypt_api_key_for_probe(row.api_key_encrypted)
        if api_key is None:
            return CredentialProbeResult(
                credential_id=credential_id,
                probe_at=datetime.now(UTC),
                support="error",
                upstream="none",
                items=(),
                message="无法解密凭据中的 API Key，请检查服务端密钥配置或重新保存凭据。",
                http_status=None,
            )
        raw = await self._port.fetch_models(list_url=url, api_key=api_key)
        base = self._map_raw_to_probe_result(credential_id=credential_id, raw=raw)
        if base.support not in ("full", "partial") or not base.items:
            return base
        items = await self._enrich_probe_items(
            credential_id=credential_id,
            provider=row.provider,
            items=base.items,
        )
        return CredentialProbeResult(
            credential_id=base.credential_id,
            probe_at=base.probe_at,
            support=base.support,
            upstream=base.upstream,
            items=items,
            message=base.message,
            http_status=base.http_status,
        )

    async def probe_user_credential(
        self,
        *,
        user_id: uuid.UUID,
        credential_id: uuid.UUID,
    ) -> CredentialProbeResult:
        row = await self._reads.get_user_credential_for_owner(credential_id, user_id)
        return await self._probe_credential_row(credential_id=credential_id, row=row)

    async def probe_managed_credential(
        self,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
        credential_id: uuid.UUID,
    ) -> CredentialProbeResult:
        row = await self._reads.get_managed_credential_for_team(
            credential_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )
        return await self._probe_credential_row(credential_id=credential_id, row=row)

    async def batch_import_personal_models(
        self,
        *,
        user_id: uuid.UUID,
        credential_id: uuid.UUID,
        provider: str,
        import_items: list[tuple[str, tuple[str, ...]]],
        display_name_prefix: str | None,
        enabled: bool,
        tags: dict[str, Any] | None,
        upstream_model_ids: list[str] | None = None,
        model_types: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        """批量导入个人模型。优先使用 ``import_items``；否则由 legacy 参数构造。"""
        if import_items:
            rows_to_import = list(import_items)
        elif upstream_model_ids:
            shared_types = tuple(model_types or ("text",))
            rows_to_import = [(mid, shared_types) for mid in upstream_model_ids]
        else:
            raise ValidationError("请提供 items 或 upstream_model_ids")

        await self._reads.get_user_credential_for_owner(credential_id, user_id)
        provider_norm = provider.strip().lower()
        registered_rows = await self._registered_rows_for_credential(credential_id)
        work_items: list[tuple[str, tuple[str, ...]]] = []
        pre_failed: list[dict[str, str]] = []
        for raw_id, raw_types in rows_to_import:
            mid = raw_id.strip()
            if not mid:
                continue
            types = filter_valid_personal_model_types(raw_types)
            if not types:
                _append_import_failure(
                    pre_failed,
                    mid,
                    "该上游模型类型不支持个人注册（如 embedding / rerank）",
                )
                continue
            work_items.append((mid, types))

        async def import_one(
            mid: str, payload: tuple[str, tuple[str, ...]]
        ) -> dict[str, Any] | None:
            _mid, types = payload
            display = f"{display_name_prefix} {mid}".strip() if display_name_prefix else mid
            rows = await self._writes.create_personal_models(
                user_id,
                display_name=display,
                provider=provider,
                model_id=mid,
                credential_id=credential_id,
                model_types=list(types),
                tags=tags,
                enabled=enabled,
                reload_router=False,
            )
            registered_rows.extend((r.name, r.real_model) for r in rows)
            return {"upstream_model_id": mid, "gateway_model_ids": [r.id for r in rows]}

        created, failed, reload_once = await _run_batch_import_loop(
            work_items,
            provider_norm=provider_norm,
            registered_rows=registered_rows,
            upstream_id_of=lambda payload: payload[0],
            import_one=import_one,
            log_tag="batch_import_personal_models",
        )
        failed = pre_failed + failed
        if reload_once:
            await self._writes.reload_litellm_router()
        return created, failed

    async def batch_import_team_models(
        self,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
        credential_id: uuid.UUID,
        provider: str,
        capability: str,
        weight: int,
        rpm_limit: int | None,
        tpm_limit: int | None,
        tags: dict[str, Any] | None,
        enabled: bool,
        items: list[tuple[str, str | None]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        cred = await self._reads.get_managed_credential_for_team(
            credential_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )
        if registry_target_for_credential_scope(cred.scope) == "system":
            return await self._batch_import_system_models(
                is_platform_admin=is_platform_admin,
                credential_id=credential_id,
                provider=provider,
                capability=capability,
                weight=weight,
                rpm_limit=rpm_limit,
                tpm_limit=tpm_limit,
                tags=tags,
                enabled=enabled,
                items=items,
            )
        return await self._batch_import_team_models_for_tenant(
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
            credential_id=credential_id,
            provider=provider,
            capability=capability,
            weight=weight,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            tags=tags,
            enabled=enabled,
            items=items,
        )

    async def _batch_import_team_models_for_tenant(
        self,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
        credential_id: uuid.UUID,
        provider: str,
        capability: str,
        weight: int,
        rpm_limit: int | None,
        tpm_limit: int | None,
        tags: dict[str, Any] | None,
        enabled: bool,
        items: list[tuple[str, str | None]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        provider_norm = provider.strip().lower()
        registered_rows = await self._registered_rows_for_credential(credential_id)
        work_items = list(items)

        async def import_one(
            mid: str, payload: tuple[str, str | None]
        ) -> dict[str, Any] | None:
            _upstream_id, name_override = payload
            base_name = (name_override or "").strip() or _slugify_alias(mid)
            unique_name = await self._unique_team_model_name(tenant_id, base_name)
            m = await self._writes.create_gateway_model(
                tenant_id=tenant_id,
                name=unique_name,
                capability=capability,
                real_model=mid,
                credential_id=credential_id,
                provider=provider,
                weight=weight,
                rpm_limit=rpm_limit,
                tpm_limit=tpm_limit,
                tags=tags,
                is_platform_admin=is_platform_admin,
                enabled=enabled,
                reload_router=False,
            )
            registered_rows.append((m.name, m.real_model))
            return {"upstream_model_id": mid, "gateway_model_id": m.id}

        created, failed, reload_once = await _run_batch_import_loop(
            work_items,
            provider_norm=provider_norm,
            registered_rows=registered_rows,
            upstream_id_of=lambda payload: payload[0],
            import_one=import_one,
            log_tag="batch_import_team_models",
        )
        if reload_once:
            await self._writes.reload_litellm_router()
        return created, failed

    async def _batch_import_system_models(
        self,
        *,
        is_platform_admin: bool,
        credential_id: uuid.UUID,
        provider: str,
        capability: str,
        weight: int,
        rpm_limit: int | None,
        tpm_limit: int | None,
        tags: dict[str, Any] | None,
        enabled: bool,
        items: list[tuple[str, str | None]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        provider_norm = provider.strip().lower()
        registered_rows = await self._registered_rows_for_credential(credential_id)
        work_items = list(items)

        async def import_one(
            mid: str, payload: tuple[str, str | None]
        ) -> dict[str, Any] | None:
            _upstream_id, name_override = payload
            base_name = (name_override or "").strip() or _slugify_alias(mid)
            unique_name = await self._unique_system_model_name(base_name)
            m = await self._writes.create_system_gateway_model(
                name=unique_name,
                capability=capability,
                real_model=mid,
                credential_id=credential_id,
                provider=provider,
                weight=weight,
                rpm_limit=rpm_limit,
                tpm_limit=tpm_limit,
                tags=tags,
                is_platform_admin=is_platform_admin,
                enabled=enabled,
                reload_router=False,
            )
            registered_rows.append((m.name, m.real_model))
            return {"upstream_model_id": mid, "gateway_model_id": m.id}

        created, failed, reload_once = await _run_batch_import_loop(
            work_items,
            provider_norm=provider_norm,
            registered_rows=registered_rows,
            upstream_id_of=lambda payload: payload[0],
            import_one=import_one,
            log_tag="batch_import_system_models",
        )
        if reload_once:
            await self._writes.reload_litellm_router()
        return created, failed

    async def _unique_team_model_name(self, team_id: uuid.UUID, base: str) -> str:
        from domains.gateway.infrastructure.repositories.model_repository import (
            GatewayModelRepository,
        )

        repo = GatewayModelRepository(self._session)
        name = base[:200]
        if not await repo.name_exists_for_tenant(team_id, name):
            return name
        for i in range(2, 10_000):
            suffix = f"-{i}"
            candidate = (base[: 200 - len(suffix)] + suffix).strip("-") or f"model-{i}"
            if not await repo.name_exists_for_tenant(team_id, candidate):
                return candidate
        raise ValidationError("无法生成唯一注册别名")

    async def _unique_system_model_name(self, base: str) -> str:
        from domains.gateway.infrastructure.repositories.model_repository import (
            GatewayModelRepository,
        )

        repo = GatewayModelRepository(self._session)
        name = base[:200]
        if not await repo.name_exists_in_scope(None, name):
            return name
        for i in range(2, 10_000):
            suffix = f"-{i}"
            candidate = (base[: 200 - len(suffix)] + suffix).strip("-") or f"model-{i}"
            if not await repo.name_exists_in_scope(None, candidate):
                return candidate
        raise ValidationError("无法生成唯一系统模型注册别名")


def _slugify_alias(model_id: str) -> str:
    out = []
    for ch in model_id.strip():
        if ch.isalnum():
            out.append(ch.lower())
        elif ch in ("/", "_", "-", ".", ":"):
            out.append("-")
    s = "".join(out).strip("-")
    return s[:200] if s else "model"


__all__ = [
    "CredentialUpstreamCatalogService",
    "resolve_openai_compatible_models_list_url",
]
