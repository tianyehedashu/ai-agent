"""migrate user_models rows into personal team gateway_models

Revision ID: 20260515_um_data
Revises: 20260515_gm_lum
Create Date: 2026-05-15
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "20260515_um_data"
down_revision: str | None = "20260515_gm_lum"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """在 Alembic 同一连接上执行数据迁移，禁止再开第二个 DB 连接（会与 DDL 长事务死锁）。"""
    from sqlalchemy.orm import Session

    from domains.gateway.application.user_models_migration import (
        migrate_user_models_to_personal_gateway_sync,
    )

    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        migrate_user_models_to_personal_gateway_sync(session)
        session.flush()
    finally:
        session.close()


def downgrade() -> None:
    """数据迁移不可逆：gateway_models 行与 user 凭据需人工回滚。"""
