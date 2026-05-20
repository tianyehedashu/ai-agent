"""Redirect system_gateway_models.credential_id FK to system_provider_credentials

Revision ID: 20260528_sgmcf
Revises: 20260527_pcn
Create Date: 2026-05-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260528_sgmcf"
down_revision: str | None = "20260527_pcn"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO system_provider_credentials (
            id, provider, name, api_key_encrypted, api_base, extra,
            is_active, created_at, updated_at
        )
        SELECT
            pc.id, pc.provider, pc.name, pc.api_key_encrypted, pc.api_base, pc.extra,
            pc.is_active, pc.created_at, pc.updated_at
        FROM provider_credentials pc
        WHERE pc.scope = 'system'
          AND NOT EXISTS (
            SELECT 1 FROM system_provider_credentials spc WHERE spc.id = pc.id
          )
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE system_gateway_models sgm
        SET credential_id = spc.id
        FROM provider_credentials pc
        JOIN system_provider_credentials spc
          ON spc.provider = pc.provider AND spc.name = pc.name
        WHERE sgm.credential_id = pc.id
          AND NOT EXISTS (
            SELECT 1 FROM system_provider_credentials x WHERE x.id = sgm.credential_id
          )
        """
    )
    op.execute(
        """
        UPDATE gateway_models gm
        SET credential_id = spc.id
        FROM provider_credentials pc
        JOIN system_provider_credentials spc ON spc.id = pc.id
        WHERE gm.credential_id = pc.id
          AND pc.scope = 'system'
        """
    )
    op.execute(
        """
        DELETE FROM provider_credentials pc
        WHERE pc.scope = 'system'
          AND EXISTS (
            SELECT 1 FROM system_provider_credentials spc WHERE spc.id = pc.id
          )
          AND NOT EXISTS (
            SELECT 1 FROM gateway_models gm WHERE gm.credential_id = pc.id
          )
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            fk_name text;
        BEGIN
            SELECT c.conname INTO fk_name
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'system_gateway_models'
              AND c.contype = 'f'
              AND pg_get_constraintdef(c.oid) LIKE '%provider_credentials%';
            IF fk_name IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE system_gateway_models DROP CONSTRAINT %I', fk_name
                );
            END IF;
        END $$;
        """
    )
    op.create_foreign_key(
        "fk_system_gateway_models_credential_id",
        "system_gateway_models",
        "system_provider_credentials",
        ["credential_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_system_gateway_models_credential_id",
        "system_gateway_models",
        type_="foreignkey",
    )
    op.execute(
        """
        INSERT INTO provider_credentials (
            id, tenant_id, scope, scope_id, provider, name, api_key_encrypted,
            api_base, extra, is_active, created_at, updated_at
        )
        SELECT
            spc.id, NULL, 'system', NULL, spc.provider, spc.name, spc.api_key_encrypted,
            spc.api_base, spc.extra, spc.is_active, spc.created_at, spc.updated_at
        FROM system_provider_credentials spc
        WHERE NOT EXISTS (
            SELECT 1 FROM provider_credentials pc WHERE pc.id = spc.id
        )
        """
    )
    op.create_foreign_key(
        "fk_system_gateway_models_credential_id_pc",
        "system_gateway_models",
        "provider_credentials",
        ["credential_id"],
        ["id"],
        ondelete="RESTRICT",
    )
