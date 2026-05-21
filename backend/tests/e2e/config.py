"""
E2E 测试共享配置。

通过环境变量覆盖默认地址，便于 CI 或自定义端口：

- ``E2E_API_BASE_URL``：后端根 URL，默认 ``http://localhost:8000``（无尾部斜杠）。
- ``E2E_ROOT_PATH`` / ``ROOT_PATH``：服务级前缀，须与后端进程一致（默认空）。
- ``E2E_USER_EMAIL`` / ``E2E_USER_PASSWORD``：可选；用于需登录的 E2E。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# 与后端 ROOT_PATH 对齐后再导入 paths（清除 settings 缓存）
_e2e_root = os.environ.get("E2E_ROOT_PATH", os.environ.get("ROOT_PATH", "")).strip()
if _e2e_root:
    os.environ["ROOT_PATH"] = _e2e_root

from bootstrap.config import get_settings  # noqa: E402

get_settings.cache_clear()

from libs.api.paths import (  # noqa: E402
    anthropic_compat_base,
    api_v1_path,
    openai_compat_base,
    service_path,
)

E2E_API_BASE_URL = os.environ.get("E2E_API_BASE_URL", "http://localhost:8000").rstrip("/")


def e2e_service_health_path() -> str:
    return service_path("health")


def e2e_openai_models_path() -> str:
    return f"{openai_compat_base()}/models"


def e2e_anthropic_messages_path() -> str:
    return f"{anthropic_compat_base()}/v1/messages"


def e2e_api_v1_path(*segments: str) -> str:
    return api_v1_path(*segments)
