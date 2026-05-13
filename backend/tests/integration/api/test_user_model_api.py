"""
User Model API 集成测试

覆盖 /api/v1/user-models 端点的 CRUD、列表、可用模型查询。
"""

from fastapi import status
from httpx import AsyncClient
import pytest


@pytest.mark.integration
class TestUserModelCrudApi:
    """用户模型 CRUD API"""

    @pytest.mark.asyncio
    async def test_create_model_succeeds(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """创建用户模型成功"""
        r = await dev_client.post(
            "/api/v1/user-models/",
            json={
                "display_name": "My GPT-4o",
                "provider": "openai",
                "model_id": "gpt-4o",
                "api_key": "sk-test-key-123456",
                "model_types": ["text", "image"],
            },
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_201_CREATED
        data = r.json()
        assert data["display_name"] == "My GPT-4o"
        assert data["provider"] == "openai"
        assert data["model_id"] == "gpt-4o"
        assert data["has_api_key"] is True
        assert "****" in data["api_key_masked"]
        assert data["model_types"] == ["text", "image"]
        assert data["is_system"] is False
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_model_invalid_provider_returns_400(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """不支持的 provider 返回 400"""
        r = await dev_client.post(
            "/api/v1/user-models/",
            json={
                "display_name": "Bad",
                "provider": "unknown_provider",
                "model_id": "foo",
            },
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_model_invalid_type_returns_400(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """无效的 model_types 返回 400"""
        r = await dev_client.post(
            "/api/v1/user-models/",
            json={
                "display_name": "Bad",
                "provider": "openai",
                "model_id": "gpt-4o",
                "model_types": ["audio"],
            },
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_model_missing_name_returns_422(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """缺少必填字段返回 422"""
        r = await dev_client.post(
            "/api/v1/user-models/",
            json={"provider": "openai", "model_id": "gpt-4o"},
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_list_models(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """列表返回正确结构"""
        await dev_client.post(
            "/api/v1/user-models/",
            json={
                "display_name": "ListTest",
                "provider": "deepseek",
                "model_id": "deepseek-chat",
            },
            headers=auth_headers,
        )
        r = await dev_client.get(
            "/api/v1/user-models/",
            params={"limit": 50},
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_models_filter_by_type(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """按 type 过滤"""
        await dev_client.post(
            "/api/v1/user-models/",
            json={
                "display_name": "VideoOnly",
                "provider": "custom",
                "model_id": "video-gen",
                "model_types": ["video"],
            },
            headers=auth_headers,
        )
        r = await dev_client.get(
            "/api/v1/user-models/",
            params={"type": "video"},
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        for item in r.json()["items"]:
            assert "video" in item["model_types"]

    @pytest.mark.asyncio
    async def test_get_model_detail(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """获取模型详情"""
        cr = await dev_client.post(
            "/api/v1/user-models/",
            json={
                "display_name": "Detail",
                "provider": "openai",
                "model_id": "gpt-4o",
            },
            headers=auth_headers,
        )
        model_id = cr.json()["id"]

        r = await dev_client.get(
            f"/api/v1/user-models/{model_id}",
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["id"] == model_id

    @pytest.mark.asyncio
    async def test_get_model_not_found(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """不存在的模型返回 404"""
        r = await dev_client.get(
            "/api/v1/user-models/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_model(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """更新模型部分字段"""
        cr = await dev_client.post(
            "/api/v1/user-models/",
            json={
                "display_name": "Old Name",
                "provider": "openai",
                "model_id": "gpt-4o",
            },
            headers=auth_headers,
        )
        model_id = cr.json()["id"]

        r = await dev_client.patch(
            f"/api/v1/user-models/{model_id}",
            json={"display_name": "New Name"},
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["display_name"] == "New Name"
        assert r.json()["model_id"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_update_model_not_found(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """更新不存在的模型返回 404"""
        r = await dev_client.patch(
            "/api/v1/user-models/00000000-0000-0000-0000-000000000000",
            json={"display_name": "Nope"},
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_model(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """删除模型"""
        cr = await dev_client.post(
            "/api/v1/user-models/",
            json={
                "display_name": "ToDelete",
                "provider": "openai",
                "model_id": "gpt-4o",
            },
            headers=auth_headers,
        )
        model_id = cr.json()["id"]

        r = await dev_client.delete(
            f"/api/v1/user-models/{model_id}",
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_204_NO_CONTENT

        get_r = await dev_client.get(
            f"/api/v1/user-models/{model_id}",
            headers=auth_headers,
        )
        assert get_r.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_model_not_found(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """删除不存在的模型返回 404"""
        r = await dev_client.delete(
            "/api/v1/user-models/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestUserModelAvailableApi:
    """可用模型列表 API（系统 + 用户合并）"""

    @pytest.mark.asyncio
    async def test_available_returns_both_groups(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """available 同时返回 system_models 和 user_models"""
        await dev_client.post(
            "/api/v1/user-models/",
            json={
                "display_name": "Avail User Model",
                "provider": "openai",
                "model_id": "gpt-4o",
            },
            headers=auth_headers,
        )
        r = await dev_client.get(
            "/api/v1/user-models/available",
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert "system_models" in data
        assert "user_models" in data
        assert isinstance(data["system_models"], list)
        assert isinstance(data["user_models"], list)
        assert len(data["user_models"]) >= 1

    @pytest.mark.asyncio
    async def test_available_system_models_are_flagged(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """系统模型 is_system=True"""
        r = await dev_client.get(
            "/api/v1/user-models/available",
            headers=auth_headers,
        )
        for sm in r.json()["system_models"]:
            assert sm["is_system"] is True

    @pytest.mark.asyncio
    async def test_available_filter_by_type(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """available 支持 type 过滤"""
        r = await dev_client.get(
            "/api/v1/user-models/available",
            params={"type": "text"},
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        for sm in r.json()["system_models"]:
            assert "text" in sm["model_types"]

    @pytest.mark.asyncio
    async def test_available_without_auth_returns_system_models(
        self,
        client: AsyncClient,
    ):
        """无认证时 /available 返回 200，仅含系统模型（不抛 401）"""
        r = await client.get("/api/v1/user-models/available")
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert "system_models" in data
        assert "user_models" in data
        assert isinstance(data["system_models"], list)
        assert isinstance(data["user_models"], list)
        assert len(data["user_models"]) == 0
        # system_models 来自网关 DB（app.toml 经启动/测试 catalog 同步后的全局目录）
        if data["system_models"]:
            for sm in data["system_models"]:
                assert sm.get("is_system") is True
                assert "display_name" in sm
                assert "id" in sm


@pytest.mark.integration
class TestUserModelAuthApi:
    """认证相关"""

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ):
        """未认证请求返回 401"""
        r = await client.get("/api/v1/user-models/")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_create_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ):
        """未认证创建返回 401"""
        r = await client.post(
            "/api/v1/user-models/",
            json={
                "display_name": "X",
                "provider": "openai",
                "model_id": "gpt-4o",
            },
        )
        assert r.status_code == status.HTTP_401_UNAUTHORIZED
