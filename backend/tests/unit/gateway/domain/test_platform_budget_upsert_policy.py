"""平台预算写入校验策略单测（纯函数组合校验）。"""

from __future__ import annotations

from decimal import Decimal
import uuid

import pytest

from domains.gateway.domain.policies.platform_budget_upsert_policy import (
    validate_platform_budget_upsert,
)
from libs.exceptions import ValidationError


def _ok(**overrides: object) -> None:
    params: dict[str, object] = {
        "target_kind": "user",
        "credential_id": uuid.uuid4(),
        "model_name": "gpt-4--abc",
        "period": "monthly",
        "limit_usd": Decimal("50"),
        "limit_tokens": None,
        "limit_requests": None,
    }
    params.update(overrides)
    validate_platform_budget_upsert(**params)  # type: ignore[arg-type]


def test_valid_user_credential_model_rule() -> None:
    _ok()


def test_credential_on_non_user_target_rejected() -> None:
    with pytest.raises(ValidationError):
        _ok(target_kind="tenant")


def test_credential_without_model_allowed_as_credential_total() -> None:
    # credential_id 非空、model_name 为空表示该凭据下全模型限额，合法。
    _ok(model_name=None)


def test_invalid_period_rejected() -> None:
    with pytest.raises(ValidationError):
        _ok(period="hourly")


def test_window_seconds_period_not_allowed() -> None:
    with pytest.raises(ValidationError):
        _ok(period="600")


def test_requires_at_least_one_limit() -> None:
    with pytest.raises(ValidationError):
        _ok(limit_usd=None, limit_tokens=None, limit_requests=None)


def test_tenant_total_without_credential_is_valid() -> None:
    _ok(target_kind="tenant", credential_id=None, model_name=None)
