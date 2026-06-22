"""聊天侧模型目录解析（系统目录 + personal gateway_models）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
import uuid

from bootstrap.config import settings
from domains.gateway.application.chat_model_selector_reads import count_active_credentials_for_team
from domains.gateway.application.entitlement_model_status import is_connectivity_requestable
from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_team_id
from domains.gateway.application.model_selector_reads import (
    get_default_for_model_type,
    list_personal_models_for_selector,
)
from domains.gateway.application.model_selector_reads import (
    list_available_models as list_available_models_for_selector,
)
from domains.gateway.application.model_selector_reads import (
    list_available_system_models as list_system_models_for_selector,
)
from domains.gateway.domain.policies.chat_model_readiness import (
    chat_readiness_error_code,
    chat_readiness_message,
    classify_chat_readiness,
)
from domains.gateway.domain.types import PERSONAL_MODEL_TYPES
from libs.exceptions import ValidationError
from libs.iam.permission_context import get_permission_context

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.agent.application.ports.model_catalog_port import ModelCatalogPort

_NO_VISIBLE_VISION_MODELS_MSG = "无可用视觉模型。请先在 Gateway 配置支持 vision 的模型。"
_NO_VISIBLE_IMAGE_GEN_MODELS_MSG = "无可用图像生成模型。请先在 Gateway 配置凭据并注册图像生成模型。"

VALID_MODEL_TYPES = PERSONAL_MODEL_TYPES


@dataclass(frozen=True)
class ResolvedModel:
    """解析后的 Gateway 虚拟模型名，供 AgentLlmFacade 经桥接调用。"""

    model: str


@dataclass(frozen=True)
class ResolvedImageGenModel:
    """解析后的图像生成模型信息"""

    provider: str = "volcengine"
    model: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    is_system: bool = True


class ChatModelResolutionUseCase:
    """运行时模型选择与解析（真源：Gateway 目录 + personal team gateway_models）。"""

    def __init__(self, db: AsyncSession, catalog: ModelCatalogPort) -> None:
        self.db = db
        self._catalog = catalog

    @staticmethod
    def _resolve_user_id(user_id: uuid.UUID | None = None) -> uuid.UUID | None:
        if user_id is not None:
            return user_id
        ctx = get_permission_context()
        if ctx is None:
            return None
        return ctx.user_id

    async def list_models_for_model_selector(
        self,
        model_type: str | None = None,
        *,
        user_id: uuid.UUID | None = None,
        limit: int = 100,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        uid = self._resolve_user_id(user_id)
        if uid is None:
            return []
        return await list_personal_models_for_selector(
            self._catalog,
            uid,
            model_type=model_type,
            provider=provider,
            limit=limit,
        )

    async def list_available(
        self,
        *,
        model_type: str | None = None,
        user_id: uuid.UUID | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        uid = self._resolve_user_id(user_id)
        return await list_available_models_for_selector(
            self._catalog,
            model_type=model_type,
            user_id=uid,
            provider=provider,
        )

    async def is_valid_text_personal_model_ref(
        self,
        model_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None = None,
    ) -> bool:
        uid = self._resolve_user_id(user_id)
        if uid is None:
            return False
        resolution = await self._catalog.resolve_registered_model(
            uid, model_id, required_model_type="text"
        )
        if resolution is None:
            return False
        return (
            resolution.is_active
            and "text" in resolution.model_types
            and is_connectivity_requestable(resolution.last_test_status)
        )

    async def _resolve_personal_text(self, model_id: uuid.UUID) -> ResolvedModel | None:
        uid = self._resolve_user_id()
        if uid is None:
            return None
        resolution = await self._catalog.resolve_registered_model(
            uid, model_id, required_model_type="text"
        )
        if resolution is None:
            return None
        if not resolution.is_active:
            raise ValidationError("该 Gateway 个人模型已停用")
        if not is_connectivity_requestable(resolution.last_test_status):
            raise ValidationError(
                "该 Gateway 个人模型最近一次连通性测试失败，请先在 Gateway 凭据/模型中修复并测试通过，或选择其他模型。"
            )
        if "text" not in resolution.model_types:
            raise ValidationError("该 Gateway 个人模型不支持对话（text）")
        return ResolvedModel(model=resolution.virtual_model_name)

    async def _resolve_personal_vision(self, model_id: uuid.UUID) -> ResolvedModel | None:
        uid = self._resolve_user_id()
        if uid is None:
            return None
        resolution = await self._catalog.resolve_registered_model(
            uid, model_id, required_model_type="image"
        )
        if resolution is None:
            return None
        if not resolution.is_active:
            raise ValidationError("该 Gateway 个人模型已停用")
        if not is_connectivity_requestable(resolution.last_test_status):
            raise ValidationError(
                "该 Gateway 个人模型最近一次连通性测试失败，请先在 Gateway 凭据/模型中修复并测试通过，或选择其他模型。"
            )
        if "image" not in resolution.model_types:
            raise ValidationError("该 Gateway 个人模型不支持视觉（image）")
        return ResolvedModel(model=resolution.virtual_model_name)

    async def _resolve_personal_image_gen(
        self, model_id: uuid.UUID
    ) -> ResolvedImageGenModel | None:
        uid = self._resolve_user_id()
        if uid is None:
            return None
        resolution = await self._catalog.resolve_registered_model(
            uid, model_id, required_model_type="image_gen"
        )
        if resolution is None:
            return None
        if not resolution.is_active:
            raise ValidationError("该 Gateway 个人模型已停用")
        if not is_connectivity_requestable(resolution.last_test_status):
            raise ValidationError(
                "该 Gateway 个人模型最近一次连通性测试失败，请先在 Gateway 凭据/模型中修复并测试通过，或选择其他模型。"
            )
        if "image_gen" not in resolution.model_types:
            raise ValidationError("该 Gateway 个人模型不支持图像生成（image_gen）")
        bare_model = resolution.litellm_model
        if "/" in bare_model:
            bare_model = bare_model.split("/", 1)[1]
        return ResolvedImageGenModel(
            provider=resolution.provider,
            model=bare_model or None,
            api_key=resolution.api_key,
            api_base=resolution.api_base,
            is_system=False,
        )

    async def visible_text_system_model_ids(
        self,
        *,
        billing_team_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> frozenset[str]:
        uid = self._resolve_user_id(user_id)
        team_id = billing_team_id if billing_team_id is not None else resolve_internal_gateway_team_id()
        return await self._catalog.list_requestable_text_model_ids(
            billing_team_id=team_id,
            user_id=uid,
        )

    async def visible_image_system_model_ids(
        self,
        *,
        billing_team_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> frozenset[str]:
        uid = self._resolve_user_id(user_id)
        # 与 visible_text_system_model_ids 对齐：未显式指定计费团队时回退到当前权限上下文团队，
        # 否则 billing_team_id=None 会按「未限定团队」的系统目录解析，漏掉团队可见的 image 模型。
        team_id = (
            billing_team_id if billing_team_id is not None else resolve_internal_gateway_team_id()
        )
        items = await self._catalog.list_visible_models(
            billing_team_id=team_id,
            model_type="image",
            user_id=uid,
        )
        return frozenset(str(m["id"]) for m in items if m.get("id") is not None)

    async def _raise_text_model_unavailable(
        self,
        *,
        billing_team_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> None:
        uid = self._resolve_user_id(user_id)
        requestable = await self._catalog.list_requestable_text_model_ids(
            billing_team_id=billing_team_id,
            user_id=uid,
        )
        # 计数须含连通性失败模型，否则永远落到 needs_model 而非 needs_connectivity_fix。
        total_model_count = await self._catalog.count_registered_text_models(
            billing_team_id=billing_team_id,
            user_id=uid,
        )
        active_creds = await count_active_credentials_for_team(self.db, billing_team_id)
        readiness = classify_chat_readiness(
            active_credential_count=active_creds,
            requestable_model_count=len(requestable),
            total_model_count=total_model_count,
        )
        raise ValidationError(
            chat_readiness_message(readiness),
            code=chat_readiness_error_code(readiness),
        )

    async def _resolve_default_text_model(
        self,
        *,
        billing_team_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> ResolvedModel:
        uid = self._resolve_user_id(user_id)
        picked = await self._catalog.resolve_chat_default_text_model(
            billing_team_id=billing_team_id,
            user_id=uid,
        )
        if picked is None:
            await self._raise_text_model_unavailable(
                billing_team_id=billing_team_id,
                user_id=uid,
            )
        try:
            personal_id = uuid.UUID(picked)
        except ValueError:
            return ResolvedModel(model=picked)
        resolved = await self._resolve_personal_text(personal_id)
        if resolved is not None:
            return resolved
        await self._raise_text_model_unavailable(
            billing_team_id=billing_team_id,
            user_id=uid,
        )

    def _resolve_default_vision_model(
        self, allowed_image_system_ids: frozenset[str]
    ) -> ResolvedModel:
        from domains.gateway.domain.scenario_defaults_policy import pick_scenario_from_visible

        picked = pick_scenario_from_visible(
            env_override=settings.vision_model,
            visible_ids=allowed_image_system_ids,
        )
        if picked is None:
            raise ValidationError(_NO_VISIBLE_VISION_MODELS_MSG)
        return ResolvedModel(model=picked)

    async def resolve_text_chat_model(
        self,
        model_ref: str | None,
        *,
        billing_team_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        allowed_text_system_ids: frozenset[str] | None = None,
    ) -> ResolvedModel:
        uid = self._resolve_user_id(user_id)
        # 与 visible_*_system_model_ids 对齐：未显式指定计费团队时回退到当前权限上下文团队，
        # 否则 listing studio 等不传 billing_team_id 的调用方会按「未限定团队」目录解析默认模型。
        team_id = (
            billing_team_id if billing_team_id is not None else resolve_internal_gateway_team_id()
        )
        allowed = allowed_text_system_ids
        if allowed is None:
            allowed = await self._catalog.list_requestable_text_model_ids(
                billing_team_id=team_id,
                user_id=uid,
            )
        if not model_ref or not str(model_ref).strip():
            return await self._resolve_default_text_model(
                billing_team_id=team_id,
                user_id=uid,
            )

        ref = str(model_ref).strip()
        try:
            personal_id = uuid.UUID(ref)
        except ValueError:
            if ref not in allowed:
                raise ValidationError(f"模型不在可用列表中: {ref}") from None
            return ResolvedModel(model=ref)

        resolved = await self._resolve_personal_text(personal_id)
        if resolved is not None:
            return resolved
        raise ValidationError("Gateway 个人模型不存在或无权使用")

    async def resolve_vision_chat_model(
        self,
        model_ref: str | None,
        *,
        allowed_image_system_ids: frozenset[str],
    ) -> ResolvedModel:
        if not model_ref or not str(model_ref).strip():
            return self._resolve_default_vision_model(allowed_image_system_ids)

        ref = str(model_ref).strip()
        try:
            personal_id = uuid.UUID(ref)
        except ValueError:
            if ref not in allowed_image_system_ids:
                raise ValidationError(f"视觉模型不在可用列表中: {ref}") from None
            return ResolvedModel(model=ref)

        resolved = await self._resolve_personal_vision(personal_id)
        if resolved is not None:
            return resolved
        raise ValidationError("Gateway 个人模型不存在或无权使用")

    async def list_available_system_models(
        self,
        model_type: str | None = None,
        *,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        return await list_system_models_for_selector(
            self._catalog,
            model_type=model_type,
            provider=provider,
        )

    async def get_default_for_type_async(self, model_type: str) -> dict[str, str] | None:
        return await get_default_for_model_type(self._catalog, model_type)

    async def _resolve_visible_system_image_gen(self, model_id: str) -> ResolvedImageGenModel:
        team_id = resolve_internal_gateway_team_id()
        catalog_items = await self._catalog.list_visible_models(
            billing_team_id=team_id,
            model_type="image_gen",
        )
        for item in catalog_items:
            if str(item.get("id")) == model_id:
                real_model = str(item.get("real_model") or "").strip()
                litellm = real_model or model_id
                return ResolvedImageGenModel(
                    provider=str(item.get("provider") or "volcengine"),
                    model=litellm,
                    is_system=True,
                )
        raise ValidationError(f"图像生成模型不在可用列表中: {model_id}")

    async def visible_image_gen_system_model_ids(self) -> frozenset[str]:
        team_id = resolve_internal_gateway_team_id()
        items = await self._catalog.list_visible_models(
            billing_team_id=team_id,
            model_type="image_gen",
        )
        return frozenset(str(m["id"]) for m in items if m.get("id") is not None)

    async def resolve_image_gen_model_for_chat(
        self,
        model_ref: str | None,
        *,
        allowed_image_gen_system_ids: frozenset[str],
    ) -> ResolvedImageGenModel:
        if not model_ref or not str(model_ref).strip():
            if not allowed_image_gen_system_ids:
                raise ValidationError(_NO_VISIBLE_IMAGE_GEN_MODELS_MSG)
            first = sorted(allowed_image_gen_system_ids)[0]
            return await self._resolve_visible_system_image_gen(first)

        ref = str(model_ref).strip()
        try:
            personal_id = uuid.UUID(ref)
        except ValueError:
            if ref not in allowed_image_gen_system_ids:
                raise ValidationError(f"图像生成模型不在可用列表中: {ref}") from None
            return await self._resolve_visible_system_image_gen(ref)

        resolved = await self._resolve_personal_image_gen(personal_id)
        if resolved is not None:
            return resolved
        raise ValidationError("Gateway 个人模型不存在或无权使用")

    @staticmethod
    def validate_model_types(types: list[str]) -> None:
        invalid = set(types) - VALID_MODEL_TYPES
        if invalid:
            raise ValidationError(f"无效的模型类型: {invalid}")


__all__ = [
    "VALID_MODEL_TYPES",
    "ChatModelResolutionUseCase",
    "ResolvedImageGenModel",
    "ResolvedModel",
]
