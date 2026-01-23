"""
File Tools - 文件操作工具
"""

from pathlib import Path
from typing import Any

from pydantic import Field

from bootstrap.config import settings
from shared.types import ToolCategory, ToolResult
from domains.runtime.infrastructure.tools.base import BaseTool, ToolParameters, register_tool


class ReadFileParams(ToolParameters):
    """读取文件参数"""

    path: str = Field(description="文件路径")
    encoding: str = Field(default="utf-8", description="文件编码")


class WriteFileParams(ToolParameters):
    """写入文件参数"""

    path: str = Field(description="文件路径")
    content: str = Field(description="文件内容")
    encoding: str = Field(default="utf-8", description="文件编码")


class ListDirParams(ToolParameters):
    """列出目录参数"""

    path: str = Field(default=".", description="目录路径")
    recursive: bool = Field(default=False, description="是否递归")


@register_tool
class ReadFileTool(BaseTool):
    """读取文件工具"""

    name = "read_file"
    description = "读取指定路径的文件内容"
    category = ToolCategory.FILE
    requires_confirmation = False
    parameters_model = ReadFileParams

    async def execute(self, **kwargs: Any) -> ToolResult:
        params = ReadFileParams(**kwargs)

        try:
            file_path = self._resolve_path(params.path)
            content = file_path.read_text(encoding=params.encoding)
            return ToolResult(
                tool_call_id="",
                success=True,
                output=content,
            )
        except FileNotFoundError:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"File not found: {params.path}",
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=str(e),
            )

    def _resolve_path(self, path: str) -> Path:
        """解析路径"""
        p = Path(path)
        if not p.is_absolute():
            p = Path(settings.work_dir) / p
        return p


@register_tool
class WriteFileTool(BaseTool):
    """写入文件工具"""

    name = "write_file"
    description = "将内容写入指定路径的文件"
    category = ToolCategory.FILE
    requires_confirmation = True
    parameters_model = WriteFileParams

    async def execute(self, **kwargs: Any) -> ToolResult:
        params = WriteFileParams(**kwargs)

        try:
            file_path = self._resolve_path(params.path)

            # 确保父目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)

            file_path.write_text(params.content, encoding=params.encoding)
            return ToolResult(
                tool_call_id="",
                success=True,
                output=f"Successfully wrote to {params.path}",
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=str(e),
            )

    def _resolve_path(self, path: str) -> Path:
        """解析路径"""
        p = Path(path)
        if not p.is_absolute():
            p = Path(settings.work_dir) / p
        return p


@register_tool
class ListDirTool(BaseTool):
    """列出目录工具"""

    name = "list_dir"
    description = "列出指定目录下的文件和子目录"
    category = ToolCategory.FILE
    requires_confirmation = False
    parameters_model = ListDirParams

    async def execute(self, **kwargs: Any) -> ToolResult:
        params = ListDirParams(**kwargs)

        try:
            dir_path = self._resolve_path(params.path)

            if not dir_path.exists():
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output="",
                    error=f"Directory not found: {params.path}",
                )

            if not dir_path.is_dir():
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output="",
                    error=f"Not a directory: {params.path}",
                )

            entries = []
            if params.recursive:
                for entry in dir_path.rglob("*"):
                    rel_path = entry.relative_to(dir_path)
                    entry_type = "dir" if entry.is_dir() else "file"
                    entries.append(f"[{entry_type}] {rel_path}")
            else:
                for entry in dir_path.iterdir():
                    entry_type = "dir" if entry.is_dir() else "file"
                    entries.append(f"[{entry_type}] {entry.name}")

            return ToolResult(
                tool_call_id="",
                success=True,
                output="\n".join(sorted(entries)),
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=str(e),
            )

    def _resolve_path(self, path: str) -> Path:
        """解析路径"""
        p = Path(path)
        if not p.is_absolute():
            p = Path(settings.work_dir) / p
        return p
