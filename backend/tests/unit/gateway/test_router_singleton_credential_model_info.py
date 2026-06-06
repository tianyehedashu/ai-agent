"""Router deployment model_info 含凭据字段（供 CustomLogger 归因）。"""

from unittest.mock import MagicMock
import uuid

from domains.gateway.domain.router_model_name import encode_router_model_name
from domains.gateway.infrastructure.router_singleton import _models_to_deployments


def test_models_to_deployments_includes_credential_model_info() -> None:
    cred_id = uuid.uuid4()
    team_id = uuid.uuid4()
    model_id = uuid.uuid4()
    cred = MagicMock()
    cred.id = cred_id
    cred.name = "work"
    cred.scope = "user"
    m = MagicMock()
    m.id = model_id
    m.tenant_id = team_id
    m.name = "my-virtual"
    m.capability = "chat"
    m.weight = 2
    m.credential_id = cred_id
    m.provider = "openai"
    m.real_model = "gpt-4o-mini"
    m.rpm_limit = None
    m.tpm_limit = None
    m.tags = None

    out = _models_to_deployments([m], {cred_id: cred})
    assert len(out) == 1
    assert out[0]["model_name"] == encode_router_model_name(team_id, "my-virtual")
    assert out[0]["litellm_params"]["model"] == "openai/gpt-4o-mini"
    info = out[0]["model_info"]
    assert info["gateway_credential_id"] == str(cred_id)
    assert info["gateway_credential_name"] == "work"
    assert info["gateway_credential_scope"] == "user"
    assert info["gateway_provider"] == "openai"
