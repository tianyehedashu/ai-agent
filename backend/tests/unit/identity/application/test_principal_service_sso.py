"""principal_service SSO 路径单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.identity.infrastructure.auth.giikin_gateway import GiikinGatewayClaims


@pytest.mark.unit
@pytest.mark.asyncio
class TestPrincipalFromGateway:
    async def test_gateway_principal_preserves_admin_role(self) -> None:
        """SSO 重登时 Principal.role 应来自 DB 既有 users.role，不得覆盖为 user。"""
        from domains.identity.application.principal_service import _principal_from_gateway

        user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.email = "giikin-9009@giikin.sso"
        mock_user.name = "SSO Admin"
        mock_user.role = "admin"
        mock_user.vendor_creator_id = None

        claims = GiikinGatewayClaims(
            user_id="9009",
            name="SSO Admin",
            org_code="",
            shop_id="",
        )
        request = MagicMock()
        mock_db = AsyncMock()

        with (
            patch(
                "domains.identity.infrastructure.auth.giikin_gateway.parse_gateway_identity",
                return_value=claims,
            ),
            patch(
                "domains.identity.application.giikin_identity_service.GiikinIdentityService"
            ) as mock_service_cls,
        ):
            mock_service_cls.return_value.resolve_or_provision = AsyncMock(return_value=mock_user)
            principal = await _principal_from_gateway(request, mock_db)

        assert principal.id == str(user_id)
        assert principal.role == "admin"
        assert principal.email == "giikin-9009@giikin.sso"

    async def test_gateway_principal_jit_user_defaults_to_user_role(self) -> None:
        """JIT 新建用户的 Principal.role 应为 user。"""
        from domains.identity.application.principal_service import _principal_from_gateway

        user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.email = "giikin-5005@giikin.sso"
        mock_user.name = "New SSO"
        mock_user.role = "user"
        mock_user.vendor_creator_id = None

        claims = GiikinGatewayClaims(user_id="5005", name="New SSO", org_code="", shop_id="")
        request = MagicMock()
        mock_db = AsyncMock()

        with (
            patch(
                "domains.identity.infrastructure.auth.giikin_gateway.parse_gateway_identity",
                return_value=claims,
            ),
            patch(
                "domains.identity.application.giikin_identity_service.GiikinIdentityService"
            ) as mock_service_cls,
        ):
            mock_service_cls.return_value.resolve_or_provision = AsyncMock(return_value=mock_user)
            principal = await _principal_from_gateway(request, mock_db)

        assert principal.role == "user"
