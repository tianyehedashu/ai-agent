"""Add LangGraph tables (checkpointer and store)

Revision ID: 008_add_langgraph_tables
Revises: 007
Create Date: 2026-01-14

Note: LangGraph's PostgresSaver and PostgresStore automatically create tables
on first use. This migration is for documentation and ensures compatibility.
"""

# revision identifiers, used by Alembic.
revision = "008_add_langgraph_tables"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    升级：添加 LangGraph 需要的表

    注意：LangGraph 的 PostgresSaver 和 PostgresStore 会在首次使用时
    自动创建表结构。此迁移主要用于文档化和确保兼容性。

    如果需要手动创建表，可以取消注释以下代码。
    但通常建议让 LangGraph 自动管理表结构。
    """
    # LangGraph Checkpointer 表（由 PostgresSaver 自动创建）
    # 表名: checkpoints
    # 列：
    # - thread_id (TEXT, PRIMARY KEY)
    # - checkpoint_ns (TEXT, PRIMARY KEY)
    # - checkpoint_id (TEXT, PRIMARY KEY)
    # - parent_checkpoint_id (TEXT)
    # - type (TEXT)
    # - checkpoint (JSONB)
    # - metadata (JSONB)

    # LangGraph Store 表（由 PostgresStore 自动创建）
    # 表名: store
    # 列：
    # - namespace (TEXT[], PRIMARY KEY)
    # - key (TEXT, PRIMARY KEY)
    # - value (JSONB)

    # 注意：这里不实际创建表，因为 LangGraph 会自动管理
    # 如果遇到兼容性问题，可以取消注释以下代码手动创建

    # op.create_table(
    #     "checkpoints",
    #     sa.Column("thread_id", sa.Text(), nullable=False, primary_key=True),
    #     sa.Column("checkpoint_ns", sa.Text(), nullable=False, primary_key=True),
    #     sa.Column("checkpoint_id", sa.Text(), nullable=False, primary_key=True),
    #     sa.Column("parent_checkpoint_id", sa.Text(), nullable=True),
    #     sa.Column("type", sa.Text(), nullable=True),
    #     sa.Column("checkpoint", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    #     sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    # )
    #
    # op.create_table(
    #     "store",
    #     sa.Column("namespace", postgresql.ARRAY(sa.Text()), nullable=False, primary_key=True),
    #     sa.Column("key", sa.Text(), nullable=False, primary_key=True),
    #     sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    # )

    # 添加索引（如果需要）
    # op.create_index("ix_checkpoints_thread_id", "checkpoints", ["thread_id"])
    # op.create_index("ix_store_namespace", "store", ["namespace"], using="gin")

    pass  # 让 LangGraph 自动管理表结构


def downgrade() -> None:
    """
    降级：删除 LangGraph 表

    注意：通常不需要降级，因为 LangGraph 自动管理的表。
    如果手动创建了表，取消注释以下代码。
    """
    # op.drop_index("ix_store_namespace", table_name="store")
    # op.drop_index("ix_checkpoints_thread_id", table_name="checkpoints")
    # op.drop_table("store")
    # op.drop_table("checkpoints")

    pass
