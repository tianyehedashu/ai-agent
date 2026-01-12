"""
API v1 Router - 路由汇总
"""

from fastapi import APIRouter

from api.v1 import agent, chat, memory, quality, session, studio, system, tool, user

api_router = APIRouter()

# 认证相关路由
api_router.include_router(user.router, prefix="/auth", tags=["Authentication"])

# Agent 管理
api_router.include_router(agent.router, prefix="/agents", tags=["Agents"])

# 会话管理
api_router.include_router(session.router, prefix="/sessions", tags=["Sessions"])

# 对话接口
api_router.include_router(chat.router, tags=["Chat"])

# 工具管理
api_router.include_router(tool.router, prefix="/tools", tags=["Tools"])

# 记忆管理
api_router.include_router(memory.router, prefix="/memory", tags=["Memory"])

# 工作台 (Studio)
api_router.include_router(studio.router, tags=["Studio"])

# 代码质量
api_router.include_router(quality.router, tags=["Quality"])

# 系统接口
api_router.include_router(system.router, prefix="/system", tags=["System"])
