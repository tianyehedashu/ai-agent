"""migrate user_models rows into personal team gateway_models

Revision ID: 20260515_um_data
Revises: 20260515_gm_lum
Create Date: 2026-05-15
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from alembic import op

revision: str = "20260515_um_data"
down_revision: str | None = "20260515_gm_lum"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


async def _run_data_migration() -> None:
    from bootstrap.config import settings
    from domains.gateway.application.user_models_migration import (
        migrate_user_models_to_personal_gateway,
    )
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as session:
            async with session.begin():
                await migrate_user_models_to_personal_gateway(session)
    finally:
        await engine.dispose()


def upgrade() -> None:
    asyncio.run(_run_data_migration())


def downgrade() -> None:
    """数据迁移不可逆：gateway_models 行与 user 凭据需人工回滚。"""
