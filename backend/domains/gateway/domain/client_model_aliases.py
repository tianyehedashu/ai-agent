"""第三方协议客户端常用 ``GatewayModel.name`` 别名清单（运营注册参考）。

与 Claude Code / Cursor / OpenAI SDK / Anthropic SDK 默认请求的 ``model`` 字符串对齐；
每个别名须映射到 ``provider_credentials`` + ``real_model``，且 ``capability=chat``。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClientModelAliasGroup:
    """某一类客户端建议注册的模型别名。"""

    client: str
    aliases: tuple[str, ...]
    notes: str = ""


# Claude Code：ANTHROPIC_MODEL / ANTHROPIC_SMALL_FAST_MODEL 常用值
CLAUDE_CODE_ALIASES: tuple[str, ...] = (
    "claude-sonnet-4-5",
    "claude-opus-4-5",
    "claude-haiku-4-5",
    "claude-sonnet-4-0",
    "claude-3-7-sonnet-latest",
)

# Cursor：Verify Models / 常用 Override 列表
CURSOR_ALIASES: tuple[str, ...] = (
    "gpt-5",
    "gpt-4o",
    "gpt-4o-mini",
    "claude-sonnet-4-5",
    "claude-3-7-sonnet",
    "o3",
    "o4-mini",
)

RECOMMENDED_CLIENT_MODEL_GROUPS: tuple[ClientModelAliasGroup, ...] = (
    ClientModelAliasGroup(
        client="claude-code",
        aliases=CLAUDE_CODE_ALIASES,
        notes="Anthropic Messages（POST /v1/messages）；vkey 须含 chat 能力。",
    ),
    ClientModelAliasGroup(
        client="cursor",
        aliases=CURSOR_ALIASES,
        notes="OpenAI 兼容（POST /v1/chat/completions）；Base URL 须带 /v1。",
    ),
)

ALL_RECOMMENDED_ALIASES: frozenset[str] = frozenset(
    alias for group in RECOMMENDED_CLIENT_MODEL_GROUPS for alias in group.aliases
)


__all__ = [
    "ALL_RECOMMENDED_ALIASES",
    "CLAUDE_CODE_ALIASES",
    "CURSOR_ALIASES",
    "ClientModelAliasGroup",
    "RECOMMENDED_CLIENT_MODEL_GROUPS",
]
