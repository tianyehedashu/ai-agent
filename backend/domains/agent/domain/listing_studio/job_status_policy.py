"""Job 状态聚合策略。"""

from __future__ import annotations

from domains.agent.domain.listing_studio.types import (
    ListingStudioJobStatus,
    ListingStudioJobStepStatus,
)

_IN_PROGRESS = frozenset(
    {
        ListingStudioJobStepStatus.RUNNING,
        ListingStudioJobStepStatus.PROMPT_GENERATING,
        ListingStudioJobStepStatus.PROMPT_READY,
    }
)
_TERMINAL = frozenset(
    {
        ListingStudioJobStepStatus.COMPLETED,
        ListingStudioJobStepStatus.FAILED,
    }
)


def aggregate_job_status(step_statuses: list[str]) -> str | None:
    """根据所有 step 状态聚合 Job 状态；无 step 时返回 None。"""
    if not step_statuses:
        return None
    if all(s == ListingStudioJobStepStatus.COMPLETED for s in step_statuses):
        return ListingStudioJobStatus.COMPLETED
    if all(s in _TERMINAL for s in step_statuses):
        return ListingStudioJobStatus.PARTIAL
    if any(s in _TERMINAL for s in step_statuses):
        return ListingStudioJobStatus.PARTIAL
    if any(s in _IN_PROGRESS for s in step_statuses):
        return ListingStudioJobStatus.RUNNING
    if all(s == ListingStudioJobStepStatus.PENDING for s in step_statuses):
        return ListingStudioJobStatus.DRAFT
    return ListingStudioJobStatus.FAILED


__all__ = ["aggregate_job_status"]
