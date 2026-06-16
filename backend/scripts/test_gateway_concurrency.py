#!/usr/bin/env python3
"""网关并发压测：定位 504 / 连接池 / 排队瓶颈。

用法（backend 目录）：
  uv run python scripts/test_gateway_concurrency.py \\
    --base-url https://gateway.giimallai.com \\
    --token sk-gw-xxx \\
    --model doubao-text-online \\
    --concurrency 50

环境变量（可选，默认读 backend/.env）：
  GATEWAY_BASE_URL
  GATEWAY_TOKEN
  GATEWAY_CHAT_MODEL
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any

from dotenv import load_dotenv
import httpx

_BACKEND = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND / ".env", override=False)

DEFAULT_BASE = "https://gateway.giimallai.com"
DEFAULT_MODEL = "doubao-text-online"
SHORT_PROMPT = "用一句话介绍你自己（网关并发测试，请极短回复）。"
LONG_PROMPT_PREFIX = (
    "以下是产品资料（请阅读后在最后一行用 JSON 输出 title/summary 两个字段）：\n"
)


def _openai_base(base_url: str) -> str:
    root = base_url.rstrip("/")
    if "/ai-agent/api/v1/openai" in root:
        return root if root.endswith("/v1") else f"{root}/v1"
    return f"{root}/ai-agent/api/v1/openai/v1"


def _build_long_prompt(target_chars: int) -> str:
    """构造接近真实「长文本 Prompt」的请求体。"""
    body = LONG_PROMPT_PREFIX
    filler = "【段落】这是用于压测的长上下文填充文本，模拟火山工作流最终 Prompt 阶段的大 body。\n"
    while len(body) < target_chars:
        body += filler
    body += "\n请基于以上内容输出 {\"title\":\"...\",\"summary\":\"...\"}。"
    return body


@dataclass(slots=True)
class RequestResult:
    index: int
    ok: bool
    status: int
    elapsed_ms: int
    ttfb_ms: int | None
    error: str | None
    gateway_headers: dict[str, str] = field(default_factory=dict)
    response_preview: str | None = None


def _extract_gateway_headers(headers: httpx.Headers) -> dict[str, str]:
    wanted = (
        "x-gateway-preflight-ms",
        "x-gateway-upstream-ms",
        "x-gateway-timing",
        "x-gateway-request-id",
        "retry-after",
    )
    out: dict[str, str] = {}
    for key in wanted:
        val = headers.get(key)
        if val:
            out[key] = val
    return out


async def _one_request(
    client: httpx.AsyncClient,
    *,
    url: str,
    headers: dict[str, str],
    model: str,
    prompt: str,
    max_tokens: int,
    stream: bool,
    index: int,
    timeout: float,
) -> RequestResult:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "stream": stream,
    }
    started = time.perf_counter()
    ttfb_ms: int | None = None
    try:
        if stream:
            async with client.stream(
                "POST", url, headers=headers, json=payload, timeout=timeout
            ) as resp:
                status = resp.status_code
                gw_headers = _extract_gateway_headers(resp.headers)
                if status >= 400:
                    body = (await resp.aread()).decode("utf-8", errors="replace")[:500]
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    return RequestResult(
                        index=index,
                        ok=False,
                        status=status,
                        elapsed_ms=elapsed_ms,
                        ttfb_ms=None,
                        error=body or f"HTTP {status}",
                        gateway_headers=gw_headers,
                    )
                async for line in resp.aiter_lines():
                    if ttfb_ms is None and line.startswith("data:"):
                        ttfb_ms = int((time.perf_counter() - started) * 1000)
                    if line.strip() == "data: [DONE]":
                        break
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                return RequestResult(
                    index=index,
                    ok=True,
                    status=status,
                    elapsed_ms=elapsed_ms,
                    ttfb_ms=ttfb_ms,
                    error=None,
                    gateway_headers=gw_headers,
                )

        resp = await client.post(url, headers=headers, json=payload, timeout=timeout)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        gw_headers = _extract_gateway_headers(resp.headers)
        if resp.status_code >= 400:
            preview = resp.text[:500]
            return RequestResult(
                index=index,
                ok=False,
                status=resp.status_code,
                elapsed_ms=elapsed_ms,
                ttfb_ms=elapsed_ms,
                error=preview or f"HTTP {resp.status_code}",
                gateway_headers=gw_headers,
            )
        preview = None
        try:
            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            if isinstance(content, str):
                preview = content[:120]
        except (json.JSONDecodeError, IndexError, KeyError, TypeError):
            preview = resp.text[:120]
        return RequestResult(
            index=index,
            ok=True,
            status=resp.status_code,
            elapsed_ms=elapsed_ms,
            ttfb_ms=elapsed_ms,
            error=None,
            gateway_headers=gw_headers,
            response_preview=preview,
        )
    except httpx.TimeoutException as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return RequestResult(
            index=index,
            ok=False,
            status=0,
            elapsed_ms=elapsed_ms,
            ttfb_ms=ttfb_ms,
            error=f"client timeout: {exc}",
        )
    except httpx.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return RequestResult(
            index=index,
            ok=False,
            status=0,
            elapsed_ms=elapsed_ms,
            ttfb_ms=ttfb_ms,
            error=str(exc)[:300],
        )


async def _run_batch(
    *,
    base_url: str,
    token: str,
    model: str,
    concurrency: int,
    total: int,
    prompt: str,
    max_tokens: int,
    stream: bool,
    timeout: float,
) -> list[RequestResult]:
    url = f"{_openai_base(base_url)}/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    limits = httpx.Limits(max_connections=concurrency + 5, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits, http2=True) as client:
        sem = asyncio.Semaphore(concurrency)

        async def _bounded(i: int) -> RequestResult:
            async with sem:
                return await _one_request(
                    client,
                    url=url,
                    headers=headers,
                    model=model,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    stream=stream,
                    index=i,
                    timeout=timeout,
                )

        return list(await asyncio.gather(*[_bounded(i) for i in range(total)]))


def _print_summary(label: str, results: list[RequestResult]) -> None:
    print()
    print("=" * 72)
    print(label)
    print("=" * 72)
    total = len(results)
    ok = sum(1 for r in results if r.ok)
    status_counter = Counter(r.status for r in results)
    err_counter = Counter()
    for r in results:
        if r.error:
            if r.status == 504 or "504" in (r.error or ""):
                err_counter["504_gateway_timeout"] += 1
            elif "timeout" in (r.error or "").lower():
                err_counter["timeout"] += 1
            elif "pool" in (r.error or "").lower():
                err_counter["db_pool"] += 1
            else:
                err_counter["other"] += 1

    latencies = [r.elapsed_ms for r in results if r.ok]
    ttfbs = [r.ttfb_ms for r in results if r.ttfb_ms is not None and r.ok]

    print(f"total={total}  success={ok}  failed={total - ok}")
    print(f"status_codes={dict(sorted(status_counter.items()))}")
    if err_counter:
        print(f"error_buckets={dict(err_counter)}")

    if latencies:
        print(
            "latency_ms: "
            f"min={min(latencies)}  p50={statistics.median(latencies):.0f}  "
            f"p95={sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)]}  "
            f"max={max(latencies)}"
        )
    if ttfbs:
        print(
            "ttfb_ms: "
            f"min={min(ttfbs)}  p50={statistics.median(ttfbs):.0f}  "
            f"max={max(ttfbs)}"
        )

    preflights = [
        int(r.gateway_headers["x-gateway-preflight-ms"])
        for r in results
        if "x-gateway-preflight-ms" in r.gateway_headers
    ]
    if preflights:
        print(
            "gateway_preflight_ms: "
            f"p50={statistics.median(preflights):.0f}  max={max(preflights)}"
        )

    failures = [r for r in results if not r.ok][:8]
    if failures:
        print("\n失败样本（最多 8 条）：")
        for r in failures:
            print(
                f"  #{r.index} status={r.status} elapsed={r.elapsed_ms}ms "
                f"err={((r.error or '')[:120]).replace(chr(10), ' ')}"
            )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gateway 并发压测（OpenAI chat/completions）")
    p.add_argument("--base-url", default=os.getenv("GATEWAY_BASE_URL", DEFAULT_BASE))
    p.add_argument("--token", default=os.getenv("GATEWAY_TOKEN"))
    p.add_argument("--model", default=os.getenv("GATEWAY_CHAT_MODEL", DEFAULT_MODEL))
    p.add_argument("--concurrency", type=int, default=50)
    p.add_argument("--total", type=int, default=None, help="总请求数，默认同 concurrency")
    p.add_argument("--max-tokens", type=int, default=64)
    p.add_argument("--timeout", type=float, default=320.0)
    p.add_argument("--stream", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument(
        "--prompt-chars",
        type=int,
        default=0,
        help=">0 时使用构造的长 Prompt（模拟长文本阶段）",
    )
    p.add_argument(
        "--sweep",
        default="",
        help="逗号分隔并发档位，如 1,3,10,50（覆盖 --concurrency）",
    )
    return p.parse_args()


async def _async_main() -> int:
    args = parse_args()
    token = (args.token or "").strip()
    if not token:
        print("错误: 需要 --token 或 GATEWAY_TOKEN", file=sys.stderr)
        return 1

    prompt = _build_long_prompt(args.prompt_chars) if args.prompt_chars > 0 else SHORT_PROMPT
    total = args.total or args.concurrency
    sweeps = [int(x.strip()) for x in args.sweep.split(",") if x.strip()] or [args.concurrency]

    print(f"base_url={args.base_url}")
    print(f"openai_base={_openai_base(args.base_url)}")
    print(f"model={args.model}")
    print(f"token_prefix={token[:14]}...")
    print(f"stream={args.stream}  max_tokens={args.max_tokens}  timeout={args.timeout}s")
    print(f"prompt_chars={len(prompt)}")

    overall_failed = 0
    for conc in sweeps:
        batch_total = max(total, conc) if len(sweeps) > 1 else total
        label = f"并发={conc}  总请求={batch_total}"
        print(f"\n>>> 开始 {label} ...")
        started = time.perf_counter()
        results = await _run_batch(
            base_url=args.base_url,
            token=token,
            model=args.model,
            concurrency=conc,
            total=batch_total,
            prompt=prompt,
            max_tokens=args.max_tokens,
            stream=args.stream,
            timeout=args.timeout,
        )
        wall_ms = int((time.perf_counter() - started) * 1000)
        _print_summary(f"{label}  wall={wall_ms}ms", results)
        overall_failed += sum(1 for r in results if not r.ok)

    print()
    print("=" * 72)
    print("诊断提示")
    print("=" * 72)
    print(
        "- 504 且 elapsed≈60000ms：多为入口 60s 读超时（Higress/SLB），"
        " 非流式需等上游整包返回才发首字节，排队+推理易撞线。"
    )
    print(
        "- 前端 Pod Nginx proxy_read_timeout=300s，但更外层可能仍有 60s 默认超时。"
    )
    print(
        "- 500/503 且 error 含 pool/QueuePool：AsyncPG 连接池耗尽"
        "（默认 pool_size=20 + max_overflow=10=30/进程）。"
    )
    print(
        "- gateway-preflight-ms 在失败请求上飙高：入站鉴权/预算阶段抢 DB 连接。"
    )
    print(
        "- 非流式请求在上游期间仍占用 FastAPI DB session（连接未归还池），"
        " 50 并发易超过单 worker 30 连接上限。"
    )

    return 1 if overall_failed else 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
