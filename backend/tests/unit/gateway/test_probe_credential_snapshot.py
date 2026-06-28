"""ProbeCredentialSnapshot 工厂。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid

from domains.gateway.application.catalog.management.probe_target import (
    ProbeCredentialSnapshot,
)


@dataclass
class _FakeEncryptedCredential:
    id: uuid.UUID
    name: str
    api_key_encrypted: str
    api_base: str | None
    extra: dict[str, Any] | None
    profile_id: str | None


def test_from_encrypted_maps_credential_fields() -> None:
    cred_id = uuid.uuid4()
    row = _FakeEncryptedCredential(
        id=cred_id,
        name="kimi-key",
        api_key_encrypted="enc",
        api_base="https://api.example.com",
        extra={"endpoint_id": "ep-1"},
        profile_id=" moonshot.coding_plan ",
    )

    snap = ProbeCredentialSnapshot.from_encrypted(row, api_key="sk-test")

    assert snap.id == cred_id
    assert snap.name == "kimi-key"
    assert snap.profile_id == "moonshot.coding_plan"
    assert snap.api_base == "https://api.example.com"
    assert snap.extra == {"endpoint_id": "ep-1"}
    assert snap.api_key == "sk-test"


def test_from_encrypted_normalizes_blank_profile_id() -> None:
    row = _FakeEncryptedCredential(
        id=uuid.uuid4(),
        name="x",
        api_key_encrypted="enc",
        api_base=None,
        extra=None,
        profile_id="   ",
    )

    snap = ProbeCredentialSnapshot.from_encrypted(row, api_key="k")

    assert snap.profile_id is None
    assert snap.extra is None
