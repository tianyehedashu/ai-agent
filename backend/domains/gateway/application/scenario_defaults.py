"""场景默认模型：环境变量优先，Gateway 可见目录兜底。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from bootstrap.config import settings
from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_team_id
from domains.gateway.application.model_catalog_port import ModelCatalogPort
from domains.gateway.domain.policies.chat_model_readiness import (
    chat_readiness_error_code,
    chat_readiness_message,
    classify_chat_readiness,
)
from domains.gateway.domain.scenario_defaults_policy import (
    ScenarioName,
    catalog_model_type_for_scenario,
    pick_scenario_from_visible,
)
from libs.exceptions import ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_SCENARIO_SETTINGS_ATTR: dict[ScenarioName, str] = {
    "default": "default_model",
    "fast": "fast_model",
    "reasoning": "reasoning_model",
    "code": "code_model",
    "long_context": "long_context_model",
    "vision": "vision_model",
    "embedding": "embedding_model",
}

_NO_MODEL_MESSAGES: dict[ScenarioName, str] = {
    "default": "无可用文本模型。请先在 Gateway 添加凭据并注册对话模型，或联系管理员开通系统模型。",
    "fast": "无可用快速模型。请先在 Gateway 配置凭据并注册模型。",
    "reasoning": "无可用推理模型。请先在 Gateway 配置凭据并注册模型。",
    "code": "无可用代码模型。请先在 Gateway 配置凭据并注册模型。",
    "long_context": "无可用长上下文模型。请先在 Gateway 配置凭据并注册模型。",
    "vision": "无可用视觉模型。请先在 Gateway 配置支持 vision 的模型。",
    "embedding": "无可用 Embedding 模型。请先在 Gateway 配置 Embedding 模型。",
}


def _env_override_for(scenario: ScenarioName, env_override: str | None) -> str:
    if env_override is not None:
        return env_override.strip()
    return str(getattr(settings, _SCENARIO_SETTINGS_ATTR[scenario], "") or "").strip()


async def resolve_scenario_default(
    catalog: ModelCatalogPort,
    *,
    scenario: ScenarioName,
    env_override: str | None = None,
    billing_team_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> str | None:
    """解析场景默认模型：env 优先且在可见列表则使用，否则取可见列表首个。"""
    override = _env_override_for(scenario, env_override)
    # 未显式指定计费团队时回退到当前权限上下文团队（与 X-Team-Id 对齐）；标题生成、Embedding
    # 引导、视频提示词优化等内部调用不传 billing_team_id，依赖此回退命中团队可见目录。
    team_id = billing_team_id if billing_team_id is not None else resolve_internal_gateway_team_id()

    if scenario == "embedding":
        if override:
            return override
        items = await catalog.list_visible_models(
            billing_team_id=team_id,
            model_type=None,
            user_id=user_id,
        )
        for item in items:
            types = item.get("model_types") or []
            if "embedding" in types:
                model_id = item.get("id")
                if isinstance(model_id, str) and model_id.strip():
                    return model_id.strip()
        return None

    if scenario == "default":
        return await catalog.resolve_chat_default_text_model(
            billing_team_id=team_id,
            user_id=user_id,
        )

    model_type = catalog_model_type_for_scenario(scenario)
    if model_type is None:
        return override or None

    items = await catalog.list_visible_models(
        billing_team_id=team_id,
        model_type=model_type,
        user_id=user_id,
    )
    visible = frozenset(str(m["id"]) for m in items if m.get("id") is not None)
    return pick_scenario_from_visible(env_override=override, visible_ids=visible)


async def require_scenario_default(
    catalog: ModelCatalogPort,
    *,
    scenario: ScenarioName,
    env_override: str | None = None,
    empty_message: str | None = None,
    billing_team_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    session: AsyncSession | None = None,
) -> str:
    """同 ``resolve_scenario_default``，无结果时抛 ``ValidationError``。"""
    resolved = await resolve_scenario_default(
        catalog,
        scenario=scenario,
        env_override=env_override,
        billing_team_id=billing_team_id,
        user_id=user_id,
    )
    if resolved:
        return resolved
    if scenario == "default" and session is not None and user_id is not None:
        from domains.gateway.application.chat_model_selector_reads import (
            count_active_credentials_for_team,
        )

        team_id = (
            billing_team_id if billing_team_id is not None else resolve_internal_gateway_team_id()
        )
        requestable = await catalog.list_requestable_text_model_ids(
            billing_team_id=team_id,
            user_id=user_id,
        )
        active_creds = await count_active_credentials_for_team(session, team_id)
        # 计数须含连通性失败模型，否则永远落到 needs_model 而非 needs_connectivity_fix。
        total_models = await catalog.count_registered_text_models(
            billing_team_id=team_id,
            user_id=user_id,
        )
        readiness = classify_chat_readiness(
            active_credential_count=active_creds,
            requestable_model_count=len(requestable),
            total_model_count=total_models,
        )
        raise ValidationError(
            chat_readiness_message(readiness),
            code=chat_readiness_error_code(readiness),
        )
    raise ValidationError(empty_message or _NO_MODEL_MESSAGES[scenario])


class ScenarioDefaultsService:
    """场景默认模型解析（注入 ``ModelCatalogPort``）。"""

    def __init__(self, catalog: ModelCatalogPort) -> None:
        self._catalog = catalog

    async def resolve(
        self,
        scenario: ScenarioName,
        *,
        env_override: str | None = None,
        billing_team_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> str | None:
        return await resolve_scenario_default(
            self._catalog,
            scenario=scenario,
            env_override=env_override,
            billing_team_id=billing_team_id,
            user_id=user_id,
        )

    async def require(
        self,
        scenario: ScenarioName,
        *,
        env_override: str | None = None,
        empty_message: str | None = None,
        billing_team_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        session: AsyncSession | None = None,
    ) -> str:
        return await require_scenario_default(
            self._catalog,
            scenario=scenario,
            env_override=env_override,
            empty_message=empty_message,
            billing_team_id=billing_team_id,
            user_id=user_id,
            session=session,
        )

    async def resolve_default(
        self,
        env_override: str | None = None,
        *,
        billing_team_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> str | None:
        return await self.resolve(
            "default",
            env_override=env_override,
            billing_team_id=billing_team_id,
            user_id=user_id,
        )

    async def resolve_fast(
        self,
        env_override: str | None = None,
        *,
        billing_team_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> str | None:
        return await self.resolve(
            "fast",
            env_override=env_override,
            billing_team_id=billing_team_id,
            user_id=user_id,
        )

    async def resolve_vision(
        self,
        env_override: str | None = None,
        *,
        billing_team_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> str | None:
        return await self.resolve(
            "vision",
            env_override=env_override,
            billing_team_id=billing_team_id,
            user_id=user_id,
        )


__all__ = [
    "ScenarioDefaultsService",
    "ScenarioName",
    "require_scenario_default",
    "resolve_scenario_default",
]
