"""
Celery Tasks - 异步任务定义
"""

import asyncio
from datetime import datetime, timedelta
import json
from typing import Any

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import delete, select

from app.config import settings
from core.llm.gateway import LLMGateway
from core.memory.extractor import MemoryExtractor
from core.memory.langgraph_store import LongTermMemoryStore
from core.quality.fixer import CodeFixer
from core.quality.validator import CodeValidator
from core.sandbox.executor import DockerExecutor
from db.database import get_db_session
from db.redis import get_redis
from db.vector import get_vector_store
from models.session import Session
from services.stats import StatsService
from workers.celery_app import BaseTask

logger = get_task_logger(__name__)


def run_async(coro):
    """在同步环境中运行异步代码"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ============================================
# Memory Tasks - 记忆处理任务
# ============================================


@shared_task(
    base=BaseTask,
    bind=True,
    name="workers.tasks.process_memory_extraction",
    queue="memory",
)
def process_memory_extraction(
    self,
    session_id: str,
    content: str,
    user_id: str,
) -> dict[str, Any]:
    """
    处理记忆提取任务

    从对话内容中提取关键信息存储为长期记忆
    """
    logger.info("Processing memory extraction for session %s", session_id)

    async def _process():
        vector_store = get_vector_store()
        llm = LLMGateway(config=settings)

        # 使用新的 LongTermMemoryStore
        memory_store = LongTermMemoryStore(
            llm_gateway=llm,
            vector_store=vector_store,
        )
        await memory_store.setup()

        # 使用 MemoryExtractor 提取记忆
        extractor = MemoryExtractor(llm_gateway=llm)

        # 使用对话格式
        conversation = [{"role": "user", "content": content}]

        # 提取并存储记忆（使用新接口）
        memory_ids = await extractor.extract_and_store(
            memory_store=memory_store,
            user_id=user_id,
            conversation=conversation,
            session_id=session_id,
        )

        return {
            "session_id": session_id,
            "memories_extracted": len(memory_ids),
            "memory_ids": memory_ids,
        }

    return run_async(_process())


@shared_task(
    base=BaseTask,
    bind=True,
    name="workers.tasks.generate_embeddings",
    queue="embeddings",
)
def generate_embeddings(
    self,
    texts: list[str],
    model: str | None = None,
) -> list[list[float]]:
    """
    生成文本嵌入向量

    Args:
        texts: 要生成嵌入的文本列表
        model: 嵌入模型，默认使用配置中的 embedding_model
    """
    # 使用配置中的默认模型
    if model is None:
        model = settings.embedding_model
    logger.info("Generating embeddings for %d texts", len(texts))

    async def _generate():
        llm = LLMGateway(config=settings)
        embeddings = await llm.embed_batch(texts, model=model)
        return embeddings

    return run_async(_generate())


# ============================================
# Sandbox Tasks - 沙箱执行任务
# ============================================


@shared_task(
    base=BaseTask,
    bind=True,
    name="workers.tasks.execute_code_in_sandbox",
    queue="sandbox",
    soft_time_limit=120,
    time_limit=180,
)
def execute_code_in_sandbox(
    self,
    code: str,
    language: str = "python",
    timeout: int = 60,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    在 Docker 沙箱中执行代码
    """
    logger.info("Executing %s code in sandbox", language)

    async def _execute():
        executor = DockerExecutor()
        result = await executor.execute(
            code=code,
            language=language,
            timeout=timeout,
        )

        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "execution_time": result.execution_time,
            "session_id": session_id,
        }

    return run_async(_execute())


# ============================================
# Quality Tasks - 代码质量任务
# ============================================


@shared_task(
    base=BaseTask,
    bind=True,
    name="workers.tasks.validate_code_quality",
    queue="quality",
)
def validate_code_quality(
    self,
    code: str,
    filename: str = "code.py",
    check_types: list[str] | None = None,
) -> dict[str, Any]:
    """
    验证代码质量

    包括语法检查、类型检查、Lint 检查、架构检查
    """
    logger.info("Validating code quality for %s", filename)

    async def _validate():
        validator = CodeValidator()
        result = await validator.validate(
            code=code,
            file_path=filename,
            check_types=check_types,
        )

        return {
            "is_valid": result.is_valid,
            "errors": [e.dict() for e in result.errors],
            "warnings": [w.dict() for w in result.warnings],
            "suggestions": [s.dict() for s in result.suggestions],
            "score": result.quality_score,
        }

    return run_async(_validate())


@shared_task(
    base=BaseTask,
    bind=True,
    name="workers.tasks.auto_fix_code",
    queue="quality",
)
def auto_fix_code(
    self,
    code: str,
    errors: list[dict],
    max_attempts: int = 3,
) -> dict[str, Any]:
    """
    自动修复代码错误
    """
    logger.info("Auto-fixing code with %d errors", len(errors))

    async def _fix():
        llm = LLMGateway(config=settings)
        fixer = CodeFixer(llm=llm, max_attempts=max_attempts)
        fixed_code, success = await fixer.fix(code=code)

        return {
            "success": success,
            "fixed_code": fixed_code,
            "fixes_applied": [],  # Fixer doesn't track individual fixes
            "remaining_errors": [] if success else errors,
        }

    return run_async(_fix())


# ============================================
# Maintenance Tasks - 维护任务
# ============================================


@shared_task(
    base=BaseTask,
    bind=True,
    name="workers.tasks.cleanup_expired_checkpoints",
    queue="maintenance",
)
def cleanup_expired_checkpoints(
    self,
    max_age_days: int = 7,
) -> dict[str, Any]:
    """
    清理过期的检查点
    """
    logger.info("Cleaning up checkpoints older than %d days", max_age_days)

    async def _cleanup():
        redis = await get_redis()
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)

        # 扫描并删除过期的检查点
        deleted_count = 0
        cursor = 0

        while True:
            cursor, keys = await redis.scan(
                cursor=cursor,
                match="checkpoint:*",
                count=100,
            )

            for key in keys:
                checkpoint_data = await redis.get(key)
                if checkpoint_data:
                    checkpoint = json.loads(checkpoint_data)
                    created_at = datetime.fromisoformat(checkpoint.get("created_at", ""))
                    if created_at < cutoff:
                        await redis.delete(key)
                        deleted_count += 1

            if cursor == 0:
                break

        return {
            "deleted_count": deleted_count,
            "cutoff_date": cutoff.isoformat(),
        }

    return run_async(_cleanup())


@shared_task(
    base=BaseTask,
    bind=True,
    name="workers.tasks.cleanup_old_sessions",
    queue="maintenance",
)
def cleanup_old_sessions(
    self,
    max_age_days: int = 30,
    max_sessions_to_delete: int = 1000,
) -> dict[str, Any]:
    """
    清理旧会话
    """
    logger.info("Cleaning up sessions older than %d days", max_age_days)

    async def _cleanup():
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)

        async with get_db_session() as db:
            # 查找过期会话
            result = await db.execute(
                select(Session.id).where(Session.updated_at < cutoff).limit(max_sessions_to_delete)
            )
            session_ids = [row[0] for row in result.fetchall()]

            if session_ids:
                await db.execute(delete(Session).where(Session.id.in_(session_ids)))
                await db.commit()

            return {
                "deleted_count": len(session_ids),
                "cutoff_date": cutoff.isoformat(),
            }

    return run_async(_cleanup())


# ============================================
# Notification Tasks - 通知任务
# ============================================


@shared_task(
    base=BaseTask,
    bind=True,
    name="workers.tasks.send_notification",
    queue="default",
)
def send_notification(
    self,
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
) -> dict[str, Any]:
    """
    发送通知
    """
    logger.info("Sending %s notification to user %s", notification_type, user_id)

    # TODO: 实现实际的通知发送逻辑 (WebSocket, Email, etc.)
    return {
        "user_id": user_id,
        "title": title,
        "notification_type": notification_type,
        "sent_at": datetime.utcnow().isoformat(),
    }


# ============================================
# Analytics Tasks - 分析任务
# ============================================


@shared_task(
    base=BaseTask,
    bind=True,
    name="workers.tasks.calculate_usage_stats",
    queue="default",
)
def calculate_usage_stats(
    self,
    user_id: str,
    start_date: str,  # pylint: disable=unused-argument
    end_date: str,  # pylint: disable=unused-argument
) -> dict[str, Any]:
    """
    计算用户使用统计

    注意: start_date 和 end_date 参数目前未使用，保留以备将来实现日期范围过滤
    """
    logger.info("Calculating usage stats for user %s", user_id)

    async def _calculate():
        async with get_db_session() as db:
            stats_service = StatsService(db)
            # TODO: 实现日期范围过滤功能
            stats = await stats_service.get_user_stats(user_id=user_id)
            return stats

    return run_async(_calculate())
