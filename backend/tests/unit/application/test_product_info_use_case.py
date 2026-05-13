"""
Product Info Use Case 单元测试
"""

import uuid

import pytest

from domains.agent.application.product_info_use_case import ProductInfoUseCase
from domains.gateway.application.sql_model_catalog import get_model_catalog_adapter
from domains.agent.domain.product_info.constants import (
    CAPABILITY_IDS,
    CAPABILITY_ORDER,
    DEFAULT_PROMPTS,
)
from domains.identity.infrastructure.models.user import User
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)
from libs.exceptions import NotFoundError, ValidationError


@pytest.mark.unit
class TestProductInfoConstants:
    """产品信息常量"""

    def test_capability_ids_non_empty(self):
        assert len(CAPABILITY_IDS) >= 5
        assert "image_analysis" in CAPABILITY_IDS
        assert "product_link_analysis" in CAPABILITY_IDS
        assert "video_script" in CAPABILITY_IDS

    def test_default_prompts_for_each_capability(self):
        for cid in CAPABILITY_IDS:
            assert cid in DEFAULT_PROMPTS
            assert isinstance(DEFAULT_PROMPTS[cid], str)
            assert len(DEFAULT_PROMPTS[cid]) > 0

    def test_capability_order_sort_order_unique(self):
        orders = [o for o, _ in CAPABILITY_ORDER]
        assert len(orders) == len(set(orders))


@pytest.mark.unit
class TestProductInfoUseCase:
    """ProductInfoUseCase 单元测试"""

    async def _create_test_user(self, db_session) -> User:
        user = User(
            email=f"test_{uuid.uuid4()}@example.com",
            hashed_password="hashed",
            name="Test",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_create_job(self, db_session):
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = ProductInfoUseCase(db_session, catalog=get_model_catalog_adapter(db_session))
            job = await use_case.create_job(
                principal_id=str(user.id),
                user_id=user.id,
                title="My Job",
            )
            assert job["id"] is not None
            assert job["title"] == "My Job"
            assert job["status"] == "draft"
            assert job["user_id"] == str(user.id)
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_list_jobs(self, db_session):
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = ProductInfoUseCase(db_session, catalog=get_model_catalog_adapter(db_session))
            await use_case.create_job(
                principal_id=str(user.id),
                user_id=user.id,
                title="J1",
            )
            await use_case.create_job(
                principal_id=str(user.id),
                user_id=user.id,
                title="J2",
            )
            items, total = await use_case.list_jobs(skip=0, limit=10)
            assert total >= 2
            assert len(items) >= 2
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_get_job_not_found_raises(self, db_session):
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = ProductInfoUseCase(db_session, catalog=get_model_catalog_adapter(db_session))
            with pytest.raises(NotFoundError):
                await use_case.get_job(uuid.uuid4())
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_get_job_with_steps(self, db_session):
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = ProductInfoUseCase(db_session, catalog=get_model_catalog_adapter(db_session))
            job = await use_case.create_job(
                principal_id=str(user.id),
                user_id=user.id,
                title="With Steps",
            )
            fetched = await use_case.get_job(uuid.UUID(job["id"]))
            assert fetched["id"] == job["id"]
            assert "steps" in fetched
            assert isinstance(fetched["steps"], list)
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_delete_job(self, db_session):
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = ProductInfoUseCase(db_session, catalog=get_model_catalog_adapter(db_session))
            job = await use_case.create_job(
                principal_id=str(user.id),
                user_id=user.id,
                title="To Delete",
            )
            await use_case.delete_job(uuid.UUID(job["id"]))
            with pytest.raises(NotFoundError):
                await use_case.get_job(uuid.UUID(job["id"]))
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_run_step_unknown_capability_raises(self, db_session):
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = ProductInfoUseCase(db_session, catalog=get_model_catalog_adapter(db_session))
            job = await use_case.create_job(
                principal_id=str(user.id),
                user_id=user.id,
                title="Run Step",
            )
            with pytest.raises(ValidationError):
                await use_case.run_step(
                    job_id=uuid.UUID(job["id"]),
                    capability_id="unknown_capability",
                    user_input={},
                )
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_run_step_product_link_analysis_succeeds(self, db_session):
        from unittest.mock import patch

        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = ProductInfoUseCase(db_session, catalog=get_model_catalog_adapter(db_session))
            job = await use_case.create_job(
                principal_id=str(user.id),
                user_id=user.id,
                title="Run Step Job",
            )
            job_id = uuid.UUID(job["id"])

            async def _mock_runner(_inputs, _prompt, _gateway, model_override=None):
                return {"product_info": {"category": "test", "selling_points": []}}

            with patch.dict(
                "domains.agent.application.product_info_use_case.RUNNERS",
                {"product_link_analysis": _mock_runner},
            ):
                result = await use_case.run_step(
                    job_id=job_id,
                    capability_id="product_link_analysis",
                    user_input={"product_link": "https://example.com/p"},
                )
            assert result["id"] == job["id"]
            steps = result.get("steps") or []
            assert any(
                s["capability_id"] == "product_link_analysis" and s["status"] == "completed"
                for s in steps
            )
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_get_default_prompt(self, db_session):
        use_case = ProductInfoUseCase(db_session, catalog=get_model_catalog_adapter(db_session))
        content = use_case.get_default_prompt("product_link_analysis")
        assert isinstance(content, str)
        assert len(content) > 0
        assert use_case.get_default_prompt("unknown") == ""

    @pytest.mark.asyncio
    async def test_run_step_image_analysis_requires_vision_model_raises(self, db_session):
        """测试: image_analysis 需要视觉模型，传入纯文本模型时抛出 ValidationError"""
        from unittest.mock import AsyncMock, patch

        from bootstrap.config_loader import ModelInfo, ModelsConfig

        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = ProductInfoUseCase(db_session, catalog=get_model_catalog_adapter(db_session))
            job = await use_case.create_job(
                principal_id=str(user.id),
                user_id=user.id,
                title="Vision Test",
            )
            job_id = uuid.UUID(job["id"])

            # 纯文本模型（无 vision）
            text_only_model = ModelInfo(
                id="deepseek-chat",
                name="DeepSeek Chat",
                provider="deepseek",
                supports_vision=False,
                supports_json_mode=True,
            )
            mock_models = ModelsConfig(available=[text_only_model])

            def get_model(mid: str) -> ModelInfo | None:
                if mid == "deepseek-chat" or "deepseek" in (mid or ""):
                    return text_only_model
                return None

            mock_models.get_model = get_model
            mock_config = type("AppConfig", (), {"models": mock_models})()

            with (
                patch.object(
                    use_case._user_model_uc, "resolve_model", new_callable=AsyncMock
                ) as mock_resolve,
                patch(
                    "domains.agent.application.product_info_use_case.get_app_config",
                    return_value=mock_config,
                ),
                patch.dict(
                    "domains.agent.application.product_info_use_case.RUNNERS",
                    {"image_analysis": AsyncMock(return_value={"image_descriptions": []})},
                ),
            ):
                mock_resolve.return_value = type(
                    "ResolvedModel",
                    (),
                    {
                        "model": "deepseek-chat",
                        "api_key": None,
                        "api_base": None,
                    },
                )()

                with pytest.raises(ValidationError) as exc_info:
                    await use_case.run_step(
                        job_id=job_id,
                        capability_id="image_analysis",
                        user_input={
                            "image_urls": ["https://example.com/img.jpg"],
                            "product_name": "Test",
                        },
                        model_id="deepseek-chat",
                    )

                assert "vision" in str(exc_info.value).lower() or "视觉" in str(exc_info.value)
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_run_step_product_link_analysis_accepts_text_model(self, db_session):
        """测试: product_link_analysis 不要求视觉，纯文本模型可执行"""
        from unittest.mock import patch

        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = ProductInfoUseCase(db_session, catalog=get_model_catalog_adapter(db_session))
            job = await use_case.create_job(
                principal_id=str(user.id),
                user_id=user.id,
                title="Text Model Test",
            )
            job_id = uuid.UUID(job["id"])

            async def _mock_runner(_inputs, _prompt, _gateway, model_override=None):
                return {"product_info": {"category": "test", "selling_points": []}}

            with patch.dict(
                "domains.agent.application.product_info_use_case.RUNNERS",
                {"product_link_analysis": _mock_runner},
            ):
                result = await use_case.run_step(
                    job_id=job_id,
                    capability_id="product_link_analysis",
                    user_input={"product_link": "https://example.com/p"},
                    model_id=None,  # 使用默认模型
                )
            assert result["id"] == job["id"]
            steps = result.get("steps") or []
            assert any(
                s["capability_id"] == "product_link_analysis" and s["status"] == "completed"
                for s in steps
            )
        finally:
            clear_permission_context()
