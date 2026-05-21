"""Session personal-tenant 访问策略单元测试。"""

import uuid

import pytest

from domains.session.domain.policies.session_access import (
    can_access_personal_session,
    is_session_in_personal_tenant,
)
from domains.session.infrastructure.models.session import Session


@pytest.mark.unit
def test_is_session_in_personal_tenant_match() -> None:
    tenant = uuid.uuid4()
    session = Session(tenant_id=tenant, status="active", message_count=0, token_count=0)
    assert is_session_in_personal_tenant(session, tenant) is True


@pytest.mark.unit
def test_is_session_in_personal_tenant_mismatch() -> None:
    session = Session(
        tenant_id=uuid.uuid4(),
        status="active",
        message_count=0,
        token_count=0,
    )
    assert is_session_in_personal_tenant(session, uuid.uuid4()) is False


@pytest.mark.unit
def test_can_access_personal_session_platform_admin_bypass() -> None:
    tenant = uuid.uuid4()
    session = Session(
        tenant_id=uuid.uuid4(),
        status="active",
        message_count=0,
        token_count=0,
    )
    assert (
        can_access_personal_session(
            session,
            personal_tenant_id=tenant,
            is_platform_admin=True,
        )
        is True
    )


@pytest.mark.unit
def test_can_access_personal_session_denies_foreign_tenant() -> None:
    session = Session(
        tenant_id=uuid.uuid4(),
        status="active",
        message_count=0,
        token_count=0,
    )
    assert not can_access_personal_session(
        session,
        personal_tenant_id=uuid.uuid4(),
        is_platform_admin=False,
    )
