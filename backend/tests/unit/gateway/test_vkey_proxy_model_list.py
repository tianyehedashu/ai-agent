"""vkey_proxy_list_policy 纯规则单元测试。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.vkey.virtual_key_proxy_list_policy import (
    ordered_grant_tenant_ids,
    should_include_multi_grant_entry,
    should_skip_grant_system_model_row,
    should_skip_grant_system_route_row,
)


def test_ordered_grant_tenant_ids_puts_bound_first() -> None:
    bound = uuid.uuid4()
    grant = uuid.uuid4()
    assert ordered_grant_tenant_ids(bound, (grant, bound)) == (bound, grant)


def test_should_skip_grant_system_model_row_when_bound_already_lists_bare() -> None:
    bound = uuid.uuid4()
    grant = uuid.uuid4()
    assert should_skip_grant_system_model_row(
        tenant_id=grant,
        bound_team_id=bound,
        registry_name="shared-sys",
        is_system_registry=True,
        bound_system_registry_names=frozenset({"shared-sys"}),
    )


def test_should_not_skip_grant_team_owned_model_row() -> None:
    bound = uuid.uuid4()
    grant = uuid.uuid4()
    assert not should_skip_grant_system_model_row(
        tenant_id=grant,
        bound_team_id=bound,
        registry_name="team-only",
        is_system_registry=False,
        bound_system_registry_names=frozenset({"team-only"}),
    )


def test_should_not_skip_bound_team_system_model_row() -> None:
    bound = uuid.uuid4()
    assert not should_skip_grant_system_model_row(
        tenant_id=bound,
        bound_team_id=bound,
        registry_name="sys-a",
        is_system_registry=True,
        bound_system_registry_names=frozenset(),
    )


def test_should_skip_grant_system_route_row() -> None:
    bound = uuid.uuid4()
    grant = uuid.uuid4()
    assert should_skip_grant_system_route_row(
        tenant_id=grant,
        bound_team_id=bound,
        virtual_model="shared-route",
        is_system_registry_route=True,
        bound_system_registry_names=frozenset({"shared-route"}),
    )


def test_should_include_multi_grant_entry_rejects_homonym_grant() -> None:
    bound = uuid.uuid4()
    grant = uuid.uuid4()
    assert should_include_multi_grant_entry(
        tenant_id=bound,
        bound_team_id=bound,
        list_id="gpt-4o",
        seen_list_ids=frozenset(),
        prefix_dispatchable=True,
    )
    assert not should_include_multi_grant_entry(
        tenant_id=grant,
        bound_team_id=bound,
        list_id="same-slug/gpt-4o",
        seen_list_ids=frozenset(),
        prefix_dispatchable=False,
    )
