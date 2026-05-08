"""
Product Info API 集成测试
"""

from unittest.mock import patch

from fastapi import status
from httpx import AsyncClient
import pytest


@pytest.mark.integration
class TestProductInfoJobApi:
    """产品信息 Job API"""

    @pytest.mark.asyncio
    async def test_create_job_succeeds(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """创建任务成功"""
        r = await dev_client.post(
            "/api/v1/product-info/jobs",
            params={"title": "Test Job"},
            json={},
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_201_CREATED
        data = r.json()
        assert "id" in data
        assert data["title"] == "Test Job"
        assert data["status"] == "draft"

    @pytest.mark.asyncio
    async def test_list_jobs_succeeds(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """任务列表成功"""
        await dev_client.post(
            "/api/v1/product-info/jobs",
            params={"title": "J1"},
            json={},
            headers=auth_headers,
        )
        r = await dev_client.get(
            "/api/v1/product-info/jobs",
            params={"limit": 10},
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_get_job_succeeds(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """获取任务详情（含 steps）"""
        create_r = await dev_client.post(
            "/api/v1/product-info/jobs",
            params={"title": "Get Me"},
            json={},
            headers=auth_headers,
        )
        assert create_r.status_code == status.HTTP_201_CREATED
        job_id = create_r.json()["id"]

        r = await dev_client.get(
            f"/api/v1/product-info/jobs/{job_id}",
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert data["id"] == job_id
        assert "steps" in data
        assert isinstance(data["steps"], list)

    @pytest.mark.asyncio
    async def test_get_job_not_found(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """不存在的任务返回 404"""
        r = await dev_client.get(
            "/api/v1/product-info/jobs/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_job_succeeds(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """删除任务成功"""
        create_r = await dev_client.post(
            "/api/v1/product-info/jobs",
            params={"title": "To Delete"},
            json={},
            headers=auth_headers,
        )
        job_id = create_r.json()["id"]

        r = await dev_client.delete(
            f"/api/v1/product-info/jobs/{job_id}",
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_204_NO_CONTENT

        get_r = await dev_client.get(
            f"/api/v1/product-info/jobs/{job_id}",
            headers=auth_headers,
        )
        assert get_r.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestProductInfoCapabilitiesApi:
    """能力与默认提示词 API"""

    @pytest.mark.asyncio
    async def test_list_capabilities_succeeds(self, dev_client: AsyncClient):
        """能力列表（无需认证）"""
        r = await dev_client.get("/api/v1/product-info/capabilities")
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 5
        ids = [x["id"] for x in data]
        assert "image_analysis" in ids
        assert "product_link_analysis" in ids

    @pytest.mark.asyncio
    async def test_get_default_prompt_succeeds(self, dev_client: AsyncClient):
        """默认提示词"""
        r = await dev_client.get(
            "/api/v1/product-info/capabilities/product_link_analysis/default-prompt"
        )
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert data["capability_id"] == "product_link_analysis"
        assert "content" in data
        assert len(data["content"]) > 0


@pytest.mark.integration
class TestProductInfoRunStepApi:
    """执行单步 API（mock LLM）"""

    @pytest.mark.asyncio
    async def test_run_step_succeeds(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """执行 product_link_analysis 一步成功（mock 执行器）"""
        create_r = await dev_client.post(
            "/api/v1/product-info/jobs",
            params={"title": "Run Step"},
            json={},
            headers=auth_headers,
        )
        job_id = create_r.json()["id"]

        async def _mock_runner(_inputs, _prompt, _gateway, **_kw):
            return {"product_info": {"category": "test", "selling_points": []}}

        with patch.dict(
            "domains.agent.application.product_info_use_case.RUNNERS",
            {"product_link_analysis": _mock_runner},
        ):
            r = await dev_client.post(
                f"/api/v1/product-info/jobs/{job_id}/steps",
                json={
                    "capability_id": "product_link_analysis",
                    "user_input": {"product_link": "https://example.com/p"},
                },
                headers=auth_headers,
            )
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert data["id"] == job_id
        steps = data.get("steps") or []
        assert any(
            s["capability_id"] == "product_link_analysis" and s["status"] == "completed"
            for s in steps
        )

    @pytest.mark.asyncio
    async def test_run_step_unknown_capability_returns_400(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """未知 capability_id 返回 400"""
        create_r = await dev_client.post(
            "/api/v1/product-info/jobs",
            params={"title": "Bad Step"},
            json={},
            headers=auth_headers,
        )
        job_id = create_r.json()["id"]

        r = await dev_client.post(
            f"/api/v1/product-info/jobs/{job_id}/steps",
            json={
                "capability_id": "unknown_cap",
                "user_input": {},
            },
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.integration
class TestProductInfoStepAndOptimizeApi:
    """步骤执行与提示词优化 API（mock LLM）"""

    async def _create_job(self, dev_client: AsyncClient, auth_headers: dict) -> str:
        r = await dev_client.post(
            "/api/v1/product-info/jobs",
            params={"title": "Step API Test"},
            json={},
            headers=auth_headers,
        )
        return r.json()["id"]

    @pytest.mark.asyncio
    async def test_run_step_renders_and_executes(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """run_step 渲染提示词后直接执行，status=completed"""
        job_id = await self._create_job(dev_client, auth_headers)

        async def _mock_runner(_inputs, prompt, _gw, **_kw):
            return {"product_info": {"prompt_received": prompt}}

        with patch.dict(
            "domains.agent.application.product_info_use_case.RUNNERS",
            {"product_link_analysis": _mock_runner},
        ):
            r = await dev_client.post(
                f"/api/v1/product-info/jobs/{job_id}/steps",
                json={
                    "capability_id": "product_link_analysis",
                    "user_input": {"product_link": "https://a.com"},
                    "meta_prompt": "分析产品 {{product_link}}",
                },
                headers=auth_headers,
            )
        assert r.status_code == status.HTTP_200_OK
        step = next(s for s in r.json()["steps"] if s["capability_id"] == "product_link_analysis")
        assert step["status"] == "completed"
        assert "https://a.com" in step["output_snapshot"]["product_info"]["prompt_received"]

    @pytest.mark.asyncio
    async def test_optimize_prompt_endpoint(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """optimize-prompt 返回优化后的提示词"""
        job_id = await self._create_job(dev_client, auth_headers)

        async def _mock_optimize(_cap, _meta, _ctx, _gw, **_kw):
            return "AI optimized prompt"

        with patch(
            "domains.agent.application.product_info_use_case.optimize_prompt_for_capability",
            side_effect=_mock_optimize,
        ):
            r = await dev_client.post(
                f"/api/v1/product-info/jobs/{job_id}/optimize-prompt",
                json={
                    "capability_id": "product_link_analysis",
                    "user_input": {"product_link": "https://a.com"},
                    "meta_prompt": "Analyze carefully",
                },
                headers=auth_headers,
            )
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert data["capability_id"] == "product_link_analysis"
        assert data["optimized_prompt"] == "AI optimized prompt"

    @pytest.mark.asyncio
    async def test_step_response_includes_prompt_fields(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """响应 JSON 中包含 meta_prompt 和 prompt_used 字段"""
        job_id = await self._create_job(dev_client, auth_headers)

        async def _mock_runner(_i, _p, _g, **_kw):
            return {"product_info": {}}

        with patch.dict(
            "domains.agent.application.product_info_use_case.RUNNERS",
            {"product_link_analysis": _mock_runner},
        ):
            r = await dev_client.post(
                f"/api/v1/product-info/jobs/{job_id}/steps",
                json={
                    "capability_id": "product_link_analysis",
                    "user_input": {},
                    "meta_prompt": "my prompt",
                },
                headers=auth_headers,
            )
        step = r.json()["steps"][0]
        assert step["meta_prompt"] == "my prompt"
        assert step["prompt_used"] is not None
        assert step["status"] == "completed"


@pytest.mark.integration
class TestProductInfoRunPipelineApi:
    """一键异步执行 API"""

    @pytest.mark.asyncio
    async def test_run_pipeline_returns_202(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """一键执行返回 202 与 job_id"""
        async def _noop_pipeline(**_kwargs: object) -> None:
            return None

        with patch(
            "domains.agent.presentation.product_info_router.run_pipeline_async",
            _noop_pipeline,
        ):
            r = await dev_client.post(
                "/api/v1/product-info/run",
                json={"inputs": {"product_name": "test"}},
                headers=auth_headers,
            )
        assert r.status_code == status.HTTP_202_ACCEPTED
        data = r.json()
        assert "job_id" in data
        assert data["status"] == "running"
        assert "poll_url" in data


@pytest.mark.integration
class TestProductInfoTemplatesApi:
    """用户模板 API"""

    @pytest.mark.asyncio
    async def test_list_templates_succeeds(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """模板列表"""
        r = await dev_client.get(
            "/api/v1/product-info/capabilities/product_link_analysis/templates",
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_create_and_get_template_succeeds(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        """创建模板并获取"""
        create_r = await dev_client.post(
            "/api/v1/product-info/capabilities/product_link_analysis/templates",
            json={"name": "My Template", "content": "Analyze this product..."},
            headers=auth_headers,
        )
        assert create_r.status_code == status.HTTP_201_CREATED
        template = create_r.json()
        assert template["name"] == "My Template"
        assert template["content"] == "Analyze this product..."
        template_id = template["id"]

        get_r = await dev_client.get(
            f"/api/v1/product-info/templates/{template_id}",
            headers=auth_headers,
        )
        assert get_r.status_code == status.HTTP_200_OK
        assert get_r.json()["id"] == template_id
