#!/usr/bin/env python3
"""
AI Gateway 入站代理联调脚本（OpenAI 兼容 + Anthropic Messages）

网关根路径挂载与官方 SDK 一致：
  - OpenAI：  {base}/v1/chat/completions、/v1/images/generations、/v1/models
  - Anthropic：{base}/v1/messages

鉴权（二选一，同时存在时优先 Bearer）：
  - Authorization: Bearer <sk-gw-...>  或  <sk-...>（需 gateway:proxy scope + grant）
  - x-api-key: <同上>

平台 sk-* 可选请求头 X-Team-Id 选择已授权团队；sk-gw-* 绑定团队，无需该头。

配置：默认仅加载 backend/.env.test（可用 --env-file 换文件）；命令行参数优先。

复制 backend/.env.test.example 为 backend/.env.test（已 gitignore，仅存本地密钥）。

在 .env.test 中可写：
  GATEWAY_BASE_URL=http://127.0.0.1:8000
  GATEWAY_TOKEN=sk-gw-xxxx
  GATEWAY_TEAM_ID=                          # 平台 sk-* 时可选
  GATEWAY_CHAT_MODEL=dashscope/qwen-max   # 可选；未设时自动选 callable=true 的 chat 模型
  GATEWAY_IMAGE_MODEL=volcengine/seedream # 可选；未设时自动选 callable=true 的 image 模型
  GATEWAY_SKIP_IMAGE=true                   # 跳过生图
  GATEWAY_ANTHROPIC_X_API_KEY=true          # 额外测 x-api-key 鉴权
  GATEWAY_TIMEOUT=120
  GATEWAY_ENV_FILE=.env.test                # 覆盖默认 env 路径（亦可 --env-file）

示例：
  cd backend
  copy .env.test.example .env.test
  python scripts/test_gateway_proxy.py

  python scripts/test_gateway_proxy.py --env-file .env   # 改用其它 env 文件
  python scripts/test_gateway_proxy.py --token sk-gw-xxx --chat-model deepseek-chat
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv
import httpx

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ENV_FILE = ".env.test"
_LOADED_ENV_FILES: list[Path] = []


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _resolve_env_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (_BACKEND_ROOT / path).resolve()
    return path


def _load_env_files(cli_env_file: str) -> None:
    """默认加载 backend/.env.test；--env-file / GATEWAY_ENV_FILE 可指定其它文件。"""
    global _LOADED_ENV_FILES
    _LOADED_ENV_FILES = []
    explicit = (cli_env_file or os.getenv("GATEWAY_ENV_FILE") or _DEFAULT_ENV_FILE).strip()
    path = _resolve_env_path(explicit)
    if path.is_file():
        load_dotenv(path, override=True)
        _LOADED_ENV_FILES.append(path.resolve())


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return float(str(raw).strip())


def _preparse_env_file(argv: list[str] | None) -> str:
    """预解析 --env-file，以便加载 .env.test 后其余默认值正确。"""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument(
        "--env-file",
        default=os.getenv("GATEWAY_ENV_FILE", _DEFAULT_ENV_FILE),
        help=argparse.SUPPRESS,
    )
    pre_args, _ = pre.parse_known_args(argv)
    return (pre_args.env_file or _DEFAULT_ENV_FILE).strip()


_pre_env_file = _preparse_env_file(sys.argv[1:])
_load_env_files(_pre_env_file)

DEFAULT_BASE = os.getenv("GATEWAY_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_TIMEOUT = _env_float("GATEWAY_TIMEOUT", 120.0)


def _auth_headers(token: str, *, use_x_api_key: bool) -> dict[str, str]:
    if use_x_api_key:
        return {"x-api-key": token}
    return {"Authorization": f"Bearer {token}"}


def _merge_headers(
    token: str,
    team_id: str | None,
    *,
    use_x_api_key: bool,
) -> dict[str, str]:
    headers = {
        **_auth_headers(token, use_x_api_key=use_x_api_key),
        "Content-Type": "application/json",
    }
    if team_id:
        headers["X-Team-Id"] = team_id
    return headers


def _print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _sanitize_for_print(value: Any) -> Any:
    """完整打印 JSON，但省略超长 base64 等字段内容（保留长度说明）。"""
    if isinstance(value, dict):
        return {str(k): _sanitize_for_print(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_print(v) for v in value]
    if isinstance(value, str) and len(value) > 512:
        sample = value[:64]
        if (
            len(value) > 2048
            or "base64" in value[:32].lower()
            or sample.startswith("iVBOR")
            or sample.startswith("/9j/")
        ):
            return f"<omitted string, {len(value)} chars>"
    return value


def _print_json(label: str, data: Any, *, max_len: int | None = None) -> None:
    text = json.dumps(_sanitize_for_print(data), ensure_ascii=False, indent=2)
    if max_len is not None and len(text) > max_len:
        text = text[:max_len] + "\n... (truncated)"
    print(f"\n[{label}]\n{text}")


def _print_http_response(r: httpx.Response) -> Any | None:
    """打印 status 与完整响应体（JSON 美化；非 JSON 则 raw text）。"""
    print(f"status={r.status_code}")
    content_type = (r.headers.get("content-type") or "").lower()
    if "application/json" in content_type or r.text.lstrip().startswith(("{", "[")):
        try:
            body = r.json()
        except json.JSONDecodeError:
            print(f"\n[response body (raw)]\n{r.text}")
            return None
        _print_json("response body", body)
        return body
    if r.text:
        print(f"\n[response body (raw)]\n{r.text}")
    return None


def _gateway_meta(item: dict[str, Any]) -> dict[str, Any]:
    gw = item.get("gateway")
    return gw if isinstance(gw, dict) else {}


def _model_pick_rank(item: dict[str, Any]) -> tuple[int, int, str]:
    """callable 优先，其次连通性 success > 未测 > failed，最后按 id 稳定排序。"""
    gw = _gateway_meta(item)
    callable_rank = 0 if gw.get("callable") is True else 1
    conn = gw.get("connectivity_status")
    if conn == "success":
        conn_rank = 0
    elif conn is None:
        conn_rank = 1
    else:
        conn_rank = 2
    return (callable_rank, conn_rank, str(item.get("id", "")))


def _pick_model(
    models: list[dict[str, Any]],
    capability: str,
    explicit: str | None,
) -> str | None:
    cap = capability.lower()
    matching = [m for m in models if str(m.get("capability", "")).lower() == cap]
    if not matching:
        return None

    if explicit:
        mid = explicit.strip()
        for m in matching:
            if str(m.get("id", "")) == mid:
                gw = _gateway_meta(m)
                if gw.get("callable") is False:
                    print(
                        f"\n警告: 指定的模型 {mid!r} gateway.callable=false "
                        f"(connectivity={gw.get('connectivity_status')!r}, "
                        f"entitlement={gw.get('entitlement_status')!r})，仍按指定发起请求。"
                    )
                return mid
        print(f"\n警告: 指定的模型 {mid!r} 不在 GET /v1/models 列表中，仍尝试调用。")
        return mid

    matching.sort(key=_model_pick_rank)
    chosen = matching[0]
    mid = str(chosen.get("id", "")).strip()
    if not mid:
        return None
    gw = _gateway_meta(chosen)
    callable_count = sum(1 for m in matching if _gateway_meta(m).get("callable") is True)
    if gw.get("callable") is True:
        print(
            f"\n自动选用 {capability} 模型: {mid} "
            f"(callable=true；列表中 {callable_count}/{len(matching)} 个可调用)"
        )
    else:
        print(
            f"\n警告: 无 callable=true 的 {capability} 模型，仍选用 {mid} "
            f"(connectivity={gw.get('connectivity_status')!r}；"
            f"可设置 GATEWAY_{capability.upper()}_MODEL 或 --{capability.replace('_', '-')}-model)"
        )
    return mid


def test_list_models(
    client: httpx.Client,
    base_url: str,
    headers: dict[str, str],
) -> list[dict[str, Any]]:
    _print_section("1. GET /v1/models")
    r = client.get(f"{base_url}/v1/models", headers=headers)
    body = _print_http_response(r)
    if r.status_code != 200:
        r.raise_for_status()
    if not isinstance(body, dict):
        msg = "Unexpected /v1/models shape"
        raise TypeError(msg)
    data = body.get("data")
    if not isinstance(data, list):
        msg = "Unexpected /v1/models shape: missing data[]"
        raise TypeError(msg)
    typed = [x for x in data if isinstance(x, dict)]
    callable_n = sum(1 for m in typed if _gateway_meta(m).get("callable") is True)
    print(f"summary: models={len(typed)}, callable=true: {callable_n}/{len(typed)}")
    return typed


def test_openai_chat(
    client: httpx.Client,
    base_url: str,
    headers: dict[str, str],
    model: str,
) -> None:
    _print_section(f"2. OpenAI POST /v1/chat/completions  model={model}")
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "用一句话介绍你自己（测试网关，请简短回复）。"},
        ],
        "max_tokens": 128,
        "temperature": 0.3,
    }
    _print_json("request body", payload)
    r = client.post(
        f"{base_url}/v1/chat/completions",
        headers=headers,
        json=payload,
    )
    _print_http_response(r)
    if r.status_code != 200:
        r.raise_for_status()


def test_openai_image(
    client: httpx.Client,
    base_url: str,
    headers: dict[str, str],
    model: str,
) -> None:
    _print_section(f"3. OpenAI POST /v1/images/generations  model={model}")
    payload = {
        "model": model,
        "prompt": "A minimal flat icon of a robot, blue background, test only.",
        "n": 1,
        "size": "1024x1024",
    }
    _print_json("request body", payload)
    r = client.post(
        f"{base_url}/v1/images/generations",
        headers=headers,
        json=payload,
        timeout=DEFAULT_TIMEOUT,
    )
    _print_http_response(r)
    if r.status_code != 200:
        r.raise_for_status()


def test_anthropic_messages(
    client: httpx.Client,
    base_url: str,
    headers: dict[str, str],
    model: str,
) -> None:
    _print_section(f"4. Anthropic POST /v1/messages  model={model}")
    payload = {
        "model": model,
        "max_tokens": 128,
        "messages": [
            {
                "role": "user",
                "content": "Reply in one short English sentence (gateway test).",
            },
        ],
    }
    _print_json("request body", payload)
    r = client.post(
        f"{base_url}/v1/messages",
        headers=headers,
        json=payload,
    )
    _print_http_response(r)
    if r.status_code != 200:
        r.raise_for_status()


def test_anthropic_messages_x_api_key(
    client: httpx.Client,
    base_url: str,
    token: str,
    team_id: str | None,
    model: str,
) -> None:
    _print_section("5. Anthropic POST /v1/messages  (x-api-key 鉴权)")
    headers = _merge_headers(token, team_id, use_x_api_key=True)
    test_anthropic_messages(client, base_url, headers, model)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test AI Gateway OpenAI + Anthropic inbound APIs")
    parser.add_argument(
        "--env-file",
        default=_pre_env_file,
        metavar="PATH",
        help=f"env 文件路径，相对 backend 目录（默认: {_DEFAULT_ENV_FILE}）",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("GATEWAY_BASE_URL", DEFAULT_BASE),
        help="Gateway origin without trailing slash",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GATEWAY_TOKEN") or os.getenv("GATEWAY_API_KEY"),
        help="sk-gw-* or platform sk-* with gateway:proxy（默认读 GATEWAY_TOKEN）",
    )
    parser.add_argument(
        "--team-id",
        default=os.getenv("GATEWAY_TEAM_ID"),
        help="X-Team-Id for sk-*（默认读 GATEWAY_TEAM_ID）",
    )
    parser.add_argument(
        "--chat-model",
        default=os.getenv("GATEWAY_CHAT_MODEL"),
        help="默认读 GATEWAY_CHAT_MODEL",
    )
    parser.add_argument(
        "--image-model",
        default=os.getenv("GATEWAY_IMAGE_MODEL"),
        help="默认读 GATEWAY_IMAGE_MODEL",
    )
    parser.add_argument(
        "--skip-image",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("GATEWAY_SKIP_IMAGE"),
        help="跳过生图（.env: GATEWAY_SKIP_IMAGE=true）",
    )
    parser.add_argument(
        "--anthropic-x-api-key",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("GATEWAY_ANTHROPIC_X_API_KEY"),
        help="额外测 x-api-key（.env: GATEWAY_ANTHROPIC_X_API_KEY=true）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=_env_float("GATEWAY_TIMEOUT", DEFAULT_TIMEOUT),
        help="请求超时秒数（默认读 GATEWAY_TIMEOUT）",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = str(args.base_url).rstrip("/")

    token = (args.token or "").strip()
    if not token:
        print(
            f"错误: 请在 backend/{_DEFAULT_ENV_FILE} 设置 GATEWAY_TOKEN，或传入 --token",
            file=sys.stderr,
        )
        print(
            "  示例: copy .env.test.example .env.test  并填写 GATEWAY_TOKEN=sk-gw-...",
            file=sys.stderr,
        )
        print(
            "\n获取虚拟 Key：登录后 POST /api/v1/gateway/keys（需 JWT + X-Team-Id），响应 plain_key。",
            file=sys.stderr,
        )
        return 1

    team_id = (args.team_id or "").strip() or None
    headers = _merge_headers(token, team_id, use_x_api_key=False)

    if _LOADED_ENV_FILES:
        print("loaded .env:")
        for p in _LOADED_ENV_FILES:
            print(f"  - {p}")
    print(f"base_url={base_url}")
    print(f"token_prefix={token[:12]}...")
    if team_id:
        print(f"X-Team-Id={team_id}")

    failed = 0
    with httpx.Client(timeout=args.timeout) as client:
        try:
            models = test_list_models(client, base_url, headers)
        except Exception as exc:
            print(f"FAIL list models: {exc}")
            return 1

        chat_model = _pick_model(models, "chat", args.chat_model)
        if not chat_model:
            print("\n跳过对话：未找到 chat 模型，请配置路由或 --chat-model")
            failed += 1
        else:
            try:
                test_openai_chat(client, base_url, headers, chat_model)
            except Exception as exc:
                print(f"FAIL openai chat: {exc}")
                failed += 1

        if not args.skip_image:
            image_model = _pick_model(models, "image", args.image_model)
            if not image_model:
                print("\n跳过生图：未找到 image 能力模型（可用 --image-model 指定）")
            else:
                try:
                    test_openai_image(client, base_url, headers, image_model)
                except Exception as exc:
                    print(f"FAIL openai image: {exc}")
                    failed += 1

        if chat_model:
            try:
                test_anthropic_messages(client, base_url, headers, chat_model)
            except Exception as exc:
                print(f"FAIL anthropic messages: {exc}")
                failed += 1

            if args.anthropic_x_api_key:
                try:
                    test_anthropic_messages_x_api_key(
                        client, base_url, token, team_id, chat_model
                    )
                except Exception as exc:
                    print(f"FAIL anthropic x-api-key: {exc}")
                    failed += 1

    _print_section("完成")
    if failed:
        print(f"{failed} 项失败")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
