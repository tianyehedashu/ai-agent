"""ProviderQuotaRepository：模型级联删除/迁移辅助方法。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.infrastructure.models.provider_quota import ProviderQuota
from domains.gateway.infrastructure.repositories.provider_quota_repository import (
    ProviderQuotaRepository,
)


@pytest.mark.asyncio
async def test_delete_all_for_credential_real_model_skips_credential_wide_rows(
    db_session,
) -> None:
    cred_id = uuid.uuid4()
    repo = ProviderQuotaRepository(db_session)
    db_session.add(
        ProviderQuota(
            credential_id=cred_id,
            real_model="volcengine/doubao-a",
            label="daily",
            window_seconds=86400,
            reset_strategy="rolling",
            reset_timezone="UTC",
            reset_time_minutes=0,
            reset_day_of_month=1,
        )
    )
    db_session.add(
        ProviderQuota(
            credential_id=cred_id,
            real_model=None,
            label="all-models",
            window_seconds=86400,
            reset_strategy="rolling",
            reset_timezone="UTC",
            reset_time_minutes=0,
            reset_day_of_month=1,
        )
    )
    await db_session.flush()

    removed = await repo.delete_all_for_credential_real_model(cred_id, "volcengine/doubao-a")
    assert removed == 1
    remaining = await repo.list_for_credential(cred_id)
    assert len(remaining) == 1
    assert remaining[0].real_model is None


@pytest.mark.asyncio
async def test_rekey_real_model_updates_quota_binding(db_session) -> None:
    cred_id = uuid.uuid4()
    repo = ProviderQuotaRepository(db_session)
    row = ProviderQuota(
        credential_id=cred_id,
        real_model="volcengine/doubao-old",
        label="daily",
        window_seconds=86400,
        reset_strategy="rolling",
        reset_timezone="UTC",
        reset_time_minutes=0,
        reset_day_of_month=1,
    )
    db_session.add(row)
    await db_session.flush()

    updated = await repo.rekey_real_model(
        cred_id,
        "volcengine/doubao-old",
        "volcengine/doubao-new",
    )
    assert updated == 1
    await db_session.refresh(row)
    assert row.real_model == "volcengine/doubao-new"


@pytest.mark.asyncio
async def test_rebind_quotas_migrates_credential_and_real_model(db_session) -> None:
    old_cred = uuid.uuid4()
    new_cred = uuid.uuid4()
    repo = ProviderQuotaRepository(db_session)
    row = ProviderQuota(
        credential_id=old_cred,
        real_model="volcengine/doubao-old",
        label="daily",
        window_seconds=86400,
        reset_strategy="rolling",
        reset_timezone="UTC",
        reset_time_minutes=0,
        reset_day_of_month=1,
    )
    db_session.add(row)
    await db_session.flush()

    updated = await repo.rebind_quotas(
        old_credential_id=old_cred,
        old_real_model="volcengine/doubao-old",
        new_credential_id=new_cred,
        new_real_model="volcengine/doubao-new",
    )
    assert updated == 1
    await db_session.refresh(row)
    assert row.credential_id == new_cred
    assert row.real_model == "volcengine/doubao-new"
