"""Gateway 目录种子 JSON 单条模型结构（与历史 app.toml ``[[models.available]]`` 同形）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CatalogSeedModel:
    """单个系统模型种子条目。"""

    id: str
    name: str
    provider: str
    context_window: int = 128000
    input_price: float = 0.0
    output_price: float = 0.0
    input_cost_per_token: float = 0.0
    output_cost_per_token: float = 0.0
    supports_vision: bool = False
    supports_tools: bool = True
    supports_reasoning: bool = False
    thinking_param: str = ""
    supports_json_mode: bool = True
    supports_image_gen: bool = False
    supports_txt2img: bool = True
    supports_img2img: bool = True
    supports_video_gen: bool = False
    supports_image_to_video: bool = False
    max_reference_images: int = 0
    litellm_model: str = ""
    recommended_for: list[str] = field(default_factory=list)
    description: str = ""

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
        if self.supports_txt2img and self.supports_image_gen:
            result.add("txt2img")
        if self.supports_img2img and self.supports_image_gen:
            result.add("img2img")
        if self.supports_video_gen:
            result.add("video_gen")
        if self.supports_image_to_video:
            result.add("image_to_video")
        return frozenset(result)


__all__ = ["CatalogSeedModel"]
