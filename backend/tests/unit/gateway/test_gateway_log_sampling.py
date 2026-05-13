"""gateway_log_sampling 单元测试。"""

from __future__ import annotations

import pytest

from domains.gateway.infrastructure.gateway_log_sampling import (
    deterministic_success_sample,
    should_persist_request_log_row,
)


@pytest.mark.unit
class TestDeterministicSuccessSample:
    def test_full_rate_always_true(self) -> None:
        assert deterministic_success_sample(request_key="any", sample_rate=1.0) is True

    def test_zero_rate_always_false(self) -> None:
        assert deterministic_success_sample(request_key="any", sample_rate=0.0) is False

    def test_stable_for_same_key(self) -> None:
        r = 0.5
        a = deterministic_success_sample(request_key="stable-key-1", sample_rate=r)
        b = deterministic_success_sample(request_key="stable-key-1", sample_rate=r)
        assert a is b


@pytest.mark.unit
class TestShouldPersistRequestLogRow:
    def test_non_success_respects_flag(self) -> None:
        assert (
            should_persist_request_log_row(
                status="failed",
                cost_usd=0.0,
                request_id=None,
                litellm_call_id=None,
                success_sample_rate=0.0,
                always_persist_non_success=True,
                always_persist_cost_above_usd=None,
            )
            is True
        )
        assert (
            should_persist_request_log_row(
                status="failed",
                cost_usd=0.0,
                request_id=None,
                litellm_call_id=None,
                success_sample_rate=1.0,
                always_persist_non_success=False,
                always_persist_cost_above_usd=None,
            )
            is False
        )

    def test_high_cost_always_persisted(self) -> None:
        assert (
            should_persist_request_log_row(
                status="success",
                cost_usd=10.0,
                request_id="rid",
                litellm_call_id=None,
                success_sample_rate=0.0,
                always_persist_non_success=True,
                always_persist_cost_above_usd=1.0,
            )
            is True
        )

    def test_success_sample_rate_zero_skips(self) -> None:
        assert (
            should_persist_request_log_row(
                status="success",
                cost_usd=0.0,
                request_id="rid",
                litellm_call_id=None,
                success_sample_rate=0.0,
                always_persist_non_success=True,
                always_persist_cost_above_usd=None,
            )
            is False
        )
