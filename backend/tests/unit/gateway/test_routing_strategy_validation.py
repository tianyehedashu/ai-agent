"""routing_strategy 校验。"""

from __future__ import annotations

import pytest

from domains.gateway.application.routing_strategy_validation import validate_routing_strategy
from libs.exceptions import ValidationError


def test_validate_accepts_known_strategy() -> None:
    assert validate_routing_strategy("cost-based-routing") == "cost-based-routing"


def test_validate_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        validate_routing_strategy("weighted-pick")
