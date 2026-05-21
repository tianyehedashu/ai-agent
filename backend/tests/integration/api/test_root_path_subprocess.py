"""ROOT_PATH 子进程集成测试（独立 import bootstrap.main）。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.integration
def test_root_path_routes_in_fresh_process() -> None:
    """ROOT_PATH=/ai-agent 时在全新进程中注册预期路由。"""
    script = """
import os
from unittest.mock import patch

os.environ.setdefault("APP_ENV", "development")
os.environ["ROOT_PATH"] = "/ai-agent"

with patch("libs.db.database.init_db"), patch("libs.db.redis.init_redis"):
    from bootstrap.main import app

paths = {getattr(r, "path", "") for r in app.routes}
assert "/ai-agent/health" in paths
assert "/ai-agent/api/v1/openai/v1/models" in paths
assert "/ai-agent/api/v1/anthropic/v1/messages" in paths
print("OK")
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_BACKEND_ROOT)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
