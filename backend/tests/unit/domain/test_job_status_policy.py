"""job_status_policy 单元测试。"""

import pytest

from domains.agent.domain.listing_studio.job_status_policy import aggregate_job_status
from domains.agent.domain.listing_studio.types import (
    ListingStudioJobStatus,
    ListingStudioJobStepStatus,
)


@pytest.mark.unit
class TestAggregateJobStatus:
    def test_empty_returns_none(self):
        assert aggregate_job_status([]) is None

    def test_all_completed(self):
        statuses = [ListingStudioJobStepStatus.COMPLETED] * 3
        assert aggregate_job_status(statuses) == ListingStudioJobStatus.COMPLETED

    def test_all_failed(self):
        statuses = [ListingStudioJobStepStatus.FAILED] * 2
        assert aggregate_job_status(statuses) == ListingStudioJobStatus.PARTIAL

    def test_mixed_terminal(self):
        statuses = [
            ListingStudioJobStepStatus.COMPLETED,
            ListingStudioJobStepStatus.FAILED,
        ]
        assert aggregate_job_status(statuses) == ListingStudioJobStatus.PARTIAL

    def test_running_only(self):
        statuses = [ListingStudioJobStepStatus.RUNNING, ListingStudioJobStepStatus.PENDING]
        assert aggregate_job_status(statuses) == ListingStudioJobStatus.RUNNING

    def test_all_pending(self):
        statuses = [ListingStudioJobStepStatus.PENDING] * 3
        assert aggregate_job_status(statuses) == ListingStudioJobStatus.DRAFT
