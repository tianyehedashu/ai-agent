"""
Session 鉴权路径一致性：REST 与 Chat 对外部会话 ID 的拒绝语义应对齐。
"""

from __future__ import annotations

import uuid

from fastapi import status
from httpx import AsyncClient
import pytest

from domains.identity.application import UserUseCase
from domains.identity.infrastructure.models.user import User


async def _auth_headers_for_user(db_session, user: User) -> dict[str, str]:
    token_pair = await UserUseCase(db_session).create_token(user)
    return {"Authorization": f"Bearer {token_pair.access_token}"}


@pytest.mark.integration
class TestSessionAuthzPathParity:
    """REST GET 与 Chat 复用 Session 域 personal tenant 校验时的结果应对齐。"""

    @pytest.mark.asyncio
    async def test_foreign_user_rest_and_chat_both_deny(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
    ) -> None:
        create = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Owner Session"},
            headers=auth_headers,
        )
        assert create.status_code == status.HTTP_201_CREATED
        session_id = create.json()["id"]

        owner_get = await dev_client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )
        assert owner_get.status_code == status.HTTP_200_OK

        other = User(
            email=f"other_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Other User",
        )
        db_session.add(other)
        await db_session.commit()
        await db_session.refresh(other)
        other_headers = await _auth_headers_for_user(db_session, other)

        rest_get = await dev_client.get(
            f"/api/v1/sessions/{session_id}",
            headers=other_headers,
        )
        assert rest_get.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

        chat_resp = await dev_client.post(
            "/api/v1/chat",
            json={"session_id": session_id, "message": "hello"},
            headers=other_headers,
        )
        assert chat_resp.status_code == status.HTTP_200_OK
        body = chat_resp.text.lower()
        assert (
            "not found" in body or "permission" in body or "don't have" in body or "error" in body
        )
