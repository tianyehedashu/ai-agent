"""drop low-cardinality unused indexes on gateway_request_logs

Revision ID: 8418cdb1fed7
Revises: 20260628_fpq
Create Date: 2026-06-22 10:36:14.257307

新表约定（多租户业务表）:
  id UUID PK, created_at/updated_at TIMESTAMPTZ NOT NULL,
  tenant_id UUID NOT NULL（系统级配置用 system_* 表，勿 tenant_id NULL）
策略挂载表可另加 target_kind/target_id；禁止新增 user_id/team_id/scope/scope_id 列名。

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8418cdb1fed7"
down_revision: str | None = "20260628_fpq"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # capability（chat/embedding/image/... 约 5 值）与 client_type（cursor/claude-code/... 约 6 值）
    # 均为低基数列：PG 规划器对低选择性单列 btree 几乎不选用（走 bitmap/seq），全生命周期
    # idx_scan=0，仅徒增每条 INSERT 的索引页随机 I/O（慢存储下被放大）。过滤/分组场景由
    # (tenant_id, created_at) 复合索引 + 时间窗 BRIN 覆盖。删除以降低写放大。
    op.drop_index(
        "ix_gateway_request_logs_capability",
        table_name="gateway_request_logs",
        if_exists=True,
    )
    op.drop_index(
        "ix_gateway_request_logs_client_type",
        table_name="gateway_request_logs",
        if_exists=True,
    )


def downgrade() -> None:
    op.create_index(
        "ix_gateway_request_logs_client_type",
        "gateway_request_logs",
        ["client_type"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_gateway_request_logs_capability",
        "gateway_request_logs",
        ["capability"],
        unique=False,
        if_not_exists=True,
    )
