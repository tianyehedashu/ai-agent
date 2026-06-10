"""downstream_model_pricing: add partial index for active rows

Revision ID: 20260616_dppi
Revises: 20260615_gbtb
Create Date: 2026-06-16

- 新增部分索引 ix_downstream_model_pricing_lookup_active，只覆盖
  effective_to IS NULL 或 effective_to > now() 的活跃行，减少热路径
  查询的索引扫描量，提升 pricing 解析性能。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260616_dppi"
down_revision: str | None = "20260615_gbtb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 部分索引：只覆盖当前生效的行（effective_to 为 NULL；本表采用 soft-close，
    # close_effective 将 effective_to 设为当前时间后不会再变更，因此 IS NULL
    # 即代表活跃）。使用 IMMUTABLE 条件以符合 PostgreSQL 对部分索引谓词的要求。
    op.create_index(
        "ix_downstream_model_pricing_lookup_active",
        "downstream_model_pricing",
        ["scope", "scope_id", "gateway_model_id", "effective_from"],
        postgresql_where=sa.text("effective_to IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_downstream_model_pricing_lookup_active",
        table_name="downstream_model_pricing",
    )
