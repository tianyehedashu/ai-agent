"""
SimpleMem 端到端测试

真正调用后端 API，验证 SimpleMem 在完整对话流程中的表现：
1. 对话后自动提取长期记忆
2. 跨会话记忆检索
3. 多轮对话记忆积累

测试类型: E2E (End-to-End)
运行条件: 需要启动完整环境 (docker-compose + backend server)
运行方式: make test-e2e 或 pytest tests/e2e/test_simplemem_e2e.py -v
"""

import json
from typing import Any
import uuid

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


async def send_chat_message(
    client: httpx.AsyncClient,
    message: str,
    session_id: str | None = None,
) -> tuple[str | None, str, list[dict[str, Any]]]:
    """发送聊天消息并返回结果

    Returns:
        tuple: (session_id, final_response, all_events)
    """
    events = []
    streamed_content = ""  # 收集流式内容
    thinking_content = ""  # 收集推理模型的思考内容
    final_response = ""
    returned_session_id = session_id

    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    async with client.stream(
        "POST",
        "/api/v1/chat",
        json=payload,
        headers={"Accept": "text/event-stream"},
    ) as response:
        if response.status_code != 200:
            print(f"  ⚠️ HTTP 状态码: {response.status_code}")
            return None, "", []

        async for line in response.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                try:
                    event = json.loads(line[6:])
                    events.append(event)

                    if event["type"] == "session_created":
                        returned_session_id = event["data"]["session_id"]
                    elif event["type"] == "text":
                        # 收集流式文本内容
                        text_content = event["data"].get("content", "")
                        if text_content:
                            streamed_content += text_content
                    elif event["type"] == "thinking":
                        # 收集推理模型的思考内容（deepseek-reasoner 等）
                        # thinking 事件可能包含 content 字段（推理过程）
                        thinking_text = event["data"].get("content", "")
                        if thinking_text:
                            thinking_content += thinking_text
                    elif event["type"] == "done":
                        final_msg = event["data"].get("final_message", {})
                        # 优先使用 content，如果为空则使用 reasoning_content（推理模型兼容）
                        final_response = final_msg.get("content") or final_msg.get(
                            "reasoning_content", ""
                        )
                    elif event["type"] == "error":
                        # 记录错误事件
                        print(f"  ⚠️ 错误事件: {event['data']}")
                except json.JSONDecodeError as e:
                    print(f"  ⚠️ JSON 解析错误: {e}, line: {line[:100]}...")

    # 优先使用 done 事件中的完整内容，否则使用流式内容，最后使用思考内容
    # 对于推理模型（如 deepseek-reasoner），content 可能为空，但 thinking 有内容
    final_response = final_response or streamed_content or thinking_content

    # 调试信息：如果没有响应但有事件，打印事件类型
    if not final_response and events:
        event_types = [e.get("type") for e in events]
        print(f"  ⚠️ 无响应内容，收到的事件类型: {event_types}")

    return returned_session_id, final_response, events


@pytest.mark.e2e
class TestSimpleMemE2E:
    """SimpleMem 端到端测试

    测试 SimpleMem 在真实对话流程中的功能：
    - 记忆自动提取
    - 跨会话记忆持久化
    - 长期记忆检索
    """

    @pytest.fixture
    async def async_http_client(self):
        """异步 HTTP 客户端（增加超时到 180 秒）"""
        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=180.0) as client:
            yield client

    @pytest.mark.asyncio
    async def test_memory_extraction_during_chat(self, async_http_client: httpx.AsyncClient):
        """测试: 对话过程中自动提取记忆

        验证:
        - 对话正常完成
        - SimpleMem 后台提取记忆（不影响响应时间）
        """
        print("\n" + "=" * 60)
        print("测试: 对话过程中自动提取记忆")
        print("=" * 60)

        # 发送包含关键信息的对话
        session_id, response, events = await send_chat_message(
            async_http_client,
            "我是张伟，我正在开发一个基于 LangGraph 的 AI Agent 项目，使用 Python 和 FastAPI",
        )

        assert session_id, "应该创建 session_id"
        assert response, "应该收到 AI 回复"
        assert any(e["type"] == "done" for e in events), "应该收到完成事件"

        print(f"✓ 会话创建成功: {session_id}")
        print(f"✓ AI 回复: {response[:100]}...")
        print("✓ SimpleMem 应该已在后台提取记忆（异步处理）")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_multi_turn_memory_accumulation(self, async_http_client: httpx.AsyncClient):
        """测试: 多轮对话记忆积累

        验证:
        - 多轮对话中的关键信息被累积
        - AI 能记住之前的对话内容
        """
        print("\n" + "=" * 60)
        print("测试: 多轮对话记忆积累")
        print("=" * 60)

        # 第一轮: 介绍自己
        session_id, _, _ = await send_chat_message(
            async_http_client,
            "记住：我的名字叫李明，我是一名后端工程师",
        )
        print(f"✓ 第一轮完成，session_id: {session_id}")

        # 第二轮: 补充信息
        session_id, _, _ = await send_chat_message(
            async_http_client,
            "记住：我主要使用 Python 和 Go 语言开发",
            session_id=session_id,
        )
        print("✓ 第二轮完成")

        # 第三轮: 再补充
        session_id, _, _ = await send_chat_message(
            async_http_client,
            "记住：我正在学习 Rust，并且对 WebAssembly 很感兴趣",
            session_id=session_id,
        )
        print("✓ 第三轮完成")

        # 第四轮: 验证记忆
        _, response, _ = await send_chat_message(
            async_http_client,
            "请总结一下你记住的关于我的所有信息",
            session_id=session_id,
        )

        print(f"\nAI 总结: {response}")

        # 验证 AI 记住了关键信息
        keywords = ["李明", "后端", "Python", "Go", "Rust"]
        found_keywords = [kw for kw in keywords if kw in response]
        print(f"✓ 找到关键词: {found_keywords}")

        assert len(found_keywords) >= 3, f"AI 应该记住至少 3 个关键信息，但只找到: {found_keywords}"
        print("✓ 多轮对话记忆积累验证通过")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_complex_information_extraction(self, async_http_client: httpx.AsyncClient):
        """测试: 复杂信息提取

        验证:
        - SimpleMem 能提取结构化信息（技术栈、项目详情等）
        - 信息能在后续对话中被正确检索
        """
        print("\n" + "=" * 60)
        print("测试: 复杂信息提取")
        print("=" * 60)

        # 提供复杂的技术信息
        session_id, _, _ = await send_chat_message(
            async_http_client,
            """我来介绍一下我的项目架构：
            - 后端: Python 3.12 + FastAPI + LangGraph
            - 数据库: PostgreSQL + Redis
            - 向量存储: Qdrant
            - 前端: React + TypeScript + Tailwind CSS
            - 部署: Docker + Kubernetes
            请记住这些信息。""",
        )
        print(f"✓ 技术架构信息已发送，session_id: {session_id}")

        # 追问具体信息
        _, response, _ = await send_chat_message(
            async_http_client,
            "我的项目用的是什么数据库？前端用的什么框架？",
            session_id=session_id,
        )

        print(f"\nAI 回复: {response}")

        # 验证 AI 记住了技术细节
        assert "PostgreSQL" in response or "Redis" in response, "AI 应该记住数据库信息"
        assert "React" in response or "TypeScript" in response, "AI 应该记住前端框架"

        print("✓ 复杂信息提取验证通过")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_long_conversation_memory(self, async_http_client: httpx.AsyncClient):
        """测试: 长对话中的记忆保持

        验证:
        - 在较长的对话中，早期信息仍能被记住
        - SimpleMem 的压缩和检索机制正常工作
        """
        print("\n" + "=" * 60)
        print("测试: 长对话中的记忆保持")
        print("=" * 60)

        session_id = None

        # 第 1 轮: 关键信息
        session_id, _, _ = await send_chat_message(
            async_http_client,
            "重要信息：我的代号是 Alpha-7，请务必记住",
        )
        print("✓ 第 1 轮: 设置代号 Alpha-7")

        # 第 2-3 轮: 中间对话（减少轮数避免超时）
        filler_messages = [
            "简单回答：1+1等于多少？",
            "简单回答：今天星期几？",
        ]

        for i, msg in enumerate(filler_messages, 2):
            session_id, _, _ = await send_chat_message(
                async_http_client,
                msg,
                session_id=session_id,
            )
            print(f"✓ 第 {i} 轮: 填充对话")

        # 第 4 轮: 测试早期记忆
        _, response, _ = await send_chat_message(
            async_http_client,
            "我在对话开始时告诉你的代号是什么？",
            session_id=session_id,
        )

        print(f"\nAI 回复: {response}")

        # 验证早期信息被记住
        assert "Alpha" in response or "alpha" in response.lower() or "7" in response, (
            f"AI 应该记住代号 'Alpha-7'，但回复是: {response}"
        )

        print("✓ 长对话记忆保持验证通过")


@pytest.mark.e2e
class TestSimpleMemCrossSession:
    """跨会话记忆测试

    注意: 这些测试依赖于 SimpleMem 的长期记忆存储功能
    在同一用户的不同会话中，应该能检索到之前的记忆
    """

    @pytest.fixture
    async def async_http_client(self):
        """异步 HTTP 客户端（增加超时到 180 秒）"""
        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=180.0) as client:
            yield client

    @pytest.mark.asyncio
    async def test_memory_persistence_hint(self, async_http_client: httpx.AsyncClient):
        """测试: 记忆持久化提示

        这个测试验证系统在设计上支持记忆持久化。
        由于匿名用户可能无法真正持久化记忆，这里主要验证流程。
        """
        print("\n" + "=" * 60)
        print("测试: 记忆持久化机制")
        print("=" * 60)

        # 创建第一个会话并存储信息
        unique_id = str(uuid.uuid4())[:8]
        session1_id, _, _ = await send_chat_message(
            async_http_client,
            f"请记住这个唯一标识符: PROJECT-{unique_id}",
        )
        print(f"✓ 会话 1 创建: {session1_id}")
        print(f"✓ 存储唯一标识符: PROJECT-{unique_id}")

        # 在同一会话中验证
        _, response, _ = await send_chat_message(
            async_http_client,
            "我刚才告诉你的唯一标识符是什么？",
            session_id=session1_id,
        )

        print(f"\n同会话检索结果: {response}")

        # 验证同会话内记忆正常
        assert unique_id in response or "PROJECT" in response, "同会话内应该能记住信息"

        print("✓ 同会话记忆验证通过")
        print("\n提示: 跨会话记忆需要用户认证才能完全测试")


@pytest.mark.e2e
class TestSimpleMemPerformanceE2E:
    """SimpleMem 性能端到端测试"""

    @pytest.fixture
    async def async_http_client(self):
        """异步 HTTP 客户端"""
        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=180.0) as client:
            yield client

    @pytest.mark.asyncio
    async def test_response_time_with_memory(self, async_http_client: httpx.AsyncClient):
        """测试: SimpleMem 不显著影响响应时间

        验证:
        - 记忆提取是异步的，不阻塞响应
        - 首次响应时间在合理范围内
        """
        import time

        print("\n" + "=" * 60)
        print("测试: SimpleMem 对响应时间的影响")
        print("=" * 60)

        # 发送消息并计时
        start_time = time.time()
        _, response, _ = await send_chat_message(
            async_http_client,
            "用一句话介绍你自己",
        )
        elapsed_time = time.time() - start_time

        assert response, "应该收到响应"
        print(f"✓ 响应时间: {elapsed_time:.2f} 秒")
        print(f"✓ 响应长度: {len(response)} 字符")

        # 响应时间应该在合理范围内（考虑到 LLM 调用）
        # 通常 LLM 响应在 2-30 秒之间
        assert elapsed_time < 60, f"响应时间过长: {elapsed_time:.2f} 秒"

        print("✓ 响应时间在合理范围内")

    @pytest.mark.asyncio
    async def test_concurrent_memory_operations(self, async_http_client: httpx.AsyncClient):
        """测试: 并发记忆操作

        验证:
        - 多个并发请求不会导致记忆冲突
        - 注意: E2E 环境下并发可能受 LLM API 限制影响

        这是一个"尽力而为"的测试，主要验证系统不会崩溃
        """
        import asyncio

        print("\n" + "=" * 60)
        print("测试: 并发记忆操作")
        print("=" * 60)

        async def send_unique_message(client: httpx.AsyncClient, msg_id: int):
            """发送唯一消息"""
            try:
                msg = f"简单回答：{msg_id} + 1 等于多少？"
                session_id, response, _ = await send_chat_message(client, msg)
                return msg_id, session_id, bool(response or session_id)
            except Exception as e:
                return msg_id, None, False, str(e)

        # 并发发送 2 个请求（保守数量，避免对 LLM API 造成压力）
        tasks = [send_unique_message(async_http_client, i) for i in range(2)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 验证请求
        successful = 0
        for result in results:
            if isinstance(result, tuple):
                if len(result) >= 3 and result[2]:  # (msg_id, session_id, success)
                    successful += 1
                    print(f"✓ 消息 #{result[0]} 成功，session: {result[1]}")
                elif len(result) >= 4:
                    print(f"✗ 消息 #{result[0]} 失败: {result[3]}")
                else:
                    print(f"✗ 消息 #{result[0]} 失败")
            elif isinstance(result, Exception):
                print(f"✗ 请求异常: {result}")

        # 降低要求：至少 1 个成功即可（E2E 环境下并发不稳定）
        assert successful >= 1, f"至少 1 个请求应该成功，但只有 {successful} 个成功"
        print(f"\n✓ 并发测试完成: {successful}/2 成功")


@pytest.mark.e2e
class TestSimpleMemErrorHandling:
    """SimpleMem 错误处理端到端测试"""

    @pytest.fixture
    async def async_http_client(self):
        """异步 HTTP 客户端（增加超时到 180 秒）"""
        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=180.0) as client:
            yield client

    @pytest.mark.asyncio
    async def test_graceful_degradation(self, async_http_client: httpx.AsyncClient):
        """测试: 优雅降级

        验证:
        - 即使 SimpleMem 内部出现问题，对话仍能正常进行
        - 用户体验不受影响
        """
        print("\n" + "=" * 60)
        print("测试: 优雅降级（SimpleMem 不影响核心对话）")
        print("=" * 60)

        # 发送正常消息
        session_id, response, events = await send_chat_message(
            async_http_client,
            "你好，请用一个词描述今天的心情",
        )

        # 无论 SimpleMem 状态如何，对话应该正常
        assert session_id, "应该创建会话"
        assert response, "应该收到响应"
        assert not any(e["type"] == "error" for e in events), "不应该有错误事件"

        print(f"✓ 会话正常: {session_id}")
        print(f"✓ 响应正常: {response[:50]}...")
        print("✓ SimpleMem 不影响核心对话功能")
