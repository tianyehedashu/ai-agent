"""
API Dependencies - API 依赖注入

提供 FastAPI 路由的依赖注入
"""

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.agent import AgentService
from services.chat import ChatService
from services.checkpoint import CheckpointService
from services.memory import MemoryService
from services.session import SessionService
from services.stats import StatsService
from services.user import UserService

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    """
    获取当前用户

    在开发模式下返回匿名用户
    """
    if not credentials:
        # 开发模式：返回匿名用户
        return {
            "id": "anonymous",
            "email": "anonymous@local",
            "name": "Anonymous User",
        }

    token = credentials.credentials
    user_service = UserService()

    user = await user_service.get_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
    }


async def require_auth(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """要求必须认证"""
    if current_user.get("id") == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return current_user


def get_user_service() -> UserService:
    """获取用户服务"""
    return UserService()


def get_agent_service() -> AgentService:
    """获取 Agent 服务"""
    return AgentService()


def get_session_service() -> SessionService:
    """获取会话服务"""
    return SessionService()


def get_chat_service() -> ChatService:
    """获取对话服务"""
    return ChatService()


def get_checkpoint_service() -> CheckpointService:
    """获取检查点服务"""
    return CheckpointService()


def get_memory_service() -> MemoryService:
    """获取记忆服务"""
    return MemoryService()


def get_stats_service() -> StatsService:
    """获取统计服务"""
    return StatsService()
