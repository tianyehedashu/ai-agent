"""
MCP Dynamic Tool Factory - 动态工具工厂

根据 tool_type + config 生成可供 FastMCP.add_tool 注册的 async 函数。
仅支持预定义类型，避免任意代码执行。
"""

from collections.abc import Callable
import json
from typing import Any
from uuid import UUID

import httpx

from domains.agent.application.video_task_use_case import VideoTaskUseCase
from domains.agent.domain.mcp.dynamic_tool import DynamicToolType
from domains.agent.infrastructure.mcp_server.context import get_mcp_user_id
from domains.identity.application.permission_context_composer import (
    PermissionContextComposer,
)
from libs.db.database import get_session_context
from libs.iam.permission_context import clear_permission_context


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

    通过 MCP 动态工具调用视频任务用例（走 Gateway），与 Web 端 / llm-server 同一入口。
    需在 MCP 请求上下文内执行（依赖 ``get_mcp_user_id``）。
    """

    async def _amazon_video_submit(
        prompt: str,
        reference_images: list[str] | None = None,
        marketplace: str = "jp",
    ) -> str:
        user_id = get_mcp_user_id()
        if not user_id:
            return json.dumps(
                {"success": False, "error": "MCP 视频任务需要已认证用户（API Key）"},
                ensure_ascii=False,
            )
        try:
            async with get_session_context() as db:
                composer = PermissionContextComposer(db)
                composer.install(await composer.compose_for_user_id(user_id))
                from libs.api.deps import (
                    build_session_use_case,  # pylint: disable=import-outside-toplevel
                )

                use_case = VideoTaskUseCase(db, session_use_case=build_session_use_case(db))
                task = await use_case.create_task(
                    principal_id=str(user_id),
                    session_id=None,
                    prompt_text=prompt,
                    prompt_source="agent_generated",
                    reference_images=reference_images or [],
                    marketplace=marketplace,
                    auto_submit=True,
                )
            return json.dumps(
                {
                    "success": True,
                    "task_id": task["id"],
                    "status": task["status"],
                    "workflow_id": task.get("workflow_id"),
                    "run_id": task.get("run_id"),
                    "message": "视频生成任务已提交到 Gateway",
                },
                ensure_ascii=False,
            )
        except Exception as e:  # pylint: disable=broad-except
            return json.dumps(
                {"success": False, "error": str(e)},
                ensure_ascii=False,
            )
        finally:
            clear_permission_context()

    return _amazon_video_submit


def build_amazon_video_poll_fn(config: dict[str, Any]) -> Callable[..., Any]:
    """构建亚马逊视频轮询函数

    通过 MCP 动态工具查询视频任务状态（只读 DB，后台 task 完成后自动写入终态）。
    需在 MCP 请求上下文内执行（依赖 ``get_mcp_user_id``）。
    """

    async def _amazon_video_poll(task_id: str) -> str:
        user_id = get_mcp_user_id()
        if not user_id:
            return json.dumps(
                {"success": False, "error": "MCP 视频任务需要已认证用户（API Key）"},
                ensure_ascii=False,
            )
        try:
            UUID(task_id)
        except ValueError:
            return json.dumps(
                {"success": False, "error": f"无效的 task_id: {task_id}"},
                ensure_ascii=False,
            )
        try:
            async with get_session_context() as db:
                composer = PermissionContextComposer(db)
                composer.install(await composer.compose_for_user_id(user_id))
                from libs.api.deps import (
                    build_session_use_case,  # pylint: disable=import-outside-toplevel
                )

                use_case = VideoTaskUseCase(db, session_use_case=build_session_use_case(db))
                task = await use_case.poll_task(UUID(task_id), once=True)
            result_data = {
                "success": True,
                "task_id": task["id"],
                "status": task["status"],
                "workflow_id": task.get("workflow_id"),
                "run_id": task.get("run_id"),
            }
            if task["status"] == "completed":
                result_data["video_url"] = task.get("video_url")
                result_data["message"] = "视频生成已完成"
            elif task["status"] == "failed":
                result_data["error_message"] = task.get("error_message")
                result_data["message"] = "视频生成失败"
            else:
                result_data["message"] = "视频正在生成中"
            return json.dumps(result_data, ensure_ascii=False)
        except Exception as e:  # pylint: disable=broad-except
            return json.dumps(
                {"success": False, "error": str(e)},
                ensure_ascii=False,
            )
        finally:
            clear_permission_context()

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
