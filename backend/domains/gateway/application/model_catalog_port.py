"""Gateway 模型目录端口（提供方域声明，Agent 等消费方依赖此契约）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import uuid


@dataclass(frozen=True)
class ModelCapabilitySnapshot:
    """与 LLM 参数适配相关的模型能力（与 config_loader.ModelInfo 字段对齐子集）。"""

    supports_tools: bool = True
    supports_reasoning: bool = False
    supports_json_mode: bool = True
    supports_vision: bool = False
    supports_image_gen: bool = False
    supports_txt2img: bool = True
    supports_img2img: bool = False
    supports_video_gen: bool = False
    supports_image_to_video: bool = False
    max_reference_images: int = 0

    @property
    def features(self) -> frozenset[str]:
        result: set[str] = set()
        if self.supports_vision:
            result.add("vision")
        if self.supports_tools:
            result.add("tools")
        if self.supports_reasoning:
            result.add("reasoning")
        if self.supports_json_mode:
            result.add("json_mode")
        if self.supports_image_gen:
            result.add("image_gen")
        if self.supports_txt2img:
            result.add("txt2img")
        if self.supports_img2img:
            result.add("img2img")
        if self.supports_video_gen:
            result.add("video_gen")
        if self.supports_image_to_video:
            result.add("image_to_video")
        return frozenset(result)


@dataclass(frozen=True)
class RegisteredModelResolution:
    """个人 Gateway 模型解析结果（供 Agent 对话 / 生图路径使用）。"""

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
    ) -> list[dict[str, Any]]:
        """返回与模型选择器兼容的 system_models 项结构。"""

    async def resolve_capabilities(self, model_id: str) -> ModelCapabilitySnapshot | None:
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
