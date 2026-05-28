#!/usr/bin/env python3
"""幂等将 gateway-catalog.seed.json 同步到 system_gateway_models。"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

# 保证 backend 根在 sys.path
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


async def _run(*, seed_path: Path | None, reload_router: bool) -> int:
    from domains.gateway.application.config_catalog_sync import sync_gateway_catalog_from_seed
    from domains.gateway.application.gateway_catalog_seed import default_seed_path
    from domains.gateway.infrastructure.router_singleton import reload_router
    from libs.db.database import get_session_context

    path = seed_path or default_seed_path()
    if not path.is_file():
        print(f"Seed file not found: {path}", file=sys.stderr)
        return 1

    async with get_session_context() as session:
        stats = await sync_gateway_catalog_from_seed(session, seed_path=path)
        await session.commit()
        if reload_router:
            await reload_router(session)
    print("Gateway catalog seed sync:", stats)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Gateway system model catalog from JSON")
    parser.add_argument(
        "--seed",
        type=Path,
        default=None,
        help="Path to gateway-catalog.seed.json (default: backend/seeds/gateway-catalog.seed.json)",
    )
    parser.add_argument(
        "--reload-router",
        action="store_true",
        help="Reload LiteLLM Router after sync",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(seed_path=args.seed, reload_router=args.reload_router)))


if __name__ == "__main__":
    main()
