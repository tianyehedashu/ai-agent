"""
UserModelUseCase 单元测试

覆盖：
- create 验证、加密
- list_models / get_model
- update（含 api_key 重加密）
- delete（含 not found）
- resolve_model（系统模型 / 用户模型 UUID / 回退）
- get_available_models
- _validate_model_types
- _build_litellm_model

注意：不在模块顶层导入 UserModelUseCase，避免触发
domains.agent.application.__init__ -> ChatUseCase -> MCP 依赖链。
"""

import uuid

import pytest

from domains.identity.infrastructure.models.user import User
from exceptions import NotFoundError, ValidationError
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


def _uc_module():
    """延迟导入 user_model_use_case 模块，绕过 __init__.py 链式导入 MCP"""
    import importlib

    return importlib.import_module("domains.agent.application.user_model_use_case")


@pytest.mark.unit
class TestUserModelValidation:
    """验证逻辑"""

    def test_validate_model_types_passes(self):
        _uc_module().UserModelUseCase._validate_model_types(["text", "image"])

    def test_validate_model_types_rejects_invalid(self):
        with pytest.raises(ValidationError, match="无效的模型类型"):
            _uc_module().UserModelUseCase._validate_model_types(["text", "audio"])

    def test_valid_model_types_exhaustive(self):
        assert {"text", "image", "video"} == _uc_module().VALID_MODEL_TYPES

    def test_valid_providers_cover_all(self):
        expected = {
            "openai",
            "deepseek",
            "dashscope",
            "anthropic",
            "zhipuai",
            "volcengine",
            "custom",
        }
        assert expected == _uc_module().VALID_PROVIDERS


@pytest.mark.unit
class TestBuildLitellmModel:
    """_build_litellm_model 静态方法"""

    @property
    def _cls(self):
        return _uc_module().UserModelUseCase

    def test_already_has_slash(self):
        assert self._cls._build_litellm_model("openai", "openai/gpt-4o") == "openai/gpt-4o"

    def test_deepseek(self):
        assert (
            self._cls._build_litellm_model("deepseek", "deepseek-chat") == "deepseek/deepseek-chat"
        )

    def test_dashscope(self):
        assert self._cls._build_litellm_model("dashscope", "qwen-max") == "dashscope/qwen-max"

    def test_volcengine(self):
        assert self._cls._build_litellm_model("volcengine", "ep-xxx") == "volcengine/ep-xxx"

    def test_zhipuai(self):
        assert self._cls._build_litellm_model("zhipuai", "glm-4") == "zai/glm-4"

    def test_openai_bare(self):
        assert self._cls._build_litellm_model("openai", "gpt-4o") == "gpt-4o"


@pytest.mark.unit
class TestIsSystemModel:
    """_is_system_model 静态方法"""

    @property
    def _cls(self):
        return _uc_module().UserModelUseCase

    def test_slash_model_is_system(self):
        assert self._cls._is_system_model("deepseek/deepseek-chat") is True

    def test_gpt_prefix_is_system(self):
        assert self._cls._is_system_model("gpt-4o") is True

    def test_claude_prefix_is_system(self):
        assert self._cls._is_system_model("claude-3.5-sonnet") is True

    def test_uuid_is_not_system(self):
        assert self._cls._is_system_model(str(uuid.uuid4())) is False


@pytest.mark.unit
class TestUserModelUseCaseCRUD:
    """CRUD 操作（需要 DB）"""

    @pytest.fixture(autouse=True)
    async def _setup(self, db_session):
        user = User(
            email=f"model_test_{uuid.uuid4().hex[:8]}@test.com",
            hashed_password="hashed",
            name="Model Tester",
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        self.user = user
        self.ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(self.ctx)
        self.uc = _uc_module().UserModelUseCase(db_session)
        yield
        clear_permission_context()

    @pytest.mark.asyncio
    async def test_create_and_get(self, db_session):
        """创建模型并获取详情"""
        result = await self.uc.create(
            user_id=self.user.id,
            display_name="Test DeepSeek",
            provider="deepseek",
            model_id="deepseek-chat",
            api_key="sk-test123456789",
            model_types=["text"],
        )
        assert result["display_name"] == "Test DeepSeek"
        assert result["provider"] == "deepseek"
        assert result["has_api_key"] is True
        assert result["api_key_masked"].startswith("sk-")
        assert "****" in result["api_key_masked"]
        assert result["is_system"] is False

        detail = await self.uc.get_model(uuid.UUID(result["id"]))
        assert detail["id"] == result["id"]

    @pytest.mark.asyncio
    async def test_create_invalid_provider_raises(self, db_session):
        """不支持的提供商抛 ValidationError"""
        with pytest.raises(ValidationError, match="不支持的提供商"):
            await self.uc.create(
                user_id=self.user.id,
                display_name="Bad",
                provider="unsupported",
                model_id="foo",
            )

    @pytest.mark.asyncio
    async def test_create_invalid_type_raises(self, db_session):
        """无效的模型类型抛 ValidationError"""
        with pytest.raises(ValidationError, match="无效的模型类型"):
            await self.uc.create(
                user_id=self.user.id,
                display_name="Bad",
                provider="openai",
                model_id="gpt-4o",
                model_types=["audio"],
            )

    @pytest.mark.asyncio
    async def test_list_models(self, db_session):
        """列出当前用户模型"""
        await self.uc.create(
            user_id=self.user.id,
            display_name="M1",
            provider="openai",
            model_id="gpt-4o",
        )
        await self.uc.create(
            user_id=self.user.id,
            display_name="M2",
            provider="deepseek",
            model_id="deepseek-chat",
        )
        items, total = await self.uc.list_models()
        assert total >= 2
        names = {m["display_name"] for m in items}
        assert "M1" in names
        assert "M2" in names

    @pytest.mark.asyncio
    async def test_list_models_filter_by_type(self, db_session):
        """按类型过滤"""
        await self.uc.create(
            user_id=self.user.id,
            display_name="TextOnly",
            provider="openai",
            model_id="gpt-4o",
            model_types=["text"],
        )
        await self.uc.create(
            user_id=self.user.id,
            display_name="ImageModel",
            provider="dashscope",
            model_id="qwen-vl",
            model_types=["image"],
        )
        text_items, _ = await self.uc.list_models(model_type="text")
        image_items, _ = await self.uc.list_models(model_type="image")
        assert all("text" in m["model_types"] for m in text_items)
        assert all("image" in m["model_types"] for m in image_items)

    @pytest.mark.asyncio
    async def test_update_display_name(self, db_session):
        """更新显示名称"""
        created = await self.uc.create(
            user_id=self.user.id,
            display_name="Old",
            provider="openai",
            model_id="gpt-4o",
        )
        updated = await self.uc.update(
            uuid.UUID(created["id"]),
            display_name="New Name",
        )
        assert updated["display_name"] == "New Name"

    @pytest.mark.asyncio
    async def test_update_api_key_re_encrypts(self, db_session):
        """更新 api_key 会重新加密"""
        created = await self.uc.create(
            user_id=self.user.id,
            display_name="ReKey",
            provider="openai",
            model_id="gpt-4o",
            api_key="sk-old-key-1234567",
        )
        updated = await self.uc.update(
            uuid.UUID(created["id"]),
            api_key="sk-new-key-9876543",
        )
        assert updated["has_api_key"] is True
        assert "new" not in updated.get("api_key_masked", "")

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self, db_session):
        """更新不存在的模型抛 NotFoundError"""
        with pytest.raises(NotFoundError):
            await self.uc.update(uuid.uuid4(), display_name="Nope")

    @pytest.mark.asyncio
    async def test_delete(self, db_session):
        """删除模型"""
        created = await self.uc.create(
            user_id=self.user.id,
            display_name="ToDelete",
            provider="openai",
            model_id="gpt-4o",
        )
        await self.uc.delete(uuid.UUID(created["id"]))
        with pytest.raises(NotFoundError):
            await self.uc.get_model(uuid.UUID(created["id"]))

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, db_session):
        """删除不存在的模型抛 NotFoundError"""
        with pytest.raises(NotFoundError):
            await self.uc.delete(uuid.uuid4())


@pytest.mark.unit
class TestResolveModel:
    """resolve_model 模型解析"""

    @pytest.fixture(autouse=True)
    async def _setup(self, db_session):
        user = User(
            email=f"resolve_{uuid.uuid4().hex[:8]}@test.com",
            hashed_password="hashed",
            name="Resolver",
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        self.user = user
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        self.uc = _uc_module().UserModelUseCase(db_session)
        yield
        clear_permission_context()

    @pytest.mark.asyncio
    async def test_none_returns_default(self, db_session):
        """None → 系统默认模型"""
        resolved = await self.uc.resolve_model(None)
        assert resolved.is_system is True
        assert resolved.api_key is None

    @pytest.mark.asyncio
    async def test_system_model_id(self, db_session):
        """系统模型 ID（含 / 分隔符）直接返回"""
        resolved = await self.uc.resolve_model("deepseek/deepseek-chat")
        assert resolved.model == "deepseek/deepseek-chat"
        assert resolved.is_system is True

    @pytest.mark.asyncio
    async def test_user_model_uuid(self, db_session):
        """用户模型 UUID → 解密 API Key 返回"""
        created = await self.uc.create(
            user_id=self.user.id,
            display_name="Resolvable",
            provider="deepseek",
            model_id="deepseek-chat",
            api_key="sk-resolve-me-12345",
        )
        resolved = await self.uc.resolve_model(created["id"])
        assert resolved.is_system is False
        assert resolved.model == "deepseek/deepseek-chat"
        assert resolved.api_key == "sk-resolve-me-12345"

    @pytest.mark.asyncio
    async def test_unknown_uuid_falls_back(self, db_session):
        """不存在的 UUID → 回退到默认模型"""
        resolved = await self.uc.resolve_model(str(uuid.uuid4()))
        assert resolved.is_system is True

    @pytest.mark.asyncio
    async def test_non_uuid_string_treated_as_system(self, db_session):
        """非 UUID、非系统 ID → 当做系统模型"""
        resolved = await self.uc.resolve_model("not-a-uuid-but-not-system-either")
        assert resolved.is_system is True


@pytest.mark.unit
class TestGetAvailableModels:
    """get_available_models 系统模型列表"""

    @pytest.fixture(autouse=True)
    async def _setup(self, db_session):
        user = User(
            email=f"avail_{uuid.uuid4().hex[:8]}@test.com",
            hashed_password="hashed",
            name="Avail",
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        self.uc = _uc_module().UserModelUseCase(db_session)
        yield
        clear_permission_context()

    def test_returns_list(self):
        """返回系统模型列表"""
        models = self.uc.get_available_models()
        assert isinstance(models, list)
        for m in models:
            assert m["is_system"] is True
            assert "id" in m
            assert "model_types" in m

    def test_filter_by_type(self):
        """按类型过滤系统模型"""
        all_models = self.uc.get_available_models()
        text_models = self.uc.get_available_models(model_type="text")
        assert len(text_models) <= len(all_models)
        for m in text_models:
            assert "text" in m["model_types"]
