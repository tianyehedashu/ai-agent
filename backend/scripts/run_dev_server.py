#!/usr/bin/env python3
"""热重载开发服务器（make dev-reload）。常规开发请用与生产一致的 ``make dev``。"""

from __future__ import annotations

import argparse
import errno
from pathlib import Path
import socket
import sys

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_RELOAD_EXCLUDES = [
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/.ruff_cache/**",
]

_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8000


def _port_available(host: str, port: int) -> bool:
    """连接探测：已有服务监听时返回 False（Windows 上 bind 对 0.0.0.0 不可靠）。"""
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        if sock.connect_ex((probe_host, port)) == 0:
            return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((probe_host, port))
        except OSError as exc:
            if exc.errno in (errno.EADDRINUSE, 10048, 10013):
                return False
            raise
    return True


def _format_port_busy_message(host: str, port: int) -> str:
    return (
        f"\n端口 {port} 已被占用，无法启动开发服务器（WinError 10013 / EADDRINUSE）。\n"
        "常见原因：另一个 make dev / make dev-stable 仍在运行。\n"
        f"排查：netstat -ano | findstr \":{port}\"\n"
        f"结束进程：taskkill /PID <PID> /F\n"
        f"或改用其他端口：uv run python scripts/run_dev_server.py --port {port + 1}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run uvicorn with reload excludes")
    parser.add_argument("--host", default=_DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    if not _port_available(args.host, args.port):
        print(_format_port_busy_message(args.host, args.port), file=sys.stderr)
        raise SystemExit(1)

    import uvicorn

    uvicorn.run(
        "bootstrap.main:app",
        host=args.host,
        port=args.port,
        reload=True,
        reload_excludes=_RELOAD_EXCLUDES,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
