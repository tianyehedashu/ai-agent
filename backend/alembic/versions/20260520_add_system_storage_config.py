"""add system_storage_config table

Revision ID: 20260520_ssc
Revises: 20260520_grlc
Create Date: 2026-05-20

本地/开发: ``alembic upgrade`` 执行本文件。
生产运维手工脚本（不自动执行）: alembic/sql/20260520_add_system_storage_config.{up,down}.sql
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260520_ssc"
down_revision: str | None = "20260520_grlc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_storage_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "storage_type",
            sa.String(20),
            nullable=False,
            server_default="local",
        ),
        sa.Column("local_storage_path", sa.String(500), nullable=True),
        sa.Column(
            "local_serve_prefix",
            sa.String(200),
            nullable=True,
            server_default="/api/v1/listing-studio/images",
        ),
        sa.Column("s3_bucket", sa.String(200), nullable=True),
        sa.Column("s3_region", sa.String(50), nullable=True),
        sa.Column("s3_endpoint_url", sa.String(500), nullable=True),
        sa.Column("s3_access_key", sa.String(200), nullable=True),
        sa.Column("s3_secret_key_encrypted", sa.Text(), nullable=True),
        sa.Column("s3_public_base_url", sa.String(500), nullable=True),
        sa.Column(
            "image_upload_max_bytes",
            sa.Integer(),
            nullable=False,
            server_default="10485760",
        ),
        sa.Column(
            "public_access",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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

    op.execute(
        sa.text(
            """
            INSERT INTO system_storage_config (
                id, storage_type, local_storage_path, local_serve_prefix,
                image_upload_max_bytes, public_access, is_active
            )
            SELECT
                gen_random_uuid(), 'local', './data/storage/images',
                '/api/v1/listing-studio/images', 10485760, true, true
            WHERE NOT EXISTS (SELECT 1 FROM system_storage_config)
            """
        )
    )


def downgrade() -> None:
    op.drop_table("system_storage_config")
