"""
Session Ownership permission check unit tests.

Tests the behavior of check_session_ownership function.
"""

import uuid

import pytest

from domains.identity.presentation.deps import check_session_ownership
from domains.identity.presentation.schemas import CurrentUser
from domains.session.infrastructure.models import Session
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)
from libs.exceptions import PermissionDeniedError


@pytest.mark.unit
class TestSessionOwnership:
    """Session ownership check tests."""

    def _create_mock_session(self, tenant_id: uuid.UUID) -> Session:
        return Session(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            status="active",
            message_count=0,
            token_count=0,
        )

    def _create_registered_user(self, user_id: str | None = None) -> CurrentUser:
        if user_id is None:
            user_id = str(uuid.uuid4())
        return CurrentUser(
            id=user_id,
            email=f"test_{user_id}@example.com",
            name="Test User",
            is_anonymous=False,
        )

    def _create_anonymous_user(self, anonymous_id: str | None = None) -> CurrentUser:
        if anonymous_id is None:
            anonymous_id = str(uuid.uuid4())
        from domains.identity.domain.types import Principal

        principal_id = Principal.make_anonymous_id(anonymous_id)
        return CurrentUser(
            id=principal_id,
            email=Principal.make_anonymous_email(anonymous_id),
            name="Anonymous User",
            is_anonymous=True,
        )

    def test_registered_user_owns_session(self):
        tenant_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        user = self._create_registered_user(user_id)
        session = self._create_mock_session(tenant_id)
        set_permission_context(
            PermissionContext(
                user_id=uuid.UUID(user_id),
                role="user",
                team_ids=frozenset({tenant_id}),
            )
        )
        try:
            check_session_ownership(session, user)
        finally:
            clear_permission_context()

    def test_registered_user_cannot_access_other_user_session(self):
        user1_id = str(uuid.uuid4())
        user1 = self._create_registered_user(user1_id)
        session = self._create_mock_session(uuid.uuid4())
        set_permission_context(
            PermissionContext(
                user_id=uuid.UUID(user1_id),
                role="user",
                team_ids=frozenset({uuid.uuid4()}),
            )
        )
        try:
            with pytest.raises(PermissionDeniedError) as exc_info:
                check_session_ownership(session, user1)
            assert "permission" in exc_info.value.message.lower()
        finally:
            clear_permission_context()

    def test_anonymous_user_owns_session(self):
        anonymous_id = str(uuid.uuid4())
        tenant_id = uuid.uuid4()
        user = self._create_anonymous_user(anonymous_id)
        session = self._create_mock_session(tenant_id)
        set_permission_context(
            PermissionContext(
                anonymous_user_id=anonymous_id,
                role="user",
                team_ids=frozenset({tenant_id}),
            )
        )
        try:
            check_session_ownership(session, user)
        finally:
            clear_permission_context()

    def test_anonymous_user_cannot_access_other_anonymous_user_session(self):
        anonymous_id_1 = str(uuid.uuid4())
        user1 = self._create_anonymous_user(anonymous_id_1)
        session = self._create_mock_session(uuid.uuid4())
        set_permission_context(
            PermissionContext(
                anonymous_user_id=anonymous_id_1,
                role="user",
                team_ids=frozenset({uuid.uuid4()}),
            )
        )
        try:
            with pytest.raises(PermissionDeniedError):
                check_session_ownership(session, user1)
        finally:
            clear_permission_context()

    def test_admin_can_access_any_session(self):
        from domains.identity.presentation.deps import ADMIN_ROLE

        session = self._create_mock_session(uuid.uuid4())
        admin = CurrentUser(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            name="Admin",
            is_anonymous=False,
            role=ADMIN_ROLE,
        )
        check_session_ownership(session, admin)
