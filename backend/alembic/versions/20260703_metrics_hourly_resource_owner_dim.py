"""gateway_metrics_hourly: resource_owner_user_id 纳入唯一约束维度

Revision ID: 20260703_mhro
Revises: 20260702_rtg
Create Date: 2026-07-03

委派（跨团队共享路由）下，``resource_owner_user_id`` 标识"共享出资源的人"。此前小时级
rollup 既不按它分组、也不在唯一约束里，而用 ``max()`` 取值——当同一消费团队下两条不同
owner 的共享路由引用同一底层（团队作用域）模型/凭据时，会塌缩到同一聚合行并任意压成
一个 owner，导致按提供方维度的归因失真。

将 ``resource_owner_user_id`` 纳入 ``uq_gateway_metrics_hourly_dim``（紧随 ``user_id``），
使 rollup 按其分组。仅令唯一键更细，不会与既有行产生冲突（无需去重）。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260703_mhro"
down_revision: str | None = "20260702_rtg"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "uq_gateway_metrics_hourly_dim"
_DIMS_WITH_OWNER = (
    "bucket_at, tenant_id, user_id, resource_owner_user_id, vkey_id, credential_id, "
    "entitlement_plan_id, provider_plan_id, provider, model_key, capability"
)
_DIMS_LEGACY = (
    "bucket_at, tenant_id, user_id, vkey_id, credential_id, "
    "entitlement_plan_id, provider_plan_id, provider, model_key, capability"
)


def upgrade() -> None:
    op.execute(f"ALTER TABLE gateway_metrics_hourly DROP CONSTRAINT {CONSTRAINT}")
    op.execute(
        f"ALTER TABLE gateway_metrics_hourly "
        f"ADD CONSTRAINT {CONSTRAINT} UNIQUE ({_DIMS_WITH_OWNER})"
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE gateway_metrics_hourly DROP CONSTRAINT {CONSTRAINT}")
    op.execute(
        f"ALTER TABLE gateway_metrics_hourly "
        f"ADD CONSTRAINT {CONSTRAINT} UNIQUE ({_DIMS_LEGACY})"
    )
