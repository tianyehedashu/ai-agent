"""
Evaluation Router - 评估路由

提供评估相关API 端点
"""

from fastapi import APIRouter

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


@router.get("/benchmarks")
async def list_benchmarks() -> dict:
    """获取可用的基准测试列""
    return {
        "benchmarks": [
            {
                "id": "gaia",
                "name": "GAIA Benchmark",
                "description": "General AI Assistant benchmark",
            },
        ]
    }


@router.get("/health")
async def health_check() -> dict:
    """评估服务健康检""
    return {"status": "healthy", "service": "evaluation"}
