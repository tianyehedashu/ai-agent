"""``_deployment_from_model_info_kwargs`` 从 Router kwargs 解析 deployment 归因。"""

from __future__ import annotations

import uuid

from domains.gateway.infrastructure.callbacks.custom_logger import (
    _deployment_from_model_info_kwargs,
)


def test_deployment_from_litellm_params_model_info() -> None:
    gid = uuid.uuid4()
    kwargs = {
        "litellm_params": {
            "model_info": {
                "id": str(gid),
                "gateway_model_name": "  reg-alias  ",
            }
        }
    }
    did, name = _deployment_from_model_info_kwargs(kwargs)
    assert did == gid
    assert name == "reg-alias"


def test_deployment_prefers_litellm_params_over_standard_logging() -> None:
    first = uuid.uuid4()
    second = uuid.uuid4()
    kwargs = {
        "litellm_params": {"model_info": {"id": str(first)}},
        "standard_logging_object": {"model_info": {"id": str(second), "gateway_model_name": "ignored"}},
    }
    did, name = _deployment_from_model_info_kwargs(kwargs)
    assert did == first
    assert name is None


def test_deployment_falls_back_to_standard_logging_object() -> None:
    gid = uuid.uuid4()
    kwargs = {
        "standard_logging_object": {
            "model_info": {"id": str(gid), "gateway_model_name": "x"}
        }
    }
    assert _deployment_from_model_info_kwargs(kwargs) == (gid, "x")


def test_deployment_returns_none_when_no_id() -> None:
    kwargs = {"litellm_params": {"model_info": {"gateway_model_name": "only-name"}}}
    assert _deployment_from_model_info_kwargs(kwargs) == (None, None)
