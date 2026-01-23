"""
Search Tools - 搜索工具
"""

import asyncio
from pathlib import Path
from typing import Any

import httpx
from pydantic import Field

from bootstrap.config import settings
from shared.types import ToolCategory, ToolResult
from domains.runtime.infrastructure.tools.base import BaseTool, ToolParameters, register_tool


class WebSearchParams(ToolParameters):
    """网络搜索参数"""

    query: str = Field(description="搜索查询")
    num_results: int = Field(default=5, description="结果数量")


class GrepSearchParams(ToolParameters):
    """代码搜索参数 (Grep)"""

    pattern: str = Field(description="搜索模式")
    path: str = Field(default=".", description="搜索路径")
    case_sensitive: bool = Field(default=True, description="是否区分大小写")
    file_pattern: str | None = Field(default=None, description="文件名模式")


@register_tool
class WebSearchTool(BaseTool):
    """网络搜索工具"""

    name = "web_search"
    description = "在网络上搜索信息"
    category = ToolCategory.SEARCH
    requires_confirmation = False
    parameters_model = WebSearchParams

    async def execute(self, **kwargs: Any) -> ToolResult:
        params = WebSearchParams(**kwargs)

        try:
            # 使用 DuckDuckGo 搜索 (无需 API Key)
            results = await self._duckduckgo_search(
                params.query,
                params.num_results,
            )

            if not results:
                return ToolResult(
                    tool_call_id="",
                    success=True,
                    output="No results found",
                )

            # 格式化结果
            formatted = []
            for i, r in enumerate(results, 1):
                formatted.append(f"{i}. {r['title']}\n   URL: {r['url']}\n   {r['snippet']}")

            return ToolResult(
                tool_call_id="",
                success=True,
                output="\n\n".join(formatted),
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=str(e),
            )

    async def _duckduckgo_search(
        self,
        query: str,
        num_results: int,
    ) -> list[dict[str, str]]:
        """使用 DuckDuckGo 搜索"""
        # DuckDuckGo Instant Answer API
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        results = []

        # 提取抽象结果
        if data.get("Abstract"):
            results.append(
                {
                    "title": data.get("Heading", "Abstract"),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("Abstract", ""),
                }
            )

        # 提取相关话题
        for topic in data.get("RelatedTopics", [])[:num_results]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append(
                    {
                        "title": topic.get("Text", "")[:50],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", ""),
                    }
                )

        return results[:num_results]


@register_tool
class GrepTool(BaseTool):
    """Grep 搜索工具"""

    name = "grep"
    description = "在文件中搜索文本模式"
    category = ToolCategory.SEARCH
    requires_confirmation = False
    parameters_model = GrepSearchParams

    async def execute(self, **kwargs: Any) -> ToolResult:
        params = GrepSearchParams(**kwargs)

        try:
            search_path = Path(settings.work_dir) / params.path

            if not search_path.exists():
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output="",
                    error=f"Path not found: {params.path}",
                )

            # 构建 grep 命令
            cmd = ["grep", "-r", "-n"]

            if not params.case_sensitive:
                cmd.append("-i")

            if params.file_pattern:
                cmd.extend(["--include", params.file_pattern])

            cmd.extend([params.pattern, str(search_path)])

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, _ = await asyncio.wait_for(
                    process.communicate(),
                    timeout=30,
                )
            except TimeoutError:
                process.kill()
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output="",
                    error="Search timed out",
                )

            if process.returncode == 1 and not stdout:
                return ToolResult(
                    tool_call_id="",
                    success=True,
                    output="No matches found",
                )

            # 限制输出行数
            lines = stdout.decode().strip().split("\n")
            if len(lines) > 100:
                output = "\n".join(lines[:100])
                output += f"\n\n... ({len(lines) - 100} more lines)"
            else:
                output = stdout.decode().strip()

            return ToolResult(
                tool_call_id="",
                success=True,
                output=output,
            )
        except TimeoutError:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error="Search timed out",
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=str(e),
            )
