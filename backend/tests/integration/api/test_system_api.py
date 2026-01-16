"""
System API 集成测试

测试系统API端点，包括模型列表
"""

from fastapi import status
from httpx import AsyncClient
import pytest


class TestSystemAPI:
    """System API 集成测试"""

    @pytest.mark.asyncio
    async def test_list_models_simple(self, client: AsyncClient):
        """测试: 获取简单模型列表"""
        # Act
        response = await client.get("/api/v1/system/models/simple")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # 检查模型格式
        if len(data) > 0:
            model = data[0]
            assert "value" in model
            assert "label" in model
            assert "provider" in model

    @pytest.mark.asyncio
    async def test_list_models_simple_includes_glm_when_configured(
        self, client: AsyncClient, monkeypatch
    ):
        """测试: 当配置了智谱AI API Key时，模型列表包含GLM模型"""
        # Arrange - Mock API Key配置
        from app.config import settings

        monkeypatch.setattr(settings, "zhipuai_api_key", "test-key")

        # Act
        response = await client.get("/api/v1/system/models/simple")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

        # 查找GLM模型
        glm_models = [m for m in data if m["provider"] == "zhipuai"]
        if glm_models:
            assert any(m["value"] == "glm-4.7" for m in glm_models)
            # 检查显示名称
            glm_47 = next((m for m in glm_models if m["value"] == "glm-4.7"), None)
            if glm_47:
                assert glm_47["label"] == "GLM-4.7"

    @pytest.mark.asyncio
    async def test_list_models_simple_excludes_glm_when_not_configured(
        self, client: AsyncClient, monkeypatch
    ):
        """测试: 当未配置智谱AI API Key时，模型列表不包含GLM模型"""
        # Arrange - Mock API Key为None
        from app.config import settings

        monkeypatch.setattr(settings, "zhipuai_api_key", None)

        # Act
        response = await client.get("/api/v1/system/models/simple")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

        # 不应该有zhipuai提供商的模型
        glm_models = [m for m in data if m["provider"] == "zhipuai"]
        assert len(glm_models) == 0

    @pytest.mark.asyncio
    async def test_get_public_config(self, client: AsyncClient):
        """测试: 获取公开配置"""
        # Act
        response = await client.get("/api/v1/system/config")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "app_name" in data
        assert "environment" in data
        assert "features" in data
        assert "limits" in data
