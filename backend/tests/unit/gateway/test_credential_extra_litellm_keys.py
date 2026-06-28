"""LiteLLM provider extra 字段透传白名单 + api_key 重命名映射。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import uuid

import pytest

from domains.gateway.domain.litellm.litellm_credential_extra_keys import (
    API_KEY_RENAME,
    credential_extra_keys_for_litellm,
    litellm_api_key_param_name,
)
from domains.gateway.infrastructure.litellm.router_singleton import _build_litellm_params


@pytest.mark.parametrize(
    "provider, must_contain, must_not_contain",
    [
        ("openai", ("organization", "project_id"), ("aws_region_name",)),
        ("azure", ("api_version",), ("organization",)),
        (
            "bedrock",
            ("aws_secret_access_key", "aws_region_name", "aws_session_token"),
            ("api_version",),
        ),
        (
            "vertex_ai",
            ("vertex_project", "vertex_location", "vertex_credentials"),
            ("api_version",),
        ),
        ("dashscope", ("workspace_id",), ("api_version",)),
        ("volcengine", ("region", "endpoint_id"), ("workspace_id",)),
    ],
)
def test_credential_extra_keys_for_litellm_matrix(
    provider: str,
    must_contain: tuple[str, ...],
    must_not_contain: tuple[str, ...],
) -> None:
    keys = set(credential_extra_keys_for_litellm(provider))
    for k in must_contain:
        assert k in keys, f"expected {k} in {provider} whitelist"
    for k in must_not_contain:
        assert k not in keys, f"unexpected {k} leaked into {provider} whitelist"


@pytest.mark.parametrize(
    "provider",
    ["anthropic", "deepseek", "zhipuai", "gemini", "cohere", "mistral", "fireworks", "together_ai"],
)
def test_credential_extra_keys_for_litellm_empty_when_no_extras(provider: str) -> None:
    assert credential_extra_keys_for_litellm(provider) == ()


def test_credential_extra_keys_for_litellm_unknown_provider_is_safe_default() -> None:
    assert credential_extra_keys_for_litellm("brand-new-vendor") == ()


def test_litellm_api_key_param_name_defaults_to_api_key() -> None:
    assert litellm_api_key_param_name("openai") == "api_key"
    assert litellm_api_key_param_name("dashscope") == "api_key"


def test_litellm_api_key_param_name_renames_bedrock_to_access_key_id() -> None:
    assert litellm_api_key_param_name("bedrock") == "aws_access_key_id"
    assert API_KEY_RENAME["bedrock"] == "aws_access_key_id"


def _make_credential(*, encrypted_value: str, extra: dict | None) -> MagicMock:
    cred = MagicMock()
    cred.id = uuid.uuid4()
    cred.api_key_encrypted = encrypted_value
    cred.api_base = "https://example.com/v1"
    cred.extra = extra
    return cred


def test_build_litellm_params_filters_extra_to_provider_whitelist() -> None:
    cred = _make_credential(
        encrypted_value="encrypted-blob",
        extra={
            "organization": "org-x",
            "project_id": "proj-y",
            "workspace_id": "ws-should-be-dropped-for-openai",
            "vertex_project": "vp-should-be-dropped",
        },
    )

    with patch(
        "domains.gateway.infrastructure.litellm.router_singleton.decrypt_value",
        return_value="sk-decrypted",
    ):
        params = _build_litellm_params(
            real_model="gpt-4o-mini",
            provider="openai",
            credential=cred,
            rpm_limit=None,
            tpm_limit=None,
            tags=None,
        )

    assert params["api_key"] == "sk-decrypted"
    assert params["organization"] == "org-x"
    assert params["project_id"] == "proj-y"
    assert "workspace_id" not in params
    assert "vertex_project" not in params


def test_build_litellm_params_renames_api_key_for_bedrock() -> None:
    cred = _make_credential(
        encrypted_value="encrypted-access-key",
        extra={
            "aws_secret_access_key": "secret-z",
            "aws_region_name": "us-east-1",
            "organization": "ignored-for-bedrock",
        },
    )

    with patch(
        "domains.gateway.infrastructure.litellm.router_singleton.decrypt_value",
        return_value="AKIA-DECRYPTED",
    ):
        params = _build_litellm_params(
            real_model="anthropic.claude-3-5-sonnet-20240620-v1:0",
            provider="bedrock",
            credential=cred,
            rpm_limit=None,
            tpm_limit=None,
            tags=None,
        )

    assert params["aws_access_key_id"] == "AKIA-DECRYPTED"
    assert "api_key" not in params
    assert params["aws_secret_access_key"] == "secret-z"
    assert params["aws_region_name"] == "us-east-1"
    assert "organization" not in params


def test_build_litellm_params_passes_azure_api_version() -> None:
    cred = _make_credential(
        encrypted_value="encrypted-azure",
        extra={"api_version": "2024-08-01-preview"},
    )
    with patch(
        "domains.gateway.infrastructure.litellm.router_singleton.decrypt_value",
        return_value="azure-key",
    ):
        params = _build_litellm_params(
            real_model="gpt-4o",
            provider="azure",
            credential=cred,
            rpm_limit=None,
            tpm_limit=None,
            tags=None,
        )
    assert params["api_key"] == "azure-key"
    assert params["api_version"] == "2024-08-01-preview"


def test_build_litellm_params_skips_empty_extra_values() -> None:
    cred = _make_credential(
        encrypted_value="encrypted",
        extra={"region": "", "endpoint_id": None, "organization": "ok"},
    )
    with patch(
        "domains.gateway.infrastructure.litellm.router_singleton.decrypt_value",
        return_value="key",
    ):
        params = _build_litellm_params(
            real_model="doubao-pro",
            provider="volcengine",
            credential=cred,
            rpm_limit=None,
            tpm_limit=None,
            tags=None,
        )
    assert "region" not in params
    assert "endpoint_id" not in params
    # organization is not in volcengine whitelist
    assert "organization" not in params
