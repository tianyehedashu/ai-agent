"""
LLM 配置持有者 - 依赖注入入口

Infrastructure 层通过 get_llm_config() 获取 LLM 配置，避免直接依赖 bootstrap。
由 bootstrap 在应用启动时调用 set_llm_config(settings) 注入。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from libs.config.interfaces import LLMConfigProtocol

_config: LLMConfigProtocol | None = None


def set_llm_config(config: LLMConfigProtocol) -> None:
    """由 bootstrap 在启动时调用，注入 LLM 配置。"""
    global _config
    _config = config


def get_llm_config() -> LLMConfigProtocol:
    """获取当前注入的 LLM 配置。必须在 set_llm_config 之后调用。"""
    if _config is None:
        raise RuntimeError(
            "LLM config not set. Bootstrap must call set_llm_config(settings) at startup."
        )
    return _config
