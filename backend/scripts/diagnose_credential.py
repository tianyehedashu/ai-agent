"""诊断凭据数据：查看 taoqi-kimi 凭据的 created_by_user_id 等字段。

使用方法:
    uv run python -m scripts.diagnose_credential
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
from domains.tenancy.infrastructure.models.team import TeamMember
from libs.db.database import get_db_session, init_db


async def diagnose() -> None:
    await init_db()
    async with get_db_session() as session:
        # 查找 taoqi-kimi 凭据
        stmt = select(ProviderCredential).where(ProviderCredential.name.ilike("%taoqi-kimi%"))
        result = await session.execute(stmt)
        credentials = list(result.scalars().all())

        if not credentials:
            print("未找到 taoqi-kimi 凭据")
            # 查看所有凭据
            all_stmt = select(ProviderCredential)
            all_result = await session.execute(all_stmt)
            all_creds = list(all_result.scalars().all())
            print(f"\n所有凭据 ({len(all_creds)} 条):")
            for c in all_creds:
                print(
                    f"  id={c.id} name={c.name} scope={c.scope} "
                    f"tenant_id={c.tenant_id} created_by_user_id={c.created_by_user_id}"
                )
            return

        print(f"找到 {len(credentials)} 条 taoqi-kimi 凭据:")
        for c in credentials:
            print(f"  id: {c.id}")
            print(f"  name: {c.name}")
            print(f"  provider: {c.provider}")
            print(f"  scope: {c.scope}")
            print(f"  tenant_id: {c.tenant_id}")
            print(f"  created_by_user_id: {c.created_by_user_id}")
            print(f"  is_active: {c.is_active}")
            print(f"  created_at: {c.created_at}")

            # 查看该团队的成员
            if c.tenant_id:
                member_stmt = select(TeamMember).where(TeamMember.team_id == c.tenant_id)
                member_result = await session.execute(member_stmt)
                members = list(member_result.scalars().all())
                print(f"\n  团队 {c.tenant_id} 的成员 ({len(members)} 条):")
                for m in members:
                    print(f"    user_id={m.user_id} role={m.role} created_at={m.created_at}")

        # 查看所有 created_by_user_id 为 NULL 的团队凭据
        null_stmt = select(ProviderCredential).where(
            ProviderCredential.tenant_id.isnot(None),
            ProviderCredential.created_by_user_id.is_(None),
        )
        null_result = await session.execute(null_stmt)
        null_creds = list(null_result.scalars().all())
        print(f"\ncreated_by_user_id 仍为 NULL 的团队凭据（应运行迁移 20260619_tccb 回填）({len(null_creds)} 条):")
        for c in null_creds:
            print(f"  id={c.id} name={c.name} scope={c.scope} tenant_id={c.tenant_id}")


if __name__ == "__main__":
    asyncio.run(diagnose())
