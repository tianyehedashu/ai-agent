"""
MCP Dynamic Prompt Factory - 动态 Prompt 工厂

根据 template + arguments_schema 生成可供 FastMCP.add_prompt 注册的 Prompt 实例。
模板占位符使用 {{name}}，渲染时用 arguments 中的值替换。
"""

import re
from typing import Any

from mcp.server.fastmcp.prompts.base import Prompt, PromptArgument, UserMessage
from mcp.types import TextContent


def _render_template(template: str, arguments: dict[str, Any]) -> str:
    """将模板中的 {{key}} 替换为 arguments.get(key, '')。"""
    result = template
    for key, value in arguments.items():
        placeholder = "{{" + key + "}}"
        result = result.replace(placeholder, str(value) if value is not None else "")
    # 未提供的占位符保留或替换为空
    result = re.sub(r"\{\{(\w+)\}\}", "", result)
    return result


def build_prompt(
    name: str,
    template: str,
    title: str | None = None,
    description: str | None = None,
    arguments_schema: list[dict[str, Any]] | None = None,
) -> Prompt:
    """根据配置构建 MCP Prompt 实例，供 server.add_prompt 注册。

    arguments_schema 格式: [{"name": "x", "description": "...", "required": true}, ...]
    模板中占位符为 {{name}}。

    Returns:
        Prompt 实例，可直接 add_prompt(prompt)。

    Raises:
        ValueError: 若 arguments_schema 格式不合法。
    """
    args_list = arguments_schema or []
    mcp_args: list[PromptArgument] = []
    for item in args_list:
        if not isinstance(item, dict) or "name" not in item:
            raise ValueError(f"Invalid arguments_schema item: {item}")
        mcp_args.append(
            PromptArgument(
                name=str(item["name"]),
                description=item.get("description"),
                required=item.get("required", True),
            )
        )

    def _fn(**kwargs: Any) -> UserMessage:
        rendered = _render_template(template, kwargs)
        return UserMessage(
            role="user",
            content=TextContent(type="text", text=rendered),
        )

    async def _async_fn(**kwargs: Any) -> UserMessage:
        return _fn(**kwargs)

    return Prompt(
        name=name,
        title=title or name,
        description=description or "",
        arguments=mcp_args if mcp_args else None,
        fn=_async_fn,
        context_kwarg=None,
    )
