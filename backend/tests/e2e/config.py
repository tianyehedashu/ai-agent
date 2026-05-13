"""
E2E 测试共享配置。

通过环境变量覆盖默认地址，便于 CI 或自定义端口：

- ``E2E_API_BASE_URL``：后端根 URL，默认 ``http://localhost:8000``（无尾部斜杠）。
"""

from __future__ import annotations

import os

E2E_API_BASE_URL = os.environ.get("E2E_API_BASE_URL", "http://localhost:8000").rstrip("/")
