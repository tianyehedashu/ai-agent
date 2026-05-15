"""migrate user_models rows into personal team gateway_models

Revision ID: 20260515_um_data
Revises: 20260515_gm_lum
Create Date: 2026-05-15
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "20260515_um_data"
down_revision: str | None = "20260515_gm_lum"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


async def _run_data_migration() -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from bootstrap.config import settings
    from domains.gateway.application.user_models_migration import (
        migrate_user_models_to_personal_gateway,
    )

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as session, session.begin():
            await migrate_user_models_to_personal_gateway(session)
    finally:
        await engine.dispose()


def upgrade() -> None:
    """Alembic online 在 async 引擎的 run_sync 内调用 upgrade，不可再嵌套 asyncio.run。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_run_data_migration())
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, _run_data_migration()).result()


def downgrade() -> None:
    """数据迁移不可逆：gateway_models 行与 user 凭据需人工回滚。"""
