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
    async def test_list_models_simple_includes_zhipuai_catalog(self, client: AsyncClient):
        """测试: 静态模型目录包含智谱 GLM（凭据由 Gateway 管理，不随 settings API Key 过滤）"""
        response = await client.get("/api/v1/system/models/simple")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

        glm_models = [m for m in data if m["provider"] == "zhipuai"]
        assert glm_models, "static catalog should list zhipuai models"
        assert any(m["value"] == "glm-4.7" for m in glm_models)
        glm_47 = next(m for m in glm_models if m["value"] == "glm-4.7")
        assert glm_47["label"] == "GLM-4.7"

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
