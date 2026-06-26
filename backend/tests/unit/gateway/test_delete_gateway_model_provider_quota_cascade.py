"""delete_gateway_model / update_gateway_model：上游配额级联。"""

from __future__ import annotations

from decimal import Decimal
import uuid

import pytest

from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.infrastructure.models.provider_quota import ProviderQuota
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.provider_quota_repository import (
    ProviderQuotaRepository,
)
from domains.tenancy.application.team_service import TeamService
from tests.unit.gateway.credential_test_helpers import (
    create_tenant_test_credential,
    team_owner_actor_kw,
)


@pytest.mark.asyncio
async def test_delete_gateway_model_cascades_provider_quotas(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(
        db_session,
        team.id,
        provider="volcengine",
        name=f"pq-cascade-cred-{uuid.uuid4().hex[:6]}",
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        created_by_user_id=test_user.id,
    )
    await db_session.flush()
    real_model = "volcengine/doubao-cascade-test"
    model = await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
        name=f"pq-cascade-model-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model=real_model,
        credential_id=cred.id,
        provider="volcengine",
    )
    quota = ProviderQuota(
        credential_id=cred.id,
        real_model=real_model,
        label="daily",
        window_seconds=86400,
        reset_strategy="calendar_daily_utc",
        reset_timezone="Asia/Shanghai",
        reset_time_minutes=660,
        reset_day_of_month=1,
        limit_tokens=4_800_000,
    )
    db_session.add(quota)
    await db_session.flush()
    quota_id = quota.id

    writes = GatewayManagementWriteService(db_session)
    await writes.delete_gateway_model(
        model.id,
        tenant_id=team.id,
        **team_owner_actor_kw(test_user),
    )
    await db_session.flush()

    assert await GatewayModelRepository(db_session).get(model.id) is None
    assert await ProviderQuotaRepository(db_session).get(quota_id) is None


@pytest.mark.asyncio
async def test_update_gateway_model_rekeys_provider_quotas(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(
        db_session,
        team.id,
        provider="volcengine",
        name=f"pq-rekey-cred-{uuid.uuid4().hex[:6]}",
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        created_by_user_id=test_user.id,
    )
    await db_session.flush()
    old_rm = "volcengine/doubao-old-250615"
    new_rm = "volcengine/doubao-new-251015"
    model = await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
        name=f"pq-rekey-model-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model=old_rm,
        credential_id=cred.id,
        provider="volcengine",
    )
    quota = ProviderQuota(
        credential_id=cred.id,
        real_model=old_rm,
        label="daily",
        window_seconds=86400,
        reset_strategy="rolling",
        reset_timezone="UTC",
        reset_time_minutes=0,
        reset_day_of_month=1,
        limit_usd=Decimal("10"),
    )
    db_session.add(quota)
    await db_session.flush()
    quota_id = quota.id

    writes = GatewayManagementWriteService(db_session)
    await writes.update_gateway_model(
        model.id,
        tenant_id=team.id,
        is_platform_admin=False,
        fields={"real_model": new_rm},
        **team_owner_actor_kw(test_user),
    )
    await db_session.flush()

    row = await ProviderQuotaRepository(db_session).get(quota_id)
    assert row is not None
    assert row.real_model == new_rm
    updated = await GatewayModelRepository(db_session).get(model.id)
    assert updated is not None
    assert updated.real_model == new_rm


@pytest.mark.asyncio
async def test_delete_gateway_model_keeps_quotas_when_sibling_registration_exists(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(
        db_session,
        team.id,
        provider="volcengine",
        name=f"pq-sibling-cred-{uuid.uuid4().hex[:6]}",
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        created_by_user_id=test_user.id,
    )
    await db_session.flush()
    real_model = "volcengine/doubao-shared-binding"
    model_repo = GatewayModelRepository(db_session)
    model_a = await model_repo.create(
        tenant_id=team.id,
        name=f"pq-sibling-a-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model=real_model,
        credential_id=cred.id,
        provider="volcengine",
    )
    await model_repo.create(
        tenant_id=team.id,
        name=f"pq-sibling-b-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model=real_model,
        credential_id=cred.id,
        provider="volcengine",
    )
    quota = ProviderQuota(
        credential_id=cred.id,
        real_model=real_model,
        label="daily",
        window_seconds=86400,
        reset_strategy="rolling",
        reset_timezone="UTC",
        reset_time_minutes=0,
        reset_day_of_month=1,
        limit_tokens=1_000_000,
    )
    db_session.add(quota)
    await db_session.flush()
    quota_id = quota.id

    writes = GatewayManagementWriteService(db_session)
    await writes.delete_gateway_model(
        model_a.id,
        tenant_id=team.id,
        **team_owner_actor_kw(test_user),
    )
    await db_session.flush()

    row = await ProviderQuotaRepository(db_session).get(quota_id)
    assert row is not None
    assert row.real_model == real_model


@pytest.mark.asyncio
async def test_update_gateway_model_rebinds_quotas_on_credential_change(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    old_cred = await create_tenant_test_credential(
        db_session,
        team.id,
        provider="volcengine",
        name=f"pq-old-cred-{uuid.uuid4().hex[:6]}",
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        created_by_user_id=test_user.id,
    )
    new_cred = await create_tenant_test_credential(
        db_session,
        team.id,
        provider="volcengine",
        name=f"pq-new-cred-{uuid.uuid4().hex[:6]}",
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        created_by_user_id=test_user.id,
    )
    await db_session.flush()
    real_model = "volcengine/doubao-cred-move"
    model = await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
        name=f"pq-cred-move-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model=real_model,
        credential_id=old_cred.id,
        provider="volcengine",
    )
    quota = ProviderQuota(
        credential_id=old_cred.id,
        real_model=real_model,
        label="daily",
        window_seconds=86400,
        reset_strategy="rolling",
        reset_timezone="UTC",
        reset_time_minutes=0,
        reset_day_of_month=1,
        limit_tokens=2_000_000,
    )
    db_session.add(quota)
    await db_session.flush()
    quota_id = quota.id

    writes = GatewayManagementWriteService(db_session)
    await writes.update_gateway_model(
        model.id,
        tenant_id=team.id,
        is_platform_admin=False,
        fields={"credential_id": new_cred.id},
        **team_owner_actor_kw(test_user),
    )
    await db_session.flush()

    row = await ProviderQuotaRepository(db_session).get(quota_id)
    assert row is not None
    assert row.credential_id == new_cred.id
    assert row.real_model == real_model
