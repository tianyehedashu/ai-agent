"""ORM 与多租户约定架构守门。"""

from __future__ import annotations

import ast
from pathlib import Path

from libs.db.database import Base
from libs.orm.base import TenantScopedMixin

_BACKEND = Path(__file__).resolve().parents[2]
_LIBS = _BACKEND / "libs"

# 豁免标准 created_at/updated_at 约定的非业务表：
# - users：沿用 fastapi-users schema
# - gateway_rollup_state：id=1 单行水位表（rollup watermark），刻意不继承 BaseModel，
#   只需 last_rolled_at/updated_at；created_at 对单例行无业务语义。
TIMESTAMP_ALLOWLIST = frozenset({"users", "gateway_rollup_state"})

TENANT_BUSINESS_TABLES = frozenset(
    {
        "sessions",
        "agents",
        "memories",
        "mcp_servers",
        "video_gen_tasks",
        "product_image_gen_tasks",
        "product_info_jobs",
        "product_info_prompt_templates",
        "gateway_models",
        "gateway_routes",
        "gateway_alert_rules",
        "gateway_virtual_keys",
        "api_keys",
    }
)

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


def _tenant_business_orm_classes() -> dict[str, type]:
    """显式导入租户业务 ORM，避免 Base.registry 未加载全部 mapper。"""
    from domains.agent.infrastructure.models.agent import Agent
    from domains.agent.infrastructure.models.listing_studio_job import ListingStudioJob
    from domains.agent.infrastructure.models.listing_studio_prompt_template import (
        ListingStudioPromptTemplate,
    )
    from domains.agent.infrastructure.models.mcp_server import MCPServer
    from domains.agent.infrastructure.models.memory import Memory
    from domains.agent.infrastructure.models.product_image_gen_task import ProductImageGenTask
    from domains.agent.infrastructure.models.video_gen_task import VideoGenTask
    from domains.gateway.infrastructure.models.alert import GatewayAlertRule
    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
    from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey
    from domains.identity.infrastructure.models.api_key import ApiKey
    from domains.session.infrastructure.models.session import Session

    return {
        "sessions": Session,
        "agents": Agent,
        "memories": Memory,
        "mcp_servers": MCPServer,
        "video_gen_tasks": VideoGenTask,
        "product_image_gen_tasks": ProductImageGenTask,
        "product_info_jobs": ListingStudioJob,
        "product_info_prompt_templates": ListingStudioPromptTemplate,
        "gateway_models": GatewayModel,
        "gateway_routes": GatewayRoute,
        "gateway_alert_rules": GatewayAlertRule,
        "gateway_virtual_keys": GatewayVirtualKey,
        "api_keys": ApiKey,
    }


def _orm_class_by_table(table_name: str) -> type:
    mapping = _tenant_business_orm_classes()
    if table_name not in mapping:
        msg = f"No ORM class registered for table {table_name!r}"
        raise AssertionError(msg)
    return mapping[table_name]


def _iter_tenant_scoped_orm_classes() -> list[type]:
    mapping = _tenant_business_orm_classes()
    return [mapping[name] for name in sorted(TENANT_BUSINESS_TABLES)]


def test_all_tenant_business_tables_inherit_mixin() -> None:
    """所有租户业务 ORM 类必须继承 TenantScopedMixin。"""
    for table_name in TENANT_BUSINESS_TABLES:
        model = _orm_class_by_table(table_name)
        assert issubclass(model, TenantScopedMixin), table_name
        assert "tenant_id" in model.__table__.c, table_name
        assert "team_id" not in model.__table__.c, table_name


def test_orm_metadata_has_no_db_foreign_keys() -> None:
    """全库 ORM 元数据不得声明 DB FOREIGN KEY（应用层保证引用完整性）。"""
    violations: list[str] = []
    for table_name, table in sorted(Base.metadata.tables.items()):
        for col in table.c:
            col_fks = list(col.foreign_keys)
            if col_fks:
                violations.append(f"{table_name}.{col.name}: {col_fks}")
        for fk in table.foreign_keys:
            violations.append(f"{table_name} (table-level): {fk}")
    assert not violations, "ORM metadata has DB FK:\n" + "\n".join(violations)


def test_tenant_id_has_no_db_foreign_key() -> None:
    """tenant_id 列不得带 DB 外键（由 test_orm_metadata_has_no_db_foreign_keys 覆盖）。"""
    for model in _iter_tenant_scoped_orm_classes():
        col = model.__table__.c["tenant_id"]
        assert not list(col.foreign_keys), f"{model.__name__}: tenant_id has FK"


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


def test_system_gateway_models_credential_id_column_exists() -> None:
    from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel

    assert "credential_id" in SystemGatewayModel.__table__.c
    assert not list(SystemGatewayModel.__table__.c.credential_id.foreign_keys)


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
