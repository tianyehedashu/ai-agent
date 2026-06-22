"""通用并发原语（纯技术基础设施，不含业务）。

设计说明见 ``backend/docs/gateway/DEFERRED_WRITE_CONCURRENCY.md``。

- ``CoalescingFlusher``：进程内按键合并增量、单 flusher 周期批量落库，消除写热点行锁串行化。
- ``DeferredDbTaskRunner``：有界队列 + 固定 worker 池，治理无上限 fire-and-forget 写入。
"""

from __future__ import annotations

from libs.concurrency.coalescing_flusher import CoalescingFlusher
from libs.concurrency.deferred_task_runner import DeferredDbTaskRunner, JobFactory

__all__ = ["CoalescingFlusher", "DeferredDbTaskRunner", "JobFactory"]
