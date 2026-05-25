"""LiteLLM model_cost / get_model_info 字段 → GatewayModel.tags 映射（纯 domain）。"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

HintMergeMode = Literal["fill_missing", "resync"]

LITELLM_CAPABILITY_TAG_KEYS: frozenset[str] = frozenset(
    {
        "supports_vision",
        "supports_reasoning",
        "supports_tools",
        "supports_json_mode",
        "supports_image_gen",
        "supports_video_gen",
    }
)


class LitellmModelInfoHints(TypedDict, total=False):
    supports_vision: bool | None
    supports_reasoning: bool | None
    supports_function_calling: bool | None
    supports_response_schema: bool | None
    mode: str | None


def hints_without_reasoning(hints: LitellmModelInfoHints) -> LitellmModelInfoHints:
    """显式 ``thinking_param`` 时跳过 LiteLLM reasoning 覆盖。"""
    stripped = dict(hints)
    stripped.pop("supports_reasoning", None)
    return LitellmModelInfoHints(**stripped)


def hints_from_model_info(info: dict[str, Any]) -> LitellmModelInfoHints:
    """从 ``litellm.get_model_info`` 条目提取写侧 hint 子集。"""
    return LitellmModelInfoHints(
        supports_vision=_as_optional_bool(info.get("supports_vision")),
        supports_reasoning=_as_optional_bool(info.get("supports_reasoning")),
        supports_function_calling=_as_optional_bool(info.get("supports_function_calling")),
        supports_response_schema=_as_optional_bool(info.get("supports_response_schema")),
        mode=str(info["mode"]).strip() if info.get("mode") else None,
    )


def tag_hints_from_litellm(hints: LitellmModelInfoHints) -> dict[str, bool]:
    """LiteLLM hint → Gateway tags 布尔字段（仅含可映射键）。"""
    out: dict[str, bool] = {}
    _map_bool_hint(hints.get("supports_vision"), "supports_vision", out)
    _map_bool_hint(hints.get("supports_reasoning"), "supports_reasoning", out)
    _map_bool_hint(hints.get("supports_function_calling"), "supports_tools", out)
    _map_bool_hint(hints.get("supports_response_schema"), "supports_json_mode", out)
    mode = (hints.get("mode") or "").strip().lower()
    if mode == "image_generation":
        out["supports_image_gen"] = True
    elif mode in ("video_generation", "video"):
        out["supports_video_gen"] = True
    return out


def apply_litellm_hints_to_tags(
    tags: dict[str, Any],
    hints: LitellmModelInfoHints,
    *,
    mode: HintMergeMode,
) -> dict[str, Any]:
    """按 merge 模式将 LiteLLM hint 合并进 tags。"""
    merged = dict(tags)
    mapped = tag_hints_from_litellm(hints)
    for key, value in mapped.items():
        if mode == "fill_missing":
            if value is True and key not in merged:
                merged[key] = True
        elif value is True:
            merged[key] = True
        elif value is False:
            merged[key] = False
    return merged


def strip_litellm_capability_tags(tags: dict[str, Any]) -> dict[str, Any]:
    """resync 前剥离由 LiteLLM 映射的能力键。"""
    merged = dict(tags)
    for key in LITELLM_CAPABILITY_TAG_KEYS:
        merged.pop(key, None)
    return merged


def _map_bool_hint(value: bool | None, tag_key: str, out: dict[str, bool]) -> None:
    if isinstance(value, bool):
        out[tag_key] = value


def _as_optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


__all__ = [
    "LITELLM_CAPABILITY_TAG_KEYS",
    "HintMergeMode",
    "LitellmModelInfoHints",
    "apply_litellm_hints_to_tags",
    "hints_from_model_info",
    "hints_without_reasoning",
    "strip_litellm_capability_tags",
    "tag_hints_from_litellm",
]
