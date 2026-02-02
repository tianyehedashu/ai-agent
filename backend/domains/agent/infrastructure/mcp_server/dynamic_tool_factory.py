"""
MCP Dynamic Tool Factory - 动态工具工厂

根据 tool_type + config 生成可供 FastMCP.add_tool 注册的 async 函数。
仅支持预定义类型，避免任意代码执行。
"""

from collections.abc import Callable
from typing import Any

from domains.agent.domain.mcp.dynamic_tool import DynamicToolType


def build_http_call_fn(config: dict[str, Any]) -> Callable[..., Any]:
    """根据 config 构建 http_call 异步函数。

    config 期望: url (str), method (str, 默认 GET), headers (dict 可选), body (dict 可选)。
    返回的 async 函数签名可无参或接受可选 body/headers 覆盖，返回响应文本。
    """
    url = config.get("url") or ""
    method = (config.get("method") or "GET").upper()
    headers = dict(config.get("headers") or {})
    default_body = config.get("body")

    async def _http_call(
        body: dict[str, Any] | None = None,
        headers_override: dict[str, str] | None = None,
    ) -> str:
        import httpx

        req_headers = dict(headers)
        if headers_override:
            req_headers.update(headers_override)
        payload = body if body is not None else default_body
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(url, headers=req_headers or None)
            elif method == "POST":
                resp = await client.post(url, json=payload, headers=req_headers or None)
            elif method == "PUT":
                resp = await client.put(url, json=payload, headers=req_headers or None)
            elif method == "PATCH":
                resp = await client.patch(url, json=payload, headers=req_headers or None)
            elif method == "DELETE":
                resp = await client.delete(url, headers=req_headers or None)
            else:
                resp = await client.request(method, url, json=payload, headers=req_headers or None)
            resp.raise_for_status()
            return resp.text

    return _http_call


def build_tool_fn(tool_type: str, config: dict[str, Any]) -> Callable[..., Any]:
    """根据 tool_type 与 config 构建可供 add_tool 注册的 async 函数。

    Raises:
        ValueError: 未知 tool_type 或 config 不合法
    """
    if tool_type == DynamicToolType.HTTP_CALL.value:
        if not config.get("url"):
            raise ValueError("http_call requires config.url")
        return build_http_call_fn(config)
    raise ValueError(f"Unknown dynamic tool type: {tool_type}")
