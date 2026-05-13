"""从 app 配置中的 ModelInfo 推断 Gateway capability（与 management_router 预设逻辑一致）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bootstrap.config_loader import ModelInfo


def infer_catalog_capability(model: ModelInfo) -> str:
    """chat / embedding / image（图像生成走 image capability 与现有网关一致）。"""
    if getattr(model, "supports_image_gen", False):
        return "image"
    if "embedding" in model.id:
        return "embedding"
    return "chat"


__all__ = ["infer_catalog_capability"]
