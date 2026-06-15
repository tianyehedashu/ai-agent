"""vkey 代理模型列表 id 纯规则单元测试。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.domain.vkey_team_prefix_policy import resolve_vkey_proxy_list_id


def test_bound_team_uses_bare_registry_name() -> None:
    bound = uuid.uuid4()
    slug_by_tenant = {bound: "primary-slug"}
    assert (
        resolve_vkey_proxy_list_id(
            bound_team_id=bound,
            model_tenant_id=bound,
            model_name="gpt-4o",
            slug_by_tenant=slug_by_tenant,
        )
        == "gpt-4o"
    )


def test_grant_team_uses_slug_prefix() -> None:
    bound = uuid.uuid4()
    grant = uuid.uuid4()
    slug_by_tenant = {bound: "primary-slug", grant: "shared-team"}
    assert (
        resolve_vkey_proxy_list_id(
            bound_team_id=bound,
            model_tenant_id=grant,
            model_name="gpt-4o",
            slug_by_tenant=slug_by_tenant,
        )
        == "shared-team/gpt-4o"
    )


def test_grant_team_missing_slug_raises_key_error() -> None:
    bound = uuid.uuid4()
    grant = uuid.uuid4()
    with pytest.raises(KeyError):
        resolve_vkey_proxy_list_id(
            bound_team_id=bound,
            model_tenant_id=grant,
            model_name="gpt-4o",
            slug_by_tenant={bound: "primary-slug"},
        )


def test_homonym_grant_gets_prefix_while_bound_stays_bare() -> None:
    bound = uuid.uuid4()
    grant = uuid.uuid4()
    slug_by_tenant = {bound: "my-primary", grant: "collab"}
    model_name = "custom-model"
    assert (
        resolve_vkey_proxy_list_id(
            bound_team_id=bound,
            model_tenant_id=bound,
            model_name=model_name,
            slug_by_tenant=slug_by_tenant,
        )
        == model_name
    )
    assert (
        resolve_vkey_proxy_list_id(
            bound_team_id=bound,
            model_tenant_id=grant,
            model_name=model_name,
            slug_by_tenant=slug_by_tenant,
        )
        == f"collab/{model_name}"
    )
