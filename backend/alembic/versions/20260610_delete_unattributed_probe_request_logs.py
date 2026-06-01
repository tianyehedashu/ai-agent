"""Delete gateway_request_logs rows from unattributed model connectivity probes

Revision ID: 20260610_del_probe_logs
Revises: 20260609_giikin_uid
Create Date: 2026-05-29

探活直连 LiteLLM 未注入 gateway_* metadata，产生 user_id/credential_id/tenant_id
皆为 NULL 的垃圾行；新请求由 probe_litellm_attribution 修复。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260610_del_probe_logs"
down_revision: str | None = "20260609_giikin_uid"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM gateway_request_logs
        WHERE user_id IS NULL
          AND credential_id IS NULL
          AND tenant_id IS NULL
        """
    )


def downgrade() -> None:
    """数据清理不可回滚。"""

