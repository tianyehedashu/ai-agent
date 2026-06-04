"""Gateway 管理面子域 — 出站 HTTP 等应用端口（非跨域 ``application/ports.py`` 桥接契约）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawUpstreamListResult:
    """OpenAI 兼容 ``GET .../models`` 适配器原始结果。"""

    ok: bool
    http_status: int | None
    items: tuple[tuple[str, str | None], ...]
    """(model_id, owned_by) 元组序列。"""
    error_message: str | None


class UpstreamModelListPort(Protocol):
    async def fetch_models(
        self,
        *,
        list_url: str,
        api_key: str,
        timeout_seconds: float = 15.0,
        user_agent: str | None = None,
    ) -> RawUpstreamListResult:
        """GET ``list_url``，使用 Bearer API Key。"""


__all__ = ["RawUpstreamListResult", "UpstreamModelListPort"]
