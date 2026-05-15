"""LLM 服务抽象层 - 跨域 LLM 调用的协议定义"""

from .litellm_model_id import build_litellm_model_id
from .protocol import LLMServiceProtocol

__all__ = ["LLMServiceProtocol", "build_litellm_model_id"]
