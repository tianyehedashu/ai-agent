"""delete_gateway_models_batch：部分成功与孤儿清理。"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.domain.types import CONFIG_MANAGED_BY, GATEWAY_MODEL_MANAGED_BY_TAG
from domains.gateway.infrastructure.models.budget import GatewayBudget
from domains.gateway.infrastructure.models.system_gateway import (
    SystemGatewayGrant,
    SystemGatewayModel,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.system_gateway_grant_repository import (
    SystemGatewayGrantRepository,
)
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value
from libs.exceptions import ValidationError


@pytest.mark.asyncio
async def test_batch_delete_system_models_partial_success(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-batch-cred-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await db_session.flush()

    deletable_name = f"sys-batch-del-{uuid.uuid4().hex[:6]}"
    deletable = SystemGatewayModel(
        name=deletable_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    managed = SystemGatewayModel(
        name=f"sys-batch-managed-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
        tags={GATEWAY_MODEL_MANAGED_BY_TAG: CONFIG_MANAGED_BY},
    )
    db_session.add_all([deletable, managed])
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    result = await writes.delete_gateway_models_batch(
        [deletable.id, managed.id],
        tenant_id=team.id,
        is_platform_admin=True,
    )
    await db_session.flush()

    assert deletable.id in result.succeeded
    assert len(result.failed) == 1
    assert result.failed[0].id == managed.id
    assert await GatewayModelRepository(db_session).get_system(deletable.id) is None
    assert await GatewayModelRepository(db_session).get_system(managed.id) is not None


@pytest.mark.asyncio
async def test_batch_delete_requires_platform_admin_for_system_rows(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-batch-noadmin-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await db_session.flush()
    model = SystemGatewayModel(
        name=f"sys-batch-noadmin-model-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    db_session.add(model)
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    result = await writes.delete_gateway_models_batch(
        [model.id],
        tenant_id=team.id,
        is_platform_admin=False,
    )
    assert result.succeeded == []
    assert len(result.failed) == 1
    assert "平台管理员" in result.failed[0].message


@pytest.mark.asyncio
async def test_batch_delete_prunes_grants_and_budgets(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-batch-orphan-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await db_session.flush()
    model_name = f"sys-batch-orphan-model-{uuid.uuid4().hex[:6]}"
    model = SystemGatewayModel(
        name=model_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    db_session.add(model)
    await db_session.flush()
    db_session.add(
        SystemGatewayGrant(
            subject_kind="team",
            subject_id=team.id,
            target_kind="model",
            target_id=model.id,
            granted_by=test_user.id,
        )
    )
    db_session.add(
        GatewayBudget(
            target_kind="system",
            target_id=None,
            period="monthly",
            model_name=model_name,
            limit_usd=Decimal("10"),
        )
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    result = await writes.delete_gateway_models_batch(
        [model.id],
        tenant_id=team.id,
        is_platform_admin=True,
    )
    await db_session.flush()

    assert result.succeeded == [model.id]
    assert result.grants_removed >= 1
    assert result.budgets_removed >= 1
    grants_repo = SystemGatewayGrantRepository(db_session)
    assert (
        await grants_repo.list_for_target("model", model.id) == []
    )


@pytest.mark.asyncio
async def test_batch_delete_rejects_over_limit(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    writes = GatewayManagementWriteService(db_session)
    too_many = [uuid.uuid4() for _ in range(201)]
    with pytest.raises(ValidationError):
        await writes.delete_gateway_models_batch(
            too_many,
            tenant_id=team.id,
            is_platform_admin=True,
        )
