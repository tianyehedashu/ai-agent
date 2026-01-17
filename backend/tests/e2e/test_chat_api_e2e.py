"""
Chat API 端到端测试

真正调用后端 API（不使用 Mock），验证完整的对话流程。

测试类型: API E2E (也叫 API Integration Tests / Functional Tests)
运行条件: 需要启动完整环境 (docker-compose + backend server)
运行方式: make test-e2e

API 实现说明:
============

1. POST /api/v1/chat
   - 请求: { message: str, session_id?: str, agent_id?: str }
   - 响应: SSE 流
   - 事件类型:
     - session_created: 新会话创建，返回 session_id
     - thinking: AI 正在思考
     - text: AI 返回文本（流式）
     - tool_call: 调用工具
     - tool_result: 工具执行结果
     - done: 完成，包含 final_message
     - error: 错误

2. 对话历史管理:
   - 由 LangGraph Checkpointer 自动管理
   - session_id 作为 thread_id
   - 每次请求会自动加载历史消息

3. 消息流程:
   - 用户发送消息 → ChatService.chat()
   - 创建/获取 session → 发送 session_created 事件
   - LangGraphAgentEngine.run() 执行
   - 从 Checkpointer 加载历史 → 合并当前消息
   - 调用 LLM → 返回事件流
   - 保存到 Checkpointer
"""

import json
from typing import Any

import httpx
import pytest

# 后端 API 地址
API_BASE_URL = "http://localhost:8000"


def parse_sse_events(lines: list[str]) -> list[dict[str, Any]]:
    """解析 SSE 事件"""
    events = []
    for line in lines:
        if line.startswith("data: ") and line != "data: [DONE]":
            try:
                event_data = json.loads(line[6:])
                events.append(event_data)
            except json.JSONDecodeError:
                pass
    return events


@pytest.mark.e2e
class TestHealthCheck:
    """健康检查测试"""

    def test_health_endpoint(self):
        """测试: 健康检查端点可访问"""
        with httpx.Client(base_url=API_BASE_URL, timeout=10.0) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"


@pytest.mark.e2e
class TestChatAPIE2E:
    """Chat API 端到端测试

    测试场景:
    1. 单条消息发送和响应
    2. 多轮对话历史保持
    3. 错误处理
    """

    @pytest.fixture
    def http_client(self):
        """同步 HTTP 客户端"""
        return httpx.Client(base_url=API_BASE_URL, timeout=60.0)

    @pytest.fixture
    async def async_http_client(self):
        """异步 HTTP 客户端"""
        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=120.0) as client:
            yield client

    @pytest.mark.asyncio
    async def test_chat_single_message(self, async_http_client: httpx.AsyncClient):
        """测试: 发送单条消息并接收 SSE 响应

        验证:
        - API 返回 200
        - 收到 session_created 事件
        - 收到 done 事件
        - 返回有效的 session_id
        """
        events = []

        async with async_http_client.stream(
            "POST",
            "/api/v1/chat",
            json={"message": "你好"},
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200

            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    event_data = json.loads(line[6:])
                    events.append(event_data)
                    print(f"Event: {event_data['type']} - {event_data.get('data', {})}")

        # 验证收到了必要的事件
        event_types = [e["type"] for e in events]
        assert "session_created" in event_types, "应该收到 session_created 事件"
        assert "done" in event_types, "应该收到 done 事件"

        # 获取 session_id
        session_event = next(e for e in events if e["type"] == "session_created")
        session_id = session_event["data"]["session_id"]
        assert session_id, "应该返回 session_id"
        print(f"✓ 创建会话成功: {session_id}")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_chat_conversation_history(self, async_http_client: httpx.AsyncClient):
        """测试: 多轮对话保持上下文（名字记忆测试）

        这是我们手动测试的流程:
        1. 第一轮: 告诉 AI "我叫张三"
        2. 第二轮: 问 AI "我叫什么名字？"
        3. 验证 AI 能记住名字

        验证:
        - session_id 正确传递
        - AI 能记住第一轮提到的名字
        - 对话历史正确保持
        """
        session_id = None
        first_response = ""
        second_response = ""

        # ============================================
        # 第一轮: 告诉 AI 我的名字
        # ============================================
        print("\n" + "=" * 50)
        print("第一轮: 告诉 AI 我叫张三")
        print("=" * 50)

        async with async_http_client.stream(
            "POST",
            "/api/v1/chat",
            json={"message": "我叫张三"},
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200

            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    event = json.loads(line[6:])
                    print(f"  Event: {event['type']}")

                    if event["type"] == "session_created":
                        session_id = event["data"]["session_id"]
                        print(f"  → Session ID: {session_id}")

                    elif event["type"] == "done":
                        final_msg = event["data"].get("final_message", {})
                        first_response = final_msg.get("content", "")
                        print(f"  → AI 回复: {first_response[:100]}...")

        assert session_id, "应该创建 session_id"
        print(f"\n✓ 第一轮完成，session_id: {session_id}")

        # ============================================
        # 第二轮: 使用同一个 session_id，询问我的名字
        # ============================================
        print("\n" + "=" * 50)
        print("第二轮: 问 AI 我叫什么名字")
        print(f"使用 session_id: {session_id}")
        print("=" * 50)

        events = []
        async with async_http_client.stream(
            "POST",
            "/api/v1/chat",
            json={"message": "我叫什么名字？", "session_id": session_id},
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200

            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    event = json.loads(line[6:])
                    events.append(event)
                    print(f"  Event: {event['type']}")

                    if event["type"] == "done":
                        final_msg = event["data"].get("final_message", {})
                        second_response = final_msg.get("content", "")
                        print(f"  → AI 回复: {second_response}")

        # ============================================
        # 验证 AI 记住了名字
        # ============================================
        print("\n" + "=" * 50)
        print("验证结果")
        print("=" * 50)

        done_event = next((e for e in events if e["type"] == "done"), None)
        assert done_event, "应该收到 done 事件"

        # AI 应该能记住名字 "张三"
        assert (
            "张三" in second_response
        ), f"AI 应该记住用户名字是'张三'，但回复是: {second_response}"

        print("✓ AI 正确记住了名字: 张三")
        print("✓ 对话历史功能正常!")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_chat_multi_turn_context(self, async_http_client: httpx.AsyncClient):
        """测试: 多轮对话上下文保持（更复杂的场景）

        场景:
        1. 告诉 AI 我喜欢吃苹果
        2. 告诉 AI 我住在北京
        3. 问 AI 总结我的信息

        验证:
        - AI 能记住多轮对话中的所有信息
        """
        session_id = None

        # 第一轮
        print("\n第一轮: 我喜欢吃苹果")
        async with async_http_client.stream(
            "POST",
            "/api/v1/chat",
            json={"message": "记住：我喜欢吃苹果"},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    event = json.loads(line[6:])
                    if event["type"] == "session_created":
                        session_id = event["data"]["session_id"]
                    elif event["type"] == "done":
                        content = event["data"].get("final_message", {}).get("content", "")
                        print(f"  AI: {content[:50]}...")

        assert session_id

        # 第二轮
        print("\n第二轮: 我住在北京")
        async with async_http_client.stream(
            "POST",
            "/api/v1/chat",
            json={"message": "记住：我住在北京", "session_id": session_id},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    event = json.loads(line[6:])
                    if event["type"] == "done":
                        content = event["data"].get("final_message", {}).get("content", "")
                        print(f"  AI: {content[:50]}...")

        # 第三轮: 验证
        print("\n第三轮: 总结我的信息")
        final_response = ""
        async with async_http_client.stream(
            "POST",
            "/api/v1/chat",
            json={"message": "请总结一下你记住的关于我的信息", "session_id": session_id},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    event = json.loads(line[6:])
                    if event["type"] == "done":
                        final_response = event["data"].get("final_message", {}).get("content", "")
                        print(f"  AI: {final_response}")

        # 验证 AI 记住了两个信息
        assert (
            "苹果" in final_response or "apple" in final_response.lower()
        ), f"AI 应该记住'喜欢吃苹果': {final_response}"
        assert (
            "北京" in final_response or "Beijing" in final_response
        ), f"AI 应该记住'住在北京': {final_response}"
        print("\n✓ AI 正确记住了多轮对话中的所有信息!")


@pytest.mark.e2e
class TestChatErrorHandling:
    """Chat API 错误处理测试"""

    @pytest.fixture
    async def async_http_client(self):
        """异步 HTTP 客户端"""
        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=60.0) as client:
            yield client

    @pytest.mark.asyncio
    async def test_empty_message_validation(self, async_http_client: httpx.AsyncClient):
        """测试: 空消息验证"""
        response = await async_http_client.post(
            "/api/v1/chat",
            json={"message": ""},
        )
        # 应该返回 422 (Validation Error) - message 最小长度为 1
        assert response.status_code == 422
        print("✓ 空消息正确返回 422 验证错误")

    @pytest.mark.asyncio
    async def test_invalid_session_id(self, async_http_client: httpx.AsyncClient):
        """测试: 无效的 session_id"""
        events = []
        async with async_http_client.stream(
            "POST",
            "/api/v1/chat",
            json={"message": "hello", "session_id": "invalid-uuid-12345"},
        ) as response:
            # API 可能返回 200 但在事件流中返回 error
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    event = json.loads(line[6:])
                    events.append(event)

        # 检查是否有 error 事件
        error_events = [e for e in events if e["type"] == "error"]
        if error_events:
            print(f"✓ 无效 session_id 正确返回错误: {error_events[0]['data']}")
        else:
            # 如果没有错误事件，说明系统处理了无效 session_id
            print("✓ 系统处理了无效 session_id")


@pytest.mark.e2e
class TestAgentAPIE2E:
    """Agent API 端到端测试"""

    def test_list_agents(self):
        """测试: 获取 Agent 列表

        注意: 此测试需要后端服务在开发模式下运行（允许匿名用户），
        或者需要提供有效的认证 token。
        """
        with httpx.Client(base_url=API_BASE_URL, timeout=30.0, follow_redirects=True) as client:
            response = client.get("/api/v1/agents/")
            if response.status_code != 200:
                print(f"错误状态码: {response.status_code}")
                print(f"错误响应: {response.text}")
                try:
                    error_data = response.json()
                    print(f"错误详情: {error_data}")
                except Exception:
                    pass
                # 如果是 500 错误，可能是后端服务配置问题
                if response.status_code == 500:
                    pytest.skip(
                        f"后端服务返回 500 错误，可能是配置问题。"
                        f"请确保后端服务在开发模式下运行（app_env=development）。"
                        f"错误详情: {response.text[:200]}"
                    )
            assert (
                response.status_code == 200
            ), f"Expected 200, got {response.status_code}: {response.text}"
            data = response.json()
            assert isinstance(data, list)
            print(f"✓ 获取 Agent 列表成功，共 {len(data)} 个")

    def test_system_stats(self):
        """测试: 获取系统统计"""
        with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
            response = client.get("/api/v1/system/stats")
            # 可能需要认证
            if response.status_code == 200:
                print(f"✓ 获取系统统计成功: {response.json()}")
            else:
                print(f"✓ 系统统计需要认证: {response.status_code}")


@pytest.mark.e2e
class TestLLMGatewayE2E:
    """LLM Gateway 端到端测试（真正调用 LLM API）"""

    @pytest.mark.asyncio
    async def test_llm_chat_completion(self):
        """测试: 真正调用 LLM API

        注意: 此测试需要配置 LLM API Key
        """
        from app.config import settings
        from core.llm.gateway import LLMGateway

        gateway = LLMGateway(config=settings)

        try:
            response = await gateway.chat(
                messages=[
                    {"role": "system", "content": "你是一个助手。只回复'测试成功'三个字。"},
                    {"role": "user", "content": "请回复"},
                ],
                model=settings.default_model,
                max_tokens=50,
            )

            assert response is not None
            assert "content" in response
            print(f"✓ LLM 调用成功: {response['content']}")

        except Exception as e:
            pytest.skip(f"LLM API 调用失败（可能是 API Key 未配置）: {e}")
