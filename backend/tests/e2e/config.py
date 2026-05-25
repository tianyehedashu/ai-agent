"""
E2E 测试共享配置。

通过环境变量覆盖默认地址，便于 CI 或自定义端口：

- ``E2E_API_BASE_URL``：后端根 URL，默认 ``http://localhost:8000``（无尾部斜杠）。
- ``ROOT_PATH``：与 ``backend/.env`` 中一致（默认 ``/ai-agent``），E2E 直连 .env 读取，不另设变量。
- ``E2E_USER_EMAIL`` / ``E2E_USER_PASSWORD``：可选；用于需登录的 E2E。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

_E2E_ENV = Path(__file__).resolve().parents[2] / ".env"
_DOTENV = dotenv_values(_E2E_ENV)


def _e2e_root_path() -> str:
    """与 backend 进程相同：读 ``.env`` 的 ``ROOT_PATH``（根 conftest 会置空进程 env 以跑集成测试）。"""
    raw = _DOTENV.get("ROOT_PATH")
    if raw is not None:
        return str(raw).strip()
    return "/ai-agent"


def _e2e_api_prefix() -> str:
    raw = _DOTENV.get("API_PREFIX")
    if raw is not None:
        return str(raw).strip()
    return "/api/v1"


def _normalize_segments(*parts: str) -> list[str]:
    segments: list[str] = []
    for part in parts:
        if not part:
            continue
        for piece in part.strip("/").split("/"):
            if piece:
                segments.append(piece)
    return segments


def _service_path(*segments: str) -> str:
    combined = _normalize_segments(_e2e_root_path(), *segments)
    if not combined:
        return "/"
    return "/" + "/".join(combined)


def _api_v1_path(*segments: str) -> str:
    combined = _normalize_segments(_e2e_root_path(), _e2e_api_prefix(), *segments)
    return "/" + "/".join(combined)


E2E_API_BASE_URL = os.environ.get("E2E_API_BASE_URL", "http://localhost:8000").rstrip("/")


def e2e_service_health_path() -> str:
    return _service_path("health")


def e2e_openai_models_path() -> str:
    return f"{_api_v1_path('openai', 'v1')}/models"


def e2e_anthropic_messages_path() -> str:
    return f"{_api_v1_path('anthropic')}/v1/messages"


def e2e_api_v1_path(*segments: str) -> str:
    return _api_v1_path(*segments)


def append_sse_data_line(line: str, events: list) -> bool:
    """解析一行 SSE ``data:`` 载荷；收到 ``done`` 时返回 True，便于结束流式读取。"""
    import json

    if not line.startswith("data: ") or line == "data: [DONE]":
        return False
    event = json.loads(line[6:])
    events.append(event)
    return event.get("type") == "done"
