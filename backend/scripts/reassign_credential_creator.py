"""将 huoshan-common 凭据及其绑定模型的 created_by 调整为指定用户。

用法（本地 / Pod 内）::

    uv run python -m scripts.reassign_credential_creator \\
        --credential-name huoshan-common \\
        --creator-email giikin-19@giikin.sso

仅更新数据，不修改 schema。
"""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import text

from libs.db.database import get_session_context, init_db


async def reassign_credential_creator(
    *,
    credential_name: str,
    creator_email: str,
    dry_run: bool = True,
) -> None:
    await init_db()
    async with get_session_context() as session:
        user_row = (
            await session.execute(
                text("SELECT id, email FROM users WHERE email = :email"),
                {"email": creator_email.strip()},
            )
        ).mappings().first()
        if user_row is None:
            raise SystemExit(f"user not found: {creator_email}")

        cred_row = (
            await session.execute(
                text(
                    """
                    SELECT id, name, tenant_id, created_by_user_id
                    FROM provider_credentials
                    WHERE name = :name
                    """
                ),
                {"name": credential_name.strip()},
            )
        ).mappings().first()
        if cred_row is None:
            raise SystemExit(f"credential not found: {credential_name}")

        creator_id: UUID = user_row["id"]
        cred_id: UUID = cred_row["id"]
        model_count = (
            await session.execute(
                text(
                    """
                    SELECT count(*) FROM gateway_models
                    WHERE credential_id = :cred_id
                    """
                ),
                {"cred_id": cred_id},
            )
        ).scalar_one()

        print("credential:", dict(cred_row))
        print("new creator:", dict(user_row))
        print("bound gateway_models:", int(model_count))

        if dry_run:
            print("DRY-RUN: no changes written")
            return

        await session.execute(
            text(
                """
                UPDATE provider_credentials
                SET created_by_user_id = :creator_id, updated_at = NOW()
                WHERE id = :cred_id
                """
            ),
            {"creator_id": creator_id, "cred_id": cred_id},
        )
        result = await session.execute(
            text(
                """
                UPDATE gateway_models
                SET created_by_user_id = :creator_id, updated_at = NOW()
                WHERE credential_id = :cred_id
                """
            ),
            {"creator_id": creator_id, "cred_id": cred_id},
        )
        await session.commit()
        print(f"updated credential + {result.rowcount} gateway_models")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reassign team credential creator and bound models")
    parser.add_argument("--credential-name", required=True)
    parser.add_argument("--creator-email", required=True)
    parser.add_argument("--confirm", action="store_true", help="Apply changes (default: dry-run)")
    args = parser.parse_args()
    asyncio.run(
        reassign_credential_creator(
            credential_name=args.credential_name,
            creator_email=args.creator_email,
            dry_run=not args.confirm,
        )
    )


if __name__ == "__main__":
    main()
