"""聊天模型就绪分档（纯函数，无 IO）。"""

from __future__ import annotations

from typing import Literal

ChatModelReadiness = Literal[
    "ready",
    "needs_model",
    "needs_connectivity_fix",
    "needs_credential",
]

CHAT_READINESS_NEEDS_CREDENTIAL = "CHAT_READINESS_NEEDS_CREDENTIAL"
CHAT_READINESS_NEEDS_MODEL = "CHAT_READINESS_NEEDS_MODEL"
CHAT_READINESS_NEEDS_CONNECTIVITY = "CHAT_READINESS_NEEDS_CONNECTIVITY"


def classify_chat_readiness(
    *,
    active_credential_count: int,
    requestable_model_count: int,
    total_model_count: int,
) -> ChatModelReadiness:
    """按凭据与可请求模型数量分档。"""
    if requestable_model_count > 0:
        return "ready"
    if total_model_count > 0 and active_credential_count > 0:
        return "needs_connectivity_fix"
    if active_credential_count > 0:
        return "needs_model"
    return "needs_credential"


def chat_readiness_message(readiness: ChatModelReadiness) -> str:
    if readiness == "ready":
        return ""
    if readiness == "needs_credential":
        return "无可用文本模型。请先在 Gateway 添加并启用凭据。"
    if readiness == "needs_model":
        return "凭据已配置，请注册至少一个对话模型后再开始聊天。"
    return "模型连通性不可用，请先在 Gateway 修复并测试通过后再试。"


def chat_readiness_error_code(readiness: ChatModelReadiness) -> str:
    if readiness == "needs_credential":
        return CHAT_READINESS_NEEDS_CREDENTIAL
    if readiness == "needs_model":
        return CHAT_READINESS_NEEDS_MODEL
    if readiness == "needs_connectivity_fix":
        return CHAT_READINESS_NEEDS_CONNECTIVITY
    return "VALIDATION_ERROR"


__all__ = [
    "CHAT_READINESS_NEEDS_CONNECTIVITY",
    "CHAT_READINESS_NEEDS_CREDENTIAL",
    "CHAT_READINESS_NEEDS_MODEL",
    "ChatModelReadiness",
    "chat_readiness_error_code",
    "chat_readiness_message",
    "classify_chat_readiness",
]
