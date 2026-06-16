"""LiteLLM deployment 归因字段提取单测。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.litellm_deployment_attribution import (
    gateway_deployment_credential_id,
    gateway_deployment_real_model,
)


def test_gateway_deployment_real_model_from_model_info() -> None:
    kwargs = {
        "litellm_params": {
            "model": "volcengine/ep-abc",
            "model_info": {"gateway_real_model": "volcengine/doubao-lite"},
        }
    }
    assert gateway_deployment_real_model(kwargs) == "volcengine/doubao-lite"


def test_gateway_deployment_real_model_ignores_litellm_model_param() -> None:
    kwargs = {
        "litellm_params": {
            "model": "volcengine/ep-abc",
            "model_info": {"gateway_real_model": "ep-abc"},
        }
    }
    assert gateway_deployment_real_model(kwargs) == "ep-abc"


def test_gateway_deployment_real_model_from_top_level_model_info() -> None:
    """Router ``_update_kwargs_with_deployment`` 将 model_info 置于 kwargs 顶层。"""
    kwargs = {
        "model": "gw/t/team/Doubao-Lite",
        "model_info": {"gateway_real_model": "ep-20260410150612-9pncb"},
        "litellm_params": {"model": "ep-20260410150612-9pncb"},
    }
    assert gateway_deployment_real_model(kwargs) == "ep-20260410150612-9pncb"


def test_gateway_deployment_credential_id() -> None:
    cred_id = uuid.uuid4()
    kwargs = {
        "litellm_params": {
            "model_info": {"gateway_credential_id": str(cred_id)},
        }
    }
    assert gateway_deployment_credential_id(kwargs) == cred_id
