"""drop_api_key_foreign_keys

Revision ID: f4g5h6i7j8k9
Revises: e3f4g5h6i7j8
Create Date: 2026-01-28 09:00:00.000000

移除 api_keys / api_key_usage_logs 的外键约束，符合设计决策：应用层保证完整性。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4g5h6i7j8k9"
down_revision: str | None = "e3f4g5h6i7j8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """移除外键约束（若存在）"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # api_keys.user_id -> users.id
    fks_api_keys = inspector.get_foreign_keys("api_keys")
    for fk in fks_api_keys:
        if "user_id" in fk.get("constrained_columns", []):
            op.drop_constraint(
                fk["name"],
                "api_keys",
                type_="foreignkey",
            )
            break

    # api_key_usage_logs.api_key_id -> api_keys.id
    fks_usage_logs = inspector.get_foreign_keys("api_key_usage_logs")
    for fk in fks_usage_logs:
        if "api_key_id" in fk.get("constrained_columns", []):
            op.drop_constraint(
                fk["name"],
                "api_key_usage_logs",
                type_="foreignkey",
            )
            break


def downgrade() -> None:
    """恢复外键约束（与 add_api_keys 原设计一致）"""
    op.create_foreign_key(
        "api_keys_user_id_fkey",
        "api_keys",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "api_key_usage_logs_api_key_id_fkey",
        "api_key_usage_logs",
        "api_keys",
        ["api_key_id"],
        ["id"],
        ondelete="CASCADE",
    )
