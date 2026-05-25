"""Listing Studio 8 图生成 - 槽位参考图解析规则。"""

from __future__ import annotations

from typing import Literal

SlotReferenceMode = Literal["current", "source", "chain"]


def resolve_product_source_image_url(
    manual_reference_url: str | None,
    input_image_urls: list[str] | None,
) -> str | None:
    """生图参考图：手动参考图优先，否则输入区第一张原图。"""
    manual = (manual_reference_url or "").strip()
    if manual:
        return manual
    if input_image_urls:
        first = (input_image_urls[0] or "").strip()
        if first:
            return first
    return None


def resolve_slot_reference_image(
    *,
    mode: SlotReferenceMode,
    slot: int,
    current_slot_url: str | None = None,
    source_image_url: str | None = None,
    slot1_generated_url: str | None = None,
    explicit_reference_url: str | None = None,
) -> str | None:
    """解析单槽 img2img 参考图 URL。

    - explicit_reference_url: prompt item 显式指定，最高优先级
    - mode=current: 当前槽生成图，无则回退 source
    - mode=source: 生图参考图（原图/手动）
    - mode=chain: 批量链式 — slot1 用 source，slot2-8 用 slot1 生成图，无则回退 source
    """
    explicit = (explicit_reference_url or "").strip()
    if explicit:
        return explicit

    source = (source_image_url or "").strip() or None
    current = (current_slot_url or "").strip() or None
    slot1 = (slot1_generated_url or "").strip() or None

    if mode == "current":
        return current or source

    if mode == "source":
        return source

    # chain — batch generation
    if slot <= 1:
        return source
    return slot1 or source


def normalize_explicit_reference_url(
    *,
    slot: int,
    explicit_reference_url: str | None,
    global_source_reference_url: str | None,
    prompt_count: int,
) -> str | None:
    """Router 批量 merge 会把 source 参考图复制到全部槽；2+ 槽在批量任务中应走链式。

    单槽任务（prompt_count == 1）保留显式 reference，供「当前图 / 生图参考图」重生成。
    """
    explicit = (explicit_reference_url or "").strip() or None
    if not explicit:
        return None
    if prompt_count <= 1:
        return explicit
    global_source = (global_source_reference_url or "").strip() or None
    if slot > 1 and global_source and explicit == global_source:
        return None
    return explicit


def extract_global_source_reference(
    prompts: list[dict[str, object]],
) -> str | None:
    """从 prompt 列表中取首个非空 reference_image_url 作为生图参考图。"""
    for item in sorted(prompts, key=lambda p: int(p.get("slot") or 0)):
        raw_ref = item.get("reference_image_url")
        if raw_ref and str(raw_ref).strip():
            return str(raw_ref).strip()
    return None
