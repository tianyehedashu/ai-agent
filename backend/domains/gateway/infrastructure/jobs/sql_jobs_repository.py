"""Gateway 后台任务所需的原始 SQL（请求日志分区维护）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


_PARTITION_NAME = re.compile(r"^gateway_request_logs_y(\d{4})m(\d{2})$")
_SAFE_SQL_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")


def month_partition_upper_bound(year: int, month: int) -> datetime:
    if month == 12:
        return datetime(year + 1, 1, 1, tzinfo=UTC)
    return datetime(year, month + 1, 1, tzinfo=UTC)


class GatewaySqlJobsRepository:
    """请求日志分区上的 SQL 写路径（供 application/jobs 编排调用）。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_request_log_partition(self, year: int, month: int) -> None:
        start = datetime(year, month, 1, tzinfo=UTC)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=UTC)
        else:
            end = datetime(year, month + 1, 1, tzinfo=UTC)
        partition_name = f"gateway_request_logs_y{year:04d}m{month:02d}"
        await self._session.execute(
            text(
                f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF gateway_request_logs
            FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')
            """
            )
        )
        await self._session.commit()

    async def drop_expired_request_log_partitions(self, retention_days: int) -> int:
        """删除「分区上界」不晚于 cutoff 的整月子分区（数据全部早于保留窗口）。"""
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        stmt = text(
            """
        SELECT n.nspname AS schema_name, c.relname AS partition_name
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        JOIN pg_class p ON p.oid = i.inhparent
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE p.relname = 'gateway_request_logs'
        """
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        dropped = 0
        for row in rows:
            schema_name = str(row["schema_name"])
            partition_name = str(row["partition_name"])
            if not _SAFE_SQL_IDENT.match(schema_name):
                continue
            match = _PARTITION_NAME.match(partition_name)
            if not match:
                continue
            year, month = int(match.group(1)), int(match.group(2))
            upper = month_partition_upper_bound(year, month)
            if upper > cutoff:
                continue
            await self._session.execute(
                text(f'DROP TABLE IF EXISTS "{schema_name}"."{partition_name}"')
            )
            dropped += 1
        return dropped


# 测试与 jobs 模块向后兼容的模块级别名
_PARTITION_NAME_RE = _PARTITION_NAME

__all__ = [
    "_PARTITION_NAME_RE",
    "_SAFE_SQL_IDENT",
    "GatewaySqlJobsRepository",
    "month_partition_upper_bound",
]
