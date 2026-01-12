"""
测试数据工厂

使用 factory pattern 创建测试数据
"""

from datetime import datetime
from typing import Any


def create_test_user(
    email: str = "test@example.com",
    name: str = "Test User",
    password_hash: str = "hashed_password",
    **kwargs: Any,
) -> dict[str, Any]:
    """创建测试用户数据"""
    return {
        "email": email,
        "name": name,
        "password_hash": password_hash,
        "created_at": datetime.utcnow(),
        **kwargs,
    }


def create_test_agent(
    user_id: str,
    name: str = "Test Agent",
    system_prompt: str = "You are a helpful assistant.",
    model: str = "gpt-4",
    **kwargs: Any,
) -> dict[str, Any]:
    """创建测试 Agent 数据"""
    return {
        "user_id": user_id,
        "name": name,
        "system_prompt": system_prompt,
        "model": model,
        "tools": [],
        "config": {"temperature": 0.7},
        "created_at": datetime.utcnow(),
        **kwargs,
    }


def create_test_session(
    user_id: str,
    agent_id: str,
    status: str = "active",
    **kwargs: Any,
) -> dict[str, Any]:
    """创建测试会话数据"""
    return {
        "user_id": user_id,
        "agent_id": agent_id,
        "status": status,
        "created_at": datetime.utcnow(),
        **kwargs,
    }


def create_test_message(
    session_id: str,
    role: str = "user",
    content: str = "Test message",
    **kwargs: Any,
) -> dict[str, Any]:
    """创建测试消息数据"""
    return {
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": datetime.utcnow(),
        **kwargs,
    }
