"""ORM 与多租户约定架构守门。"""

from __future__ import annotations

import ast
from pathlib import Path

from libs.db.database import Base
from libs.orm.base import TenantScopedMixin

_BACKEND = Path(__file__).resolve().parents[2]
_LIBS = _BACKEND / "libs"

TIMESTAMP_ALLOWLIST = frozenset({"users"})
TENANT_OPTIONAL_ALLOWLIST = frozenset(
    {
        "gateway_request_logs",
        "users",
        "system_gateway_models",
        "system_gateway_routes",
        "system_gateway_alert_rules",
        "system_provider_credentials",
    }
)


def test_business_tables_have_timestamps() -> None:
    for name, table in Base.metadata.tables.items():
        if name in TIMESTAMP_ALLOWLIST or name.startswith("system_"):
            continue
        if name == "gateway_request_logs":
            assert "created_at" in table.c
            continue
        assert "created_at" in table.c, name
        assert "updated_at" in table.c, name


def test_system_tables_have_no_tenant_id_column() -> None:
    for name in Base.metadata.tables:
        if not name.startswith("system_"):
            continue
        assert "tenant_id" not in Base.metadata.tables[name].c, name


def test_libs_no_domain_owner_kind_literals() -> None:
    forbidden = {"vkey", "apikey_grant"}
    for path in _LIBS.rglob("*.py"):
        if path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in forbidden:
                    msg = f"{path}: forbidden literal {node.value!r}"
                    raise AssertionError(msg)


def test_tenant_scoped_models_expose_tenant_id() -> None:
    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute

    for model in (GatewayModel, GatewayRoute):
        assert issubclass(model, TenantScopedMixin)
        assert "tenant_id" in model.__table__.c
        assert "team_id" not in model.__table__.c


def test_gateway_models_no_legacy_team_id_column() -> None:
    for name in ("gateway_models", "gateway_routes", "gateway_alert_rules", "gateway_virtual_keys"):
        table = Base.metadata.tables[name]
        assert "tenant_id" in table.c, name
        assert "team_id" not in table.c, name


def test_session_and_agent_expose_tenant_id() -> None:
    from domains.agent.infrastructure.models.agent import Agent
    from domains.session.infrastructure.models.session import Session

    assert issubclass(Session, TenantScopedMixin)
    assert issubclass(Agent, TenantScopedMixin)
    assert "tenant_id" in Session.__table__.c
    assert "tenant_id" in Agent.__table__.c


def test_agent_has_no_user_id_column() -> None:
    from domains.agent.infrastructure.models.agent import Agent

    assert "user_id" not in Agent.__table__.c


def test_provider_credentials_tenant_scoped_rows_use_tenant_id() -> None:
    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential

    assert "tenant_id" in ProviderCredential.__table__.c


def test_gateway_budgets_uses_target_kind() -> None:
    from domains.gateway.infrastructure.models.budget import GatewayBudget

    assert "target_kind" in GatewayBudget.__table__.c
    assert "target_id" in GatewayBudget.__table__.c
    assert "scope" not in GatewayBudget.__table__.c
    assert "scope_id" not in GatewayBudget.__table__.c


def test_system_gateway_models_credential_fk_to_system_pc() -> None:
    from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel

    fk = next(iter(SystemGatewayModel.__table__.foreign_keys))
    assert fk.column.table.name == "system_provider_credentials"


def test_config_catalog_sync_no_scope_system_write() -> None:
    import inspect

    from domains.gateway.application import config_catalog_sync

    source = inspect.getsource(config_catalog_sync._ensure_system_credential)
    assert 'scope="system"' not in source
    assert "scope='system'" not in source


def test_no_import_libs_db_team_ids_resolver() -> None:
    backend = Path(__file__).resolve().parents[2]
    forbidden = "libs.db.team_ids_resolver"
    for path in backend.rglob("*.py"):
        if path.name.startswith("test_"):
            continue
        if "team_ids_resolver.py" in str(path):
            continue
        text = path.read_text(encoding="utf-8")
        if forbidden in text:
            raise AssertionError(f"{path}: must not import {forbidden}")


def test_session_has_no_legacy_owner_columns() -> None:
    from domains.session.infrastructure.models.session import Session

    assert "tenant_id" in Session.__table__.c
    assert Session.__table__.c.tenant_id.nullable is False
    assert "user_id" not in Session.__table__.c
    assert "anonymous_user_id" not in Session.__table__.c
