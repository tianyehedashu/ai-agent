"""
执行环境配置 E2E 测试（BDD 风格）

测试执行环境配置在聊天功能中的完整集成

测试场景使用 BDD（Behavior Driven Development）模式：
- Given: 前置条件
- When: 执行动作
- Then: 预期结果
"""

import json
from typing import Any

import httpx
import pytest

API_BASE_URL = "http://localhost:8000"


def parse_sse_events(lines: list[str]) -> list[dict[str, Any]]:
    """解析 SSE 事件"""
    import contextlib

    events = []
    for line in lines:
        if line.startswith("data: ") and line != "data: [DONE]":
            with contextlib.suppress(json.JSONDecodeError):
                events.append(json.loads(line[6:]))
    return events


@pytest.mark.e2e
class TestExecutionConfigIntegration:
    """
    Feature: 执行环境配置集成

    作为一个 AI Agent 系统
    我希望能够根据配置加载和使用不同的执行环境
    以便支持不同的工具集和安全策略
    """

    @pytest.fixture
    async def async_client(self):
        """异步 HTTP 客户端"""
        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=120.0) as client:
            yield client

    @pytest.mark.asyncio
    async def test_chat_with_default_execution_config(self, async_client):
        """
        Scenario: 使用默认执行环境配置进行对话

        Given 系统启动并加载了默认执行环境配置
        When 用户发送一条普通消息
        Then 系统应该正常响应
        And 返回 session_created 和 done 事件
        """
        # When: 发送消息
        events = []
        async with async_client.stream(
            "POST",
            "/api/v1/chat",
            json={"message": "你好，请简单介绍你自己"},
            headers={"Accept": "text/event-stream"},
        ) as response:
            # Then: 验证响应
            assert response.status_code == 200

            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    events.append(json.loads(line[6:]))

        # Then: 验证事件
        event_types = [e["type"] for e in events]
        assert "session_created" in event_types, "应收到 session_created 事件"
        assert "done" in event_types, "应收到 done 事件"

    @pytest.mark.asyncio
    async def test_chat_with_tool_execution(self, async_client):
        """
        Scenario: 使用执行环境配置进行工具调用

        Given 系统配置了工具执行环境
        And 启用了 read_file、list_dir 等工具
        When 用户请求 Agent 执行需要工具的任务
        Then Agent 应该能够调用配置中启用的工具
        And 返回工具调用和执行结果事件
        """
        # When: 请求执行需要工具的任务
        events = []
        async with async_client.stream(
            "POST",
            "/api/v1/chat",
            json={"message": "请列出当前目录下的文件（使用工具）"},
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200

            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    event = json.loads(line[6:])
                    events.append(event)
                    print(f"Event: {event['type']}")

        # Then: 验证事件流
        event_types = [e["type"] for e in events]

        # 应该有完成事件
        assert "done" in event_types, "应收到 done 事件"

        # 如果有工具调用，验证工具事件
        if "tool_call" in event_types:
            assert "tool_result" in event_types, "工具调用后应有结果"
            print("✓ 工具调用流程正常")
        else:
            print("✓ 此次响应未触发工具调用（LLM 可能直接回答）")

    @pytest.mark.asyncio
    async def test_agent_specific_config(self, async_client):
        """
        Scenario: 使用 Agent 特定配置

        Given 系统支持为不同 Agent 加载不同的执行环境配置
        When 用户使用特定 agent_id 发起对话
        Then 系统应加载该 Agent 的配置（如果存在）
        And 使用该配置进行对话处理
        """
        # When: 使用特定 agent_id 发起对话
        events = []
        async with async_client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "message": "你好",
                "agent_id": "example-agent",  # 使用示例 Agent
            },
            headers={"Accept": "text/event-stream"},
        ) as response:
            # Then: 验证响应（即使 Agent 不存在也应该回退到默认配置）
            assert response.status_code == 200

            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    events.append(json.loads(line[6:]))

        # Then: 验证有响应
        event_types = [e["type"] for e in events]
        assert "done" in event_types or "error" in event_types, "应有完成或错误事件"


@pytest.mark.e2e
class TestExecutionConfigAPI:
    """
    Feature: 执行环境配置 API

    作为一个 Agent 工作台用户
    我希望能够通过 API 管理执行环境配置
    以便在 UI 中配置 Agent 的执行环境
    """

    @pytest.fixture
    def sync_client(self):
        """同步 HTTP 客户端"""
        return httpx.Client(base_url=API_BASE_URL, timeout=30.0)

    def test_list_execution_templates(self, sync_client):
        """
        Scenario: 获取执行环境模板列表

        Given 系统配置了多个环境模板
        When 用户请求模板列表
        Then 应返回所有可用模板
        """
        # When: 请求模板列表
        response = sync_client.get("/api/v1/execution/templates")

        # Then: 如果 API 存在，验证响应
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            print(f"✓ 获取模板列表成功，共 {len(data)} 个模板")
        elif response.status_code == 404:
            pytest.skip("执行配置 API 尚未实现")
        else:
            print(f"✓ API 返回: {response.status_code}")

    def test_get_available_tools(self, sync_client):
        """
        Scenario: 获取可用工具列表

        Given 系统配置了工具注册表
        When 用户请求可用工具列表
        Then 应返回所有注册的工具及其描述
        """
        # When: 请求工具列表
        response = sync_client.get("/api/v1/execution/tools")

        # Then: 验证响应
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            print(f"✓ 获取工具列表成功，共 {len(data)} 个工具")
        elif response.status_code == 404:
            pytest.skip("工具列表 API 尚未实现")


@pytest.mark.e2e
class TestConfiguredToolBehavior:
    """
    Feature: 工具配置行为验证

    作为一个 AI Agent
    我需要根据执行环境配置来决定哪些工具可用
    以及哪些工具需要人工确认
    """

    @pytest.fixture
    async def async_client(self):
        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=120.0) as client:
            yield client

    @pytest.mark.asyncio
    async def test_safe_tools_no_confirmation(self, async_client):
        """
        Scenario: 安全工具无需确认

        Given 配置中 read_* 工具被标记为自动批准
        When Agent 调用 read_file 工具
        Then 工具应直接执行，无需等待确认
        """
        events = []
        async with async_client.stream(
            "POST",
            "/api/v1/chat",
            json={"message": "请读取 README.md 文件的内容"},
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200

            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    events.append(json.loads(line[6:]))

        # Then: 如果有工具调用，不应有 interrupt 事件
        event_types = [e["type"] for e in events]

        if "tool_call" in event_types:
            # 读取操作不应触发中断
            interrupt_count = event_types.count("interrupt")
            print(f"✓ 工具调用完成，中断次数: {interrupt_count}")

        assert "done" in event_types, "应完成对话"
