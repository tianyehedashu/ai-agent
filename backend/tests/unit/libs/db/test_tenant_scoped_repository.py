"""TenantScopedRepositoryBase 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.session.infrastructure.models import Session
from libs.db.base_repository import TenantScopedRepositoryBase
from libs.iam.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


class MockTenantSessionRepository(TenantScopedRepositoryBase[Session]):
    @property
    def model_class(self) -> type[Session]:
        return Session


@pytest.mark.unit
class TestTenantScopedRepositoryBase:
    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def repository(self, mock_db: AsyncMock) -> MockTenantSessionRepository:
        return MockTenantSessionRepository(mock_db)

    @pytest.mark.asyncio
    async def test_apply_tenant_scope_admin_bypass(
        self, repository: MockTenantSessionRepository
    ) -> None:
        tid = uuid.uuid4()
        ctx = PermissionContext(user_id=uuid.uuid4(), role="admin", team_ids=frozenset({tid}))
        set_permission_context(ctx)
        try:
            query = select(Session)
            filtered = repository._apply_tenant_scope(query)
            assert filtered is not None
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_find_for_tenants_with_team_ids(
        self, repository: MockTenantSessionRepository, mock_db: AsyncMock
    ) -> None:
        tid = uuid.uuid4()
        ctx = PermissionContext(user_id=uuid.uuid4(), role="user", team_ids=frozenset({tid}))
        set_permission_context(ctx)
        try:
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_db.execute = AsyncMock(return_value=mock_result)

            rows = await repository.find_for_tenants(skip=0, limit=10)
            assert rows == []
            assert mock_db.execute.called
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_get_in_tenants_no_context_returns_none(
        self, repository: MockTenantSessionRepository, mock_db: AsyncMock
    ) -> None:
        clear_permission_context()
        with pytest.raises(RuntimeError, match="PermissionContext"):
            await repository.get_in_tenants(uuid.uuid4())
