"""
Celery Application - 异步任务队列配置
"""

import logging
from typing import Any, ClassVar

from celery import Celery
from kombu import Exchange, Queue

from app.config import settings

# 创建 Celery 应用
celery_app = Celery(
    "ai_agent_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "workers.tasks",
    ],
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # 时区
    timezone="UTC",
    enable_utc=True,

    # 任务结果配置
    result_expires=3600,  # 结果过期时间 (1小时)
    result_extended=True,

    # 任务执行配置
    task_soft_time_limit=300,  # 软超时 5 分钟
    task_time_limit=600,       # 硬超时 10 分钟
    task_acks_late=True,       # 任务完成后再确认
    task_reject_on_worker_lost=True,

    # Worker 配置
    worker_prefetch_multiplier=1,  # 每个 worker 预取 1 个任务
    worker_max_tasks_per_child=100,  # 每个子进程处理 100 个任务后重启
    worker_max_memory_per_child=256000,  # 256MB 内存限制

    # 任务路由
    task_routes={
        "workers.tasks.process_memory_extraction": {"queue": "memory"},
        "workers.tasks.execute_code_in_sandbox": {"queue": "sandbox"},
        "workers.tasks.validate_code_quality": {"queue": "quality"},
        "workers.tasks.cleanup_expired_checkpoints": {"queue": "maintenance"},
        "workers.tasks.generate_embeddings": {"queue": "embeddings"},
    },

    # 队列定义
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("memory", Exchange("memory"), routing_key="memory"),
        Queue("sandbox", Exchange("sandbox"), routing_key="sandbox"),
        Queue("quality", Exchange("quality"), routing_key="quality"),
        Queue("maintenance", Exchange("maintenance"), routing_key="maintenance"),
        Queue("embeddings", Exchange("embeddings"), routing_key="embeddings"),
    ),

    # 默认队列
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",

    # 任务优先级
    task_queue_max_priority=10,
    task_default_priority=5,

    # 重试配置
    task_annotations={
        "*": {
            "rate_limit": "100/m",  # 每分钟最多 100 个任务
        },
    },

    # Beat 调度配置 (定时任务)
    beat_schedule={
        "cleanup-checkpoints-hourly": {
            "task": "workers.tasks.cleanup_expired_checkpoints",
            "schedule": 3600.0,  # 每小时
        },
        "cleanup-old-sessions-daily": {
            "task": "workers.tasks.cleanup_old_sessions",
            "schedule": 86400.0,  # 每天
        },
    },
)


# 任务基类
class BaseTask(celery_app.Task):
    """任务基类，提供公共功能"""

    abstract = True
    autoretry_for = (Exception,)
    retry_kwargs: ClassVar[dict[str, Any]] = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败回调"""
        logging.error("Task %s[%s] failed: %s", self.name, task_id, exc)

    def on_success(self, retval, task_id, args, kwargs):
        """任务成功回调"""
        logging.info("Task %s[%s] completed successfully", self.name, task_id)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试回调"""
        logging.warning("Task %s[%s] retrying: %s", self.name, task_id, exc)


# 导出
__all__ = ["BaseTask", "celery_app"]
