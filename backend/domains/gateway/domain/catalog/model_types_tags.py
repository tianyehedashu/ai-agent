"""model_types 与 GatewayModel.tags 能力键的双向映射（纯 domain）。

写侧产品规则（与前端 ``ModelCapabilityEditor`` 对齐）：
- ``capability=chat`` 仅允许 ``model_types`` 为 ``text`` / ``image``（图片理解）；
  生图须 ``capability=image``，视频须 ``capability=video_generation``。
- 读侧 ``registry_model_types.infer_model_types_from_tags`` 仍可因历史
  ``supports_image_gen`` 等 tags 推导 ``image_gen``；仅当 PATCH 显式提交
  ``model_types`` 时才按本模块规则同步 tags（未 PATCH 则保留历史值）。
"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.types import PERSONAL_MODEL_TYPES
from libs.exceptions import ValidationError

_TYPE_CAPABILITY_KEYS: dict[str, str] = {
    "image": "supports_vision",
    "image_gen": "supports_image_gen",
    "video": "supports_video_gen",
}

_CAPABILITY_ALLOWED_TYPES: dict[str, frozenset[str]] = {
    "chat": frozenset({"text", "image"}),
    "image": frozenset({"image_gen"}),
    "video_generation": frozenset({"video"}),
    "embedding": frozenset({"text"}),
    "audio_transcription": frozenset({"text"}),
    "audio_speech": frozenset({"text"}),
    "rerank": frozenset({"text"}),
    "moderation": frozenset({"text"}),
}

_MODEL_TYPE_TO_CAPABILITY: dict[str, str] = {
    "text": "chat",
    "image": "chat",
    "image_gen": "image",
    "video": "video_generation",
}

_CAPABILITY_TYPE_PRIORITY: tuple[str, ...] = ("video", "image_gen", "image", "text")


def capability_for_model_type(model_type: str) -> str:
    """单个 model_type → gateway ``capability`` 列值。"""
    return _MODEL_TYPE_TO_CAPABILITY.get(model_type.strip().lower(), "chat")


def primary_capability_from_model_types(model_types: tuple[str, ...]) -> str:
    """多 model_types 时按产品优先级取主 capability。"""
    for preferred in _CAPABILITY_TYPE_PRIORITY:
        if preferred in model_types:
            return capability_for_model_type(preferred)
    return "chat"


def model_types_for_capability_write(
    model_types: tuple[str, ...],
    capability: str,
) -> tuple[str, ...]:
    """写侧：按 capability 过滤 catalog 推断的 model_types。"""
    cap = capability.strip().lower()
    allowed = _CAPABILITY_ALLOWED_TYPES.get(cap)
    if allowed is None:
        return model_types
    filtered = tuple(t for t in model_types if t in allowed)
    if not filtered:
        return model_types
    return normalize_model_types(filtered, ensure_text=cap == "chat")


def resolve_catalog_write_capability(
    model_types: tuple[str, ...],
    *,
    capability_override: str | None,
) -> str:
    """目录写侧：推断 capability；override 不兼容时回退推断值。"""
    inferred = primary_capability_from_model_types(model_types)
    if capability_override is None:
        return inferred
    override = capability_override.strip()
    if not override:
        return inferred
    try:
        validate_model_types_for_capability(list(model_types), override)
        return override
    except ValidationError:
        return inferred


def normalize_model_types(
    types: list[str] | tuple[str, ...],
    *,
    ensure_text: bool = True,
) -> tuple[str, ...]:
    """去重保序，过滤非法值；chat 等多模态场景至少保留 text。"""
    out: list[str] = []
    for raw in types:
        key = str(raw).strip().lower()
        if key in PERSONAL_MODEL_TYPES and key not in out:
            out.append(key)
    if not out:
        return ("text",)
    if ensure_text:
        if "text" not in out and any(t in out for t in ("image", "image_gen", "video")):
            out.insert(0, "text")
        elif "text" in out:
            out.remove("text")
            out.insert(0, "text")
    return tuple(out)


def validate_model_types_for_capability(model_types: list[str], capability: str) -> None:
    """校验 model_types 与主调用面 capability 是否兼容。"""
    cap = (capability or "").strip().lower()
    allowed = _CAPABILITY_ALLOWED_TYPES.get(cap)
    if allowed is None:
        raise ValidationError(f"不支持的 capability: {capability}")
    ensure_text = cap == "chat"
    normalized = normalize_model_types(model_types, ensure_text=ensure_text)
    invalid = [t for t in normalized if t not in allowed]
    if invalid:
        raise ValidationError(
            f"capability={cap!r} 下不允许 model_types {invalid!r}；"
            f"允许: {sorted(allowed)}"
        )


def tags_from_model_types(
    model_types: list[str],
    *,
    existing_tags: dict[str, Any],
    capability: str,
    clear_unselected: bool = True,
) -> dict[str, Any]:
    """按选中的 model_types 设置/清除 supports_* 能力 tags。

    ``clear_unselected=False`` 时仅写入 true 标记（用于 create 初始 tags）。
    """
    validate_model_types_for_capability(model_types, capability)
    cap = (capability or "").strip().lower()
    ensure_text = cap == "chat"
    merged = dict(existing_tags)
    normalized = normalize_model_types(model_types, ensure_text=ensure_text)
    for mtype in normalized:
        tag_key = _TYPE_CAPABILITY_KEYS.get(mtype)
        if tag_key:
            merged[tag_key] = True
    if clear_unselected:
        for mtype, tag_key in _TYPE_CAPABILITY_KEYS.items():
            if mtype not in normalized:
                merged[tag_key] = False
    return merged


__all__ = [
    "capability_for_model_type",
    "model_types_for_capability_write",
    "normalize_model_types",
    "primary_capability_from_model_types",
    "resolve_catalog_write_capability",
    "tags_from_model_types",
    "validate_model_types_for_capability",
]
