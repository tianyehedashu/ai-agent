"""Backfill gateway_request_logs.provider via model registry + name inference

Revision ID: 20260528_bfrlp2
Revises: 20260527_bfrlp
Create Date: 2026-05-28

首轮回填后仍大量 provider IS NULL：real_model 无 LiteLLM 前缀（如 doubao-*），
且 deployment_gateway_model_id 未写入。本迁移按 GatewayModel 注册名匹配并
用 ``infer_provider_name`` 推断剩余行。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260528_bfrlp2"
down_revision: str | None = "20260527_bfrlp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REGISTRY_BACKFILL_STATEMENTS: tuple[str, ...] = (
    """
    UPDATE gateway_request_logs AS grl
    SET provider = gm.provider
    FROM gateway_models AS gm
    WHERE grl.provider IS NULL
      AND grl.tenant_id = gm.tenant_id
      AND (
        gm.name = grl.route_name
        OR gm.name = grl.deployment_model_name
        OR gm.real_model = grl.real_model
      )
    """,
    """
    UPDATE gateway_request_logs AS grl
    SET provider = sgm.provider
    FROM system_gateway_models AS sgm
    WHERE grl.provider IS NULL
      AND (
        sgm.name = grl.route_name
        OR sgm.name = grl.deployment_model_name
        OR sgm.real_model = grl.real_model
      )
    """,
)


def _infer_provider_from_hints(*values: object) -> str | None:
    from domains.gateway.domain.usage.request_log_provider import infer_provider_from_model_hints

    return infer_provider_from_model_hints(*values)


_INFER_BATCH_SIZE = 500


def upgrade() -> None:
    conn = op.get_bind()
    for statement in _REGISTRY_BACKFILL_STATEMENTS:
        conn.execute(sa.text(statement))

    rows = conn.execute(
        sa.text(
            """
            SELECT id, created_at, real_model, route_name, deployment_model_name
            FROM gateway_request_logs
            WHERE provider IS NULL
            """
        )
    ).fetchall()
    update_stmt = sa.text(
        """
        UPDATE gateway_request_logs
        SET provider = :provider
        WHERE id = :id AND created_at = :created_at AND provider IS NULL
        """
    )
    pending: list[dict[str, object]] = []
    for row in rows:
        provider = _infer_provider_from_hints(
            row.real_model,
            row.route_name,
            row.deployment_model_name,
        )
        if not provider:
            continue
        pending.append({"provider": provider, "id": row.id, "created_at": row.created_at})
        if len(pending) >= _INFER_BATCH_SIZE:
            conn.execute(update_stmt, pending)
            pending.clear()
    if pending:
        conn.execute(update_stmt, pending)


def downgrade() -> None:
    """数据回填不可逆。"""
