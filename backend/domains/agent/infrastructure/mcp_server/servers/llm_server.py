"""
LLM Server - 使用 FastMCP 实现

提供 LLM 调用能力作为 MCP 工具。配置通过 libs.config.get_llm_config() 获取，
由 bootstrap 在启动时注入，不直接依赖 bootstrap。
鉴权通过 MCP 路由设置 contextvar，本工具读取 user_id 并传入 gateway 以支持用户 Key 与配额。
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from domains.agent.infrastructure.llm import get_configured_models
from domains.agent.infrastructure.llm.gateway import LLMGateway
from domains.agent.infrastructure.mcp_server.context import get_mcp_user_id
from libs.config import get_llm_config

# 创建 LLM Server 实例
llm_server = FastMCP(
    name="AI Agent LLM Server",
)


@llm_server.tool()
async def llm_create(
    messages: list[dict[str, Any]],
    model: str = "gpt-4",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """调用大语言模型生成文本（非流式）

    Args:
        messages: 消息列表 [{"role": "user", "content": "..."}]
        model: 模型名称（如 gpt-4, claude-3-opus）
        temperature: 温度参数 (0-2)
        max_tokens: 最大生成 token 数

    Returns:
        LLM 生成的文本内容
    """
    config = get_llm_config()
    gateway = LLMGateway(config=config)
    user_id = get_mcp_user_id()

    response = await gateway.chat(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
        user_id=user_id,
    )
    return response.content or ""


@llm_server.tool()
async def llm_list_models() -> dict[str, list[dict[str, str]]]:
    """列出当前系统已配置的大语言模型

    仅返回已配置 API Key 的提供商及其模型，与系统配置一致。

    Returns:
        按提供商分组的模型列表，每项含 id、name
    """
    return get_configured_models(get_llm_config())
