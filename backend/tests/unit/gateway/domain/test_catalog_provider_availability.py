"""``build_catalog_provider_retirement_plan`` 纯函数行为。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid

from domains.gateway.domain.catalog.catalog_provider_availability import (
    build_catalog_provider_retirement_plan,
)


@dataclass
class _Model:
    id: uuid.UUID
    name: str
    provider: str
    credential_id: uuid.UUID
    enabled: bool
    tags: dict[str, Any] | None


@dataclass
class _Cred:
    id: uuid.UUID
    provider: str
    is_active: bool


def _mk_model(
    provider: str, *, enabled: bool = True, managed: bool = True, name: str | None = None
) -> _Model:
    return _Model(
        id=uuid.uuid4(),
        name=name or f"{provider}-m",
        provider=provider,
        credential_id=uuid.uuid4(),
        enabled=enabled,
        tags={"managed_by": "config"} if managed else {"managed_by": "manual"},
    )


def test_no_providers_without_key_returns_empty_plan() -> None:
    plan = build_catalog_provider_retirement_plan(
        providers_without_key=[],
        system_models=[_mk_model("openai")],
        system_credentials=[_Cred(uuid.uuid4(), "openai", True)],
    )
    assert plan.model_ids_to_disable == ()
    assert plan.credential_ids_to_deactivate == ()


def test_disables_only_config_managed_models_for_affected_provider() -> None:
    m1 = _mk_model("openai", name="gpt-4o")
    m2 = _mk_model("openai", name="manual-gpt", managed=False)  # 手动注册不动
    m3 = _mk_model("deepseek", name="deepseek-chat")  # 不在 provider 列表
    plan = build_catalog_provider_retirement_plan(
        providers_without_key={"openai"},
        system_models=[m1, m2, m3],
        system_credentials=[],
    )
    assert plan.model_ids_to_disable == (m1.id,)
    assert plan.affected_model_names == ("gpt-4o",)


def test_idempotent_skips_already_disabled_and_inactive() -> None:
    disabled_model = _mk_model("openai", enabled=False)
    active_cred = _Cred(uuid.uuid4(), "openai", True)
    inactive_cred = _Cred(uuid.uuid4(), "openai", False)
    plan = build_catalog_provider_retirement_plan(
        providers_without_key={"openai"},
        system_models=[disabled_model],
        system_credentials=[active_cred, inactive_cred],
    )
    assert plan.model_ids_to_disable == ()
    assert plan.credential_ids_to_deactivate == (active_cred.id,)


def test_provider_match_is_case_insensitive() -> None:
    m = _mk_model("OpenAI")
    plan = build_catalog_provider_retirement_plan(
        providers_without_key={"openai"},
        system_models=[m],
        system_credentials=[],
    )
    assert plan.model_ids_to_disable == (m.id,)
