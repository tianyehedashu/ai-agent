"""resolve_deployment_litellm_params：租户 / 系统凭据解析。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.router_deployment_params import (
    require_volcengine_image_endpoint_id,
    resolve_deployment_litellm_params,
    resolve_volcengine_image_deployment,
)
from domains.gateway.infrastructure.models.system_gateway import (
    SystemGatewayModel,
    SystemProviderCredential,
)
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value
from libs.exceptions import ValidationError


@pytest.mark.asyncio
async def test_resolve_deployment_uses_system_credential_when_no_tenant_cred(
    db_session, test_user
) -> None:
    """系统模型凭据不在 provider_credentials 中，须回退 system_provider_credentials。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = SystemProviderCredential(
        provider="dashscope",
        name="embed-sys-cred",
        api_key_encrypted=encrypt_value("sk-sys-embed", encryption_key),
        visibility="public",
    )
    db_session.add(cred)
    await db_session.flush()

    model_name = f"dashscope/text-embedding-v3-{uuid.uuid4().hex[:6]}"
    db_session.add(
        SystemGatewayModel(
            name=model_name,
            capability="embedding",
            real_model="text-embedding-v3",
            credential_id=cred.id,
            provider="dashscope",
            visibility="public",
        )
    )
    await db_session.flush()

    dep = await resolve_deployment_litellm_params(
        db_session, team.id, model_name, user_id=test_user.id
    )

    assert dep is not None
    assert dep.get("model") == "dashscope/text-embedding-v3"
    assert dep.get("api_key") == "sk-sys-embed"


def test_require_volcengine_image_endpoint_id_raises_when_missing() -> None:
    with pytest.raises(ValidationError, match="image_endpoint_id"):
        require_volcengine_image_endpoint_id({})


@pytest.mark.asyncio
async def test_resolve_volcengine_image_deployment_reads_endpoint_from_extra(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = SystemProviderCredential(
        provider="volcengine",
        name="img-sys-cred",
        api_key_encrypted=encrypt_value("sk-volc-img", encryption_key),
        visibility="public",
        extra={"image_endpoint_id": "ep-img-42"},
    )
    db_session.add(cred)
    await db_session.flush()

    model_name = f"volcengine/seedream-{uuid.uuid4().hex[:6]}"
    db_session.add(
        SystemGatewayModel(
            name=model_name,
            capability="image",
            real_model="seedream",
            credential_id=cred.id,
            provider="volcengine",
            visibility="public",
        )
    )
    await db_session.flush()

    deployment = await resolve_volcengine_image_deployment(
        db_session, team.id, model_name, user_id=test_user.id
    )

    assert deployment is not None
    assert deployment.image_endpoint_id == "ep-img-42"
    assert deployment.litellm_params.get("api_key") == "sk-volc-img"
