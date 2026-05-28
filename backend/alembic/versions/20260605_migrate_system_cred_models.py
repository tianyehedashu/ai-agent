"""Move gateway_models rows bound to system credentials into system_gateway_models

Revision ID: 20260605_sys_cred_models
Revises: 20260604_revoked
Create Date: 2026-06-05
"""

from collections.abc import Sequence
import json

import sqlalchemy as sa

from alembic import op

revision: str = "20260605_sys_cred_models"
down_revision: str | None = "20260604_revoked"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _prune_orphans_for_deleted_model(conn, *, model_id, model_name: str) -> None:
    conn.execute(
        sa.text(
            """
            DELETE FROM system_gateway_grants
            WHERE subject_kind = 'model' AND subject_id = :model_id
            """
        ),
        {"model_id": model_id},
    )
    conn.execute(
        sa.text("DELETE FROM gateway_budgets WHERE model_name = :model_name"),
        {"model_name": model_name},
    )


def upgrade() -> None:
    conn = op.get_bind()

    misfiled = conn.execute(
        sa.text(
            """
            SELECT gm.id, gm.name, gm.capability, gm.real_model, gm.credential_id,
                   gm.provider, gm.weight, gm.rpm_limit, gm.tpm_limit, gm.enabled,
                   gm.tags, gm.last_test_status, gm.last_tested_at, gm.last_test_reason,
                   gm.created_at, gm.updated_at
            FROM gateway_models gm
            WHERE gm.credential_id IN (SELECT id FROM system_provider_credentials)
            ORDER BY gm.created_at
            """
        )
    ).fetchall()

    for row in misfiled:
        row_id = row.id
        row_name = row.name
        existing = conn.execute(
            sa.text(
                """
                SELECT id, real_model, provider FROM system_gateway_models
                WHERE name = :name
                LIMIT 1
                """
            ),
            {"name": row_name},
        ).fetchone()

        if existing is not None:
            same_upstream = (
                str(existing.real_model) == str(row.real_model)
                and str(existing.provider).strip().lower() == str(row.provider).strip().lower()
            )
            if not same_upstream:
                suffix = str(row_id).replace("-", "")[:8]
                row_name = f"{row.name}-migrated-{suffix}"[:200]
            else:
                target_id = existing.id
                conn.execute(
                    sa.text(
                        """
                        UPDATE system_gateway_grants
                        SET subject_id = :target_id
                        WHERE subject_kind = 'model' AND subject_id = :old_id
                        """
                    ),
                    {"target_id": target_id, "old_id": row_id},
                )
                conn.execute(
                    sa.text("DELETE FROM gateway_models WHERE id = :id"),
                    {"id": row_id},
                )
                _prune_orphans_for_deleted_model(conn, model_id=row_id, model_name=row.name)
                continue

        conn.execute(
            sa.text(
                """
                INSERT INTO system_gateway_models (
                    id, name, capability, real_model, credential_id, provider,
                    weight, rpm_limit, tpm_limit, enabled, visibility, tags,
                    last_test_status, last_tested_at, last_test_reason,
                    created_at, updated_at
                )
                VALUES (
                    :id, :name, :capability, :real_model, :credential_id, :provider,
                    :weight, :rpm_limit, :tpm_limit, :enabled, 'inherit', :tags,
                    :last_test_status, :last_tested_at, :last_test_reason,
                    :created_at, :updated_at
                )
                """
            ),
            {
                "id": row_id,
                "name": row_name,
                "capability": row.capability,
                "real_model": row.real_model,
                "credential_id": row.credential_id,
                "provider": row.provider,
                "weight": row.weight,
                "rpm_limit": row.rpm_limit,
                "tpm_limit": row.tpm_limit,
                "enabled": row.enabled,
                "tags": json.dumps(row.tags) if row.tags is not None else None,
                "last_test_status": row.last_test_status,
                "last_tested_at": row.last_tested_at,
                "last_test_reason": row.last_test_reason,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            },
        )
        conn.execute(
            sa.text("DELETE FROM gateway_models WHERE id = :id"),
            {"id": row_id},
        )


def downgrade() -> None:
    # 数据回迁不可逆：无法可靠区分原误写行与正常团队模型
    pass
