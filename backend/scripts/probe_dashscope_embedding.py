#!/usr/bin/env python3
"""DashScope embedding LiteLLM 回归 probe。

验证 ``litellm.aembedding`` 对 dashscope 是否仍报 ``Unmapped LLM provider``。
升级 litellm 后运行本脚本，PASS 则可在 staging 设 ``GATEWAY_DASHSCOPE_EMBEDDING_VIA_LITELLM=true``。

用法:
    cd backend
    uv run python scripts/probe_dashscope_embedding.py
    uv run python scripts/probe_dashscope_embedding.py --model text-embedding-v3
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

DEFAULT_MODELS = (
    "dashscope/text-embedding-v3",
    "text-embedding-v3",
)


async def _probe_model(model: str, api_key: str | None) -> tuple[str, bool, str]:
    import litellm

    kwargs: dict[str, object] = {
        "model": model,
        "input": ["probe"],
    }
    if api_key:
        kwargs["api_key"] = api_key
    try:
        await litellm.aembedding(**kwargs)
        return model, True, "PASS"
    except Exception as exc:
        return model, False, f"FAIL: {type(exc).__name__}: {exc}"


async def main() -> int:
    parser = argparse.ArgumentParser(description="Probe DashScope embedding via LiteLLM")
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="LiteLLM model id (repeatable)",
    )
    args = parser.parse_args()
    models = tuple(args.models) if args.models else DEFAULT_MODELS
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("DASHSCOPE_COMPAT_API_KEY")

    try:
        import litellm as _litellm

        print(f"litellm version: {_litellm.__version__}")
    except Exception:
        print("litellm version: unknown")

    if not api_key:
        print("WARN: DASHSCOPE_API_KEY not set; probe may fail on auth")

    any_pass = False
    for model in models:
        _, ok, msg = await _probe_model(model, api_key)
        print(f"{model}: {msg}")
        any_pass = any_pass or ok

    if any_pass:
        print(
            "\nAt least one model PASS — consider enabling gateway_dashscope_embedding_via_litellm"
        )
        return 0
    print("\nAll probes FAIL — keep DashScope direct embedding path")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
