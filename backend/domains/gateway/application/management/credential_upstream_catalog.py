"""凭据上游模型目录：探测与批量导入（Application 编排）。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.management.ports import (
    RawUpstreamListResult,
    UpstreamModelListPort,
)
from domains.gateway.domain.credential_probe import (
    CredentialProbeResult,
    UpstreamModelItem,
)
from domains.gateway.domain.upstream_catalog_policy import (
    resolve_openai_compatible_models_list_url,
)
from domains.gateway.infrastructure.upstream.openai_compatible_model_list_adapter import (
    OpenAICompatibleModelListAdapter,
)
from libs.crypto import decrypt_value, derive_encryption_key
from libs.exceptions import HttpMappableDomainError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)


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

    def _map_raw_to_probe_result(
        self,
        *,
        credential_id: uuid.UUID,
        raw: RawUpstreamListResult,
    ) -> CredentialProbeResult:
        now = datetime.now(UTC)
        if raw.ok:
            items = tuple(
                UpstreamModelItem(id=mid, owned_by=ob) for mid, ob in raw.items
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

    async def probe_user_credential(
        self,
        *,
        user_id: uuid.UUID,
        credential_id: uuid.UUID,
    ) -> CredentialProbeResult:
        row = await self._reads.get_user_credential_for_owner(credential_id, user_id)
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
        return self._map_raw_to_probe_result(credential_id=credential_id, raw=raw)

    async def probe_managed_credential(
        self,
        *,
        team_id: uuid.UUID,
        is_platform_admin: bool,
        credential_id: uuid.UUID,
    ) -> CredentialProbeResult:
        row = await self._reads.get_managed_credential_for_team(
            credential_id,
            team_id=team_id,
            is_platform_admin=is_platform_admin,
        )
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
        return self._map_raw_to_probe_result(credential_id=credential_id, raw=raw)

    async def batch_import_personal_models(
        self,
        *,
        user_id: uuid.UUID,
        credential_id: uuid.UUID,
        provider: str,
        upstream_model_ids: list[str],
        model_types: list[str],
        display_name_prefix: str | None,
        enabled: bool,
        tags: dict[str, Any] | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        await self._reads.get_user_credential_for_owner(credential_id, user_id)
        created: list[dict[str, Any]] = []
        failed: list[dict[str, str]] = []
        reload_once = False
        for raw_id in upstream_model_ids:
            mid = raw_id.strip()
            if not mid:
                continue
            display = f"{display_name_prefix} {mid}".strip() if display_name_prefix else mid
            try:
                rows = await self._writes.create_personal_models(
                    user_id,
                    display_name=display,
                    provider=provider,
                    model_id=mid,
                    credential_id=credential_id,
                    model_types=list(model_types),
                    tags=tags,
                    enabled=enabled,
                    reload_router=False,
                )
                reload_once = True
            except ValidationError as exc:
                failed.append({"upstream_model_id": mid, "reason": exc.message})
                continue
            except HttpMappableDomainError as exc:
                failed.append({"upstream_model_id": mid, "reason": exc.message})
                continue
            except Exception:
                logger.exception(
                    "batch_import_personal_models unexpected error upstream_model_id=%s",
                    mid,
                )
                failed.append(
                    {
                        "upstream_model_id": mid,
                        "reason": "导入失败（内部错误），请稍后重试。",
                    }
                )
                continue
            created.append(
                {
                    "upstream_model_id": mid,
                    "gateway_model_ids": [r.id for r in rows],
                }
            )
        if reload_once:
            await self._writes.reload_litellm_router()
        return created, failed

    async def batch_import_team_models(
        self,
        *,
        team_id: uuid.UUID,
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
        await self._reads.get_managed_credential_for_team(
            credential_id,
            team_id=team_id,
            is_platform_admin=is_platform_admin,
        )

        created: list[dict[str, Any]] = []
        failed: list[dict[str, str]] = []
        reload_once = False
        for upstream_id, name_override in items:
            mid = upstream_id.strip()
            if not mid:
                continue
            base_name = (name_override or "").strip() or _slugify_alias(mid)
            try:
                unique_name = await self._unique_team_model_name(team_id, base_name)
                m = await self._writes.create_gateway_model(
                    team_id=team_id,
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
                reload_once = True
            except ValidationError as exc:
                failed.append({"upstream_model_id": mid, "reason": exc.message})
                continue
            except HttpMappableDomainError as exc:
                failed.append({"upstream_model_id": mid, "reason": exc.message})
                continue
            except Exception:
                logger.exception(
                    "batch_import_team_models unexpected error upstream_model_id=%s",
                    mid,
                )
                failed.append(
                    {
                        "upstream_model_id": mid,
                        "reason": "导入失败（内部错误），请稍后重试。",
                    }
                )
                continue
            created.append({"upstream_model_id": mid, "gateway_model_id": m.id})
        if reload_once:
            await self._writes.reload_litellm_router()
        return created, failed

    async def _unique_team_model_name(self, team_id: uuid.UUID, base: str) -> str:
        from domains.gateway.infrastructure.repositories.model_repository import (
            GatewayModelRepository,
        )

        repo = GatewayModelRepository(self._session)
        name = base[:200]
        if not await repo.name_exists_on_team(team_id, name):
            return name
        for i in range(2, 10_000):
            suffix = f"-{i}"
            candidate = (base[: 200 - len(suffix)] + suffix).strip("-") or f"model-{i}"
            if not await repo.name_exists_on_team(team_id, candidate):
                return candidate
        raise ValidationError("无法生成唯一注册别名")


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
