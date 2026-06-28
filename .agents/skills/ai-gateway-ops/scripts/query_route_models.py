#!/usr/bin/env python3
"""查询 gateway_routes 路由的 primary_models 配置，并关联 gateway_models 显示状态。

用途：
  - 验证路由内的模型列表与 enabled 状态（数据库 SSOT，而非日志推断）
  - 检测 primary_models 中的重复项（重复会导致 deployment 权重翻倍）

环境变量:
  GATEWAY_DB_DSN  PostgreSQL 连接串（默认连生产 ai_agent 库，仅只读查询）

用法:
  python .agents/skills/ai-gateway-ops/scripts/query_route_models.py
  python .agents/skills/ai-gateway-ops/scripts/query_route_models.py --routes volcano-text-pool,volcano-vision-pool
  python .agents/skills/ai-gateway-ops/scripts/query_route_models.py --check-dups

依赖: asyncpg (backend venv 已自带)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback

import asyncpg

DEFAULT_DSN = "postgresql://pgroot:G6J8jvvoD3G3EE@prod-giimall-pg.rwlb.rds.aliyuncs.com:5432/ai_agent"
DEFAULT_ROUTES = "volcano-text-pool,volcano-vision-pool"


async def main() -> int:
    ap = argparse.ArgumentParser(description="查询路由模型配置 + 重复检测")
    ap.add_argument(
        "--routes",
        default=DEFAULT_ROUTES,
        help=f"逗号分隔的路由名（默认 {DEFAULT_ROUTES}）",
    )
    ap.add_argument(
        "--check-dups",
        action="store_true",
        help="只检测重复项并退出码反映结果（CI 友好）",
    )
    args = ap.parse_args()

    dsn = __import__("os").environ.get("GATEWAY_DB_DSN", DEFAULT_DSN)
    route_names = [r.strip() for r in args.routes.split(",") if r.strip()]

    try:
        conn = await asyncpg.connect(dsn)
    except Exception:
        traceback.print_exc(file=sys.stdout)
        return 2

    try:
        rows = await conn.fetch(
            "SELECT id, tenant_id, virtual_model, primary_models "
            "FROM gateway_routes WHERE virtual_model = ANY($1::text[]) "
            "ORDER BY virtual_model",
            route_names,
        )
        if not rows:
            print(f"未找到路由: {route_names}", file=sys.stderr)
            return 1

        has_dup = False
        for r in rows:
            vm = r["virtual_model"]
            pm = list(r["primary_models"])
            print(f"\n=== {vm} ===")
            print(f"  route_id  = {r['id']}")
            print(f"  tenant_id = {r['tenant_id']}")
            print(f"  count     = {len(pm)}")

            # 重复检测
            seen: dict[str, int] = {}
            dups: list[tuple[int, int, str]] = []
            for i, entry in enumerate(pm):
                if entry in seen:
                    dups.append((seen[entry], i, entry))
                else:
                    seen[entry] = i
            if dups:
                has_dup = True
                print(f"  DUPLICATES ({len(dups)}):")
                for first_idx, dup_idx, entry in dups:
                    print(f"    idx[{first_idx}] == idx[{dup_idx}] == {entry}")
            else:
                print("  no duplicates")

            if args.check_dups:
                continue

            # 关联 gateway_models 显示状态
            print(f"  --- models ---")
            for entry in pm:
                model_name = entry.split("/", 1)[-1] if "/" in entry else entry
                m = await conn.fetchrow(
                    "SELECT name, real_model, enabled, capability, provider "
                    "FROM gateway_models WHERE real_model LIKE $1",
                    f"volcengine/{model_name}",
                )
                if m:
                    flag = "OK" if m["enabled"] else "DISABLED"
                    print(
                        f"    [{flag}] {m['name']:45} real={m['real_model']:50} cap={m['capability']}"
                    )
                else:
                    print(f"    [NOT FOUND] {entry}")
    finally:
        await conn.close()

    if args.check_dups and has_dup:
        print("\nFAIL: 存在重复配置", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
