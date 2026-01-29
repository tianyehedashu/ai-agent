"""
LLM Service Protocol - LLM 服务抽象

定义跨域使用的 LLM 服务接口，避免直接依赖 agent 域的 infrastructure 实现。
"""

from typing import Any


class LLMServiceProtocol:
    """
    LLM 服务协议

    跨域使用 LLM 服务的抽象接口，各域通过依赖注入使用。
    LLMGateway 实现此协议。

    注意：这是结构化类型（Protocol），任何实现这些方法的类都兼容。
    """

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        """
        调用 LLM 聊天接口

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            model: 模型名称（可选，使用默认模型）
            temperature: 温度参数
            max_tokens: 最大 tokens
            tools: 工具列表
            stream: 是否流式
            **kwargs: 其他参数

        Returns:
            LLMResponse 对象（有 content 属性）或流式生成器
        """
        ...

    async def count_tokens(self, text: str, model: str | None = None) -> int:
        """
        计算 tokens 数量

        Args:
            text: 文本内容
            model: 模型名称（可选）

        Returns:
            tokens 数量
        """
        ...
