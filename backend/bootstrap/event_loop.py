"""uvicorn 自定义事件循环工厂（Windows + psycopg 兼容）。

存在原因
========
uvicorn ≥ 0.40 重写了事件循环创建路径：``Server.run()`` 调用
``asyncio.Runner(loop_factory=Config.get_loop_factory())`` 创建循环，
**完全绕过 ``asyncio.set_event_loop_policy()``**。
Windows 上默认 ``asyncio_loop_factory`` 返回 ``asyncio.ProactorEventLoop``，
而 ``psycopg`` 的异步连接（langgraph ``AsyncPostgresSaver`` 依赖）只支持
``SelectorEventLoop``，否则抛 ``psycopg.InterfaceError``。

uvicorn ``Config.loop`` 接受 ``"module:func"`` 字符串作为自定义工厂的导入
路径（见 ``Config.get_loop_factory`` 的 else 分支）。本模块导出
``selector_event_loop_factory``，通过
``uvicorn.run(..., loop="bootstrap.event_loop:selector_event_loop_factory")``
显式注入。

非 Windows 平台不会触发 ProactorEventLoop 问题，但此工厂在任意平台上都
等价于 uvicorn 默认 ``asyncio_loop_factory`` 的非 Windows 分支，可放心
跨平台使用（或仅在 Windows 上注入，保留其他平台默认行为）。
"""

from __future__ import annotations

import asyncio


def selector_event_loop_factory() -> asyncio.AbstractEventLoop:
    """uvicorn loop factory：返回 ``SelectorEventLoop`` 实例。

    供 uvicorn ``Config(loop="bootstrap.event_loop:selector_event_loop_factory")``
    通过 ``import_from_string`` 加载并交给 ``asyncio.Runner`` 使用。
    必须是无参 callable 且返回 ``asyncio.AbstractEventLoop`` 实例。
    """
    return asyncio.SelectorEventLoop()


__all__ = ["selector_event_loop_factory"]
