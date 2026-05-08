"""
User Model Use Case - 用户模型管理用例

CRUD、连接测试、模型解析（系统模型 + 用户模型统一查询）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from bootstrap.config_loader import ModelInfo, app_config
from domains.agent.infrastructure.llm.gateway import LLMGateway
from domains.agent.infrastructure.models.user_model import UserModel
from domains.agent.infrastructure.repositories.user_model_repository import (
    UserModelRepository,
)
from exceptions import NotFoundError, ValidationError
from libs.crypto import decrypt_value, derive_encryption_key, encrypt_value, mask_api_key
from utils.logging import get_logger

logger = get_logger(__name__)

VALID_MODEL_TYPES = {"text", "image", "image_gen", "video"}
VALID_PROVIDERS = {
    "openai", "deepseek", "dashscope", "anthropic",
    "zhipuai", "volcengine", "custom",
}


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

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserModelRepository(db)
        self._encryption_key = derive_encryption_key(
            settings.secret_key.get_secret_value()
        )

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
        if provider not in VALID_PROVIDERS:
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
    ) -> tuple[list[dict[str, Any]], int]:
        """列出当前用户的模型"""
        if model_type:
            items = await self.repo.find_by_type(model_type, skip=skip, limit=limit)
            total = await self.repo.count_by_type(model_type)
        else:
            items = await self.repo.find_active(skip=skip, limit=limit)
            total = await self.repo.count_owned(is_active=True)
        return [self._to_dict(m) for m in items], total

    async def get_model(self, model_id: uuid.UUID) -> dict[str, Any]:
        """获取模型详情"""
        model = await self.repo.get_owned(model_id)
        if not model:
            raise NotFoundError("UserModel", str(model_id))
        return self._to_dict(model)

    async def update(self, model_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        """更新模型"""
        if "model_types" in kwargs and kwargs["model_types"]:
            self._validate_model_types(kwargs["model_types"])
        if "provider" in kwargs and kwargs["provider"] and kwargs["provider"] not in VALID_PROVIDERS:
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
        """测试模型连接（发送简单请求验证 API Key 有效性）"""
        model = await self.repo.get_owned(model_id)
        if not model:
            raise NotFoundError("UserModel", str(model_id))

        api_key = None
        if model.api_key_encrypted:
            api_key = decrypt_value(model.api_key_encrypted, self._encryption_key)

        litellm_model = self._build_litellm_model(model.provider, model.model_id)

        gateway = LLMGateway(config=settings)

        try:
            response = await gateway.chat(
                messages=[{"role": "user", "content": "Hi"}],
                model=litellm_model,
                api_key=api_key,
                api_base=model.api_base,
                max_tokens=10,
                temperature=0,
            )
            return {
                "success": True,
                "message": "连接成功",
                "model": litellm_model,
                "response_preview": (response.content or "")[:100],
            }
        except Exception as e:
            logger.warning("Model connection test failed for %s: %s", model_id, e)
            return {
                "success": False,
                "message": f"连接失败: {e}",
                "model": litellm_model,
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

        litellm_model = self._build_litellm_model(model.provider, model.model_id)
        return ResolvedModel(
            model=litellm_model,
            api_key=api_key,
            api_base=model.api_base,
            is_system=False,
        )

    def get_available_models(self, model_type: str | None = None) -> list[dict[str, Any]]:
        """获取系统预置模型列表（从 app.toml 读取）"""
        models = []
        for m in app_config.models.available:
            item = {
                "id": m.id,
                "display_name": m.name,
                "provider": m.provider,
                "model_id": m.id,
                "model_types": self._infer_system_model_types(m),
                "is_system": True,
                "config": {
                    "context_window": m.context_window,
                    "supports_vision": m.supports_vision,
                    "supports_tools": m.supports_tools,
                    "supports_reasoning": m.supports_reasoning,
                    "input_price": m.input_price,
                    "output_price": m.output_price,
                    "description": m.description,
                },
            }
            if model_type and model_type not in item["model_types"]:
                continue
            models.append(item)
        return models

    def get_default_for_type(self, model_type: str) -> dict[str, str] | None:
        """获取指定类型的默认模型信息（用于前端展示「默认（模型名）」）。

        model_type:
        - 'text' -> default_model
        - 'image' -> vision_model
        - 'image_gen' -> 首个 image_gen 系统模型
        """
        if model_type == "image":
            model_id = settings.vision_model
        elif model_type == "image_gen":
            available = self.get_available_models(model_type="image_gen")
            if available:
                return {"id": available[0]["id"], "display_name": available[0]["display_name"]}
            return None
        else:
            model_id = settings.default_model
        for m in self.get_available_models(model_type=model_type):
            if m["id"] == model_id:
                return {"id": model_id, "display_name": m["display_name"]}
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

        system_image_models = {
            m.id: m.provider for m in app_config.models.available
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
    def _infer_system_model_types(model_info: ModelInfo) -> list[str]:
        """推断系统模型的类型标签"""
        if getattr(model_info, "supports_image_gen", False):
            return ["image_gen"]
        types = ["text"]
        if getattr(model_info, "supports_vision", False):
            types.append("image")
        return types

    @staticmethod
    def _is_system_model(model_ref: str) -> bool:
        """判断是否为系统模型 ID（含 / 分隔符或已知前缀）"""
        if "/" in model_ref:
            return True
        known_prefixes = ("gpt-", "claude-", "o1", "o3")
        return any(model_ref.startswith(p) for p in known_prefixes)

    @staticmethod
    def _build_litellm_model(provider: str, model_id: str) -> str:
        """构建 LiteLLM 模型名称"""
        if "/" in model_id:
            return model_id
        if provider == "zhipuai":
            return f"zai/{model_id}"
        if provider in ("dashscope", "deepseek", "volcengine"):
            return f"{provider}/{model_id}"
        return model_id

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
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }
