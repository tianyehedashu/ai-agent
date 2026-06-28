"""GatewayModel / SystemGatewayModel → HTTP ``GatewayModelResponse``。"""

from __future__ import annotations

from domains.gateway.application.catalog.config_catalog_sync import selector_capabilities_from_tags
from domains.gateway.domain.catalog.model_selection import (
    RegistryKind,
    registry_kind_for_merged_row,
)
from domains.gateway.domain.visibility.visibility import credential_visibility_for_api
from domains.gateway.presentation.schemas.common import (
    GatewayModelResponse,
    SystemCredentialSummary,
)
from domains.gateway.presentation.tenant_scoped_response import tenant_scoped_orm_dict


def registry_kind_for_row(record: object) -> RegistryKind:
    return registry_kind_for_merged_row(record)


def _system_credential_summary(cred: object | None) -> SystemCredentialSummary | None:
    if cred is None:
        return None
    vis = credential_visibility_for_api(getattr(cred, "visibility", None)) or "public"
    return SystemCredentialSummary(
        id=cred.id,
        provider=cred.provider,
        name=cred.name,
        visibility=vis,
    )


def build_gateway_model_response(
    record: object,
    *,
    include_system_credential: bool = False,
    credentials_by_id: dict | None = None,
    team_credentials_by_id: dict | None = None,
) -> GatewayModelResponse:
    data = tenant_scoped_orm_dict(record)
    kind = registry_kind_for_row(record)
    data["registry_kind"] = kind
    cred_id = getattr(record, "credential_id", None)
    credential_profile_id: str | None = None
    if team_credentials_by_id is not None and cred_id is not None:
        team_cred = team_credentials_by_id.get(cred_id)
        if team_cred is not None:
            data["credential_name"] = team_cred.name
            data["credential_created_by_user_id"] = team_cred.created_by_user_id
            raw_profile = getattr(team_cred, "profile_id", None)
            credential_profile_id = (
                raw_profile.strip() if isinstance(raw_profile, str) and raw_profile.strip() else None
            )
    if kind == "system":
        data["visibility"] = getattr(record, "visibility", None)
        if include_system_credential:
            cred = None
            if credentials_by_id is not None:
                cred = credentials_by_id.get(getattr(record, "credential_id", None))
            if cred is not None:
                data["system_credential"] = _system_credential_summary(cred)
                raw_profile = getattr(cred, "profile_id", None)
                if credential_profile_id is None and isinstance(raw_profile, str) and raw_profile.strip():
                    credential_profile_id = raw_profile.strip()
    response = GatewayModelResponse.model_validate(data)
    if credential_profile_id is None:
        return response
    caps = selector_capabilities_from_tags(
        response.tags or {},
        provider=response.provider,
        real_model=response.real_model,
        credential_profile_id=credential_profile_id,
    )
    return response.model_copy(update={"selector_capabilities": caps})


__all__ = [
    "RegistryKind",
    "build_gateway_model_response",
    "registry_kind_for_row",
]
