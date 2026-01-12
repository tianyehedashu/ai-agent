"""
Pyright Service - Pyright 类型检查服务

提供:
- 类型检查诊断
- 代码补全
- 悬停信息
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from utils.logging import get_logger

logger = get_logger(__name__)


class PyrightService:
    """
    Pyright 类型检查服务

    通过命令行调用 Pyright
    """

    def __init__(self) -> None:
        self.workspace_path: str | None = None
        self._initialized = False

    async def initialize(self, workspace_path: str) -> dict[str, Any]:
        """
        初始化服务

        Args:
            workspace_path: 工作区路径

        Returns:
            初始化结果
        """
        self.workspace_path = workspace_path
        self._initialized = True

        # 检查 Pyright 是否可用
        try:
            process = await asyncio.create_subprocess_exec(
                "pyright",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            version = stdout.decode().strip()
            logger.info(f"Pyright initialized: {version}")
            return {"status": "ok", "version": version}
        except Exception as e:
            logger.warning(f"Pyright not available: {e}")
            return {"status": "error", "message": str(e)}

    async def shutdown(self) -> None:
        """关闭服务"""
        self._initialized = False

    async def get_diagnostics(
        self,
        file_path: str,
        content: str,
    ) -> list[dict[str, Any]]:
        """
        获取类型检查诊断

        Args:
            file_path: 文件路径
            content: 文件内容

        Returns:
            诊断信息列表
        """
        if not self._initialized:
            return []

        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write(content)
            temp_path = f.name

        try:
            # 运行 Pyright
            process = await asyncio.create_subprocess_exec(
                "pyright",
                "--outputjson",
                temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=30,
            )

            # 解析输出
            try:
                result = json.loads(stdout.decode())
            except json.JSONDecodeError:
                return []

            diagnostics = []
            for diag in result.get("generalDiagnostics", []):
                diagnostics.append({
                    "line": diag.get("range", {}).get("start", {}).get("line", 0),
                    "column": diag.get("range", {}).get("start", {}).get("character", 0),
                    "end_line": diag.get("range", {}).get("end", {}).get("line", 0),
                    "end_column": diag.get("range", {}).get("end", {}).get("character", 0),
                    "severity": self._convert_severity(diag.get("severity", "error")),
                    "message": diag.get("message", ""),
                    "code": diag.get("rule", ""),
                })

            return diagnostics

        except asyncio.TimeoutError:
            logger.warning("Pyright timeout")
            return []
        except Exception as e:
            logger.error(f"Pyright error: {e}")
            return []
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def get_completions(
        self,
        file_path: str,
        content: str,
        line: int,
        column: int,
    ) -> list[dict[str, Any]]:
        """
        获取代码补全

        注意: 命令行 Pyright 不支持补全，这里返回空列表
        完整的补全功能需要使用 LSP 协议
        """
        # TODO: 实现 LSP 客户端以获取补全
        return []

    async def get_hover(
        self,
        file_path: str,
        content: str,
        line: int,
        column: int,
    ) -> dict[str, Any] | None:
        """
        获取悬停信息

        注意: 命令行 Pyright 不支持悬停，这里返回 None
        完整的悬停功能需要使用 LSP 协议
        """
        # TODO: 实现 LSP 客户端以获取悬停
        return None

    def _convert_severity(self, severity: str) -> str:
        """转换严重性级别"""
        mapping = {
            "error": "error",
            "warning": "warning",
            "information": "info",
            "hint": "hint",
        }
        return mapping.get(severity.lower(), "error")
