"""将 CredentialReadModel 组装为带 api_key_masked 的管理 API 响应。"""

from __future__ import annotations

from binascii import Error as BinasciiError
import uuid

from cryptography.fernet import InvalidToken

from domains.gateway.application.management.credential_read_model import CredentialReadModel
from domains.gateway.domain.errors import CredentialApiKeyDecryptError
from domains.gateway.domain.team_credential_access import team_credential_management_access
from domains.gateway.domain.types import (
    credential_api_scope,
    is_config_managed_system_credential,
)
from domains.gateway.domain.upstream_endpoint import effective_api_bases_for_credential
from domains.gateway.domain.upstream_profile_registry import get_upstream_profile
from domains.gateway.domain.visibility import credential_visibility_for_api
from domains.gateway.presentation.schemas.common import (
    CredentialApiBasesBody,
    CredentialResponse,
    CredentialSummaryResponse,
    PlaygroundCredentialSummaryResponse,
)
from libs.crypto import decrypt_value
from utils.logging import get_logger

logger = get_logger(__name__)

METADATA_ONLY_API_KEY_MASKED = "—"


def mask_plain_secret_for_display(plain: str) -> str:
    """对 API Key 类字符串做展示用掩码（不回传明文）。"""
    s = plain.strip()
    if len(s) <= 8:
        return "••••"
    prefix = s[:4]
    suffix = s[-4:]
    return f"{prefix}…{suffix}"


def credential_api_bases_response(
    stored: dict[str, str] | None,
) -> CredentialApiBasesBody | None:
    if not stored:
        return None
    return CredentialApiBasesBody(
        openai_compat=stored.get("openai_compat"),
        anthropic_native=stored.get("anthropic_native"),
    )


def credential_api_bases_from_body(
    body: CredentialApiBasesBody | None,
) -> dict[str, str | None] | None:
    if body is None:
        return None
    return {
        "openai_compat": body.openai_compat,
        "anthropic_native": body.anthropic_native,
    }


def decrypt_credential_api_key_for_reveal(
    cred: CredentialReadModel,
    *,
    encryption_key: str,
) -> str:
    """解密凭据中的 API Key（仅用于显式 reveal 接口，不写入列表/详情 DTO）。"""
    try:
        return decrypt_value(cred.api_key_encrypted, encryption_key).strip()
    except (InvalidToken, BinasciiError, UnicodeDecodeError, ValueError) as exc:
        logger.warning(
            "credential api_key reveal decrypt failed credential_id=%s exc_type=%s",
            cred.id,
            type(exc).__name__,
        )
        raise CredentialApiKeyDecryptError from exc


def build_credential_response(
    cred: CredentialReadModel,
    *,
    encryption_key: str,
) -> CredentialResponse:
    if cred.api_key_masked is not None:
        api_key_masked = cred.api_key_masked
    else:
        try:
            plain = decrypt_value(cred.api_key_encrypted, encryption_key)
            api_key_masked = mask_plain_secret_for_display(plain)
        except (InvalidToken, BinasciiError, UnicodeDecodeError, ValueError) as exc:
            logger.warning(
                "credential api_key_masked decrypt failed credential_id=%s exc_type=%s",
                cred.id,
                type(exc).__name__,
            )
            api_key_masked = "（无法展示）"
    api_scope = credential_api_scope(scope=cred.scope, tenant_id=cred.tenant_id)
    vis = credential_visibility_for_api(cred.visibility) if api_scope == "system" else None
    profile_label = (
        cred.profile_label or get_upstream_profile(cred.profile_id, provider=cred.provider).label
    )
    if cred.effective_api_base_openai or cred.effective_api_base_anthropic:
        effective_openai = cred.effective_api_base_openai
        effective_anthropic = cred.effective_api_base_anthropic
    else:
        effective = effective_api_bases_for_credential(
            provider=cred.provider,
            profile_id=cred.profile_id,
            api_base=cred.api_base,
            api_bases=cred.api_bases,
        )
        effective_openai = effective.get("openai_compat")
        effective_anthropic = effective.get("anthropic_native")
    return CredentialResponse(
        id=cred.id,
        tenant_id=cred.tenant_id,
        scope=api_scope,
        scope_id=cred.scope_id,
        provider=cred.provider,
        name=cred.name,
        api_base=cred.api_base,
        api_bases=credential_api_bases_response(cred.api_bases),
        profile_id=cred.profile_id,
        profile_label=profile_label,
        effective_api_base_openai=effective_openai,
        effective_api_base_anthropic=effective_anthropic,
        extra=cred.extra,
        is_active=cred.is_active,
        is_config_managed=is_config_managed_system_credential(
            scope=cred.scope,
            tenant_id=cred.tenant_id,
            name=cred.name,
            extra=cred.extra,
        ),
        visibility=vis,
        created_by_user_id=cred.created_by_user_id,
        created_at=cred.created_at,
        api_key_masked=api_key_masked,
        management_access="full",
    )


def build_credential_metadata_response(cred: CredentialReadModel) -> CredentialResponse:
    """团队 member 可见：展示名/通道/状态等，不含密钥与 api_base/extra。"""
    api_scope = credential_api_scope(scope=cred.scope, tenant_id=cred.tenant_id)
    profile_label = (
        cred.profile_label or get_upstream_profile(cred.profile_id, provider=cred.provider).label
    )
    return CredentialResponse(
        id=cred.id,
        tenant_id=cred.tenant_id,
        scope=api_scope,
        scope_id=cred.scope_id,
        provider=cred.provider,
        name=cred.name,
        api_base=None,
        api_bases=None,
        profile_id=cred.profile_id,
        profile_label=profile_label,
        effective_api_base_openai=None,
        effective_api_base_anthropic=None,
        extra=None,
        is_active=cred.is_active,
        is_config_managed=is_config_managed_system_credential(
            scope=cred.scope,
            tenant_id=cred.tenant_id,
            name=cred.name,
            extra=cred.extra,
        ),
        visibility=credential_visibility_for_api(cred.visibility)
        if api_scope == "system"
        else None,
        created_by_user_id=cred.created_by_user_id,
        created_at=cred.created_at,
        api_key_masked=METADATA_ONLY_API_KEY_MASKED,
        management_access="metadata",
    )


def build_credential_response_for_team_workspace_list(
    cred: CredentialReadModel,
    *,
    encryption_key: str,
    actor_user_id: uuid.UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> CredentialResponse:
    """团队凭据 Tab / 跨团队聚合列表：成员可见团队内全部凭据，敏感字段按管理权限分级。"""
    access = team_credential_management_access(
        scope=cred.scope,
        tenant_id=cred.tenant_id,
        created_by_user_id=cred.created_by_user_id,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    )
    if access == "full":
        return build_credential_response(cred, encryption_key=encryption_key)
    return build_credential_metadata_response(cred)


def build_credential_summary_response(cred: CredentialReadModel) -> CredentialSummaryResponse:
    """凭据摘要 DTO（无密钥）；读/写侧均应先映射为 CredentialReadModel。"""
    return CredentialSummaryResponse(
        id=cred.id,
        provider=cred.provider,
        name=cred.name,
        scope=credential_api_scope(scope=cred.scope, tenant_id=cred.tenant_id),
        is_active=cred.is_active,
        is_config_managed=is_config_managed_system_credential(
            scope=cred.scope,
            tenant_id=cred.tenant_id,
            name=cred.name,
            extra=cred.extra,
        ),
        created_by_user_id=cred.created_by_user_id,
    )


def build_playground_credential_summary_response(
    cred: CredentialReadModel,
    *,
    context_team_id: uuid.UUID | None,
) -> PlaygroundCredentialSummaryResponse:
    """Playground 凭据摘要（含 context_team_id）。"""
    return PlaygroundCredentialSummaryResponse(
        **build_credential_summary_response(cred).model_dump(),
        context_team_id=context_team_id,
    )


__all__ = [
    "METADATA_ONLY_API_KEY_MASKED",
    "build_credential_metadata_response",
    "build_credential_response",
    "build_credential_response_for_team_workspace_list",
    "build_credential_summary_response",
    "build_playground_credential_summary_response",
    "credential_api_bases_from_body",
    "credential_api_bases_response",
    "decrypt_credential_api_key_for_reveal",
    "mask_plain_secret_for_display",
]
