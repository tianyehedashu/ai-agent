"""
Product Info Prompt Service 单元测试
"""

import uuid

import pytest

from domains.agent.application.product_info_prompt_service import (
    ProductInfoPromptTemplateUseCase,
    get_default_image_gen_prompts,
    get_default_prompt,
    list_capabilities,
)
from domains.identity.infrastructure.models.user import User
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)
from libs.exceptions import NotFoundError


@pytest.mark.unit
class TestProductInfoPromptServiceFunctions:
    """纯函数：list_capabilities, get_default_prompt"""

    def test_list_capabilities_returns_all(self):
        caps = list_capabilities()
        assert len(caps) >= 5
        for c in caps:
            assert "id" in c and "name" in c

    def test_list_capabilities_returns_full_metadata(self):
        """测试: list_capabilities 返回完整元数据（model_type, output_key, dependencies 等）"""
        caps = list_capabilities()
        assert len(caps) >= 5
        for c in caps:
            assert "id" in c and "name" in c
            assert "sort_order" in c
            assert "model_type" in c
            assert c["model_type"] in ("text", "image")
            assert "output_key" in c
            assert "dependencies" in c
            assert isinstance(c["dependencies"], list)
            assert "input_fields" in c
            assert isinstance(c["input_fields"], list)
            assert "meta_prompt_params" in c
            assert isinstance(c["meta_prompt_params"], list)
            assert "required_features" in c
            assert isinstance(c["required_features"], list)

    def test_list_capabilities_image_analysis_has_vision(self):
        """测试: image_analysis 的 model_type 为 image，required_features 含 vision"""
        caps = list_capabilities()
        image_analysis = next((c for c in caps if c["id"] == "image_analysis"), None)
        assert image_analysis is not None
        assert image_analysis["model_type"] == "image"
        assert "vision" in image_analysis["required_features"]

    def test_list_capabilities_sorted_by_sort_order(self):
        """测试: 能力列表按 sort_order 排序"""
        caps = list_capabilities()
        orders = [c["sort_order"] for c in caps]
        assert orders == sorted(orders)

    def test_get_default_prompt_returns_string(self):
        assert isinstance(get_default_prompt("product_link_analysis"), str)
        assert get_default_prompt("unknown") == ""

    def test_get_default_image_gen_prompts_returns_8(self):
        prompts = get_default_image_gen_prompts()
        assert len(prompts) == 8
        assert all(isinstance(p, str) for p in prompts)


@pytest.mark.unit
class TestProductInfoPromptTemplateUseCase:
    """ProductInfoPromptTemplateUseCase 单元测试"""

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
    async def test_create_and_list_templates(self, db_session):
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = ProductInfoPromptTemplateUseCase(db_session)
            await use_case.create_template(
                capability_id="product_link_analysis",
                name="T1",
                content="Analyze...",
                user_id=user.id,
            )
            items, total = await use_case.list_templates(
                capability_id="product_link_analysis",
                limit=10,
            )
            assert total >= 1
            assert any(t["name"] == "T1" for t in items)
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_get_template_not_found_raises(self, db_session):
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = ProductInfoPromptTemplateUseCase(db_session)
            with pytest.raises(NotFoundError):
                await use_case.get_template(uuid.uuid4())
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_update_and_delete_template(self, db_session):
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = ProductInfoPromptTemplateUseCase(db_session)
            t = await use_case.create_template(
                capability_id="video_script",
                name="Original",
                content="Script...",
                user_id=user.id,
            )
            updated = await use_case.update_template(
                uuid.UUID(t["id"]),
                name="Updated",
            )
            assert updated["name"] == "Updated"

            await use_case.delete_template(uuid.UUID(t["id"]))
            with pytest.raises(NotFoundError):
                await use_case.get_template(uuid.UUID(t["id"]))
        finally:
            clear_permission_context()
