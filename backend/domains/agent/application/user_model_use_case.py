"""
User Model Use Case - 用户模型管理用例

CRUD、连接测试、模型解析（系统模型 + 用户模型统一查询）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
import uuid

from bootstrap.config import settings
from bootstrap.config_loader import app_config
from domains.agent.domain.user_model_constants import USER_MODEL_VALID_PROVIDERS
from domains.agent.infrastructure.llm.gateway import LLMGateway
from domains.agent.infrastructure.llm.litellm_model_id import build_litellm_model_id
from domains.agent.infrastructure.repositories.user_model_repository import (
    UserModelRepository,
)
from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_team_id
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from libs.crypto import decrypt_value, derive_encryption_key, encrypt_value, mask_api_key
from libs.exceptions import NotFoundError, ValidationError
from libs.model_connectivity import truncate_last_test_reason
from utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.agent.application.ports.model_catalog_port import ModelCatalogPort
    from domains.agent.infrastructure.models.user_model import UserModel

logger = get_logger(__name__)

VALID_MODEL_TYPES = {"text", "image", "image_gen", "video"}


@dataclass(frozen=True)
class ResolvedModel:
    """解析后的模型信息，供 LLMGateway 使用"""

    model: str
    api_key: str | None = None
    api_base: str | None = None
    is_system: bool = True


@dataclass(frozen=True)
class ResolvedImageGenModel:
    """解析后的图像生成模型信息"""

    provider: str = "volcengine"
    model: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    is_system: bool = True


class UserModelUseCase:
    """用户模型管理"""

    def __init__(self, db: AsyncSession, catalog: ModelCatalogPort) -> None:
        self.db = db
        self.repo = UserModelRepository(db)
        self._catalog = catalog
        self._encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())

    async def create(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        display_name: str = "",
        provider: str = "",
        model_id: str = "",
        api_key: str | None = None,
        api_base: str | None = None,
        model_types: list[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """创建用户模型"""
        self._validate_model_types(model_types or ["text"])
        if provider not in USER_MODEL_VALID_PROVIDERS:
            raise ValidationError(f"不支持的提供商: {provider}")

        encrypted_key = None
        if api_key:
            encrypted_key = encrypt_value(api_key, self._encryption_key)

        model = await self.repo.create(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            display_name=display_name,
            provider=provider,
            model_id=model_id,
            api_key_encrypted=encrypted_key,
            api_base=api_base,
            model_types=model_types or ["text"],
            config=config,
            is_active=True,
        )
        return self._to_dict(model)

    async def list_models(
        self,
        model_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
        *,
        provider: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """列出当前用户的模型"""
        if model_type:
            items = await self.repo.find_by_type(
                model_type, skip=skip, limit=limit, provider=provider
            )
            total = await self.repo.count_by_type(model_type, provider=provider)
        else:
            items = await self.repo.find_active(skip=skip, limit=limit, provider=provider)
            total = await self.repo.count_owned(is_active=True, provider=provider)
        return [self._to_dict(m) for m in items], total

    async def list_models_for_model_selector(
        self,
        model_type: str | None = None,
        *,
        limit: int = 100,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        """供聊天等模型选择器（``GET /user-models/available``）：排除连通性已知失败的条目。

        ``last_test_status is None``（未测）仍可选，避免新建模型必须先测才能用。
        """
        items, _ = await self.list_models(
            model_type=model_type, skip=0, limit=limit, provider=provider
        )
        return [m for m in items if m.get("last_test_status") != "failed"]

    async def get_model(self, model_id: uuid.UUID) -> dict[str, Any]:
        """获取模型详情"""
        model = await self.repo.get_owned(model_id)
        if not model:
            raise NotFoundError("UserModel", str(model_id))
        return self._to_dict(model)

    async def update(self, model_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        """更新模型"""
        if kwargs.get("model_types"):
            self._validate_model_types(kwargs["model_types"])
        if (
            "provider" in kwargs
            and kwargs["provider"]
            and kwargs["provider"] not in USER_MODEL_VALID_PROVIDERS
        ):
            raise ValidationError(f"不支持的提供商: {kwargs['provider']}")

        if "api_key" in kwargs:
            raw_key = kwargs.pop("api_key")
            if raw_key:
                kwargs["api_key_encrypted"] = encrypt_value(raw_key, self._encryption_key)

        model = await self.repo.update(model_id, **kwargs)
        if not model:
            raise NotFoundError("UserModel", str(model_id))
        return self._to_dict(model)

    async def delete(self, model_id: uuid.UUID) -> None:
        """删除模型"""
        model = await self.repo.get_owned(model_id)
        if not model:
            raise NotFoundError("UserModel", str(model_id))
        await self.db.delete(model)
        await self.db.flush()

    async def test_connection(self, model_id: uuid.UUID) -> dict[str, Any]:
        """测试模型连接（发送简单请求验证 API Key 有效性）。

        无论成功/失败，都会把 ``last_test_status`` + ``last_tested_at`` +
        ``last_test_reason``（失败时截断说明；成功时清空）写回 ``user_models``，
        让列表页直接展示连通状态而不是测一次就丢。
        """
        model = await self.repo.get_owned(model_id)
        if not model:
            raise NotFoundError("UserModel", str(model_id))

        api_key = None
        if model.api_key_encrypted:
            api_key = decrypt_value(model.api_key_encrypted, self._encryption_key)

        litellm_model = build_litellm_model_id(model.provider, model.model_id)

        gateway = LLMGateway(config=settings, model_catalog=self._catalog)

        tested_at = datetime.now(UTC)
        try:
            response = await gateway.chat(
                messages=[{"role": "user", "content": "Hi"}],
                model=litellm_model,
                api_key=api_key,
                api_base=model.api_base,
                max_tokens=10,
                temperature=0,
            )
            await self.repo.update(
                model_id,
                last_test_status="success",
                last_tested_at=tested_at,
                last_test_reason=None,
            )
            return {
                "success": True,
                "message": "连接成功",
                "model": litellm_model,
                "status": "success",
                "tested_at": tested_at.isoformat(),
                "reason": None,
                "response_preview": (response.content or "")[:100],
            }
        except Exception as e:
            logger.warning("Model connection test failed for %s: %s", model_id, e)
            fail_reason = truncate_last_test_reason(f"连接失败: {e}")
            await self.repo.update(
                model_id,
                last_test_status="failed",
                last_tested_at=tested_at,
                last_test_reason=fail_reason,
            )
            return {
                "success": False,
                "message": f"连接失败: {e}",
                "model": litellm_model,
                "status": "failed",
                "tested_at": tested_at.isoformat(),
                "reason": fail_reason,
            }

    async def resolve_model(self, model_ref: str | None) -> ResolvedModel:
        """解析模型引用，返回可供 LLMGateway 使用的模型信息。

        model_ref 可以是:
        - None: 使用系统默认模型
        - 系统模型 ID (如 "deepseek/deepseek-chat"): 使用系统配置
        - 用户模型 UUID: 解密 API Key 并返回
        """
        if not model_ref:
            return ResolvedModel(model=settings.default_model, is_system=True)

        if self._is_system_model(model_ref):
            return ResolvedModel(model=model_ref, is_system=True)

        try:
            user_model_id = uuid.UUID(model_ref)
        except ValueError:
            return ResolvedModel(model=model_ref, is_system=True)

        model = await self.repo.get_owned(user_model_id)
        if not model:
            logger.warning("User model %s not found, falling back to default", model_ref)
            return ResolvedModel(model=settings.default_model, is_system=True)

        api_key = None
        if model.api_key_encrypted:
            try:
                api_key = decrypt_value(model.api_key_encrypted, self._encryption_key)
            except Exception:
                logger.exception("Failed to decrypt API key for model %s", model_ref)
                return ResolvedModel(model=settings.default_model, is_system=True)

        litellm_model = build_litellm_model_id(model.provider, model.model_id)
        return ResolvedModel(
            model=litellm_model,
            api_key=api_key,
            api_base=model.api_base,
            is_system=False,
        )

    async def resolve_text_chat_model(
        self,
        model_ref: str | None,
        *,
        allowed_text_system_ids: frozenset[str],
    ) -> ResolvedModel:
        """解析对话用文本模型：系统 id 须在目录白名单内；UUID 须为当前用户自有且含 text 类型。

        非法输入抛出 ValidationError（不做静默回退默认模型）。
        """
        if not model_ref or not str(model_ref).strip():
            return ResolvedModel(model=settings.default_model, is_system=True)

        ref = str(model_ref).strip()
        try:
            user_model_id = uuid.UUID(ref)
        except ValueError:
            if ref not in allowed_text_system_ids:
                raise ValidationError(f"模型不在可用列表中: {ref}") from None
            return ResolvedModel(model=ref, is_system=True)

        model = await self.repo.get_owned(user_model_id)
        if not model:
            raise ValidationError("用户模型不存在或无权使用")
        if not model.is_active:
            raise ValidationError("该用户模型已停用")
        if model.last_test_status == "failed":
            raise ValidationError(
                "该模型最近一次连通性测试失败，请先在设置中修复并测试通过，或选择其他模型。"
            )
        types = list(model.model_types or [])
        if "text" not in types:
            raise ValidationError("该模型不支持对话（text）")

        api_key: str | None = None
        if model.api_key_encrypted:
            try:
                api_key = decrypt_value(model.api_key_encrypted, self._encryption_key)
            except Exception as e:
                logger.exception("Failed to decrypt API key for chat model %s", ref)
                raise ValidationError("无法解密该模型的 API Key") from e

        litellm_model = build_litellm_model_id(model.provider, model.model_id)
        return ResolvedModel(
            model=litellm_model,
            api_key=api_key,
            api_base=model.api_base,
            is_system=False,
        )

    async def list_available_system_models(
        self,
        model_type: str | None = None,
        *,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        """系统预置模型列表（以 Gateway 目录为准；匿名仅全局）。"""
        team_id = resolve_internal_gateway_team_id()
        items = await self._catalog.list_visible_models(
            billing_team_id=team_id,
            model_type=model_type,
        )
        if provider is None:
            return items
        return [m for m in items if str(m.get("provider") or "") == provider]

    async def get_default_for_type_async(self, model_type: str) -> dict[str, str] | None:
        """获取指定类型的默认模型信息（用于前端展示「默认（模型名）」）。"""
        team_id = resolve_internal_gateway_team_id()
        if model_type == "image":
            model_id = settings.vision_model
            items = await self._catalog.list_visible_models(
                billing_team_id=team_id,
                model_type="image",
            )
            for m in items:
                if m["id"] == model_id:
                    return {"id": model_id, "display_name": str(m["display_name"])}
            return {"id": model_id, "display_name": model_id}
        if model_type == "image_gen":
            available = await self._catalog.list_visible_models(
                billing_team_id=team_id,
                model_type="image_gen",
            )
            if available:
                return {"id": available[0]["id"], "display_name": available[0]["display_name"]}
            return None
        model_id = settings.default_model
        items = await self._catalog.list_visible_models(
            billing_team_id=team_id,
            model_type="text",
        )
        for m in items:
            if m["id"] == model_id:
                return {"id": model_id, "display_name": str(m["display_name"])}
        return {"id": model_id, "display_name": model_id}

    async def resolve_image_gen_model(self, model_ref: str | None) -> ResolvedImageGenModel:
        """解析图像生成模型引用。

        model_ref 可以是:
        - None: 使用默认图像生成模型 (volcengine/seedream)
        - 系统模型 ID (如 "volcengine/seedream", "openai/dall-e-3")
        - 用户模型 UUID
        """
        if not model_ref:
            return ResolvedImageGenModel(provider="volcengine")

        repo = GatewayModelRepository(self.db)
        row = await repo.get_by_name(None, model_ref)
        if row is not None and bool((row.tags or {}).get("supports_image_gen")):
            return ResolvedImageGenModel(provider=row.provider, is_system=True)

        system_image_models = {
            m.id: m.provider
            for m in app_config.models.available
            if getattr(m, "supports_image_gen", False)
        }
        if model_ref in system_image_models:
            return ResolvedImageGenModel(
                provider=system_image_models[model_ref],
                is_system=True,
            )

        try:
            user_model_id = uuid.UUID(model_ref)
        except ValueError:
            logger.warning("Unknown image_gen model_ref %s, using default", model_ref)
            return ResolvedImageGenModel(provider="volcengine")

        model = await self.repo.get_owned(user_model_id)
        if not model:
            logger.warning("User model %s not found, using default", model_ref)
            return ResolvedImageGenModel(provider="volcengine")

        api_key = None
        if model.api_key_encrypted:
            try:
                api_key = decrypt_value(model.api_key_encrypted, self._encryption_key)
            except Exception:
                logger.exception("Failed to decrypt API key for image gen model %s", model_ref)
                return ResolvedImageGenModel(provider="volcengine")

        return ResolvedImageGenModel(
            provider=model.provider,
            model=model.model_id or None,
            api_key=api_key,
            api_base=model.api_base,
            is_system=False,
        )

    @staticmethod
    def _is_system_model(model_ref: str) -> bool:
        """判断是否为系统模型 ID（含 / 分隔符或已知前缀）"""
        if "/" in model_ref:
            return True
        known_prefixes = ("gpt-", "claude-", "o1", "o3")
        return any(model_ref.startswith(p) for p in known_prefixes)

    @staticmethod
    def _validate_model_types(types: list[str]) -> None:
        invalid = set(types) - VALID_MODEL_TYPES
        if invalid:
            raise ValidationError(f"无效的模型类型: {invalid}")

    def _to_dict(self, model: UserModel) -> dict[str, Any]:
        """转换为字典（API Key 脱敏）"""
        api_key_masked = None
        if model.api_key_encrypted:
            try:
                plain = decrypt_value(model.api_key_encrypted, self._encryption_key)
                api_key_masked = mask_api_key(plain)
            except Exception:
                api_key_masked = "****"

        return {
            "id": str(model.id),
            "user_id": str(model.user_id) if model.user_id else None,
            "anonymous_user_id": model.anonymous_user_id,
            "display_name": model.display_name,
            "provider": model.provider,
            "model_id": model.model_id,
            "api_key_masked": api_key_masked,
            "has_api_key": model.api_key_encrypted is not None,
            "api_base": model.api_base,
            "model_types": model.model_types,
            "config": model.config,
            "is_active": model.is_active,
            "is_system": False,
            "last_test_status": model.last_test_status,
            "last_tested_at": (
                model.last_tested_at.isoformat() if model.last_tested_at else None
            ),
            "last_test_reason": model.last_test_reason,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }
