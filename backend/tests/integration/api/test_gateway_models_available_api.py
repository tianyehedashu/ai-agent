"""
Gateway 可用模型列表 API 集成测试

覆盖 GET /api/v1/gateway/models/available（系统目录 + personal gateway_models）。
"""

import uuid

from fastapi import status
from httpx import AsyncClient
import pytest

_AVAILABLE = "/api/v1/gateway/models/available"


def _paginated_items(section: dict) -> list:
    return section.get("items", section) if isinstance(section, dict) else section


@pytest.mark.integration
class TestGatewayModelsAvailableApi:
    """可用模型列表 API（系统 + 用户合并）"""

    @pytest.mark.asyncio
    async def test_available_returns_both_groups(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """available 同时返回 system_models 和 user_models"""
        r_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"avail-cred-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-avail-int-test-key-123456",
            },
        )
        assert r_cred.status_code == status.HTTP_201_CREATED, r_cred.text
        cred_id = r_cred.json()["id"]

        r_create = await dev_client.post(
            "/api/v1/gateway/my-models",
            headers=auth_headers,
            json={
                "display_name": "Avail User Model",
                "provider": "openai",
                "model_id": "gpt-4o",
                "credential_id": cred_id,
                "model_types": ["text"],
            },
        )
        assert r_create.status_code == status.HTTP_201_CREATED, r_create.text

        r = await dev_client.get(_AVAILABLE, headers=auth_headers)
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert "system_models" in data
        assert "user_models" in data
        assert isinstance(data["system_models"], dict)
        assert isinstance(data["user_models"], dict)
        assert "items" in data["system_models"]
        assert "items" in data["user_models"]
        assert len(_paginated_items(data["user_models"])) >= 1

    @pytest.mark.asyncio
    async def test_available_system_models_are_flagged(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """系统模型 is_system=True"""
        r = await dev_client.get(_AVAILABLE, headers=auth_headers)
        for sm in _paginated_items(r.json()["system_models"]):
            assert sm["is_system"] is True

    @pytest.mark.asyncio
    async def test_available_filter_by_type(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """available 支持 type 过滤"""
        r = await dev_client.get(
            _AVAILABLE,
            params={"type": "text"},
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        for sm in _paginated_items(r.json()["system_models"]):
            assert "text" in sm["model_types"]

    @pytest.mark.asyncio
    async def test_available_invalid_provider_returns_400(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        r = await dev_client.get(
            _AVAILABLE,
            params={"provider": "bad_vendor"},
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_available_filter_by_provider(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        r_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "deepseek",
                "name": f"avail-ds-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-avail-ds-int-test-key-123456",
            },
        )
        assert r_cred.status_code == status.HTTP_201_CREATED, r_cred.text
        cred_id = r_cred.json()["id"]

        r_create = await dev_client.post(
            "/api/v1/gateway/my-models",
            headers=auth_headers,
            json={
                "display_name": "Avail DS",
                "provider": "deepseek",
                "model_id": "deepseek-chat",
                "credential_id": cred_id,
                "model_types": ["text"],
            },
        )
        assert r_create.status_code == status.HTTP_201_CREATED, r_create.text

        r = await dev_client.get(
            _AVAILABLE,
            params={"type": "text", "provider": "deepseek"},
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        for sm in _paginated_items(data["system_models"]):
            assert sm["provider"] == "deepseek"
        for um in _paginated_items(data["user_models"]):
            assert um["provider"] == "deepseek"

    @pytest.mark.asyncio
    async def test_available_without_auth_returns_system_models(
        self,
        client: AsyncClient,
    ):
        """无认证时 /available 返回 200，仅含系统模型（不抛 401）"""
        r = await client.get(_AVAILABLE)
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert "system_models" in data
        assert "user_models" in data
        assert isinstance(data["system_models"], dict)
        assert isinstance(data["user_models"], dict)
        assert len(_paginated_items(data["user_models"])) == 0
        system_items = _paginated_items(data["system_models"])
        if system_items:
            for sm in system_items:
                assert sm.get("is_system") is True
                assert "display_name" in sm
                assert "id" in sm
