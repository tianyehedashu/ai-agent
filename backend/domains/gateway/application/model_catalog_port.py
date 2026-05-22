"""Gateway 模型目录端口（提供方域声明，Agent 等消费方依赖此契约）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from domains.gateway.domain.model_capability import ModelCapabilitySnapshot

if TYPE_CHECKING:
    import uuid


@dataclass(frozen=True)
class RegisteredModelResolution:
    """个人 Gateway 模型解析结果（供 Agent 对话 / 生图路径使用）。"""

    virtual_model_name: str
    litellm_model: str
    provider: str
    api_key: str | None
    api_base: str | None
    gateway_model_id: uuid.UUID
    is_active: bool
    last_test_status: str | None
    model_types: tuple[str, ...]


class ModelCatalogPort(Protocol):
    """运行时模型目录（以 Gateway DB 为准；能力字段来自 tags）。"""

    async def list_visible_models(
        self,
        *,
        billing_team_id: uuid.UUID | None,
        model_type: str | None,
        user_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """返回与模型选择器兼容的 system_models 项结构（system 行经可见性过滤）。"""

    async def resolve_capabilities(
        self,
        model_id: str,
        *,
        billing_team_id: uuid.UUID | None = None,
    ) -> ModelCapabilitySnapshot | None:
        """按虚拟模型名解析能力；未知返回 None。"""

    async def model_features(self, model_id: str) -> frozenset[str] | None:
        """返回特性集合，供产品信息能力校验等场景使用。"""

    async def list_personal_models_for_selector(
        self,
        user_id: uuid.UUID,
        model_type: str | None,
        provider: str | None,
    ) -> list[dict[str, Any]]:
        """个人团队 gateway_models，供聊天选择器 personal_models 段使用。"""

    async def resolve_registered_model(
        self,
        user_id: uuid.UUID,
        model_ref: uuid.UUID,
        required_model_type: str | None,
    ) -> RegisteredModelResolution | None:
        """按 gateway_models.id 解析个人注册模型。"""


__all__ = [
    "ModelCapabilitySnapshot",
    "ModelCatalogPort",
    "RegisteredModelResolution",
]
