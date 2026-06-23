"""从上游模型 id（及可选 owned_by）推断 personal gateway_models 的 model_types。"""

from __future__ import annotations

import re

from domains.gateway.domain.types import PERSONAL_MODEL_TYPES

# 个人不支持的 SKU（无对应 model_type 行）
_NON_IMPORTABLE_RE = re.compile(
    r"(embedding|embed|rerank|moderation|whisper|tts|speech|transcri)",
    re.IGNORECASE,
)

_IMAGE_GEN_RE = re.compile(
    r"(^dall-e|dall-e|/dall-e|imagen|flux|stable-diffusion|sdxl|"
    r"wanx.*image|wan.*-image|gpt-image|image-1|/image/)",
    re.IGNORECASE,
)

_VIDEO_RE = re.compile(
    r"(^sora|/sora|sora-|wan.*t2v|wanx.*video|cogvideox|kling|"
    r"runway|luma|veo|seedance|video-gen|/video/)",
    re.IGNORECASE,
)

_VISION_CHAT_RE = re.compile(
    r"(-vl-|/vl/|vision|omni|gpt-4o|gpt-4\.1|gpt-5|claude-3|claude-sonnet|"
    r"claude-opus|claude-haiku|gemini-|qwen.*vl|qwen-vl|glm-4v|yi-vision|"
    r"kimi-k2|kimi-k2\.|moonshot)",
    re.IGNORECASE,
)

# 非 personal model_types SKU → Gateway ``capability`` 列（顺序优先于 batch 默认 chat）
_CAPABILITY_FROM_ID: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(embedding|embed)", re.IGNORECASE), "embedding"),
    (re.compile(r"rerank", re.IGNORECASE), "rerank"),
    (re.compile(r"moderation", re.IGNORECASE), "moderation"),
    (re.compile(r"(whisper|transcri)", re.IGNORECASE), "audio_transcription"),
    (re.compile(r"(tts|speech)", re.IGNORECASE), "audio_speech"),
)


def infer_non_personal_gateway_capability(upstream_id: str) -> str | None:
    """personal model_types 为空时，从上游 id 推断主调用面 capability。"""
    mid = upstream_id.strip()
    if not mid:
        return None
    for pattern, capability in _CAPABILITY_FROM_ID:
        if pattern.search(mid):
            return capability
    return None


def infer_upstream_model_types(
    provider: str,
    upstream_id: str,
    owned_by: str | None = None,
) -> tuple[str, ...]:
    """推断 personal 批量导入应创建的 model_types（与前端 infer-model-types 对齐）。

    返回空元组表示当前个人模型注册不支持该 SKU（探测列表中应视为不可导入）。
    """
    _ = provider.strip().lower()
    mid = upstream_id.strip()
    if not mid:
        return ()

    haystack = mid
    if owned_by:
        haystack = f"{mid} {owned_by}"

    if _NON_IMPORTABLE_RE.search(haystack):
        return ()

    if _IMAGE_GEN_RE.search(mid):
        return ("image_gen",)

    if _VIDEO_RE.search(mid):
        return ("video",)

    if _VISION_CHAT_RE.search(mid):
        return ("text", "image")

    return ("text",)


def filter_valid_personal_model_types(types: tuple[str, ...]) -> tuple[str, ...]:
    """只保留 PERSONAL_MODEL_TYPES 中的值，且至少保留 text 作为兜底。"""
    if not types:
        return ()
    out: list[str] = []
    for t in types:
        if t in PERSONAL_MODEL_TYPES and t not in out:
            out.append(t)
    return tuple(out)


__all__ = [
    "filter_valid_personal_model_types",
    "infer_non_personal_gateway_capability",
    "infer_upstream_model_types",
]
