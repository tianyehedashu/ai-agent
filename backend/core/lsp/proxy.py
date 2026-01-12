"""
LSP Proxy - LSP 代理服务

作为 LSP 服务器的代理，提供:
- 进程管理
- 请求转发
- 结果聚合
"""

import asyncio
from typing import Any

from core.lsp.pyright import PyrightService
from core.lsp.ruff import RuffService
from utils.logging import get_logger

logger = get_logger(__name__)


class LSPProxy:
    """
    LSP 代理服务

    统一管理 Pyright 和 Ruff 服务
    """

    def __init__(self) -> None:
        self.pyright = PyrightService()
        self.ruff = RuffService()

    async def initialize(self, workspace_path: str) -> dict[str, Any]:
        """
        初始化 LSP 服务

        Args:
            workspace_path: 工作区路径

        Returns:
            初始化结果
        """
        results = await asyncio.gather(
            self.pyright.initialize(workspace_path),
            self.ruff.initialize(workspace_path),
            return_exceptions=True,
        )

        return {
            "pyright": results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])},
            "ruff": results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])},
        }

    async def shutdown(self) -> None:
        """关闭 LSP 服务"""
        await asyncio.gather(
            self.pyright.shutdown(),
            self.ruff.shutdown(),
            return_exceptions=True,
        )

    async def get_diagnostics(
        self,
        file_path: str,
        content: str,
    ) -> list[dict[str, Any]]:
        """
        获取诊断信息

        Args:
            file_path: 文件路径
            content: 文件内容

        Returns:
            诊断信息列表
        """
        results = await asyncio.gather(
            self.pyright.get_diagnostics(file_path, content),
            self.ruff.get_diagnostics(file_path, content),
            return_exceptions=True,
        )

        diagnostics = []

        # Pyright 诊断
        if not isinstance(results[0], Exception):
            for d in results[0]:
                d["source"] = "pyright"
                diagnostics.append(d)

        # Ruff 诊断
        if not isinstance(results[1], Exception):
            for d in results[1]:
                d["source"] = "ruff"
                diagnostics.append(d)

        # 按行号排序
        diagnostics.sort(key=lambda x: (x.get("line", 0), x.get("column", 0)))

        return diagnostics

    async def get_completions(
        self,
        file_path: str,
        content: str,
        line: int,
        column: int,
    ) -> list[dict[str, Any]]:
        """
        获取代码补全

        Args:
            file_path: 文件路径
            content: 文件内容
            line: 行号 (0-based)
            column: 列号 (0-based)

        Returns:
            补全项列表
        """
        return await self.pyright.get_completions(file_path, content, line, column)

    async def get_hover(
        self,
        file_path: str,
        content: str,
        line: int,
        column: int,
    ) -> dict[str, Any] | None:
        """
        获取悬停信息

        Args:
            file_path: 文件路径
            content: 文件内容
            line: 行号 (0-based)
            column: 列号 (0-based)

        Returns:
            悬停信息
        """
        return await self.pyright.get_hover(file_path, content, line, column)

    async def format_code(
        self,
        file_path: str,
        content: str,
    ) -> str:
        """
        格式化代码

        Args:
            file_path: 文件路径
            content: 文件内容

        Returns:
            格式化后的代码
        """
        return await self.ruff.format_code(file_path, content)

    async def fix_all(
        self,
        file_path: str,
        content: str,
    ) -> str:
        """
        修复所有可自动修复的问题

        Args:
            file_path: 文件路径
            content: 文件内容

        Returns:
            修复后的代码
        """
        return await self.ruff.fix_all(file_path, content)
