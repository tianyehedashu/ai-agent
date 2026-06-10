"""回填历史成员护栏行的 tenant_id（修复管理面不可见的数据黑洞）

Revision ID: 20260615_gbtb
Revises: 20260614_oaipfx
Create Date: 2026-06-15

迁移 ``20260612_gbt`` 为成员总量/模型护栏（``target_kind=user`` 且 ``credential_id IS NULL``）
新增 ``tenant_id`` 列但未回填，导致历史 ``tenant_id IS NULL`` 行：

- 管理面列表不可见（``member_user_budget_visible_in_team`` 要求 ``tenant_id == team_id``）；
- 热路径不再匹配（plan 坐标按计费团队填充 ``tenant_id``）；
- 因不可见也无法经 API 删除或覆盖——成为数据黑洞。

本迁移按确定性规则回填：每个成员取其所属**活跃**团队中「shared 优先、加入最早」
的一个作为护栏所属团队；若该团队下已有同坐标新行（管理员已重建），则历史行已被
取代，直接删除。无任何活跃团队成员资格的行保持 NULL（不可达，留待人工清理）。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260615_gbtb"
down_revision: str | None = "20260614_oaipfx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 每个 user 选定一个回填团队：shared 优先、加入最早、team_id 兜底排序保证确定性。
_PICKED_TEAM_CTE = """
WITH picked AS (
    SELECT DISTINCT ON (m.user_id)
        m.user_id,
        m.team_id
    FROM gateway_team_members m
    JOIN gateway_teams t ON t.id = m.team_id
    WHERE t.is_active IS TRUE
    ORDER BY m.user_id, (t.kind = 'shared') DESC, m.created_at ASC, m.team_id
)
"""


def upgrade() -> None:
    # 1. 选定团队下已存在同坐标新行（管理员已重建）→ 历史行已被取代，删除。
    op.execute(
        _PICKED_TEAM_CTE
        + """
        DELETE FROM gateway_budgets b
        USING picked p
        WHERE b.target_kind = 'user'
          AND b.credential_id IS NULL
          AND b.tenant_id IS NULL
          AND b.target_id = p.user_id
          AND EXISTS (
              SELECT 1 FROM gateway_budgets x
              WHERE x.target_kind = 'user'
                AND x.target_id = b.target_id
                AND x.credential_id IS NULL
                AND x.tenant_id = p.team_id
                AND x.period = b.period
                AND x.model_name IS NOT DISTINCT FROM b.model_name
          )
        """
    )

    # 2. 其余历史行回填到选定团队，恢复管理面可见与热路径匹配。
    op.execute(
        _PICKED_TEAM_CTE
        + """
        UPDATE gateway_budgets b
        SET tenant_id = p.team_id
        FROM picked p
        WHERE b.target_kind = 'user'
          AND b.credential_id IS NULL
          AND b.tenant_id IS NULL
          AND b.target_id = p.user_id
        """
    )


def downgrade() -> None:
    # 数据回填不可逆（无法区分回填行与管理员新建行），保持现状。
    pass
