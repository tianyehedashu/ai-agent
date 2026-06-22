"""代理结算专用的有界延迟任务执行器单例（装配 Gateway 配置）。

通用实现见 ``libs.concurrency.DeferredDbTaskRunner``；本模块仅按 Gateway 配置装配进程级单例：
响应后结算（``settle_usage`` 等不可合并任务）统一经此有界执行器派发，消除无界 ``create_task``。
"""

from __future__ import annotations

from libs.concurrency import DeferredDbTaskRunner


def _build_proxy_deferred_runner() -> DeferredDbTaskRunner:
    from bootstrap.config import settings

    return DeferredDbTaskRunner(
        name="proxy-settlement",
        max_workers=lambda: int(settings.gateway_deferred_task_max_workers),
        max_queue=lambda: int(settings.gateway_deferred_task_max_queue),
        submit_block_timeout_seconds=lambda: (
            float(settings.gateway_deferred_task_submit_block_timeout_ms) / 1000.0
        ),
    )


# 进程级单例：响应后结算（settle_usage 等不可合并任务）统一经此有界执行器派发。
proxy_deferred_runner = _build_proxy_deferred_runner()


__all__ = ["proxy_deferred_runner"]
