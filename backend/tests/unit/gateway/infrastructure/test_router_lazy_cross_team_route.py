"""Router 增量装配：个人路由跨团队 ``{slug}/{model}`` primary 引用。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.route.route_owner_slug_maps import RouteOwnerSlugContext
from domains.gateway.domain.route.router_model_name import encode_router_model_name
from domains.gateway.infrastructure.litellm.router_singleton import (
    _build_deployments_for_encoded_model,
)


@pytest.mark.asyncio
async def test_lazy_build_resolves_slug_prefixed_primary(db_session: AsyncSession) -> None:
    personal_team = uuid.uuid4()
    shared_team = uuid.uuid4()
    shared_slug = "team-ceb079fb"
    cred_id = uuid.uuid4()
    encoded = encode_router_model_name(personal_team, "volcano-text-pool")

    route = MagicMock()
    route.virtual_model = "volcano-text-pool"
    route.primary_models = [f"{shared_slug}/doubao-1-5-lite-32k-250115"]
    route.retry_policy = None
    route.tenant_id = personal_team
    route.enabled = True

    src = MagicMock()
    src.id = uuid.uuid4()
    src.tenant_id = shared_team
    src.name = "doubao-1-5-lite-32k-250115"
    src.real_model = "volcengine/doubao-1-5-lite-32k-250115"
    src.provider = "volcengine"
    src.credential_id = cred_id
    src.capability = "chat"
    src.weight = 1
    src.rpm_limit = None
    src.tpm_limit = None
    src.tags = None

    cred = MagicMock()
    cred.id = cred_id
    cred.name = "volc-cred"
    cred.is_active = True
    cred.scope = "team"
    cred.tenant_id = shared_team
    cred.scope_id = None
    cred.api_key_encrypted = "enc"
    cred.api_base = None
    cred.extra = None

    slug_context = RouteOwnerSlugContext(
        slug_to_tenant={shared_slug: shared_team},
        enable_slug_prefix=True,
    )

    with (
        patch(
            "domains.gateway.infrastructure.repositories.model_repository.GatewayRouteRepository",
        ) as route_repo_cls,
        patch(
            "domains.gateway.infrastructure.repositories.model_repository.GatewayModelRepository",
        ) as model_repo_cls,
        patch(
            "domains.gateway.infrastructure.litellm.router_singleton._load_upstream_pricing_lookup",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "domains.gateway.infrastructure.litellm.router_singleton.build_route_owner_slug_contexts",
            new=AsyncMock(return_value={personal_team: slug_context}),
        ),
        patch(
            "domains.gateway.infrastructure.litellm.router_singleton._resolve_router_credential",
            new=AsyncMock(return_value=cred),
        ),
        patch(
            "domains.gateway.infrastructure.litellm.router_singleton._build_litellm_params",
            return_value={"model": "doubao-1-5-lite-32k-250115", "custom_llm_provider": "volcengine"},
        ),
    ):
        route_repo = route_repo_cls.return_value
        route_repo.resolve_by_virtual_model = AsyncMock(return_value=route)
        model_repo = model_repo_cls.return_value
        model_repo.resolve_by_name = AsyncMock(return_value=None)
        model_repo.resolve_by_name.side_effect = lambda tenant_id, name: (
            src if tenant_id == shared_team and name == "doubao-1-5-lite-32k-250115" else None
        )

        deployments = await _build_deployments_for_encoded_model(db_session, encoded)

    assert len(deployments) == 1
    assert deployments[0]["model_name"] == encoded
    assert deployments[0]["model_info"]["gateway_model_name"] == "doubao-1-5-lite-32k-250115"
    # 团队过滤键须等于 model_name 作用域团队（消费/owner 命名空间），而非底层 src 的 tenant；
    # 否则 LiteLLM filter_team_based_models 会把跨团队委派 deployment 剔除（无可用部署）。
    assert deployments[0]["model_info"]["team_id"] == str(personal_team)
    assert deployments[0]["model_info"]["team_id"] != str(shared_team)
    # 模型身份（用量归因 SSOT）落在 gateway_model_id；行 id 唯一且不等于 GatewayModel.id，
    # 避免同一 src 在多 model_group 下复用 id 造成 cooldown/统计串台。
    assert deployments[0]["model_info"]["gateway_model_id"] == str(src.id)
    assert deployments[0]["model_info"]["id"] != str(src.id)
    model_repo.resolve_by_name.assert_awaited_with(shared_team, "doubao-1-5-lite-32k-250115")
