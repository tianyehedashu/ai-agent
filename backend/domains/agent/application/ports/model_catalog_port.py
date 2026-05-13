"""Agent 域对「模型目录 / 能力元数据」的端口（由 Gateway 实现，避免 presentation 直连 infrastructure）。"""

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
        return frozenset(result)


class ModelCatalogPort(Protocol):
    """运行时模型目录（以 Gateway DB 为准；能力字段来自 tags）。"""

    async def list_visible_models(
        self,
        *,
        billing_team_id: uuid.UUID | None,
        model_type: str | None,
    ) -> list[dict[str, Any]]:
        """返回与 UserModel 选择器兼容的 system_models 项结构。"""

    async def resolve_capabilities(self, model_id: str) -> ModelCapabilitySnapshot | None:
        """按虚拟模型名解析能力；未知返回 None。"""

    async def model_features(self, model_id: str) -> frozenset[str] | None:
        """返回特性集合，供产品信息能力校验等场景使用。"""


__all__ = ["ModelCapabilitySnapshot", "ModelCatalogPort"]
