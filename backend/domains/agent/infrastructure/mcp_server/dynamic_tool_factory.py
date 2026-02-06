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


def build_amazon_video_submit_fn(config: dict[str, Any]) -> Callable[..., Any]:
    """构建亚马逊视频提交函数

    通过 MCP 动态工具调用视频提交服务。
    """

    async def _amazon_video_submit(
        prompt: str,
        reference_images: list[str] | None = None,
        marketplace: str = "jp",
    ) -> str:
        import json

        from domains.agent.infrastructure.video_api.client import VideoAPIClient, VideoAPIError

        try:
            client = VideoAPIClient()
            workflow_id, run_id = await client.submit(
                prompt=prompt,
                reference_images=reference_images or [],
                marketplace=marketplace,
            )
            return json.dumps(
                {
                    "success": True,
                    "workflow_id": workflow_id,
                    "run_id": run_id,
                    "message": "视频生成任务已提交",
                },
                ensure_ascii=False,
            )
        except VideoAPIError as e:
            return json.dumps(
                {
                    "success": False,
                    "error": e.message,
                    "code": e.code,
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                },
                ensure_ascii=False,
            )

    return _amazon_video_submit


def build_amazon_video_poll_fn(config: dict[str, Any]) -> Callable[..., Any]:
    """构建亚马逊视频轮询函数

    通过 MCP 动态工具调用视频轮询服务。
    """

    async def _amazon_video_poll(
        workflow_id: str,
        run_id: str,
    ) -> str:
        import json

        from domains.agent.infrastructure.video_api.client import VideoAPIClient, VideoAPIError

        try:
            client = VideoAPIClient()
            status, result = await client.poll(
                workflow_id=workflow_id,
                run_id=run_id,
            )

            video_url = client.extract_video_url(result) if status == 2 else None

            return json.dumps(
                {
                    "success": True,
                    "status": status,
                    "status_text": {
                        0: "未知",
                        1: "运行中",
                        2: "已完成",
                        3: "失败",
                        4: "已取消",
                        5: "已终止",
                        6: "已重新创建",
                        7: "超时",
                    }.get(status, f"状态码 {status}"),
                    "video_url": video_url,
                    "result": result if status == 2 else None,
                },
                ensure_ascii=False,
            )
        except VideoAPIError as e:
            return json.dumps(
                {
                    "success": False,
                    "error": e.message,
                    "code": e.code,
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                },
                ensure_ascii=False,
            )

    return _amazon_video_poll


def build_tool_fn(tool_type: str, config: dict[str, Any]) -> Callable[..., Any]:
    """根据 tool_type 与 config 构建可供 add_tool 注册的 async 函数。

    Raises:
        ValueError: 未知 tool_type 或 config 不合法
    """
    if tool_type == DynamicToolType.HTTP_CALL.value:
        if not config.get("url"):
            raise ValueError("http_call requires config.url")
        return build_http_call_fn(config)

    if tool_type == DynamicToolType.AMAZON_VIDEO_SUBMIT.value:
        return build_amazon_video_submit_fn(config)

    if tool_type == DynamicToolType.AMAZON_VIDEO_POLL.value:
        return build_amazon_video_poll_fn(config)

    raise ValueError(f"Unknown dynamic tool type: {tool_type}")
