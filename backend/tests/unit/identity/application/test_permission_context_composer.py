"""PermissionContextComposer 单元测试。"""

import uuid

import pytest

from domains.identity.application.permission_context_composer import PermissionContextComposer
from domains.identity.domain.types import Principal
from libs.iam.permission_context import get_permission_context


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compose_from_principal_sets_team_ids(db_session) -> None:
    composer = PermissionContextComposer(db_session)
    user_id = uuid.uuid4()
    principal = Principal(
        id=str(user_id),
        email="u@example.com",
        name="U",
        role="user",
    )
    ctx = await composer.compose_from_principal(principal)
    composer.install(ctx)
    installed = get_permission_context()
    assert installed is not None
    assert installed.user_id == user_id
