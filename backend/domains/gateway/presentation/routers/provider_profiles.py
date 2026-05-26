"""GET /api/v1/gateway/provider-profiles — 上游方案 SSOT。"""

from __future__ import annotations

from fastapi import APIRouter

from domains.gateway.domain.upstream_profile import UpstreamProtocol
from domains.gateway.domain.upstream_profile_registry import list_all_upstream_profiles
from domains.gateway.presentation.schemas.provider_profiles import (
    ProviderProfileApiBaseResponse,
    ProviderProfileResponse,
    ProviderProfilesListResponse,
)
from domains.identity.presentation.deps import RequiredAuthUser

router = APIRouter()


@router.get("/provider-profiles", response_model=ProviderProfilesListResponse)
async def list_provider_profiles(
    _user: RequiredAuthUser,
) -> ProviderProfilesListResponse:
    profiles = [
        ProviderProfileResponse(
            id=p.id,
            provider=p.provider,
            label=p.label,
            api_bases=ProviderProfileApiBaseResponse(
                openai_compat=p.api_bases.get(UpstreamProtocol.OPENAI_COMPAT),
                anthropic_native=p.api_bases.get(UpstreamProtocol.ANTHROPIC_NATIVE),
            ),
            models_list_path=p.models_list_path,
            default_call_shape=p.default_call_shape.value,
            probe_supported=p.probe_supported,
        )
        for p in list_all_upstream_profiles()
    ]
    return ProviderProfilesListResponse(profiles=profiles)


__all__ = ["router"]
