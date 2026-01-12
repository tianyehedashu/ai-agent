"""
AI Agent Backend - Main Application

FastAPI 应用入口点
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.router import api_router
from app.config import settings
from db.database import init_db
from db.redis import close_redis, init_redis
from utils.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    # 启动时
    setup_logging()

    # 初始化数据库
    await init_db()

    # 初始化 Redis
    try:
        await init_redis()
    except Exception as e:
        print(f"Warning: Redis not available: {e}")

    yield

    # 关闭时
    await close_redis()


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    description="AI Agent 系统后端 API",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "AI Agent API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}
