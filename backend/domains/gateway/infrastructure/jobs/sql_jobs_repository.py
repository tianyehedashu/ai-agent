"""Gateway 后台任务所需的原始 SQL（分区维护、Plan 生命周期）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from typing import TYPE_CHECKING, Any

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
    """分区与 Plan 表上的 SQL 写路径（供 application/jobs 编排调用）。"""

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

    async def renew_plan_with_quotas(
        self,
        *,
        table: str,
        quota_table: str,
        plan_id: Any,
        valid_from: datetime,
        valid_until: datetime,
    ) -> None:
        """续期：复制 plan 行 + 全部 quota 行至新 plan_id。"""
        if table == "entitlement_plans":
            plan_sql = text(
                """
            INSERT INTO entitlement_plans (
                id, created_at, updated_at,
                scope, scope_id, label,
                included_models, included_capabilities,
                valid_from, valid_until,
                is_active, auto_renew,
                notes, extra
            )
            SELECT gen_random_uuid(), NOW(), NOW(),
                   p.scope, p.scope_id, p.label,
                   p.included_models, p.included_capabilities,
                   :valid_from, :valid_until,
                   TRUE, p.auto_renew,
                   p.notes, p.extra
            FROM entitlement_plans p
            WHERE p.id = :plan_id
            RETURNING id
            """
            )
        else:
            plan_sql = text(
                """
            INSERT INTO provider_plans (
                id, created_at, updated_at,
                credential_id, real_model, label,
                valid_from, valid_until,
                is_active, auto_renew,
                notes, extra
            )
            SELECT gen_random_uuid(), NOW(), NOW(),
                   p.credential_id, p.real_model, p.label,
                   :valid_from, :valid_until,
                   TRUE, p.auto_renew,
                   p.notes, p.extra
            FROM provider_plans p
            WHERE p.id = :plan_id
            RETURNING id
            """
            )
        new_plan_id = (
            await self._session.execute(
                plan_sql,
                {"valid_from": valid_from, "valid_until": valid_until, "plan_id": plan_id},
            )
        ).scalar_one_or_none()
        if new_plan_id is None:
            return
        if quota_table == "entitlement_plan_quotas":
            quota_sql = text(
                """
            INSERT INTO entitlement_plan_quotas (
                id, created_at, updated_at,
                plan_id, label, window_seconds, reset_strategy,
                limit_usd, limit_tokens, limit_requests,
                unit_price_usd_per_token, unit_price_usd_per_request
            )
            SELECT gen_random_uuid(), NOW(), NOW(),
                   :new_plan_id, q.label, q.window_seconds, q.reset_strategy,
                   q.limit_usd, q.limit_tokens, q.limit_requests,
                   q.unit_price_usd_per_token, q.unit_price_usd_per_request
            FROM entitlement_plan_quotas q
            WHERE q.plan_id = :plan_id
            """
            )
        else:
            quota_sql = text(
                """
            INSERT INTO provider_plan_quotas (
                id, created_at, updated_at,
                plan_id, label, window_seconds, reset_strategy,
                limit_usd, limit_tokens, limit_requests
            )
            SELECT gen_random_uuid(), NOW(), NOW(),
                   :new_plan_id, q.label, q.window_seconds, q.reset_strategy,
                   q.limit_usd, q.limit_tokens, q.limit_requests
            FROM provider_plan_quotas q
            WHERE q.plan_id = :plan_id
            """
            )
        await self._session.execute(
            quota_sql,
            {"new_plan_id": new_plan_id, "plan_id": plan_id},
        )

    async def process_plan_lifecycle_for_table(
        self, *, table: str, quota_table: str
    ) -> tuple[int, int]:
        """单张 plan 表 lifecycle：过期活跃行下线 +（auto_renew 时）顺延。返回 (deactivated, renewed)。"""
        now = datetime.now(UTC)
        rows = (
            (
                await self._session.execute(
                    text(
                        f"""
                SELECT id, valid_from, valid_until, auto_renew
                FROM {table}
                WHERE is_active = TRUE AND valid_until <= :now
                """
                    ),
                    {"now": now},
                )
            )
            .mappings()
            .all()
        )
        deactivated = 0
        renewed = 0
        for row in rows:
            plan_id = row["id"]
            await self._session.execute(
                text(f"UPDATE {table} SET is_active = FALSE, updated_at = NOW() WHERE id = :id"),
                {"id": plan_id},
            )
            deactivated += 1
            if not row["auto_renew"]:
                continue
            old_from: datetime = row["valid_from"]
            old_until: datetime = row["valid_until"]
            duration = old_until - old_from
            new_from = old_until
            new_until = old_until + duration
            await self.renew_plan_with_quotas(
                table=table,
                quota_table=quota_table,
                plan_id=plan_id,
                valid_from=new_from,
                valid_until=new_until,
            )
            renewed += 1
        return deactivated, renewed


# 测试与 jobs 模块向后兼容的模块级别名
_PARTITION_NAME_RE = _PARTITION_NAME

__all__ = [
    "_PARTITION_NAME_RE",
    "_SAFE_SQL_IDENT",
    "GatewaySqlJobsRepository",
    "month_partition_upper_bound",
]
