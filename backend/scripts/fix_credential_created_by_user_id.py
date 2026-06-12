"""修复 provider_credentials.created_by_user_id 为 NULL 的历史数据。

使用方法:
    uv run python -m scripts.fix_credential_created_by_user_id
"""

from __future__ import annotations

import asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
from domains.tenancy.infrastructure.models.team import TeamMember
from libs.db.session import get_db_session


async def fix_credential_created_by_user_id() -> None:
    """填充团队凭据中 created_by_user_id 为 NULL 的记录。

    逻辑：选择团队中最早加入的管理员或成员作为创建者
    """
    async with get_db_session() as session:
        # 查询所有 created_by_user_id 为 NULL 的团队凭据
        stmt = select(ProviderCredential).where(
            ProviderCredential.tenant_id.isnot(None),
            ProviderCredential.scope.is_(None),
            ProviderCredential.created_by_user_id.is_(None),
        )
        result = await session.execute(stmt)
        credentials = list(result.scalars().all())

        if not credentials:
            print("没有需要修复的凭据")
            return

        print(f"发现 {len(credentials)} 条需要修复的凭据")
        fixed_count = 0

        for cred in credentials:
            # 查找团队中最早加入的成员
            member_stmt = (
                select(TeamMember)
                .where(
                    TeamMember.team_id == cred.tenant_id,
                    TeamMember.role.in_(["admin", "member"]),
                )
                .order_by(TeamMember.created_at.asc())
                .limit(1)
            )
            member_result = await session.execute(member_stmt)
            earliest_member = member_result.scalar_one_or_none()

            if earliest_member:
                # 更新 created_by_user_id
                update_stmt = (
                    update(ProviderCredential)
                    .where(ProviderCredential.id == cred.id)
                    .values(created_by_user_id=earliest_member.user_id)
                )
                await session.execute(update_stmt)
                fixed_count += 1
                print(f"修复凭据 {cred.id} ({cred.name}) -> {earliest_member.user_id}")
            else:
                print(f"警告：凭据 {cred.id} ({cred.name}) 所在团队未找到成员")

        await session.commit()
        print(f"完成！已修复 {fixed_count}/{len(credentials)} 条凭据")


if __name__ == "__main__":
    asyncio.run(fix_credential_created_by_user_id())
