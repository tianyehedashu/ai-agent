"""enforce one active system vkey per team via partial unique index

Revision ID: 20260513_uvk
Revises: 20260508_gw
Create Date: 2026-05-13

并发场景下 ``LLMGateway`` 同时启动标题生成 + chat 主流，会让两路调用同时
进入 ``VirtualKeyRepository.get_or_create_system_key``。原实现只有应用层的
read-modify-write，没有数据库唯一约束保护，会留下两条
``is_system=True AND is_active=True`` 的副本，并让随后的
``scalar_one_or_none()`` 抛 ``MultipleResultsFound`` —— 上层
``GatewayBridge.chat_completion`` 被回退到直连 LiteLLM，
``gateway_request_logs`` 写入时彻底丢失 ``team_id/user_id/vkey_id`` 归因，
最终让 dashboard / ``/api/v1/gateway/dashboard/summary`` 永远聚合到 0。

修复有两层：

1. （此 migration）在 ``gateway_virtual_keys`` 上创建部分唯一索引：
   ``UNIQUE (team_id) WHERE is_system AND is_active``，从 schema 层杜绝
   并发 race 留下重复行的可能。
2. （应用层）``VirtualKeyRepository.get_or_create_system_key`` 改用
   PostgreSQL ``INSERT ... ON CONFLICT DO NOTHING RETURNING``，让 upsert
   行为完全由 DB 唯一索引保证，不再做 read-then-write 防御逻辑。

为了避免升级到包含此约束的 schema 时旧数据库里残留的重复行卡住 migration，
本迁移先把每个 team 多余的 ``is_system=True AND is_active=True`` 行下沉成
``is_active=False``（保留最早创建的一条作为正本），随后再建索引。这一步是
**一次性 schema 清理**（不是运行期防御），完成后未来不会再有重复行。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260513_uvk"
down_revision: str | None = "20260508_gw"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEX_NAME = "uq_gateway_virtual_keys_team_id_active_system"


def upgrade() -> None:
    # 一次性清理已存在的重复行（保留 created_at 最早的一条为正本）。
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY team_id
                    ORDER BY created_at ASC, id ASC
                ) AS rn
            FROM gateway_virtual_keys
            WHERE is_system = TRUE
              AND is_active = TRUE
        )
        UPDATE gateway_virtual_keys gvk
        SET is_active = FALSE,
            updated_at = NOW()
        FROM ranked
        WHERE gvk.id = ranked.id
          AND ranked.rn > 1
        """
    )

    op.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME}
        ON gateway_virtual_keys (team_id)
        WHERE is_system = TRUE AND is_active = TRUE
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
