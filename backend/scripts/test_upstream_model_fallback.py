#!/usr/bin/env python3
"""探测网关出站上游模型与 fallback 链路。

用法（在 backend 目录）：
  uv run python scripts/test_upstream_model_fallback.py --token sk-gw-...

环境变量（可选，默认读 backend/.env）：
  GATEWAY_BASE_URL   如 http://gateway.giimallai.com
  GATEWAY_TOKEN      sk-gw-* 虚拟 Key
  GATEWAY_TEAM_ID    平台 sk-* 时传 X-Team-Id；sk-gw-* 可省略
  DATABASE_URL       配置后可从 gateway_request_logs 拉取 litellm 归因

示例：
  uv run python scripts/test_upstream_model_fallback.py \\
    --base-url http://gateway.giimallai.com \\
    --token sk-gw-xxx \\
    --models glm-5.1,MiniMax-M2.5,glm-5-1(pro)
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

from dotenv import load_dotenv
import httpx

_BACKEND = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND / ".env", override=False)

DEFAULT_MODELS = (
    "glm-5.1",
    "MiniMax-M2.5",
    "glm-5-1(pro)",
    "minimax-m2-5(pro)",
)


@dataclass(frozen=True, slots=True)
class ChatProbeResult:
    client_model: str
    http_status: int
    response_model: str | None
    response_id: str | None
    gateway_headers: dict[str, str]
    error_body: dict[str, Any] | None
    elapsed_ms: int


@dataclass(frozen=True, slots=True)
class LogAttribution:
    request_id: str | None
    route_name: str | None
    deployment_model_name: str | None
    real_model: str | None
    provider: str | None
    credential_name: str | None
    fallback_chain: list[str]
    litellm_model_name: str | None
    status: str | None
    created_at: datetime | None


def _openai_base(base_url: str) -> str:
    root = base_url.rstrip("/")
    return f"{root}/ai-agent/api/v1/openai/v1"


def _print_json(label: str, data: Any) -> None:
    print(f"\n[{label}]\n{json.dumps(data, ensure_ascii=False, indent=2, default=str)}")


def _gateway_timing_headers(headers: httpx.Headers) -> dict[str, str]:
    keys = (
        "x-gateway-preflight-ms",
        "x-gateway-upstream-ms",
        "x-gateway-timing",
        "x-ratelimit-remaining",
    )
    return {k: headers[k] for k in keys if k in headers}


async def _fetch_log_attribution(
    *,
    database_url: str,
    route_name: str,
    since: datetime,
) -> LogAttribution | None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url, echo=False)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT request_id, route_name, deployment_model_name, real_model,
                               provider, credential_name_snapshot, fallback_chain, status,
                               created_at,
                               metadata_extra->'hidden_params'->>'litellm_model_name'
                                   AS litellm_model_name
                        FROM gateway_request_logs
                        WHERE route_name = :route_name
                          AND created_at >= :since
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    ),
                    {"route_name": route_name, "since": since},
                )
            ).mappings().first()
            if row is None:
                return None
            fb = row.get("fallback_chain")
            return LogAttribution(
                request_id=row.get("request_id"),
                route_name=row.get("route_name"),
                deployment_model_name=row.get("deployment_model_name"),
                real_model=row.get("real_model"),
                provider=row.get("provider"),
                credential_name=row.get("credential_name_snapshot"),
                fallback_chain=list(fb) if isinstance(fb, list) else [],
                litellm_model_name=row.get("litellm_model_name"),
                status=row.get("status"),
                created_at=row.get("created_at"),
            )
    finally:
        await engine.dispose()


async def _audit_team_routes(*, database_url: str, team_id: str) -> list[dict[str, Any]]:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url, echo=False)
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        SELECT virtual_model, primary_models, fallbacks_general,
                               fallbacks_content_policy, fallbacks_context_window,
                               strategy, enabled
                        FROM gateway_routes
                        WHERE tenant_id = :tid
                        ORDER BY virtual_model
                        """
                    ),
                    {"tid": team_id},
                )
            ).mappings().all()
            return [dict(r) for r in rows]
    finally:
        await engine.dispose()


async def _audit_team_models(*, database_url: str, team_id: str) -> list[dict[str, Any]]:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url, echo=False)
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        SELECT name, real_model, provider, enabled,
                               credential_id::text AS credential_id
                        FROM gateway_models
                        WHERE tenant_id = :tid
                        ORDER BY name
                        """
                    ),
                    {"tid": team_id},
                )
            ).mappings().all()
            return [dict(r) for r in rows]
    finally:
        await engine.dispose()


def probe_chat(
    client: httpx.Client,
    *,
    openai_base: str,
    headers: dict[str, str],
    model: str,
    max_tokens: int,
) -> ChatProbeResult:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": f"reply with exactly: OK-{model}",
            },
        ],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    started = time.perf_counter()
    resp = client.post(f"{openai_base}/chat/completions", headers=headers, json=payload)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    error_body: dict[str, Any] | None = None
    response_model: str | None = None
    response_id: str | None = None
    if resp.headers.get("content-type", "").startswith("application/json"):
        try:
            body = resp.json()
            if isinstance(body, dict):
                if "error" in body:
                    err = body["error"]
                    error_body = err if isinstance(err, dict) else {"message": str(err)}
                else:
                    response_model = str(body.get("model")) if body.get("model") else None
                    response_id = str(body.get("id")) if body.get("id") else None
        except json.JSONDecodeError:
            pass

    return ChatProbeResult(
        client_model=model,
        http_status=resp.status_code,
        response_model=response_model,
        response_id=response_id,
        gateway_headers=_gateway_timing_headers(resp.headers),
        error_body=error_body,
        elapsed_ms=elapsed_ms,
    )


def _print_probe(result: ChatProbeResult) -> None:
    print(f"\n--- 客户端 model={result.client_model!r} ---")
    print(f"HTTP {result.http_status}  elapsed={result.elapsed_ms}ms")
    if result.gateway_headers:
        _print_json("gateway response headers", result.gateway_headers)
    if result.error_body is not None:
        _print_json("error", result.error_body)
        return
    print(f"response.model (上游回显): {result.response_model!r}")
    print(f"response.id: {result.response_id!r}")


def _print_attribution(attr: LogAttribution | None) -> None:
    if attr is None:
        print("\n[DB 日志] 未找到匹配行（采样/延迟或未配置 DATABASE_URL）")
        return
    _print_json(
        "DB gateway_request_logs 归因",
        {
            "request_id": attr.request_id,
            "created_at": attr.created_at,
            "status": attr.status,
            "route_name_客户端模型": attr.route_name,
            "deployment_model_name_部署": attr.deployment_model_name,
            "real_model_日志字段": attr.real_model,
            "litellm_model_name_上游实际": attr.litellm_model_name,
            "provider": attr.provider,
            "credential": attr.credential_name,
            "fallback_chain": attr.fallback_chain or [],
        },
    )


def _explain_fallback(routes: list[dict[str, Any]]) -> None:
    print("\n" + "=" * 72)
    print("Fallback 机制说明（本仓库实现）")
    print("=" * 72)
    print(
        """
1. LiteLLM Router fallback（general / content_policy / context_window）
   - 仅当团队配置了 gateway_routes 且 fallbacks_* 非空时生效
   - 由 router_singleton._routes_to_fallbacks 注入 Router
   - 失败时 metadata.gateway_fallback_chain 写入日志 fallback_chain 列

2. 无路由时（当前常见情况）
   - 单模型 deployment，无自动换模型
   - fallback_chain 为空列表「—」
   - Router 选不中 deployment 时走 is_router_model_miss；普通 vkey 不会 silent 换模型

3. 客户端 model 与注册名不一致时
   - LiteLLM 可能按 litellm_params.model（= real_model）匹配 deployment
   - 日志 route_name = 请求体 model；deployment_model_name = GatewayModel.name
"""
    )
    if not routes:
        print("当前团队 gateway_routes: (无) → 不会触发模型级 fallback")
        return
    print(f"当前团队 gateway_routes: {len(routes)} 条")
    for r in routes:
        print(
            f"  - virtual_model={r.get('virtual_model')!r} "
            f"primary={r.get('primary_models')} "
            f"fallbacks_general={r.get('fallbacks_general')} "
            f"enabled={r.get('enabled')}"
        )


async def _fetch_recent_logs_by_route(
    *,
    database_url: str,
    route_names: tuple[str, ...],
    limit_per_route: int = 2,
) -> list[dict[str, Any]]:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url, echo=False)
    out: list[dict[str, Any]] = []
    try:
        async with engine.connect() as conn:
            for name in route_names:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT request_id, created_at, route_name,
                                   deployment_model_name, real_model, status,
                                   fallback_chain,
                                   metadata_extra->'hidden_params'->>'litellm_model_name'
                                       AS litellm_model_name
                            FROM gateway_request_logs
                            WHERE route_name = :route_name
                            ORDER BY created_at DESC
                            LIMIT :lim
                            """
                        ),
                        {"route_name": name, "lim": limit_per_route},
                    )
                ).mappings().all()
                out.extend(dict(r) for r in rows)
    finally:
        await engine.dispose()
    return out


async def _async_main(args: argparse.Namespace) -> int:
    base_url = (args.base_url or os.getenv("GATEWAY_BASE_URL") or "http://127.0.0.1:8000").rstrip(
        "/"
    )
    team_id = (args.team_id or os.getenv("GATEWAY_TEAM_ID") or "").strip() or None
    database_url = (args.database_url or os.getenv("DATABASE_URL") or "").strip() or None
    token = (args.token or os.getenv("GATEWAY_TOKEN") or "").strip()
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    if args.db_audit_only:
        if not database_url:
            print("错误: --db-audit-only 需要 DATABASE_URL", file=sys.stderr)
            return 1
        if not team_id:
            print("错误: --db-audit-only 需要 --team-id", file=sys.stderr)
            return 1
        print("=" * 72)
        print("DB 审计：模型注册 / 路由 fallback / 近期日志")
        print("=" * 72)
        models_db = await _audit_team_models(database_url=database_url, team_id=team_id)
        routes_db = await _audit_team_routes(database_url=database_url, team_id=team_id)
        _print_json("gateway_models", models_db)
        _explain_fallback(routes_db)
        recent = await _fetch_recent_logs_by_route(
            database_url=database_url,
            route_names=tuple(models),
        )
        _print_json("近期日志样本 (按 route_name)", recent)
        return 0

    if not token:
        print("错误: 需要 --token 或环境变量 GATEWAY_TOKEN", file=sys.stderr)
        print("  仅查库可加: --db-audit-only --team-id <uuid>", file=sys.stderr)
        return 1

    openai_base = _openai_base(base_url)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if team_id:
        headers["X-Team-Id"] = team_id

    print("=" * 72)
    print("上游模型 + Fallback 探测")
    print("=" * 72)
    print(f"openai_base={openai_base}")
    print(f"token_prefix={token[:14]}...")
    if team_id:
        print(f"X-Team-Id={team_id}")
    print(f"models={models}")
    print(f"database={'yes' if database_url else 'no'}")

    if database_url and team_id:
        models_db = await _audit_team_models(database_url=database_url, team_id=team_id)
        routes_db = await _audit_team_routes(database_url=database_url, team_id=team_id)
        _print_json("DB 已注册模型 (gateway_models)", models_db)
        _explain_fallback(routes_db)
    elif database_url:
        print("\n提示: 同时传 --team-id 可打印该团队路由/fallback 配置")

    failed = 0
    with httpx.Client(timeout=args.timeout) as client:
        for model in models:
            since = datetime.now(UTC) - timedelta(seconds=5)
            try:
                result = probe_chat(
                    client,
                    openai_base=openai_base,
                    headers=headers,
                    model=model,
                    max_tokens=args.max_tokens,
                )
            except httpx.HTTPError as exc:
                print(f"\nFAIL {model}: {exc}")
                failed += 1
                continue

            _print_probe(result)
            if result.http_status >= 400:
                failed += 1

            if database_url:
                await asyncio.sleep(args.log_wait_sec)
                attr = await _fetch_log_attribution(
                    database_url=database_url,
                    route_name=model,
                    since=since,
                )
                _print_attribution(attr)

        if args.test_invalid_model:
            print("\n" + "=" * 72)
            print("无效模型探测（预期 4xx，无 fallback）")
            print("=" * 72)
            bad = "__gateway_probe_nonexistent_model__"
            since = datetime.now(UTC) - timedelta(seconds=5)
            result = probe_chat(
                client,
                openai_base=openai_base,
                headers=headers,
                model=bad,
                max_tokens=8,
            )
            _print_probe(result)
            if result.http_status < 400:
                print("警告: 预期 4xx，但请求成功了")
                failed += 1
            if database_url:
                await asyncio.sleep(args.log_wait_sec)
                attr = await _fetch_log_attribution(
                    database_url=database_url,
                    route_name=bad,
                    since=since,
                )
                _print_attribution(attr)

    print("\n" + "=" * 72)
    if failed:
        print(f"完成：{failed} 项失败")
        return 1
    print("完成：全部请求已探测")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="探测网关上游模型与 fallback 链路")
    p.add_argument("--base-url", default=os.getenv("GATEWAY_BASE_URL"))
    p.add_argument("--token", default=os.getenv("GATEWAY_TOKEN"))
    p.add_argument("--team-id", default=os.getenv("GATEWAY_TEAM_ID"))
    p.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    p.add_argument(
        "--models",
        default=",".join(DEFAULT_MODELS),
        help="逗号分隔的客户端 model 列表",
    )
    p.add_argument("--max-tokens", type=int, default=16)
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument(
        "--log-wait-sec",
        type=float,
        default=2.0,
        help="调用后等待日志落库秒数（配合 DATABASE_URL）",
    )
    p.add_argument(
        "--test-invalid-model",
        action="store_true",
        default=True,
        help="额外请求不存在模型，验证无 fallback 时的错误",
    )
    p.add_argument(
        "--no-test-invalid-model",
        action="store_false",
        dest="test_invalid_model",
    )
    p.add_argument(
        "--db-audit-only",
        action="store_true",
        help="仅查 DB（模型/路由/fallback/近期日志），不调用 OpenAI API",
    )
    return p.parse_args()


def main() -> int:
    return asyncio.run(_async_main(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
