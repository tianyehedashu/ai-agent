"""Provider 环境配置映射（纯函数；settings 快照由 application 传入）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderCredentialsSnapshot:
    api_key: str | None
    api_base: str | None
    extra: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ProviderEnvSnapshot:
    """从 Settings 提取的 provider 明文凭据字段（application 边界构建）。"""

    openai_api_key: str | None = None
    openai_api_base: str | None = None
    deepseek_api_key: str | None = None
    deepseek_api_base: str | None = None
    anthropic_api_key: str | None = None
    dashscope_api_key: str | None = None
    dashscope_api_base: str | None = None
    zhipuai_api_key: str | None = None
    zhipuai_api_base: str | None = None
    volcengine_api_key: str | None = None
    volcengine_api_base: str | None = None
    volcengine_chat_endpoint_id: str | None = None
    volcengine_endpoint_id: str | None = None
    volcengine_image_endpoint_id: str | None = None


def resolve_provider_credentials(
    provider: str,
    snapshot: ProviderEnvSnapshot,
) -> ProviderCredentialsSnapshot | None:
    """按 provider 从快照解析 api_key / api_base；custom 返回空凭据。"""
    p = provider.strip().lower()
    if p == "openai":
        return ProviderCredentialsSnapshot(snapshot.openai_api_key, snapshot.openai_api_base)
    if p == "deepseek":
        return ProviderCredentialsSnapshot(snapshot.deepseek_api_key, snapshot.deepseek_api_base)
    if p == "anthropic":
        return ProviderCredentialsSnapshot(snapshot.anthropic_api_key, None)
    if p == "dashscope":
        return ProviderCredentialsSnapshot(snapshot.dashscope_api_key, snapshot.dashscope_api_base)
    if p == "zhipuai":
        return ProviderCredentialsSnapshot(snapshot.zhipuai_api_key, snapshot.zhipuai_api_base)
    if p == "volcengine":
        return ProviderCredentialsSnapshot(snapshot.volcengine_api_key, snapshot.volcengine_api_base)
    if p == "custom":
        return ProviderCredentialsSnapshot(None, None)
    return None


def volcengine_extra_from_snapshot(snapshot: ProviderEnvSnapshot) -> dict[str, Any] | None:
    chat_id = snapshot.volcengine_chat_endpoint_id or snapshot.volcengine_endpoint_id
    image_id = snapshot.volcengine_image_endpoint_id
    extra: dict[str, Any] = {}
    if chat_id:
        extra["endpoint_id"] = chat_id
    if image_id:
        extra["image_endpoint_id"] = image_id
    return extra or None


def image_probe_size(provider: str) -> str:
    """生图探活/测试用最小合法尺寸。"""
    p = provider.strip().lower()
    if p == "volcengine":
        return "1920x1920"
    if p == "openai":
        return "1024x1024"
    return "1024x1024"


def provider_env_snapshot_from_settings(settings: object) -> ProviderEnvSnapshot:
    """从 bootstrap Settings 构建快照（仅 application 调用）。"""

    def _secret(attr: str) -> str | None:
        val = getattr(settings, attr, None)
        if val is None:
            return None
        get_secret = getattr(val, "get_secret_value", None)
        return get_secret() if callable(get_secret) else str(val)

    return ProviderEnvSnapshot(
        openai_api_key=_secret("openai_api_key"),
        openai_api_base=getattr(settings, "openai_api_base", None),
        deepseek_api_key=_secret("deepseek_api_key"),
        deepseek_api_base=getattr(settings, "deepseek_api_base", None),
        anthropic_api_key=_secret("anthropic_api_key"),
        dashscope_api_key=_secret("dashscope_api_key"),
        dashscope_api_base=getattr(settings, "dashscope_api_base", None),
        zhipuai_api_key=_secret("zhipuai_api_key"),
        zhipuai_api_base=getattr(settings, "zhipuai_api_base", None),
        volcengine_api_key=_secret("volcengine_api_key"),
        volcengine_api_base=getattr(settings, "volcengine_api_base", None),
        volcengine_chat_endpoint_id=getattr(settings, "volcengine_chat_endpoint_id", None),
        volcengine_endpoint_id=getattr(settings, "volcengine_endpoint_id", None),
        volcengine_image_endpoint_id=getattr(settings, "volcengine_image_endpoint_id", None),
    )


__all__ = [
    "ProviderCredentialsSnapshot",
    "ProviderEnvSnapshot",
    "image_probe_size",
    "provider_env_snapshot_from_settings",
    "resolve_provider_credentials",
    "volcengine_extra_from_snapshot",
]
