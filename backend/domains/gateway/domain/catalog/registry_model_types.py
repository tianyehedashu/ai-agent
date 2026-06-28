"""注册表模型 ``model_types`` 推导与列表 ``type`` 筛选匹配（单一真源）。"""

from __future__ import annotations

from typing import Any

# 列表/选择器 ``?type=`` 合法值：model_types 四项 + 无推导 types 的主能力
REGISTRY_ABILITY_FILTER_VALUES: frozenset[str] = frozenset(
    {
        "text",
        "image",
        "image_gen",
        "video",
        "chat",
        "embedding",
        "video_generation",
        "moderation",
        "audio_transcription",
        "audio_speech",
        "rerank",
    }
)

# model_types 筛选项（与 PERSONAL_MODEL_TYPES / 选择器对齐）
REGISTRY_MODEL_TYPE_FILTER_VALUES: frozenset[str] = frozenset(
    {"text", "image", "image_gen", "video"}
)


def infer_model_types_from_tags(tags: dict[str, Any], capability: str) -> list[str]:
    """结合网关 capability 与 tags 推断 user-model 选择器 ``model_types``。"""
    cap = (capability or "").strip().lower()
    if cap in (
        "embedding",
        "audio_transcription",
        "audio_speech",
        "rerank",
        "moderation",
    ):
        return []
    out: list[str] = []
    if tags.get("supports_video_gen"):
        out.append("video")
    if cap == "image":
        out.append("image_gen")
    elif cap == "video_generation":
        if "video" not in out:
            out.append("video")
    elif cap == "chat":
        out.append("text")
        if tags.get("supports_vision"):
            out.append("image")
        if tags.get("supports_image_gen"):
            out.append("image_gen")
    if not out:
        out.append("text")
        if tags.get("supports_vision"):
            out.append("image")
    return out


def ability_filters_via_sql_capability_column(filter_value: str) -> bool:
    """筛选值是否可仅用 ``gateway_models.capability`` 列做 SQL 等值过滤。"""
    key = filter_value.strip().lower()
    if key in REGISTRY_MODEL_TYPE_FILTER_VALUES:
        return False
    return not infer_model_types_from_tags({}, key)


def matches_registry_ability_filter(
    *,
    tags: dict[str, Any],
    capability: str,
    filter_value: str,
    model_types: list[str] | None = None,
) -> bool:
    """注册表 ``?type=`` / 选择器能力筛选：有推导 types 则成员匹配，否则 capability 相等。"""
    key = filter_value.strip().lower()
    types = (
        model_types if model_types is not None else infer_model_types_from_tags(tags, capability)
    )
    if types:
        return key in types
    return (capability or "").strip().lower() == key


def registry_row_matches_ability_filter(
    row: object,
    filter_value: str,
) -> bool:
    """对 ORM 注册表行（GatewayModel / SystemGatewayModel）做能力筛选。"""
    tags = getattr(row, "tags", None) or {}
    cap = str(getattr(row, "capability", "") or "")
    return matches_registry_ability_filter(
        tags=tags if isinstance(tags, dict) else {},
        capability=cap,
        filter_value=filter_value,
    )


def selector_item_matches_ability_filter(
    item: dict[str, object],
    filter_value: str,
) -> bool:
    """对已含 ``model_types`` / ``capability`` 的选择器 dict 做能力筛选。"""
    raw_types = item.get("model_types")
    model_types: list[str] | None = None
    if isinstance(raw_types, list):
        model_types = [str(t) for t in raw_types]
    tags_raw = item.get("tags")
    tags = tags_raw if isinstance(tags_raw, dict) else {}
    cap = str(item.get("capability") or "")
    return matches_registry_ability_filter(
        tags=tags,
        capability=cap,
        filter_value=filter_value,
        model_types=model_types,
    )


__all__ = [
    "REGISTRY_ABILITY_FILTER_VALUES",
    "REGISTRY_MODEL_TYPE_FILTER_VALUES",
    "ability_filters_via_sql_capability_column",
    "infer_model_types_from_tags",
    "matches_registry_ability_filter",
    "registry_row_matches_ability_filter",
    "selector_item_matches_ability_filter",
]
