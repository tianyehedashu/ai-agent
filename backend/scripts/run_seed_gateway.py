"""初始化 DB 并同步 Gateway 目录种子（供本地/E2E 使用）。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


async def main() -> int:
    from domains.gateway.application.gateway_catalog_seed import default_seed_path
    from libs.db.database import init_db
    from scripts.seed_gateway_models import _run

    await init_db()
    return await _run(seed_path=default_seed_path(), reload_router=False)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
