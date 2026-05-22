"""ApiKeyEntity 状态推导单测。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

from domains.identity.domain.api_key_types import ApiKeyEntity, ApiKeyScope, ApiKeyStatus


def _entity(
    *,
    is_active: bool = True,
    revoked_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> ApiKeyEntity:
    now = datetime.now(UTC)
    return ApiKeyEntity(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        key_hash="hash",
        key_id="kid",
        key_prefix="sk_",
        name="test",
        description=None,
        scopes={ApiKeyScope.GATEWAY_PROXY},
        expires_at=expires_at or (now + timedelta(days=30)),
        is_active=is_active,
        revoked_at=revoked_at,
        last_used_at=None,
        usage_count=0,
        created_at=now,
        updated_at=now,
        gateway_grants=(),
    )


def test_status_active() -> None:
    entity = _entity()
    assert entity.status == ApiKeyStatus.ACTIVE
    assert entity.is_valid is True


def test_status_disabled() -> None:
    entity = _entity(is_active=False)
    assert entity.status == ApiKeyStatus.DISABLED
    assert entity.is_valid is False


def test_status_revoked() -> None:
    entity = _entity(is_active=False, revoked_at=datetime.now(UTC))
    assert entity.status == ApiKeyStatus.REVOKED
    assert entity.is_valid is False


def test_status_expired() -> None:
    entity = _entity(expires_at=datetime.now(UTC) - timedelta(days=1))
    assert entity.status == ApiKeyStatus.EXPIRED
    assert entity.is_valid is False
