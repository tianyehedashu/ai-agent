"""Listing Studio 领域类型与状态常量。"""

from __future__ import annotations


class ListingStudioJobStatus:
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ListingStudioJobStepStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PROMPT_GENERATING = "prompt_generating"
    PROMPT_READY = "prompt_ready"


__all__ = ["ListingStudioJobStatus", "ListingStudioJobStepStatus"]
