"""第三方协议客户端常用 ``GatewayModel.name`` 别名清单（运营注册参考）。

数据基准：**2026-05**。每次厂商发版（一般 1-3 月）要回到本文件追加新别名。

核心约定
--------

- **客户端字符串即 GatewayModel.name**：运营在 Gateway 注册的别名必须与客户端
  在 ``model`` 字段实际发送的字符串完全一致（区分大小写）。
- **Anthropic 4.6+ 使用 dateless 规范 ID，且为 pinned 快照**
  （参考 ``platform.claude.com/docs/en/about-claude/models/model-ids-and-versions``）。
  即 ``claude-opus-4-7`` 本身就是规范模型 ID，并**不会**在新版本发布时自动指向
  新权重；新版本会以新的 ID 上线（``claude-opus-4-8`` 等）。
- **Anthropic 4.5 及以前**：dated ID（如 ``claude-haiku-4-5-20251001``）+
  ``...-latest`` 长期别名（如 ``claude-3-7-sonnet-latest``）。
- **OpenAI**：dateless 规范 ID（``gpt-5.5``）+ snapshot ID（``gpt-5.5-2026-04-23``）；
  规范 ID 会随 OpenAI 内部默认快照变化而切换。
- **不要删除旧别名**：老客户端可能仍在使用，仅追加。

新版本上线时的运营动作
----------------------

1. 在本文件追加新 ID（如 ``claude-opus-4-8``）。
2. 同步 ``backend/docs/GATEWAY_CURSOR_CLAUDE_CODE.md`` 与
   ``backend/docs/GATEWAY_THIRDPARTY_CLIENT_GUIDE.md`` 示例。
3. 在 Gateway 后台为新 ID 绑定 ``provider_credentials`` + ``real_model``，
   或调用 ``POST /api/v1/gateway/models/multi-credential`` 一次性绑定多凭据。
4. 上游探测到 dated ID 时，``domain.upstream_catalog_policy
   .derive_client_facing_model_alias`` 会派生短别名一并入库。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClientModelAliasGroup:
    """某一类客户端建议注册的模型别名。"""

    client: str
    aliases: tuple[str, ...]
    notes: str = ""


# ---------------------------------------------------------------------------
# Claude Code（默认 ANTHROPIC_MODEL / ANTHROPIC_SMALL_FAST_MODEL）
# ---------------------------------------------------------------------------
#
# 截至 2026-05：
#   - 主模型 (``opus`` alias) 默认解析为 Opus 4.7，要求 Claude Code v2.1.111+。
#   - ``ANTHROPIC_MODEL`` 推荐显式写 dateless 规范 ID，避免 alias 解析在不同
#     部署目标（Anthropic API / Bedrock / Vertex / Foundry）差异。
#   - 旧 3.x 家族 alias 仍然在线，运营可视客户兼容需求保留。

CLAUDE_CODE_ALIASES: tuple[str, ...] = (
    # ===== Claude 4.x（dateless 规范 ID = pinned 快照） =====
    # Opus 系列（重推理，对应 Claude Code 主模型）
    "claude-opus-4-7",  # 2026-04-16 发布，当前默认 opus
    "claude-opus-4-6",
    "claude-opus-4-5",
    "claude-opus-4-1",
    "claude-opus-4-0",
    # Sonnet 系列（平衡型）
    "claude-sonnet-4-6",  # 2026-02-17 发布，当前默认 sonnet
    "claude-sonnet-4-5",
    "claude-sonnet-4-0",
    # Haiku 系列（默认 SMALL_FAST_MODEL）—— 4.5 仍是当前唯一的 4.x Haiku
    "claude-haiku-4-5",
    "claude-haiku-4-5-20251001",  # 显式 dated（部分企业部署仅暴露 dated 形式）
    # ===== Claude 3.x（旧家族，沿用 ``-latest`` 长期别名） =====
    "claude-3-7-sonnet-latest",
    "claude-3-5-haiku-latest",
)


# ---------------------------------------------------------------------------
# Cursor（Settings → Models → Add Model 处手工填写）
# ---------------------------------------------------------------------------
#
# Cursor 2026-05 实际 "Available Models" 列表（cursor.com/help/models-and-usage
# /available-models）：覆盖 OpenAI / Anthropic / Google / xAI 与 Composer。

CURSOR_ALIASES: tuple[str, ...] = (
    # ===== OpenAI 当前前沿 =====
    "gpt-5.5",  # 2026-04-23 发布
    "gpt-5.5-pro",
    "gpt-5.4",
    "gpt-5.4-pro",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    # ===== OpenAI 前一代（保留） =====
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5-codex",
    # ===== OpenAI 推理与多模态保留 =====
    "o3",
    "o4-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4o",
    "gpt-4o-mini",
    # ===== Anthropic（与 Claude Code 共用规范 ID） =====
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-opus-4-5",
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    # ===== DeepSeek V4（OpenAI 兼容 + extra_body.thinking） =====
    "deepseek-v4-pro",
    "deepseek-v4-flash",
    # ===== Google Gemini =====
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    # ===== xAI（按需） =====
    "grok-4",
    # ===== Cursor In-House =====
    "composer-2.5",
)


RECOMMENDED_CLIENT_MODEL_GROUPS: tuple[ClientModelAliasGroup, ...] = (
    ClientModelAliasGroup(
        client="claude-code",
        aliases=CLAUDE_CODE_ALIASES,
        notes=(
            "Anthropic Messages（POST /v1/messages）；vkey 须含 chat 能力。"
            "Claude 4.6+ 的 dateless ID 是 pinned 快照，新版本会以新 ID 发布——"
            "运营在厂商发版时直接追加新 ID 即可，老 ID 保留以兼容旧客户端。"
        ),
    ),
    ClientModelAliasGroup(
        client="cursor",
        aliases=CURSOR_ALIASES,
        notes=(
            "OpenAI 兼容（POST /v1/chat/completions）；Base URL 须带 /v1。"
            "Cursor Settings → Models 中填的字符串必须与 GatewayModel.name 完全一致。"
        ),
    ),
)


ALL_RECOMMENDED_ALIASES: frozenset[str] = frozenset(
    alias for group in RECOMMENDED_CLIENT_MODEL_GROUPS for alias in group.aliases
)


__all__ = [
    "ALL_RECOMMENDED_ALIASES",
    "CLAUDE_CODE_ALIASES",
    "CURSOR_ALIASES",
    "RECOMMENDED_CLIENT_MODEL_GROUPS",
    "ClientModelAliasGroup",
]
