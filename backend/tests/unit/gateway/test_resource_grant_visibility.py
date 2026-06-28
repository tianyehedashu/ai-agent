"""resource grant 可见性与合并规则单测。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.catalog.model_selection import merge_named_rows_team_granted_system
from domains.gateway.domain.visibility.resource_grant_visibility import (
    GrantedModelSnapshot,
    visible_granted_model_ids,
)
from domains.gateway.domain.visibility.visibility import is_subject_granted


class _Row:
    def __init__(self, name: str, *, enabled: bool = True) -> None:
        self.name = name
        self.enabled = enabled


def test_is_subject_granted_model_or_credential_union() -> None:
    cred_id = uuid.uuid4()
    model_id = uuid.uuid4()
    keys = {("credential", cred_id)}
    assert is_subject_granted(
        subject_kind="model",
        subject_id=model_id,
        credential_id=cred_id,
        granted_subject_keys=keys,
    )
    assert not is_subject_granted(
        subject_kind="model",
        subject_id=uuid.uuid4(),
        credential_id=uuid.uuid4(),
        granted_subject_keys=keys,
    )


def test_visible_granted_model_ids() -> None:
    model_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    owner = uuid.uuid4()
    personal = uuid.uuid4()
    snap = GrantedModelSnapshot(
        model_id=model_id,
        credential_id=cred_id,
        owner_user_id=owner,
        personal_team_id=personal,
    )
    visible = visible_granted_model_ids(snapshots=[snap], granted_keys={("model", model_id)})
    assert visible == {model_id}


def test_merge_priority_team_granted_system() -> None:
    team = _Row("gpt")
    granted = _Row("gpt")
    system = _Row("gpt")
    merged = merge_named_rows_team_granted_system([team], [granted], [system])
    assert merged == [team]
    merged2 = merge_named_rows_team_granted_system([], [granted], [system])
    assert merged2 == [granted]
