"""
LLM Server - 使用 FastMCP 实现

提供 LLM 调用能力作为 MCP 工具。配置通过 libs.config.get_llm_config() 获取，
由 bootstrap 在启动时注入，不直接依赖 bootstrap。
鉴权通过 MCP 路由设置 contextvar，本工具读取 user_id 并传入 gateway 以支持用户 Key 与配额。

同时提供视频生成任务工具（video_create_task / video_poll_task），封装后端视频任务 API，
供 MCP 客户端创建与查询视频生成任务。
"""

import json
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from domains.agent.application.video_task_use_case import VideoTaskUseCase
from domains.agent.infrastructure.llm import get_configured_models
from domains.agent.infrastructure.llm.gateway import LLMGateway
from domains.agent.infrastructure.mcp_server.context import (
    get_mcp_user_id,
    get_mcp_vendor_creator_id,
)
from libs.config import get_llm_config
from libs.db.database import get_session_context
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)

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


@llm_server.tool()
async def video_create_task(
    prompt: str,
    reference_images: list[str] | None = None,
    marketplace: str = "jp",
    model: str = "openai::sora1.0",
    duration: int = 5,
    auto_submit: bool = True,
) -> str:
    """创建视频生成任务（封装后端视频任务 API）

    使用当前 MCP 认证用户创建一条视频任务，可选自动提交到厂商。与 Web 端「视频任务」页面同一套后端接口。

    Args:
        prompt: 视频生成提示词（必填）
        reference_images: 参考图片 URL 列表，可选
        marketplace: 目标站点 jp/us/de/uk/fr/it/es，默认 jp
        model: 模型 openai::sora1.0 或 openai::sora2.0，默认 sora1.0
        duration: 时长（秒），sora1 支持 5/10/15/20，sora2 支持 5/10/15，默认 5
        auto_submit: 是否创建后自动提交到厂商，默认 True

    Returns:
        JSON 字符串，含 id、status、workflow_id、run_id、error 等；失败时含 success=false 与 error
    """
    user_id = get_mcp_user_id()
    if not user_id:
        return json.dumps(
            {"success": False, "error": "MCP 视频任务需要已认证用户（API Key）"},
            ensure_ascii=False,
        )

    set_permission_context(PermissionContext(user_id=user_id, anonymous_user_id=None))
    try:
        async with get_session_context() as db:
            vendor_creator_id = get_mcp_vendor_creator_id()
            use_case = VideoTaskUseCase(db)
            task = await use_case.create_task(
                user_id=user_id,
                anonymous_user_id=None,
                session_id=None,
                prompt_text=prompt,
                prompt_source="agent_generated",
                reference_images=reference_images or [],
                marketplace=marketplace,
                model=model,
                duration=duration,
                auto_submit=auto_submit,
                vendor_creator_id=vendor_creator_id,
            )
        return json.dumps(
            {
                "success": True,
                "id": task["id"],
                "status": task["status"],
                "workflow_id": task.get("workflow_id"),
                "run_id": task.get("run_id"),
                "message": "视频任务已创建" + ("并已提交到厂商" if auto_submit else ""),
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


@llm_server.tool()
async def video_poll_task(task_id: str) -> str:
    """轮询视频任务状态（封装后端视频任务 API）

    根据任务 ID 查询最新状态与结果，会向厂商拉取一次并更新库。与 Web 端轮询为同一接口。

    Args:
        task_id: 视频任务 UUID 字符串（由 video_create_task 返回的 id）

    Returns:
        JSON 字符串，含 status、video_url、error_message、result 等；失败时含 success=false 与 error
    """
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

    set_permission_context(PermissionContext(user_id=user_id, anonymous_user_id=None))
    try:
        async with get_session_context() as db:
            use_case = VideoTaskUseCase(db)
            task = await use_case.poll_task(UUID(task_id), once=True)
        return json.dumps(
            {
                "success": True,
                "id": task["id"],
                "status": task["status"],
                "workflow_id": task.get("workflow_id"),
                "run_id": task.get("run_id"),
                "video_url": task.get("video_url"),
                "error_message": task.get("error_message"),
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
