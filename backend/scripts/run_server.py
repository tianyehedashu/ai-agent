#!/usr/bin/env python3
"""与生产一致的开发服务器入口（``make dev`` 使用，无热重载）。

存在原因（Windows 必读）
=========================
uvicorn ≥ 0.40 在 ``Server.run()`` 中通过
``asyncio.Runner(loop_factory=Config.get_loop_factory())`` 创建事件循环，
**完全绕过 ``asyncio.set_event_loop_policy()``**；Windows 上默认工厂返回
``ProactorEventLoop``，psycopg / langgraph ``AsyncPostgresSaver`` 因此抛
``InterfaceError``。

修复：利用 uvicorn ``Config.get_loop_factory`` 的"自定义字符串"分支
（``import_from_string(self.loop)``），把 loop 参数指向自定义工厂
``bootstrap.event_loop:selector_event_loop_factory``，强制使用
``SelectorEventLoop``。

Linux/Docker 上没有 Proactor 问题，但同时注入可使本机 dev 与生产
``Dockerfile`` CMD 行为一致；也可选择仅 Windows 注入，本脚本采取后者
以最小化对生产入口的偏离。
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8000

# uvicorn ``Config.loop`` 接受 ``"module:func"``，运行期通过 import_from_string
# 加载并交给 ``asyncio.Runner``。详见 ``bootstrap/event_loop.py`` 模块 docstring。
_WINDOWS_SELECTOR_LOOP_FACTORY = "bootstrap.event_loop:selector_event_loop_factory"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run uvicorn server (no reload; production-equivalent dev entry)",
    )
    parser.add_argument("--host", default=_DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    import uvicorn

    run_kwargs: dict[str, Any] = {
        "host": args.host,
        "port": args.port,
        "log_level": args.log_level,
    }
    if sys.platform == "win32":
        run_kwargs["loop"] = _WINDOWS_SELECTOR_LOOP_FACTORY

    uvicorn.run("bootstrap.main:app", **run_kwargs)


if __name__ == "__main__":
    main()
