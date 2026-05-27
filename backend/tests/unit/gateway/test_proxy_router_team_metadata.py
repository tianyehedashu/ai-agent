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


def test_ensure_litellm_router_team_metadata_explicit_user_id() -> None:
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    kwargs: dict = {}
    ensure_litellm_router_team_metadata(kwargs, team_id, user_id=user_id)
    assert kwargs["metadata"]["user_api_key_user_id"] == str(user_id)
    auth = kwargs["metadata"]["user_api_key_auth_metadata"]
    assert auth["gateway_user_id"] == str(user_id)
    assert auth["gateway_team_id"] == str(team_id)
    assert kwargs["litellm_metadata"]["user_api_key_user_id"] == str(user_id)


def test_ensure_litellm_router_team_metadata_mirrors_user_and_auth_to_litellm_metadata() -> None:
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    vkey_id = uuid.uuid4()
    gateway_snapshot = {
        "gateway_team_id": str(team_id),
        "gateway_user_id": str(user_id),
        "gateway_vkey_id": str(vkey_id),
        "gateway_request_id": "req-1",
    }
    kwargs: dict = {
        "metadata": {
            "gateway_team_id": str(team_id),
            "gateway_user_id": str(user_id),
            "gateway_vkey_id": str(vkey_id),
            "user_api_key_team_id": str(team_id),
            "user_api_key_user_id": str(user_id),
            "user_api_key_auth_metadata": gateway_snapshot,
        }
    }
    ensure_litellm_router_team_metadata(kwargs)
    litellm_meta = kwargs["litellm_metadata"]
    assert litellm_meta["user_api_key_team_id"] == str(team_id)
    assert litellm_meta["user_api_key_user_id"] == str(user_id)
    assert litellm_meta["user_api_key_auth_metadata"] == gateway_snapshot
