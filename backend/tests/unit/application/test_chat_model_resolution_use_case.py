"""
ChatModelResolutionUseCase 单元测试

覆盖模型类型校验、系统/个人模型解析、可用列表与严格对话路径校验。
"""

from dataclasses import dataclass
from unittest.mock import AsyncMock
import uuid

import pytest

from domains.agent.application.chat_model_resolution_use_case import (
    VALID_MODEL_TYPES,
    ChatModelResolutionUseCase,
)
from domains.gateway.domain.litellm_model_id import build_litellm_model_id
from domains.identity.infrastructure.models.user import User
from libs.exceptions import ValidationError
from libs.iam.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


@pytest.mark.unit
class TestChatModelValidation:
    def test_validate_model_types_passes(self):
        ChatModelResolutionUseCase.validate_model_types(["text", "image"])

    def test_validate_model_types_rejects_invalid(self):
        with pytest.raises(ValidationError, match="无效的模型类型"):
            ChatModelResolutionUseCase.validate_model_types(["text", "audio"])

    def test_valid_model_types_exhaustive(self):
        assert {"text", "image", "image_gen", "video"} == VALID_MODEL_TYPES

    def test_valid_providers_cover_all(self):
        from domains.gateway.domain.types import PERSONAL_MODEL_PROVIDERS

        expected = {
            "openai",
            "deepseek",
            "dashscope",
            "anthropic",
            "zhipuai",
            "volcengine",
            "moonshot",
            "agnes",
            "custom",
        }
        assert expected == PERSONAL_MODEL_PROVIDERS


@pytest.mark.unit
class TestBuildLitellmModel:
    def test_openai_bare_id(self):
        assert build_litellm_model_id("openai", "gpt-4o") == "openai/gpt-4o"

    def test_prefixes_bare_id(self):
        assert build_litellm_model_id("deepseek", "deepseek-chat") == "deepseek/deepseek-chat"


@dataclass(frozen=True)
class _FakeResolution:
    virtual_model_name: str
    litellm_model: str
    api_key: str | None
    api_base: str | None
    provider: str
    model_types: list[str]
    is_active: bool
    last_test_status: str | None
    gateway_model_id: uuid.UUID | None = None


@pytest.mark.unit
class TestResolveTextChatModelLegacyPaths:
    """原 resolve_model 行为由 resolve_text_chat_model + 可见集承接。"""

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
        from tests.helpers.permission_context import permission_context_for_user

        ctx = await permission_context_for_user(db_session, user_id=user.id)
        set_permission_context(ctx)
        self.catalog = AsyncMock()
        self.uc = ChatModelResolutionUseCase(db_session, catalog=self.catalog)
        self.allowed = frozenset(["deepseek/deepseek-chat"])
        yield
        clear_permission_context()

    @pytest.mark.asyncio
    async def test_none_picks_default_from_allowed(self):
        from bootstrap.config import settings

        self.catalog.resolve_chat_default_text_model = AsyncMock(
            side_effect=[settings.default_model, "other/model"]
        )
        allowed = frozenset([settings.default_model, "deepseek/deepseek-chat"])
        resolved = await self.uc.resolve_text_chat_model(
            None,
            allowed_text_system_ids=allowed,
        )
        assert resolved.model == settings.default_model

    @pytest.mark.asyncio
    async def test_system_model_id_in_allowed(self):
        resolved = await self.uc.resolve_text_chat_model(
            "deepseek/deepseek-chat",
            allowed_text_system_ids=self.allowed,
        )
        assert resolved.model == "deepseek/deepseek-chat"

    @pytest.mark.asyncio
    async def test_personal_model_uuid(self):
        model_id = uuid.uuid4()
        self.catalog.resolve_registered_model = AsyncMock(
            return_value=_FakeResolution(
                virtual_model_name="my-personal-model",
                litellm_model="deepseek/deepseek-chat",
                api_key="sk-resolve-me-12345",
                api_base=None,
                provider="deepseek",
                model_types=["text"],
                is_active=True,
                last_test_status=None,
                gateway_model_id=model_id,
            )
        )
        resolved = await self.uc.resolve_text_chat_model(
            str(model_id),
            allowed_text_system_ids=self.allowed,
        )
        assert resolved.model == "my-personal-model"

    @pytest.mark.asyncio
    async def test_unknown_uuid_raises(self):
        self.catalog.resolve_registered_model = AsyncMock(return_value=None)
        with pytest.raises(ValidationError, match="Gateway 个人模型不存在"):
            await self.uc.resolve_text_chat_model(
                str(uuid.uuid4()),
                allowed_text_system_ids=self.allowed,
            )

    @pytest.mark.asyncio
    async def test_system_not_in_allowed_raises(self):
        with pytest.raises(ValidationError, match="模型不在可用列表中"):
            await self.uc.resolve_text_chat_model(
                "not-a-uuid-but-not-system-either",
                allowed_text_system_ids=self.allowed,
            )


@pytest.mark.unit
class TestGetAvailableModels:
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
        from tests.helpers.permission_context import permission_context_for_user

        ctx = await permission_context_for_user(db_session, user_id=user.id)
        set_permission_context(ctx)
        from domains.gateway.application.config_catalog_sync import sync_app_config_gateway_catalog
        from domains.gateway.application.sql_model_catalog import get_model_catalog_adapter

        await sync_app_config_gateway_catalog(db_session)
        await db_session.flush()
        self.uc = ChatModelResolutionUseCase(
            db_session, catalog=get_model_catalog_adapter(db_session)
        )
        yield
        clear_permission_context()

    @pytest.mark.asyncio
    async def test_returns_list(self):
        models = await self.uc.list_available_system_models()
        assert isinstance(models, list)
        for m in models:
            assert m["is_system"] is True
            assert "id" in m
            assert "model_types" in m

    @pytest.mark.asyncio
    async def test_filter_by_type(self):
        all_models = await self.uc.list_available_system_models()
        text_models = await self.uc.list_available_system_models(model_type="text")
        assert len(text_models) <= len(all_models)
        for m in text_models:
            assert "text" in m["model_types"]

    @pytest.mark.asyncio
    async def test_filter_by_provider(self):
        text_models = await self.uc.list_available_system_models(model_type="text")
        deepseek_only = await self.uc.list_available_system_models(
            model_type="text",
            provider="deepseek",
        )
        assert len(deepseek_only) <= len(text_models)
        for m in deepseek_only:
            assert m["provider"] == "deepseek"


@pytest.mark.unit
class TestVisibleTextSystemModelIds:
    @pytest.mark.asyncio
    async def test_uses_permission_team(self, db_session):
        team_id = uuid.uuid4()
        user_id = uuid.uuid4()
        try:
            set_permission_context(
                PermissionContext(
                    user_id=user_id,
                    role="user",
                    team_id=team_id,
                    team_role="owner",
                )
            )
            catalog = AsyncMock()
            catalog.list_requestable_text_model_ids = AsyncMock(
                return_value=frozenset(["team-chat-model"])
            )
            uc = ChatModelResolutionUseCase(db_session, catalog=catalog)
            ids = await uc.visible_text_system_model_ids()
            catalog.list_requestable_text_model_ids.assert_awaited_once_with(
                billing_team_id=team_id,
                user_id=user_id,
            )
            assert ids == frozenset(["team-chat-model"])
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_default_text_resolution_falls_back_to_permission_team(self, db_session):
        """未传 billing_team_id 时默认模型解析应按权限上下文团队作用域。"""
        team_id = uuid.uuid4()
        user_id = uuid.uuid4()
        try:
            set_permission_context(
                PermissionContext(
                    user_id=user_id,
                    role="user",
                    team_id=team_id,
                    team_role="owner",
                )
            )
            catalog = AsyncMock()
            catalog.resolve_chat_default_text_model = AsyncMock(
                return_value="deepseek/deepseek-chat"
            )
            uc = ChatModelResolutionUseCase(db_session, catalog=catalog)
            resolved = await uc.resolve_text_chat_model(None)
            assert resolved.model == "deepseek/deepseek-chat"
            catalog.resolve_chat_default_text_model.assert_awaited_once_with(
                billing_team_id=team_id,
                user_id=user_id,
            )
        finally:
            clear_permission_context()


@pytest.mark.unit
class TestResolveTextChatModel:
    @pytest.mark.asyncio
    async def test_system_not_in_allowed_raises(self, db_session):
        uc = ChatModelResolutionUseCase(db_session, catalog=AsyncMock())
        with pytest.raises(ValidationError, match="模型不在可用列表中"):
            await uc.resolve_text_chat_model(
                "openai/gpt-4o",
                allowed_text_system_ids=frozenset(["deepseek/deepseek-chat"]),
            )

    @pytest.mark.asyncio
    async def test_system_in_allowed(self, db_session):
        uc = ChatModelResolutionUseCase(db_session, catalog=AsyncMock())
        r = await uc.resolve_text_chat_model(
            "deepseek/deepseek-chat",
            allowed_text_system_ids=frozenset(["deepseek/deepseek-chat"]),
        )
        assert r.model == "deepseek/deepseek-chat"

    @pytest.mark.asyncio
    async def test_none_raises_when_no_visible_models(self, db_session):
        catalog = AsyncMock()
        catalog.resolve_chat_default_text_model = AsyncMock(return_value=None)
        catalog.list_requestable_text_model_ids = AsyncMock(return_value=frozenset())
        catalog.count_registered_text_models = AsyncMock(return_value=0)
        uc = ChatModelResolutionUseCase(db_session, catalog=catalog)
        with pytest.raises(ValidationError, match="凭据"):
            await uc.resolve_text_chat_model(None, allowed_text_system_ids=frozenset())

    @pytest.mark.asyncio
    async def test_none_picks_first_visible(self, db_session):
        catalog = AsyncMock()
        catalog.resolve_chat_default_text_model = AsyncMock(return_value="deepseek/deepseek-chat")
        uc = ChatModelResolutionUseCase(db_session, catalog=catalog)
        allowed = frozenset(["deepseek/deepseek-chat"])
        r = await uc.resolve_text_chat_model(None, allowed_text_system_ids=allowed)
        assert r.model == "deepseek/deepseek-chat"

        from bootstrap.config import settings

        catalog.resolve_chat_default_text_model = AsyncMock(return_value=settings.default_model)
        allowed_with_default = frozenset([settings.default_model, "other/model"])
        r2 = await uc.resolve_text_chat_model(None, allowed_text_system_ids=allowed_with_default)
        assert r2.model == settings.default_model

    @pytest.mark.asyncio
    async def test_image_gen_empty_allowed_raises(self, db_session):
        uc = ChatModelResolutionUseCase(db_session, catalog=AsyncMock())
        with pytest.raises(ValidationError, match="无可用图像生成模型"):
            await uc.resolve_image_gen_model_for_chat(
                None,
                allowed_image_gen_system_ids=frozenset(),
            )

    @pytest.mark.asyncio
    async def test_unknown_uuid_raises(self, db_session):
        catalog = AsyncMock()
        catalog.resolve_registered_model = AsyncMock(return_value=None)
        uc = ChatModelResolutionUseCase(db_session, catalog=catalog)
        with pytest.raises(ValidationError, match="Gateway 个人模型不存在"):
            await uc.resolve_text_chat_model(
                str(uuid.uuid4()),
                allowed_text_system_ids=frozenset(),
            )
