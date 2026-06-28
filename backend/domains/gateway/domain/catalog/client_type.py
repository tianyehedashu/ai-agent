"""从 User-Agent 推断第三方协议客户端类型（仅可观测，非鉴权）。"""

from __future__ import annotations

GatewayClientType = str

CLIENT_TYPE_UNKNOWN: GatewayClientType = "unknown"
CLIENT_TYPE_CLAUDE_CODE: GatewayClientType = "claude-code"
CLIENT_TYPE_CURSOR: GatewayClientType = "cursor"
CLIENT_TYPE_OPENAI_SDK: GatewayClientType = "openai-sdk"
CLIENT_TYPE_ANTHROPIC_SDK: GatewayClientType = "anthropic-sdk"


def infer_client_type(user_agent: str | None) -> GatewayClientType:
    """按 UA 子串推断客户端；无法识别时返回 ``unknown``。"""
    if not user_agent or not user_agent.strip():
        return CLIENT_TYPE_UNKNOWN
    ua = user_agent.lower()
    if "claude-cli" in ua or "claude code" in ua:
        return CLIENT_TYPE_CLAUDE_CODE
    if ua.startswith("cursor/") or "cursor-agent" in ua or ua.startswith("cursor "):
        return CLIENT_TYPE_CURSOR
    if ua.startswith("openai/") or "openai-python" in ua or "openai-node" in ua:
        return CLIENT_TYPE_OPENAI_SDK
    if ua.startswith("anthropic/") or "anthropic-python" in ua or "anthropic-typescript" in ua:
        return CLIENT_TYPE_ANTHROPIC_SDK
    return CLIENT_TYPE_UNKNOWN


def truncate_client_ua(user_agent: str | None, *, max_len: int = 512) -> str | None:
    if user_agent is None:
        return None
    text = user_agent.strip()
    if not text:
        return None
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


__all__ = [
    "CLIENT_TYPE_ANTHROPIC_SDK",
    "CLIENT_TYPE_CLAUDE_CODE",
    "CLIENT_TYPE_CURSOR",
    "CLIENT_TYPE_OPENAI_SDK",
    "CLIENT_TYPE_UNKNOWN",
    "GatewayClientType",
    "infer_client_type",
    "truncate_client_ua",
]
