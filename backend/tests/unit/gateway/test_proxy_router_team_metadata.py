"""LiteLLM Router team metadata 补齐单测。"""

from __future__ import annotations

import uuid

from litellm.router_utils.common_utils import filter_team_based_models

from domains.gateway.application.proxy_router_team_metadata import (
    ensure_litellm_router_team_metadata,
)


def test_filter_team_based_models_requires_user_api_key_team_id() -> None:
    team_id = uuid.uuid4()
    deployments = [
        {
            "model_info": {
                "id": "dep-1",
                "team_id": str(team_id),
            }
        }
    ]
    filtered = filter_team_based_models(deployments, request_kwargs={})
    assert filtered == []

    filtered = filter_team_based_models(
        deployments,
        request_kwargs={"metadata": {"user_api_key_team_id": str(team_id)}},
    )
    assert filtered == deployments


def test_ensure_litellm_router_team_metadata_from_gateway_team_id() -> None:
    team_id = uuid.uuid4()
    kwargs: dict = {"metadata": {"gateway_team_id": str(team_id)}}
    ensure_litellm_router_team_metadata(kwargs)
    assert kwargs["metadata"]["user_api_key_team_id"] == str(team_id)
    assert kwargs["litellm_metadata"]["user_api_key_team_id"] == str(team_id)


def test_ensure_litellm_router_team_metadata_explicit_team_id() -> None:
    team_id = uuid.uuid4()
    kwargs: dict = {}
    ensure_litellm_router_team_metadata(kwargs, team_id)
    assert kwargs["metadata"]["user_api_key_team_id"] == str(team_id)
