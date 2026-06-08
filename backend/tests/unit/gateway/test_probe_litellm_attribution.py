"""模型探活 LiteLLM 归因 metadata"""

from __future__ import annotations

import uuid

from domains.gateway.application.management.write_modules.probe_litellm_attribution import (
    GATEWAY_PROBE_CLIENT_TYPE,
    build_probe_gateway_metadata,
    merge_probe_litellm_kwargs,
)
from domains.gateway.application.management.write_modules.probe_target import ProbeTarget


def _target() -> ProbeTarget:
    return ProbeTarget(
        model_id=uuid.uuid4(),
        capability="chat",
        provider="volcengine",
        real_model="doubao-test",
        credential_id=uuid.uuid4(),
        is_system=False,
    )


def test_build_probe_gateway_metadata_includes_attribution_keys() -> None:
    tenant_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target = _target()
    meta = build_probe_gateway_metadata(
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        target=target,
        credential_name="火山-company",
        user_email_snapshot="ops@example.com",
    )
    assert meta["gateway_team_id"] == str(tenant_id)
    assert meta["gateway_user_id"] == str(actor_id)
    assert meta["gateway_credential_id"] == str(target.credential_id)
    assert meta["gateway_credential_name_snapshot"] == "火山-company"
    assert meta["gateway_client_type"] == GATEWAY_PROBE_CLIENT_TYPE
    assert meta["gateway_user_email_snapshot"] == "ops@example.com"
    assert isinstance(meta.get("user_api_key_auth_metadata"), dict)


def test_merge_probe_litellm_kwargs_sets_metadata_and_model_info() -> None:
    tenant_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target = _target()
    merged = merge_probe_litellm_kwargs(
        {"model": "volcengine/doubao", "api_key": "sk-test"},
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        target=target,
        credential_name="cred-a",
    )
    assert merged["model"] == "volcengine/doubao"
    assert merged["metadata"]["gateway_team_id"] == str(tenant_id)
    mi = merged["litellm_params"]["model_info"]
    assert mi["id"] == str(target.model_id)
    assert mi["gateway_model_name"] == "doubao-test"
    assert mi["gateway_real_model"] == "doubao-test"
    assert mi["gateway_credential_id"] == str(target.credential_id)
    assert mi["gateway_credential_name"] == "cred-a"
