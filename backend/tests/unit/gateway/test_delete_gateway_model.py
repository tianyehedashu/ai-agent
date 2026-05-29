"""delete_gateway_model：租户行与系统行。"""

from __future__ import annotations

from decimal import Decimal
import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.domain.errors import SystemCredentialAdminRequiredError
from domains.gateway.domain.types import CONFIG_MANAGED_BY, GATEWAY_MODEL_MANAGED_BY_TAG
from domains.gateway.infrastructure.models.budget import GatewayBudget
from domains.gateway.infrastructure.models.system_gateway import (
    SystemGatewayGrant,
    SystemGatewayModel,
)
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
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
from tests.unit.gateway.credential_test_helpers import team_owner_actor_kw


@pytest.mark.asyncio
async def test_delete_system_gateway_model_requires_platform_admin(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-del-cred-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await db_session.flush()
    model_name = f"sys-del-model-{uuid.uuid4().hex[:6]}"
    model = SystemGatewayModel(
        name=model_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    db_session.add(model)
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(SystemCredentialAdminRequiredError):
        await writes.delete_gateway_model(
            model.id, tenant_id=team.id, is_platform_admin=False, **team_owner_actor_kw(test_user)
        )

    await writes.delete_gateway_model(
        model.id, tenant_id=team.id, is_platform_admin=True, **team_owner_actor_kw(test_user)
    )
    await db_session.flush()
    assert await GatewayModelRepository(db_session).get_system(model.id) is None


@pytest.mark.asyncio
async def test_delete_system_model_prunes_grants_and_budgets(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-orphan-cred-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await db_session.flush()
    model_name = f"sys-orphan-model-{uuid.uuid4().hex[:6]}"
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
            target_kind="tenant",
            target_id=team.id,
            period="monthly",
            model_name=model_name,
            limit_usd=Decimal("5"),
        )
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    await writes.delete_gateway_model(
        model.id, tenant_id=team.id, is_platform_admin=True, **team_owner_actor_kw(test_user)
    )
    await db_session.flush()

    assert await GatewayModelRepository(db_session).get_system(model.id) is None
    grants_repo = SystemGatewayGrantRepository(db_session)
    assert await grants_repo.list_for_target("model", model.id) == []
    budgets_repo = BudgetRepository(db_session)
    assert await budgets_repo.get_for("tenant", team.id, "monthly", model_name=model_name) is None


@pytest.mark.asyncio
async def test_delete_config_managed_system_model_rejected(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-managed-cred-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await db_session.flush()
    model = SystemGatewayModel(
        name=f"sys-managed-model-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
        tags={GATEWAY_MODEL_MANAGED_BY_TAG: CONFIG_MANAGED_BY},
    )
    db_session.add(model)
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(ValidationError):
        await writes.delete_gateway_model(
            model.id, tenant_id=team.id, is_platform_admin=True, **team_owner_actor_kw(test_user)
        )
