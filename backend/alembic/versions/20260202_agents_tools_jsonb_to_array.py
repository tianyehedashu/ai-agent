"""agents_tools_jsonb_to_array

Revision ID: a2b3c4d5e6f7
Revises: v1d3o_g3n_t4sk
Create Date: 2026-02-02

将 agents.tools 从 JSONB 改为 TEXT[]，与模型 ARRAY(String) 一致，修复
asyncpg.exceptions.InvalidTextRepresentationError: invalid input syntax for type json。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "v1d3o_g3n_t4sk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 将 agents.tools 从 JSONB 转为 TEXT[]，与模型 ARRAY(String) 一致
    # USING 中不能用子查询，故先建临时函数再 ALTER
    op.execute(
        """
        CREATE OR REPLACE FUNCTION _alembic_jsonb_to_text_array(j jsonb)
        RETURNS text[] LANGUAGE sql IMMUTABLE AS $$
          SELECT COALESCE(
            (SELECT array_agg(x) FROM jsonb_array_elements_text(j) AS x),
            '{}'
          )
        $$
        """
    )
    op.execute(
        """
        ALTER TABLE agents
        ALTER COLUMN tools TYPE TEXT[]
        USING _alembic_jsonb_to_text_array(tools)
        """
    )
    op.execute("DROP FUNCTION _alembic_jsonb_to_text_array(jsonb)")
    op.alter_column(
        "agents",
        "tools",
        server_default=sa.text("'{}'"),
    )


def downgrade() -> None:
    # 将 TEXT[] 转回 JSONB（数组转 JSON 数组）
    op.alter_column("agents", "tools", server_default=None)
    op.execute(
        """
        ALTER TABLE agents
        ALTER COLUMN tools TYPE JSONB
        USING to_jsonb(tools)
        """
    )
    op.alter_column(
        "agents",
        "tools",
        type_=postgresql.JSONB(),
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
