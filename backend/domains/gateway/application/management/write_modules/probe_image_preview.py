"""生图探活响应预览提取。"""

from __future__ import annotations

from contextlib import suppress
from typing import Any


def image_generation_probe_preview(img_response: Any) -> str:
    preview = ""
    with suppress(Exception):
        data = getattr(img_response, "data", None)
        if data is None and isinstance(img_response, dict):
            raw = img_response.get("data")
            data = raw if isinstance(raw, list) else None
        if data and len(data) > 0:
            first = data[0]
            url: str | None
            b64: str | None
            if isinstance(first, dict):
                url = first.get("url") if isinstance(first.get("url"), str) else None
                b64 = first.get("b64_json") if isinstance(first.get("b64_json"), str) else None
            else:
                url = getattr(first, "url", None)
                b64 = getattr(first, "b64_json", None)
                url = url if isinstance(url, str) else None
                b64 = b64 if isinstance(b64, str) else None
            if url:
                preview = url[:100]
            elif b64:
                preview = f"{b64[:40]}…" if len(b64) > 40 else b64
    return preview


__all__ = ["image_generation_probe_preview"]
