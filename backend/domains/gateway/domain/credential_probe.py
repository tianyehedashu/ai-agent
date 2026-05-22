"""凭据上游模型探测 — 领域值对象（无 I/O）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime
    import uuid

ProbeSupport = Literal["full", "partial", "unsupported", "error"]
ProbeUpstreamKind = Literal["openai_compatible", "none"]


@dataclass(frozen=True)
class UpstreamModelItem:
    """上游列举返回的单条模型（OpenAI /v1/models 形状子集）。"""

    id: str
    owned_by: str | None = None
    already_registered: bool = False
    registered_names: tuple[str, ...] = ()
    inferred_model_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class CredentialProbeResult:
    """探测结果，供 Application 组装为 API 响应。"""

    credential_id: uuid.UUID
    probe_at: datetime
    support: ProbeSupport
    upstream: ProbeUpstreamKind
    items: tuple[UpstreamModelItem, ...]
    message: str | None
    http_status: int | None


__all__ = [
    "CredentialProbeResult",
    "ProbeSupport",
    "ProbeUpstreamKind",
    "UpstreamModelItem",
]
