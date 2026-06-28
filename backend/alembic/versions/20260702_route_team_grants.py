"""gateway_routes.created_by_user_id + gateway_route_team_grants

Revision ID: 20260702_rtg
Revises: 20260701_grg
Create Date: 2026-07-02

支持「路由即可共享模型」：个人路由经显式 grant 发布给 shared team，团队成员以
暴露别名当普通模型调用，调用以路由 owner 身份委派解析底层模型与凭据。

- ``gateway_routes.created_by_user_id``：委派权威主体；历史行回填团队 owner。
- ``gateway_route_team_grants``：与 ``gateway_virtual_key_team_grants`` 对称（无 DB FK、
  软撤销、``is_active`` 上部分唯一索引）。

回填不可逆（``created_by_user_id`` 的 downgrade 仅删列）。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from utils.logging import get_logger

logger = get_logger(__name__)

revision: str = "20260702_rtg"
down_revision: str | None = "20260701_grg"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTS_TABLE = "gateway_route_team_grants"
IX_ROUTE_CREATOR = "ix_gateway_routes_created_by_user_id"
UQ_ACTIVE = "uq_route_team_grants_active"
UQ_ALIAS_ACTIVE = "uq_route_team_grants_alias_active"
IX_TENANT_ACTIVE = "ix_route_team_grants_tenant_active"
IX_ROUTE_ACTIVE = "ix_route_team_grants_route_active"
IX_USER_TENANT_ACTIVE = "ix_route_team_grants_user_tenant_active"


def upgrade() -> None:
    # ── gateway_routes.created_by_user_id（+ 回填团队 owner / admin）──────────
    op.add_column(
        "gateway_routes",
        sa.Column(
            "created_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index(IX_ROUTE_CREATOR, "gateway_routes", ["created_by_user_id"])
    op.execute(
        """
        UPDATE gateway_routes r
        SET created_by_user_id = t.owner_user_id
        FROM gateway_teams t
        WHERE r.tenant_id = t.id
          AND r.created_by_user_id IS NULL
          AND t.owner_user_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE gateway_routes r
        SET created_by_user_id = sub.user_id
        FROM (
            SELECT DISTINCT ON (m.team_id)
                m.team_id,
                m.user_id
            FROM gateway_team_members m
            WHERE m.role IN ('owner', 'admin')
            ORDER BY m.team_id, (m.role = 'owner') DESC, m.created_at ASC
        ) sub
        WHERE r.tenant_id = sub.team_id
          AND r.created_by_user_id IS NULL
        """
    )
    connection = op.get_bind()
    remaining = connection.execute(
        sa.text("SELECT count(*) FROM gateway_routes WHERE created_by_user_id IS NULL")
    ).scalar()
    if remaining and int(remaining) > 0:
        logger.warning(
            "route_team_grants: %s gateway_routes still have NULL created_by_user_id; "
            "their cross-team share resolution will fail-closed until reassigned",
            remaining,
        )

    # ── gateway_route_team_grants ───────────────────────────────────────────
    op.create_table(
        GRANTS_TABLE,
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("route_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exposed_alias", sa.String(200), nullable=False),
        sa.Column(
            "granted_by_user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_gateway_route_team_grants_route_id", GRANTS_TABLE, ["route_id"])
    op.create_index("ix_gateway_route_team_grants_tenant_id", GRANTS_TABLE, ["tenant_id"])
    op.create_index(
        "ix_gateway_route_team_grants_granted_by_user_id", GRANTS_TABLE, ["granted_by_user_id"]
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX {UQ_ACTIVE}
        ON {GRANTS_TABLE} (route_id, tenant_id)
        WHERE is_active = TRUE
        """
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX {UQ_ALIAS_ACTIVE}
        ON {GRANTS_TABLE} (tenant_id, exposed_alias)
        WHERE is_active = TRUE
        """
    )
    op.execute(
        f"""
        CREATE INDEX {IX_TENANT_ACTIVE}
        ON {GRANTS_TABLE} (tenant_id)
        WHERE is_active = TRUE
        """
    )
    op.execute(
        f"""
        CREATE INDEX {IX_ROUTE_ACTIVE}
        ON {GRANTS_TABLE} (route_id)
        WHERE is_active = TRUE
        """
    )
    op.execute(
        f"""
        CREATE INDEX {IX_USER_TENANT_ACTIVE}
        ON {GRANTS_TABLE} (granted_by_user_id, tenant_id)
        WHERE is_active = TRUE
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {IX_USER_TENANT_ACTIVE}")
    op.execute(f"DROP INDEX IF EXISTS {IX_ROUTE_ACTIVE}")
    op.execute(f"DROP INDEX IF EXISTS {IX_TENANT_ACTIVE}")
    op.execute(f"DROP INDEX IF EXISTS {UQ_ALIAS_ACTIVE}")
    op.execute(f"DROP INDEX IF EXISTS {UQ_ACTIVE}")
    op.drop_table(GRANTS_TABLE)
    op.execute(f"DROP INDEX IF EXISTS {IX_ROUTE_CREATOR}")
    op.drop_column("gateway_routes", "created_by_user_id")
