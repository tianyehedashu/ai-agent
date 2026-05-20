"""为对外代理响应附加限流头（编排：经端口查窗口用量 → 调 domain policy 构头）。"""

from __future__ import annotations

from domains.gateway.application.proxy_use_case import ProxyContext
from domains.gateway.domain.proxy_policy import rate_limit_target
from domains.gateway.domain.proxy_rate_limit_port import RateLimitUsageReader
from domains.gateway.domain.proxy_ratelimit_headers import (
    anthropic_rate_limit_response_headers,
    build_rate_limit_snapshot,
    openai_rate_limit_response_headers,
)
from domains.gateway.infrastructure.redis_rate_limit_usage_reader import (
    RedisRateLimitUsageReader,
)


def default_rate_limit_usage_reader() -> RateLimitUsageReader:
    """Presentation 工厂默认实现；测试可注入自有 stub。"""
    return RedisRateLimitUsageReader()


async def build_proxy_rate_limit_headers(
    ctx: ProxyContext,
    *,
    flavor: str,
    reader: RateLimitUsageReader | None = None,
) -> dict[str, str]:
    """根据当前 60s 窗口用量生成 OpenAI 或 Anthropic 形限流头。"""
    rpm_limit = ctx.rpm_limit
    tpm_limit = ctx.tpm_limit
    if rpm_limit is None and tpm_limit is None and ctx.vkey is not None:
        rpm_limit = ctx.vkey.rpm_limit
        tpm_limit = ctx.vkey.tpm_limit
    if not rpm_limit and not tpm_limit:
        return {}

    target = rate_limit_target(
        vkey_id=ctx.vkey.vkey_id if ctx.vkey is not None else None,
        platform_api_key_grant_id=ctx.platform_api_key_grant_id,
        platform_api_key_id=ctx.platform_api_key_id,
    )
    if target is None:
        return {}

    scope, scope_id = target
    usage_reader = reader or default_rate_limit_usage_reader()
    rpm_used, tpm_used = await usage_reader.peek_60s_window(scope=scope, scope_id=scope_id)
    snap = build_rate_limit_snapshot(
        rpm_limit=rpm_limit,
        rpm_used=rpm_used,
        tpm_limit=tpm_limit,
        tpm_used=tpm_used,
    )
    if flavor == "anthropic":
        return anthropic_rate_limit_response_headers(snap)
    return openai_rate_limit_response_headers(snap)


__all__ = ["build_proxy_rate_limit_headers", "default_rate_limit_usage_reader"]
