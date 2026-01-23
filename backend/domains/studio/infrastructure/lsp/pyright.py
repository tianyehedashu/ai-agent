"""
Pyright Service - Pyright 类型检查服务

提供:
- 类型检查诊断
- 代码补全
- 悬停信息
"""

import asyncio
import json
from pathlib import Path
import tempfile
from typing import Any

import jedi

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
            logger.info("Pyright initialized: %s", version)
            return {"status": "ok", "version": version}
        except OSError as e:
            logger.warning("Pyright not available: %s", e)
            return {"status": "error", "message": str(e)}

    async def shutdown(self) -> None:
        """关闭服务"""
        self._initialized = False

    async def get_diagnostics(
        self,
        _file_path: str,
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

        # 写入临时文件 (使用 asyncio.to_thread 包装同步操作)
        def create_temp_file() -> str:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
            ) as f:
                f.write(content)
                return f.name

        temp_path = await asyncio.to_thread(create_temp_file)

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
                diagnostics.append(
                    {
                        "line": diag.get("range", {}).get("start", {}).get("line", 0),
                        "column": diag.get("range", {}).get("start", {}).get("character", 0),
                        "end_line": diag.get("range", {}).get("end", {}).get("line", 0),
                        "end_column": diag.get("range", {}).get("end", {}).get("character", 0),
                        "severity": self._convert_severity(diag.get("severity", "error")),
                        "message": diag.get("message", ""),
                        "code": diag.get("rule", ""),
                    }
                )

            return diagnostics

        except TimeoutError:
            logger.warning("Pyright timeout")
            return []
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Pyright error: %s", e)
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

        使用 jedi 库提供 Python 代码补全
        """
        try:
            script = jedi.Script(content, path=file_path)
            # jedi 使用 1-based 行号
            completions = script.complete(line, column)

            return [
                {
                    "label": c.name,
                    "kind": self._convert_completion_type(c.type),
                    "detail": c.description,
                    "documentation": c.docstring() if hasattr(c, "docstring") else None,
                    "insertText": c.name,
                }
                for c in completions[:50]  # 限制最多 50 个补全
            ]
        except (AttributeError, ValueError, TypeError) as e:
            logger.error("Completion error: %s", e)
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

        使用 jedi 库提供悬停信息
        """
        try:
            script = jedi.Script(content, path=file_path)
            # jedi 使用 1-based 行号
            names = script.goto(line, column)

            if not names:
                # 尝试获取引用
                names = script.infer(line, column)

            if not names:
                return None

            name = names[0]
            docstring = name.docstring() if hasattr(name, "docstring") else ""
            type_hint = name.description if hasattr(name, "description") else ""

            # 构建悬停内容 (Markdown 格式)
            contents = []
            if type_hint:
                contents.append(f"```python\n{type_hint}\n```")
            if docstring:
                contents.append(docstring)

            return {
                "contents": "\n\n".join(contents) if contents else "No information available",
                "range": {
                    "startLine": line,
                    "startColumn": column,
                    "endLine": line,
                    "endColumn": column + len(name.name) if hasattr(name, "name") else column,
                },
            }
        except (AttributeError, ValueError, TypeError) as e:
            logger.error("Hover error: %s", e)
            return None

    def _convert_completion_type(self, jedi_type: str) -> str:
        """转换 jedi 补全类型到 Monaco 类型"""
        mapping = {
            "module": "module",
            "class": "class",
            "instance": "variable",
            "function": "function",
            "param": "variable",
            "path": "file",
            "keyword": "keyword",
            "property": "property",
            "statement": "snippet",
        }
        return mapping.get(jedi_type.lower(), "text")

    def _convert_severity(self, severity: str) -> str:
        """转换严重性级别"""
        mapping = {
            "error": "error",
            "warning": "warning",
            "information": "info",
            "hint": "hint",
        }
        return mapping.get(severity.lower(), "error")
