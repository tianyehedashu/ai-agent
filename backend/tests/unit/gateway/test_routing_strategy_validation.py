"""routing_strategy 校验。"""

from __future__ import annotations

import pytest

from domains.gateway.application.routing_strategy_validation import validate_routing_strategy
from domains.gateway.domain.types import RoutingStrategy
from libs.exceptions import ValidationError


def test_validate_accepts_known_strategy() -> None:
    assert validate_routing_strategy("cost-based-routing") == "cost-based-routing"
    assert validate_routing_strategy("weighted-pick") == "weighted-pick"


def test_validate_accepts_routing_strategy_enum() -> None:
    assert validate_routing_strategy(RoutingStrategy.SIMPLE_SHUFFLE) == "simple-shuffle"


def test_validate_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        validate_routing_strategy("weighted-random")
