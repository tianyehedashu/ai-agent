"""从 app 配置中的 ModelInfo 推断 Gateway 注册行的主调用面 ``capability``。"""

from __future__ import annotations

from bootstrap.config_loader import ModelInfo


def infer_catalog_capability(model: ModelInfo) -> str:
    """推断 ``GatewayModel.capability``（OpenAI 兼容主调用面）。

    规则要点：
    - ``embedding``：模型 id 含 ``embedding``（大小写不敏感）。
    - ``video_generation`` / ``image``：仅当为「非对话型」SKU（无视觉、无工具）时，
      分别绑定视频 / 图像生成 HTTP 面；否则仍用 ``chat``，避免多模态模型被误判为纯生图/纯视频。
    - 其余为 ``chat``（含 Anthropic Messages 等经 chat 编排的入口）。
    """
    if "embedding" in model.id.lower():
        return "embedding"
    chat_like = bool(model.supports_vision or model.supports_tools)
    if getattr(model, "supports_video_gen", False) and not chat_like:
        return "video_generation"
    if getattr(model, "supports_image_gen", False) and not chat_like:
        return "image"
    return "chat"


__all__ = ["infer_catalog_capability"]
