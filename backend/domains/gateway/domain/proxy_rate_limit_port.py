"""限流用量读取端口（domain 契约，infrastructure 实现）。

只读 60s 滚动窗口的当前用量，用于构造响应限流头（OpenAI/Anthropic 协议）。
**不**触发预扣/写入；预扣由 ``BudgetService.check_rate_limit`` 走另一路径。
"""

from __future__ import annotations

from typing import Protocol


class RateLimitUsageReader(Protocol):
    """限流窗口当前用量只读读取器。"""

    async def peek_60s_window(
        self,
        *,
        scope: str,
        scope_id: str | None,
    ) -> tuple[int, int]:
        """返回 ``(rpm_used, tpm_used)``，窗口为 60s 滚动。"""
        ...


__all__ = ["RateLimitUsageReader"]
