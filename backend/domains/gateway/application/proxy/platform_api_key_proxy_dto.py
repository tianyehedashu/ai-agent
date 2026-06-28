"""平台 API Key 走 /v1 代理时的应用层 DTO（不暴露 Identity 域实体）。"""

from __future__ import annotations

from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class PlatformApiKeyGatewayProxyAuth:
    """``sk-*`` + ``gateway:proxy`` 入站鉴权成功后的只读快照。"""

    user_id: uuid.UUID
    api_key_id: uuid.UUID
    team_id: uuid.UUID
    team_role: str
    grant_id: uuid.UUID
    allowed_models: tuple[str, ...]
    allowed_capabilities: tuple[str, ...]
    rpm_limit: int | None
    tpm_limit: int | None
    store_full_messages: bool
    guardrail_enabled: bool


__all__ = ["PlatformApiKeyGatewayProxyAuth"]
