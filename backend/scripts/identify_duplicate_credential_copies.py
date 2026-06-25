"""识别同 api_key 指纹的多份复制凭据（只读建议）。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections import defaultdict

from sqlalchemy import select

from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
from libs.db.database import get_session_context


def _fingerprint(row: ProviderCredential) -> str:
    material = f"{row.provider}|{row.api_key_encrypted}|{row.api_base or ''}"
    return hashlib.sha256(material.encode()).hexdigest()[:16]


async def _run() -> int:
    groups: dict[str, list[tuple[str, str, str | None]]] = defaultdict(list)
    async with get_session_context() as session:
        result = await session.execute(select(ProviderCredential))
        rows = list(result.scalars().all())
    for row in rows:
        fp = _fingerprint(row)
        scope = row.scope or "team"
        tenant = str(row.tenant_id) if row.tenant_id else None
        groups[fp].append((scope, str(row.id), tenant))
    dupes = {fp: items for fp, items in groups.items() if len(items) > 1}
    print(json.dumps({"duplicate_fingerprint_groups": dupes}, indent=2, ensure_ascii=False))
    print(
        "\n建议：同指纹组可合并为 resource-grants 共享，而非复制 credential 行。",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
