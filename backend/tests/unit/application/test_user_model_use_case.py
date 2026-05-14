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
- build_litellm_model_id（共享小工具）
- test_connection 持久化 last_test_status / last_tested_at
- list_models_for_model_selector（排除连通性 failed）
- resolve_text_chat_model 拒绝 last_test_failed

注意：不在模块顶层导入 UserModelUseCase，避免触发
domains.agent.application.__init__ -> ChatUseCase -> MCP 依赖链。
"""

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from domains.agent.infrastructure.llm.litellm_model_id import build_litellm_model_id
from domains.identity.infrastructure.models.user import User
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)
from libs.exceptions import NotFoundError, ValidationError


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
        assert {"text", "image", "image_gen", "video"} == _uc_module().VALID_MODEL_TYPES

    def test_valid_providers_cover_all(self):
        from domains.agent.domain.user_model_constants import USER_MODEL_VALID_PROVIDERS

        expected = {
            "openai",
            "deepseek",
            "dashscope",
            "anthropic",
            "zhipuai",
            "volcengine",
            "custom",
        }
        assert expected == USER_MODEL_VALID_PROVIDERS


@pytest.mark.unit
class TestBuildLitellmModel:
    """build_litellm_model_id 共享小工具

    UserModelUseCase 与 GatewayManagementWriteService 都依赖同一份 provider/
    model_id 拼装逻辑，集中在 ``domains.agent.infrastructure.llm.litellm_model_id``。
    """

    def test_already_has_slash(self):
        assert build_litellm_model_id("openai", "openai/gpt-4o") == "openai/gpt-4o"

    def test_deepseek(self):
        assert build_litellm_model_id("deepseek", "deepseek-chat") == "deepseek/deepseek-chat"

    def test_dashscope(self):
        assert build_litellm_model_id("dashscope", "qwen-max") == "dashscope/qwen-max"

    def test_volcengine(self):
        assert build_litellm_model_id("volcengine", "ep-xxx") == "volcengine/ep-xxx"

    def test_zhipuai(self):
        assert build_litellm_model_id("zhipuai", "glm-4") == "zai/glm-4"

    def test_openai_bare(self):
        assert build_litellm_model_id("openai", "gpt-4o") == "gpt-4o"

    def test_empty_model_id_passthrough(self):
        assert build_litellm_model_id("openai", "") == ""


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
        from domains.gateway.application.config_catalog_sync import sync_app_config_gateway_catalog
        from domains.gateway.application.sql_model_catalog import get_model_catalog_adapter

        await sync_app_config_gateway_catalog(db_session)
        await db_session.flush()
        self.uc = _uc_module().UserModelUseCase(
            db_session, catalog=get_model_catalog_adapter(db_session)
        )
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
    async def test_list_models_filter_by_provider(self, db_session):
        """按接入通道（provider）过滤，total 与 items 一致"""
        await self.uc.create(
            user_id=self.user.id,
            display_name="O1",
            provider="openai",
            model_id="gpt-4o",
        )
        await self.uc.create(
            user_id=self.user.id,
            display_name="D1",
            provider="deepseek",
            model_id="deepseek-chat",
        )
        ds_items, ds_total = await self.uc.list_models(provider="deepseek")
        assert ds_total == len(ds_items)
        assert {m["display_name"] for m in ds_items} == {"D1"}
        assert all(m["provider"] == "deepseek" for m in ds_items)

        text_ds, text_ds_total = await self.uc.list_models(
            model_type="text",
            provider="deepseek",
        )
        assert text_ds_total == len(text_ds)
        assert {m["display_name"] for m in text_ds} == {"D1"}

    @pytest.mark.asyncio
    async def test_list_models_for_selector_excludes_connectivity_failed(self, db_session):
        """选择器列表不含 last_test_status=failed（设置页完整列表仍可见）"""
        ok = await self.uc.create(
            user_id=self.user.id,
            display_name="OkModel",
            provider="openai",
            model_id="gpt-4o",
            model_types=["text"],
        )
        bad = await self.uc.create(
            user_id=self.user.id,
            display_name="BadConn",
            provider="openai",
            model_id="gpt-4o-mini",
            model_types=["text"],
        )
        await self.uc.repo.update(
            uuid.UUID(bad["id"]),
            last_test_status="failed",
            last_test_reason="连接失败: quota",
        )
        picked = await self.uc.list_models_for_model_selector(model_type="text")
        ids = {m["id"] for m in picked}
        assert ok["id"] in ids
        assert bad["id"] not in ids
        picked_openai = await self.uc.list_models_for_model_selector(
            model_type="text",
            provider="openai",
        )
        assert {m["id"] for m in picked_openai} == {ok["id"]}
        full, _ = await self.uc.list_models(model_type="text")
        assert bad["id"] in {m["id"] for m in full}

    @pytest.mark.asyncio
    async def test_resolve_text_chat_model_rejects_last_test_failed(self, db_session):
        """对话解析拒绝最近一次连通性测试失败的用户模型"""
        created = await self.uc.create(
            user_id=self.user.id,
            display_name="ConnFail",
            provider="openai",
            model_id="gpt-4o",
            api_key="sk-test-key-123456789",
            model_types=["text"],
        )
        mid = uuid.UUID(created["id"])
        await self.uc.repo.update(mid, last_test_status="failed", last_test_reason="boom")
        with pytest.raises(ValidationError, match="连通性测试失败"):
            await self.uc.resolve_text_chat_model(
                str(mid),
                allowed_text_system_ids=frozenset(),
            )

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

    @pytest.mark.asyncio
    async def test_test_connection_success_persists(self, db_session):
        """test_connection 成功 → last_test_status='success' 写回库"""
        created = await self.uc.create(
            user_id=self.user.id,
            display_name="ProbeOk",
            provider="deepseek",
            model_id="deepseek-chat",
            api_key="sk-probe-1234567",
        )
        model_id = uuid.UUID(created["id"])

        fake_resp = type("R", (), {"content": "Hello!"})()
        with patch.object(
            _uc_module().LLMGateway,
            "chat",
            new=AsyncMock(return_value=fake_resp),
        ):
            result = await self.uc.test_connection(model_id)

        assert result["success"] is True
        assert result["status"] == "success"
        assert result.get("reason") is None
        assert "tested_at" in result
        detail = await self.uc.get_model(model_id)
        assert detail["last_test_status"] == "success"
        assert detail["last_tested_at"] is not None
        assert detail.get("last_test_reason") is None

    @pytest.mark.asyncio
    async def test_test_connection_failure_persists(self, db_session):
        """test_connection 失败 → last_test_status='failed' 写回库，HTTP 仍 200"""
        created = await self.uc.create(
            user_id=self.user.id,
            display_name="ProbeFail",
            provider="openai",
            model_id="gpt-4o",
            api_key="sk-bad-key",
        )
        model_id = uuid.UUID(created["id"])

        with patch.object(
            _uc_module().LLMGateway,
            "chat",
            new=AsyncMock(side_effect=RuntimeError("401 Unauthorized")),
        ):
            result = await self.uc.test_connection(model_id)

        assert result["success"] is False
        assert result["status"] == "failed"
        assert "401" in result["message"]
        assert result.get("reason") and "401" in result["reason"]
        detail = await self.uc.get_model(model_id)
        assert detail["last_test_status"] == "failed"
        assert detail["last_tested_at"] is not None
        assert detail.get("last_test_reason")
        assert "401" in detail["last_test_reason"]

    @pytest.mark.asyncio
    async def test_test_connection_unknown_model_raises(self, db_session):
        """test_connection 不存在的模型抛 NotFoundError，不污染任何行"""
        with pytest.raises(NotFoundError):
            await self.uc.test_connection(uuid.uuid4())


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
        from domains.gateway.application.config_catalog_sync import sync_app_config_gateway_catalog
        from domains.gateway.application.sql_model_catalog import get_model_catalog_adapter

        await sync_app_config_gateway_catalog(db_session)
        await db_session.flush()
        self.uc = _uc_module().UserModelUseCase(
            db_session, catalog=get_model_catalog_adapter(db_session)
        )
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
    """list_available_system_models 系统模型列表"""

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
        from domains.gateway.application.config_catalog_sync import sync_app_config_gateway_catalog
        from domains.gateway.application.sql_model_catalog import get_model_catalog_adapter

        await sync_app_config_gateway_catalog(db_session)
        await db_session.flush()
        self.uc = _uc_module().UserModelUseCase(
            db_session, catalog=get_model_catalog_adapter(db_session)
        )
        yield
        clear_permission_context()

    @pytest.mark.asyncio
    async def test_returns_list(self):
        """返回系统模型列表"""
        models = await self.uc.list_available_system_models()
        assert isinstance(models, list)
        for m in models:
            assert m["is_system"] is True
            assert "id" in m
            assert "model_types" in m

    @pytest.mark.asyncio
    async def test_filter_by_type(self):
        """按类型过滤系统模型"""
        all_models = await self.uc.list_available_system_models()
        text_models = await self.uc.list_available_system_models(model_type="text")
        assert len(text_models) <= len(all_models)
        for m in text_models:
            assert "text" in m["model_types"]

    @pytest.mark.asyncio
    async def test_filter_by_provider(self):
        """按接入通道过滤系统模型"""
        text_models = await self.uc.list_available_system_models(model_type="text")
        deepseek_only = await self.uc.list_available_system_models(
            model_type="text",
            provider="deepseek",
        )
        assert len(deepseek_only) <= len(text_models)
        for m in deepseek_only:
            assert m["provider"] == "deepseek"


@pytest.mark.unit
class TestResolveTextChatModel:
    """resolve_text_chat_model 严格校验（对话路径）"""

    @pytest.mark.asyncio
    async def test_system_not_in_allowed_raises(self, db_session):
        from unittest.mock import AsyncMock

        uc = _uc_module().UserModelUseCase(db_session, catalog=AsyncMock())
        with pytest.raises(ValidationError, match="模型不在可用列表中"):
            await uc.resolve_text_chat_model(
                "openai/gpt-4o",
                allowed_text_system_ids=frozenset(["deepseek/deepseek-chat"]),
            )

    @pytest.mark.asyncio
    async def test_system_in_allowed(self, db_session):
        from unittest.mock import AsyncMock

        uc = _uc_module().UserModelUseCase(db_session, catalog=AsyncMock())
        r = await uc.resolve_text_chat_model(
            "deepseek/deepseek-chat",
            allowed_text_system_ids=frozenset(["deepseek/deepseek-chat"]),
        )
        assert r.model == "deepseek/deepseek-chat"
        assert r.is_system is True
        assert r.api_key is None

    @pytest.mark.asyncio
    async def test_none_uses_app_default(self, db_session):
        from unittest.mock import AsyncMock

        from bootstrap.config import settings

        uc = _uc_module().UserModelUseCase(db_session, catalog=AsyncMock())
        r = await uc.resolve_text_chat_model(None, allowed_text_system_ids=frozenset())
        assert r.model == settings.default_model
        assert r.is_system is True

    @pytest.mark.asyncio
    async def test_unknown_uuid_raises(self, db_session):
        from unittest.mock import AsyncMock

        uc = _uc_module().UserModelUseCase(db_session, catalog=AsyncMock())
        with pytest.raises(ValidationError, match="用户模型不存在"):
            await uc.resolve_text_chat_model(
                str(uuid.uuid4()),
                allowed_text_system_ids=frozenset(),
            )
