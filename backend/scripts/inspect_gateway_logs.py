"""快速排查：看最近 N 条 ``gateway_request_logs``，验证 Gateway 调用日志是否真在落库。

适用场景：
- 用户做了对话但前端 dashboard / `/api/v1/gateway/logs` 看不到记录；
- 想确认是「LiteLLM CustomLogger 根本没触发」还是「写库被吞 / 看的不是这条」。

使用：
    uv run python scripts/inspect_gateway_logs.py            # 看最近 20 条
    uv run python scripts/inspect_gateway_logs.py --limit 5  # 看最近 5 条
    uv run python scripts/inspect_gateway_logs.py --user <user_id>   # 仅本用户
    uv run python scripts/inspect_gateway_logs.py --since-minutes 10 # 最近 10 分钟
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import desc, select  # pylint: disable=wrong-import-position

from domains.gateway.infrastructure.models.request_log import (  # pylint: disable=wrong-import-position
    GatewayRequestLog,
)
from libs.db.database import (  # pylint: disable=wrong-import-position
    get_session_context,
    init_db,
)


async def run(args: argparse.Namespace) -> None:
    await init_db()
    since = datetime.now(UTC) - timedelta(minutes=args.since_minutes)

    async with get_session_context() as session:
        stmt = (
            select(GatewayRequestLog)
            .where(GatewayRequestLog.created_at >= since)
            .order_by(desc(GatewayRequestLog.created_at))
            .limit(args.limit)
        )
        if args.user:
            stmt = stmt.where(GatewayRequestLog.user_id == uuid.UUID(args.user))
        if args.team:
            stmt = stmt.where(GatewayRequestLog.team_id == uuid.UUID(args.team))

        rows = (await session.execute(stmt)).scalars().all()

        count_stmt = select(GatewayRequestLog).where(GatewayRequestLog.created_at >= since)
        total = len((await session.execute(count_stmt)).scalars().all())

    print(f"== gateway_request_logs (last {args.since_minutes} min) ==")
    print(f"matched rows: {len(rows)}  /  total in window: {total}")
    if not rows:
        print("(没有任何记录 —— 说明 Gateway 回调没有触发，或写库被吞)")
        return

    for r in rows:
        print(
            "  - "
            f"{r.created_at.isoformat()}  "
            f"status={r.status}  "
            f"cap={r.capability}  "
            f"model={r.real_model}  "
            f"provider={r.provider}  "
            f"tokens={r.input_tokens}/{r.output_tokens}  "
            f"cost=${float(r.cost_usd or 0):.6f}  "
            f"team={r.team_id}  user={r.user_id}  vkey={r.vkey_id}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect recent gateway_request_logs rows")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--since-minutes", type=int, default=60)
    parser.add_argument("--user", type=str, default=None, help="filter by user_id (uuid)")
    parser.add_argument("--team", type=str, default=None, help="filter by team_id (uuid)")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
