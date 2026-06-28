#!/usr/bin/env python3
"""批量调用 volcano-text-pool 与 volcano-vision-pool 路由（skill 内工具）。

环境变量（已持久化到 Windows 用户级，新开终端/重启后自动生效）:
  GATEWAY_API_KEY        管理面 API Key（sk_ 开头，用于 vkeys ensure 兜底）
  GATEWAY_PROXY_VKEY     代理面 vkey（sk-gw- 开头，优先使用，避免每次 ensure）
  GATEWAY_BATCH_TEAM_ID  测试团队 ID（--team-id 缺省值）
  GATEWAY_BASE_URL       API 基地址（默认 https://gateway.giimallai.com/ai-agent/api/v1）

用法（PowerShell）:
  # 最简：环境变量齐全时直接跑
  python .agents/skills/ai-gateway-ops/scripts/batch_call_pools.py --stream

  # 指定本地图片测视觉
  python .agents/skills/ai-gateway-ops/scripts/batch_call_pools.py --stream --image-file scripts/面向接口.jpg

  # 逐模型测试（绕过路由别名，直接打每个底层模型）
  python .agents/skills/ai-gateway-ops/scripts/batch_call_pools.py --stream --models model1,model2

依赖: httpx  (backend venv 已自带；否则 pip install httpx)
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import statistics
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("缺少依赖 httpx，请在 backend venv 下运行或执行: pip install httpx")

# gateway_client.py 与本脚本同目录
GATEWAY_CLIENT = Path(__file__).resolve().parent / "gateway_client.py"

DEFAULT_BASE_URL = "https://gateway.giimallai.com/ai-agent/api/v1"

# 100x100 橙色 PNG 的 base64 data URL（内嵌，不依赖外网拉取，规避火山上游图片下载超时）
BASE64_IMAGE_DATAURL = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAIAAAD/gAIDAAAA6klE"
    "QVR4nO3SMREAIRAEQXhJaMK/Bd7CTd4dbzS1+92zmPmGO8RqPCsQKxArECsQKxArECsQKxAr"
    "ECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxA"
    "rECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxA"
    "rECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxA"
    "rECsQKxArECsQKxArECsQKxArEGvN/XHDAl2U1u+vAAAAAElFTkSuQmCC"
)

TEXT_PROMPTS = [
    "用一句话介绍你自己",
    "1+1 等于几？只回答数字。",
    "写一首关于春天的四行诗",
    "解释什么是递归，30 字以内",
    "北京和上海哪个更靠北？",
]

VISION_PROMPTS = [
    "描述这张图片的内容，100 字以内。",
    "图中体现了什么软件设计原则？",
    "把图中的关键文字逐条列出来。",
]


async def ensure_vkey(team_id: str, name: str = "batch-test") -> str:
    """通过 gateway_client.py 获取/复用 vkey 明文（仅当未设置 GATEWAY_PROXY_VKEY 时兜底）。"""
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(GATEWAY_CLIENT),
        "--raw",
        "vkeys",
        "ensure",
        "--team-id",
        team_id,
        "--name",
        name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"vkeys ensure 失败 (rc={proc.returncode}): {stderr.decode()}"
        )
    data = json.loads(stdout.decode())
    return data["plain_key"]


async def call_chat(
    base_url: str,
    vkey: str,
    model: str,
    messages: list,
    idx: int,
    sem: asyncio.Semaphore,
    timeout: float = 120.0,
    stream: bool = False,
) -> dict:
    url = f"{base_url}/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {vkey}",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip",  # 规避 httpx brotli 流式解码 bug
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 100,
        "stream": stream,
    }
    async with sem:
        t0 = time.perf_counter()
        first_byte: float | None = None
        try:
            if stream:
                # 流式：首字节快，规避 ALB 60s 空闲超时
                chunks: list[str] = []
                status = 0
                err_body = ""
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "POST", url, json=payload, headers=headers
                    ) as resp:
                        status = resp.status_code
                        if status != 200:
                            err_bytes = await resp.aread()
                            err_body = err_bytes.decode(errors="replace")[:500]
                        else:
                            async for line in resp.aiter_lines():
                                if first_byte is None and line:
                                    first_byte = time.perf_counter() - t0
                                if line.startswith("data: ") and line != "data: [DONE]":
                                    try:
                                        delta = (
                                            json.loads(line[6:])
                                            .get("choices", [{}])[0]
                                            .get("delta", {})
                                        )
                                        if "content" in delta and delta["content"]:
                                            chunks.append(delta["content"])
                                    except Exception:
                                        pass
                dt = time.perf_counter() - t0
                ok = status == 200
                content = "".join(chunks)
                if ok:
                    body = {"choices": [{"message": {"content": content}}]}
                else:
                    try:
                        body = json.loads(err_body)
                    except Exception:
                        body = {"raw_error": err_body}
                return {
                    "idx": idx,
                    "model": model,
                    "ok": ok,
                    "dt": dt,
                    "status": status,
                    "body": body,
                    "first_byte": first_byte,
                }
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                dt = time.perf_counter() - t0
                ok = resp.status_code == 200
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                return {
                    "idx": idx,
                    "model": model,
                    "ok": ok,
                    "dt": dt,
                    "status": resp.status_code,
                    "body": body,
                }
        except Exception as e:
            dt = time.perf_counter() - t0
            return {
                "idx": idx,
                "model": model,
                "ok": False,
                "dt": dt,
                "status": 0,
                "error": str(e),
            }


def _extract_content(result: dict) -> str:
    body = result.get("body")
    if isinstance(body, dict):
        try:
            return body["choices"][0]["message"]["content"]
        except Exception:
            return json.dumps(body.get("error") or body, ensure_ascii=False)[:120]
    return str(body)[:120]


def _print_group(title: str, model: str, results: list) -> None:
    oks = [r for r in results if r["ok"]]
    fails = [r for r in results if not r["ok"]]
    dts = [r["dt"] for r in oks]
    print(f"\n[{title}] {model}")
    print(f"  成功 {len(oks)}/{len(results)}  失败 {len(fails)}")
    if dts:
        print(
            f"  耗时(s): min={min(dts):.2f}  median={statistics.median(dts):.2f}  "
            f"max={max(dts):.2f}  avg={statistics.mean(dts):.2f}"
        )
    for r in results:
        tag = "OK  " if r["ok"] else "FAIL"
        extra = (
            _extract_content(r)
            if r["ok"]
            else (str(r.get("body") or r.get("error"))[:100])
        )
        print(f"  [{tag}] #{r['idx']:02d} {r['dt']:5.2f}s {r['status']} {extra}")


async def main() -> None:
    ap = argparse.ArgumentParser(
        description="批量调用 volcano-text-pool / volcano-vision-pool"
    )
    ap.add_argument(
        "--team-id",
        default=os.environ.get("GATEWAY_BATCH_TEAM_ID"),
        help="团队 ID（默认读 GATEWAY_BATCH_TEAM_ID；用 --vkey 时可省略）",
    )
    ap.add_argument(
        "--vkey",
        default=os.environ.get("GATEWAY_PROXY_VKEY"),
        help="vkey 明文（默认读 GATEWAY_PROXY_VKEY；未设置则用 vkeys ensure 兜底）",
    )
    ap.add_argument("--concurrency", type=int, default=5, help="并发数（默认 5）")
    ap.add_argument(
        "--rounds", type=int, default=1, help="每个 prompt 重复轮数（默认 1）"
    )
    ap.add_argument("--text-model", default="volcano-text-pool")
    ap.add_argument("--vision-model", default="volcano-vision-pool")
    ap.add_argument("--skip-vision", action="store_true", help="跳过视觉模型")
    ap.add_argument("--skip-text", action="store_true", help="跳过文本模型")
    ap.add_argument(
        "--image-url",
        default=BASE64_IMAGE_DATAURL,
        help="视觉模型测试图 URL（默认 base64 内嵌，规避外网拉图超时）",
    )
    ap.add_argument(
        "--image-file",
        help="本地图片文件路径（转 base64 data URL，优先级高于 --image-url）",
    )
    ap.add_argument(
        "--stream",
        action="store_true",
        help="流式调用（规避 ALB 60s 空闲超时，推荐开启）",
    )
    ap.add_argument(
        "--models",
        help="逐个测试指定模型列表（逗号分隔，优先级高于路由别名批量模式）",
    )
    ap.add_argument("--vkey-name", default="batch-test")
    args = ap.parse_args()

    # 本地图片转 base64 data URL（规避外网拉图超时）
    image_url = args.image_url
    if args.image_file:
        p = Path(args.image_file)
        if not p.is_file():
            sys.exit(f"错误：图片文件不存在: {args.image_file}")
        ext = p.suffix.lower().lstrip(".")
        mime = {
            "jpg": "jpeg",
            "jpeg": "jpeg",
            "png": "png",
            "gif": "gif",
            "webp": "webp",
            "bmp": "bmp",
        }.get(ext, "jpeg")
        b64 = base64.b64encode(p.read_bytes()).decode()
        image_url = f"data:image/{mime};base64,{b64}"
        print(f"[0] 加载本地图片: {p.name} ({len(b64)} bytes base64, {mime})")

    base_url = os.environ.get("GATEWAY_BASE_URL") or DEFAULT_BASE_URL
    print(f"[1] base_url = {base_url}")

    if args.vkey:
        vkey = args.vkey
        print(f"[2] 使用环境/参数 vkey = {vkey[:16]}...")
    else:
        if not args.team_id:
            sys.exit("错误：未传 --vkey 且无 GATEWAY_PROXY_VKEY 时必须提供 --team-id")
        if not (os.environ.get("GATEWAY_API_KEY") or os.environ.get("GATEWAY_TOKEN")):
            sys.exit("错误：未设置 GATEWAY_API_KEY 环境变量（或用 --vkey 跳过）")
        print(f"[2] 获取 vkey (name={args.vkey_name}) ...")
        vkey = await ensure_vkey(args.team_id, args.vkey_name)
        print(f"    vkey = {vkey[:16]}...")

    sem = asyncio.Semaphore(args.concurrency)
    text_results: list = []
    vision_results: list = []

    # 逐模型测试模式
    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
        print(f"\n[*] 逐模型测试: {len(models)} 个模型, stream={args.stream}")
        tasks = []
        for i, m in enumerate(models):
            # 含 vision 字样的用图片 prompt，其余用文本
            if "vision" in m.lower():
                msgs = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "一句话描述这张图"},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ]
                tasks.append(
                    call_chat(
                        base_url, vkey, m, msgs, i, sem, timeout=180, stream=args.stream
                    )
                )
            else:
                tasks.append(
                    call_chat(
                        base_url,
                        vkey,
                        m,
                        [{"role": "user", "content": "hi"}],
                        i,
                        sem,
                        stream=args.stream,
                    )
                )
        results = await asyncio.gather(*tasks)
        print("\n===== 逐模型结果 =====")
        ok_n = 0
        for r in results:
            m = r["model"]
            status = "OK" if r["ok"] else "FAIL"
            dt = f"{r['dt']:.2f}s"
            err = ""
            if not r["ok"]:
                if isinstance(r.get("body"), dict):
                    err = (
                        r["body"].get("error", {}).get("message", "")
                        or str(r["body"])[:120]
                    )
                else:
                    err = str(r.get("error", r.get("body", "")))[:120]
            else:
                ok_n += 1
            fb = f", first_byte={r['first_byte']:.2f}s" if r.get("first_byte") else ""
            print(f"  [{status:4}] {m:42} {dt:8}{fb}  {err}")
        print(f"\n{ok_n}/{len(results)} 成功")
        return

    if not args.skip_text:
        total = len(TEXT_PROMPTS) * args.rounds
        print(
            f"\n[3] 文本批量: {args.text_model}  ({total} 请求, 并发 {args.concurrency})"
        )
        tasks = []
        idx = 0
        for _ in range(args.rounds):
            for p in TEXT_PROMPTS:
                tasks.append(
                    call_chat(
                        base_url,
                        vkey,
                        args.text_model,
                        [{"role": "user", "content": p}],
                        idx,
                        sem,
                        stream=args.stream,
                    )
                )
                idx += 1
        text_results = await asyncio.gather(*tasks)

    if not args.skip_vision:
        total = len(VISION_PROMPTS) * args.rounds
        print(
            f"\n[4] 视觉批量: {args.vision_model}  ({total} 请求, 并发 {args.concurrency})"
        )
        tasks = []
        idx = 0
        for _ in range(args.rounds):
            for p in VISION_PROMPTS:
                msgs = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": p},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ]
                tasks.append(
                    call_chat(
                        base_url,
                        vkey,
                        args.vision_model,
                        msgs,
                        idx,
                        sem,
                        timeout=180,
                        stream=args.stream,
                    )
                )
                idx += 1
        vision_results = await asyncio.gather(*tasks)

    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)
    if text_results:
        _print_group("TEXT", args.text_model, text_results)
    if vision_results:
        _print_group("VISION", args.vision_model, vision_results)

    all_results = text_results + vision_results
    total_ok = sum(1 for r in all_results if r["ok"])
    print(f"\n总计: {total_ok}/{len(all_results)} 成功")


if __name__ == "__main__":
    asyncio.run(main())
