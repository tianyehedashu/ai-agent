#!/usr/bin/env python3
"""从 gateway_request_logs 回填 gateway_metrics_hourly（按天窗口覆盖写）。"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from domains.gateway.infrastructure.repositories.metrics_rollup_repository import (
    GatewayMetricsRollupRepository,
    RollupUpsertMode,
)
from libs.db.database import get_session_context
from libs.db.orm_registry import register_all_orm_models


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill gateway_metrics_hourly from request logs")
    parser.add_argument("--days", type=int, default=30, help="回填最近 N 天（默认 30）")
    parser.add_argument(
        "--until",
        type=str,
        default=None,
        help="结束时刻 ISO8601（默认当前 UTC 整点）",
    )
    return parser.parse_args()


async def _run(days: int, until: datetime) -> None:
    register_all_orm_models()
    since = until - timedelta(days=days)
    cursor = since.replace(hour=0, minute=0, second=0, microsecond=0)
    while cursor < until:
        window_end = min(cursor + timedelta(days=1), until)
        async with get_session_context() as session:
            repo = GatewayMetricsRollupRepository(session)
            count = await repo.rollup_window(
                cursor,
                window_end,
                mode=RollupUpsertMode.REPLACE,
            )
            print(f"backfill [{cursor.isoformat()}, {window_end.isoformat()}): {count} rows")
        cursor = window_end


def main() -> None:
    args = _parse_args()
    until = (
        datetime.fromisoformat(args.until).astimezone(UTC)
        if args.until
        else datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    )
    asyncio.run(_run(args.days, until))


if __name__ == "__main__":
    main()
