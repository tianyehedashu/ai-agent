"""
Ruff Service - Ruff Lint 服务

提供:
- Lint 诊断
- 代码格式化
- 自动修复
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from utils.logging import get_logger

logger = get_logger(__name__)


class RuffService:
    """
    Ruff Lint 服务

    通过命令行调用 Ruff
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

        # 检查 Ruff 是否可用
        try:
            process = await asyncio.create_subprocess_exec(
                "ruff",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            version = stdout.decode().strip()
            logger.info(f"Ruff initialized: {version}")
            return {"status": "ok", "version": version}
        except Exception as e:
            logger.warning(f"Ruff not available: {e}")
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
        获取 Lint 诊断

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
            # 运行 Ruff check
            process = await asyncio.create_subprocess_exec(
                "ruff",
                "check",
                "--output-format=json",
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
                results = json.loads(stdout.decode())
            except json.JSONDecodeError:
                return []

            diagnostics = []
            for item in results:
                diagnostics.append({
                    "line": item.get("location", {}).get("row", 1) - 1,  # 转为 0-based
                    "column": item.get("location", {}).get("column", 1) - 1,
                    "end_line": item.get("end_location", {}).get("row", 1) - 1,
                    "end_column": item.get("end_location", {}).get("column", 1) - 1,
                    "severity": "warning",
                    "message": item.get("message", ""),
                    "code": item.get("code", ""),
                    "fix": item.get("fix"),
                })

            return diagnostics

        except asyncio.TimeoutError:
            logger.warning("Ruff timeout")
            return []
        except Exception as e:
            logger.error(f"Ruff error: {e}")
            return []
        finally:
            Path(temp_path).unlink(missing_ok=True)

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
        if not self._initialized:
            return content

        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write(content)
            temp_path = f.name

        try:
            # 运行 Ruff format
            process = await asyncio.create_subprocess_exec(
                "ruff",
                "format",
                temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await asyncio.wait_for(
                process.communicate(),
                timeout=30,
            )

            # 读取格式化后的内容
            return Path(temp_path).read_text()

        except asyncio.TimeoutError:
            logger.warning("Ruff format timeout")
            return content
        except Exception as e:
            logger.error(f"Ruff format error: {e}")
            return content
        finally:
            Path(temp_path).unlink(missing_ok=True)

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
        if not self._initialized:
            return content

        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write(content)
            temp_path = f.name

        try:
            # 运行 Ruff check --fix
            process = await asyncio.create_subprocess_exec(
                "ruff",
                "check",
                "--fix",
                temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await asyncio.wait_for(
                process.communicate(),
                timeout=30,
            )

            # 读取修复后的内容
            return Path(temp_path).read_text()

        except asyncio.TimeoutError:
            logger.warning("Ruff fix timeout")
            return content
        except Exception as e:
            logger.error(f"Ruff fix error: {e}")
            return content
        finally:
            Path(temp_path).unlink(missing_ok=True)
