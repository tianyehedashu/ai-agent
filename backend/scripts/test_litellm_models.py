#!/usr/bin/env python3
"""
LiteLLM 模型批量并发测试脚本

测试火山引擎、DeepSeek、智谱AI、阿里云DashScope 的模型可用性
基于项目中配置的 API Key 进行测试

使用方法:
    # 测试所有配置的提供商
    python scripts/test_litellm_models.py

    # 测试特定提供商
    python scripts/test_litellm_models.py --providers deepseek dashscope

    # 使用自定义并发数
    python scripts/test_litellm_models.py --concurrency 5

    # 详细输出
    python scripts/test_litellm_models.py --verbose
"""

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

from dotenv import load_dotenv
import litellm
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载环境变量
load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()


@dataclass
class ModelTestResult:
    """模型测试结果"""

    provider: str
    model_id: str
    model_name: str
    litellm_model: str
    success: bool
    latency_ms: float = 0.0
    response_text: str = ""
    error_message: str = ""
    tokens_used: dict[str, int] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ProviderConfig:
    """提供商配置"""

    name: str
    api_key_env: str
    api_base: str | None = None
    models: list[dict[str, Any]] = field(default_factory=list)


# =============================================================================
# 提供商和模型配置 (2026-01-17 最新)
# =============================================================================

PROVIDERS: dict[str, ProviderConfig] = {
    "deepseek": ProviderConfig(
        name="DeepSeek",
        api_key_env="DEEPSEEK_API_KEY",
        api_base="https://api.deepseek.com",
        models=[
            # ========== DeepSeek 官方 API 可用模型 (platform.deepseek.com) ==========
            # 注意: DeepSeek 官方 API 目前只提供 3 个主力模型
            # 蒸馏版等需要通过其他平台 (HuggingFace, TogetherAI, Fireworks 等)
            {
                "id": "deepseek-chat",
                "name": "DeepSeek Chat (V3)",
                "litellm_model": "deepseek/deepseek-chat",
                "supports_tools": True,
                "description": "671B MoE, 37B 激活, 64K 上下文",
            },
            {
                "id": "deepseek-coder",
                "name": "DeepSeek Coder",
                "litellm_model": "deepseek/deepseek-coder",
                "supports_tools": True,
                "description": "代码生成专用",
            },
            {
                "id": "deepseek-reasoner",
                "name": "DeepSeek Reasoner (R1)",
                "litellm_model": "deepseek/deepseek-reasoner",
                "supports_tools": False,
                "description": "671B MoE 推理模型, 支持 reasoning_content",
            },
        ],
    ),
    "dashscope": ProviderConfig(
        name="阿里云 DashScope (通义千问)",
        api_key_env="DASHSCOPE_API_KEY",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        models=[
            # ========== 商业版 ==========
            {
                "id": "qwen-turbo",
                "name": "通义千问 Turbo",
                "litellm_model": "dashscope/qwen-turbo",
                "supports_tools": True,
            },
            {
                "id": "qwen-turbo-latest",
                "name": "通义千问 Turbo (最新)",
                "litellm_model": "dashscope/qwen-turbo-latest",
                "supports_tools": True,
            },
            {
                "id": "qwen-plus",
                "name": "通义千问 Plus",
                "litellm_model": "dashscope/qwen-plus",
                "supports_tools": True,
            },
            {
                "id": "qwen-plus-latest",
                "name": "通义千问 Plus (最新)",
                "litellm_model": "dashscope/qwen-plus-latest",
                "supports_tools": True,
            },
            {
                "id": "qwen-max",
                "name": "通义千问 Max",
                "litellm_model": "dashscope/qwen-max",
                "supports_tools": True,
            },
            {
                "id": "qwen-max-latest",
                "name": "通义千问 Max (最新)",
                "litellm_model": "dashscope/qwen-max-latest",
                "supports_tools": True,
            },
            # ========== Qwen3 系列 (最新) ==========
            {
                "id": "qwen3-235b-a22b",
                "name": "Qwen3 235B-A22B (MoE)",
                "litellm_model": "dashscope/qwen3-235b-a22b",
                "supports_tools": True,
            },
            {
                "id": "qwen3-32b",
                "name": "Qwen3 32B",
                "litellm_model": "dashscope/qwen3-32b",
                "supports_tools": True,
            },
            # ========== Qwen 2.5 开源版 ==========
            {
                "id": "qwen2.5-72b-instruct",
                "name": "Qwen 2.5 72B",
                "litellm_model": "dashscope/qwen2.5-72b-instruct",
                "supports_tools": True,
            },
            {
                "id": "qwen2.5-32b-instruct",
                "name": "Qwen 2.5 32B",
                "litellm_model": "dashscope/qwen2.5-32b-instruct",
                "supports_tools": True,
            },
            {
                "id": "qwen2.5-14b-instruct",
                "name": "Qwen 2.5 14B",
                "litellm_model": "dashscope/qwen2.5-14b-instruct",
                "supports_tools": True,
            },
            {
                "id": "qwen2.5-7b-instruct",
                "name": "Qwen 2.5 7B",
                "litellm_model": "dashscope/qwen2.5-7b-instruct",
                "supports_tools": True,
            },
            # ========== Qwen 2.5 代码专用 ==========
            {
                "id": "qwen2.5-coder-32b-instruct",
                "name": "Qwen 2.5 Coder 32B",
                "litellm_model": "dashscope/qwen2.5-coder-32b-instruct",
                "supports_tools": True,
            },
            {
                "id": "qwen2.5-coder-14b-instruct",
                "name": "Qwen 2.5 Coder 14B",
                "litellm_model": "dashscope/qwen2.5-coder-14b-instruct",
                "supports_tools": True,
            },
            {
                "id": "qwen2.5-coder-7b-instruct",
                "name": "Qwen 2.5 Coder 7B",
                "litellm_model": "dashscope/qwen2.5-coder-7b-instruct",
                "supports_tools": True,
            },
            # ========== 视觉模型 ==========
            {
                "id": "qwen-vl-plus",
                "name": "通义千问 VL Plus",
                "litellm_model": "dashscope/qwen-vl-plus",
                "supports_tools": False,
            },
            {
                "id": "qwen-vl-max",
                "name": "通义千问 VL Max",
                "litellm_model": "dashscope/qwen-vl-max",
                "supports_tools": True,
            },
            # ========== QwQ 推理模型 ==========
            {
                "id": "qwq-32b-preview",
                "name": "QwQ 32B Preview (推理)",
                "litellm_model": "dashscope/qwq-32b-preview",
                "supports_tools": False,
            },
            {
                "id": "qwq-plus",
                "name": "QwQ Plus (推理)",
                "litellm_model": "dashscope/qwq-plus",
                "supports_tools": False,
            },
        ],
    ),
    "zhipuai": ProviderConfig(
        name="智谱AI (GLM)",
        api_key_env="ZHIPUAI_API_KEY",
        api_base="https://open.bigmodel.cn/api/paas/v4",
        models=[
            # ========== GLM-4.7 (最新旗舰) ==========
            {
                "id": "glm-4-alltools",
                "name": "GLM-4.7 (最新旗舰)",
                "litellm_model": "zai/glm-4-alltools",
                "supports_tools": True,
            },
            # ========== GLM-4.6 系列 ==========
            {
                "id": "glm-4.6",
                "name": "GLM-4.6",
                "litellm_model": "zai/glm-4.6",
                "supports_tools": True,
            },
            {
                "id": "glm-4.6v",
                "name": "GLM-4.6V (视觉)",
                "litellm_model": "zai/glm-4.6v",
                "supports_tools": True,
            },
            # ========== GLM-4.5 系列 ==========
            {
                "id": "glm-4.5-air",
                "name": "GLM-4.5 Air",
                "litellm_model": "zai/glm-4.5-air",
                "supports_tools": True,
            },
            {
                "id": "glm-4.5-airx",
                "name": "GLM-4.5 AirX",
                "litellm_model": "zai/glm-4.5-airx",
                "supports_tools": True,
            },
            {
                "id": "glm-4.5-flash",
                "name": "GLM-4.5 Flash",
                "litellm_model": "zai/glm-4.5-flash",
                "supports_tools": True,
            },
            # ========== GLM-4 系列 (稳定版) ==========
            {
                "id": "glm-4",
                "name": "GLM-4",
                "litellm_model": "zai/glm-4",
                "supports_tools": True,
            },
            {
                "id": "glm-4-plus",
                "name": "GLM-4 Plus",
                "litellm_model": "zai/glm-4-plus",
                "supports_tools": True,
            },
            {
                "id": "glm-4-air",
                "name": "GLM-4 Air",
                "litellm_model": "zai/glm-4-air",
                "supports_tools": True,
            },
            {
                "id": "glm-4-airx",
                "name": "GLM-4 AirX",
                "litellm_model": "zai/glm-4-airx",
                "supports_tools": True,
            },
            {
                "id": "glm-4-flash",
                "name": "GLM-4 Flash",
                "litellm_model": "zai/glm-4-flash",
                "supports_tools": True,
            },
            {
                "id": "glm-4-0520",
                "name": "GLM-4 0520",
                "litellm_model": "zai/glm-4-0520",
                "supports_tools": True,
            },
            # ========== GLM-4 Long (超长上下文) ==========
            {
                "id": "glm-4-long",
                "name": "GLM-4 Long (1M上下文)",
                "litellm_model": "zai/glm-4-long",
                "supports_tools": True,
            },
            # ========== GLM-4V 视觉系列 ==========
            {
                "id": "glm-4v",
                "name": "GLM-4V",
                "litellm_model": "zai/glm-4v",
                "supports_tools": False,
            },
            {
                "id": "glm-4v-plus",
                "name": "GLM-4V Plus",
                "litellm_model": "zai/glm-4v-plus",
                "supports_tools": True,
            },
            {
                "id": "glm-4v-flash",
                "name": "GLM-4V Flash",
                "litellm_model": "zai/glm-4v-flash",
                "supports_tools": False,
            },
            # ========== CodeGeeX (代码专用) ==========
            {
                "id": "codegeex-4",
                "name": "CodeGeeX-4",
                "litellm_model": "zai/codegeex-4",
                "supports_tools": True,
            },
            # ========== GLM-Z1 推理系列 ==========
            {
                "id": "glm-z1-32b",
                "name": "GLM-Z1 32B (推理)",
                "litellm_model": "zai/glm-z1-32b",
                "supports_tools": False,
            },
        ],
    ),
    "volcengine": ProviderConfig(
        name="火山引擎 (豆包)",
        api_key_env="VOLCENGINE_API_KEY",
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        models=[
            # 火山引擎需要 endpoint_id，所有模型共用一个 endpoint
            # 实际模型由 endpoint 配置决定
            {
                "id": "doubao-endpoint",
                "name": "豆包 (Endpoint)",
                "litellm_model": "volcengine/{endpoint_id}",
                "supports_tools": True,
                "requires_endpoint_id": True,
            },
        ],
    ),
}

# 火山引擎支持的模型列表 (参考)
# 注意: 火山引擎不是按模型名调用，而是按 endpoint_id 调用
# 每个 endpoint 对应一个具体的模型版本
VOLCENGINE_AVAILABLE_MODELS = """
火山引擎支持的豆包模型 (需要在控制台创建对应的 Endpoint):

1. Doubao 1.5 Pro 系列:
   - doubao-1.5-pro-32k (32K 上下文)
   - doubao-1.5-pro-128k (128K 上下文)
   - doubao-1.5-pro-256k (256K 上下文)

2. Doubao 1.5 Lite 系列:
   - doubao-1.5-lite-32k
   - doubao-1.5-lite-128k

3. Doubao 1.5 Vision 系列:
   - doubao-1.5-vision-pro
   - doubao-1.5-vision-lite

4. Doubao Seed 1.6 系列 (最新旗舰):
   - doubao-seed-1.6
   - doubao-seed-1.6-flash
   - doubao-seed-1.6-vision

5. 深度思考系列:
   - doubao-thinking-pro

6. 角色扮演系列:
   - doubao-character-pro-32k

7. Embedding 系列:
   - doubao-embedding-text-240715
   - doubao-embedding-large-text-240915

使用方式: volcengine/<your_endpoint_id>
"""

# 测试用的消息
TEST_MESSAGES = [{"role": "user", "content": "请用一句话介绍你自己。"}]

TEST_MESSAGES_REASONING = [{"role": "user", "content": "计算: 123 + 456 = ?"}]


class LiteLLMModelTester:
    """LiteLLM 模型测试器"""

    def __init__(
        self,
        providers: list[str] | None = None,
        concurrency: int = 3,
        timeout: float = 60.0,
        verbose: bool = False,
    ):
        self.providers = providers or list(PROVIDERS.keys())
        self.concurrency = concurrency
        self.timeout = timeout
        self.verbose = verbose
        self.results: list[ModelTestResult] = []

        # 配置 LiteLLM
        litellm.set_verbose = verbose

    def _get_api_key(self, provider: ProviderConfig) -> str | None:
        """获取提供商的 API Key"""
        return os.getenv(provider.api_key_env)

    def _get_endpoint_id(self, provider_key: str) -> str | None:
        """获取火山引擎的 endpoint_id"""
        if provider_key == "volcengine":
            # 优先使用 CHAT_ENDPOINT_ID
            endpoint_id = os.getenv("VOLCENGINE_CHAT_ENDPOINT_ID")
            if not endpoint_id:
                endpoint_id = os.getenv("VOLCENGINE_ENDPOINT_ID")
            return endpoint_id
        return None

    async def test_model(
        self,
        provider_key: str,
        model_config: dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> ModelTestResult:
        """测试单个模型"""
        provider = PROVIDERS[provider_key]
        api_key = self._get_api_key(provider)

        result = ModelTestResult(
            provider=provider_key,
            model_id=model_config["id"],
            model_name=model_config["name"],
            litellm_model=model_config["litellm_model"],
            success=False,
        )

        # 检查 API Key
        if not api_key:
            result.error_message = f"未配置 {provider.api_key_env}"
            return result

        # 处理火山引擎的 endpoint_id
        litellm_model = model_config["litellm_model"]
        if model_config.get("requires_endpoint_id"):
            endpoint_id = self._get_endpoint_id(provider_key)
            if not endpoint_id:
                result.error_message = (
                    "未配置 VOLCENGINE_CHAT_ENDPOINT_ID 或 VOLCENGINE_ENDPOINT_ID"
                )
                return result
            litellm_model = litellm_model.replace("{endpoint_id}", endpoint_id)

        # 选择测试消息
        messages = TEST_MESSAGES
        if "reasoner" in model_config["id"].lower() or "qwq" in model_config["id"].lower():
            messages = TEST_MESSAGES_REASONING

        async with semaphore:
            start_time = time.perf_counter()
            try:
                # 构建请求参数
                kwargs: dict[str, Any] = {
                    "model": litellm_model,
                    "messages": messages,
                    "max_tokens": 100,
                    "temperature": 0.7,
                    "api_key": api_key,
                }

                # 添加 api_base (如果有)
                if provider.api_base:
                    kwargs["api_base"] = provider.api_base

                # 调用 LiteLLM
                response = await asyncio.wait_for(
                    litellm.acompletion(**kwargs),
                    timeout=self.timeout,
                )

                end_time = time.perf_counter()
                result.latency_ms = (end_time - start_time) * 1000
                result.success = True

                # 提取响应内容
                if response.choices and len(response.choices) > 0:
                    choice = response.choices[0]
                    if hasattr(choice, "message") and choice.message:
                        result.response_text = choice.message.content or ""
                        # 处理推理模型的 reasoning_content
                        if hasattr(choice.message, "reasoning_content"):
                            result.response_text = (
                                f"[思考过程]: {choice.message.reasoning_content}\n"
                                f"[答案]: {result.response_text}"
                            )

                # 提取 token 使用情况
                if hasattr(response, "usage") and response.usage:
                    result.tokens_used = {
                        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                        "total_tokens": getattr(response.usage, "total_tokens", 0),
                    }

            except TimeoutError:
                result.error_message = f"超时 ({self.timeout}s)"
            except Exception as e:
                result.error_message = str(e)[:200]  # 截断错误信息

            return result

    async def test_provider(
        self,
        provider_key: str,
        progress: Progress | None = None,
        task_id: int | None = None,
    ) -> list[ModelTestResult]:
        """测试一个提供商的所有模型"""
        provider = PROVIDERS.get(provider_key)
        if not provider:
            console.print(f"[yellow]未知的提供商: {provider_key}[/yellow]")
            return []

        results: list[ModelTestResult] = []
        semaphore = asyncio.Semaphore(self.concurrency)

        # 创建测试任务
        tasks = [self.test_model(provider_key, model, semaphore) for model in provider.models]

        # 并发执行测试
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)

            if progress and task_id is not None:
                progress.advance(task_id)

            # 实时输出结果
            status = "[OK]" if result.success else "[X]"
            latency_str = f"{result.latency_ms:.0f}ms" if result.success else "-"
            if self.verbose:
                console.print(
                    f"  {status} {result.model_name}: "
                    f"{latency_str} "
                    f"{result.error_message[:50] if result.error_message else ''}"
                )

        return results

    async def run_all_tests(self) -> list[ModelTestResult]:
        """运行所有测试"""
        all_results: list[ModelTestResult] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            for provider_key in self.providers:
                if provider_key not in PROVIDERS:
                    continue

                provider = PROVIDERS[provider_key]
                console.print(f"\n[bold blue]测试 {provider.name}...[/bold blue]")

                task_id = progress.add_task(
                    f"测试 {provider.name}",
                    total=len(provider.models),
                )

                results = await self.test_provider(provider_key, progress, task_id)
                all_results.extend(results)

        self.results = all_results
        return all_results

    def print_results_table(self) -> None:
        """打印结果表格"""
        table = Table(title="LiteLLM 模型测试结果")

        table.add_column("提供商", style="cyan")
        table.add_column("模型", style="white")
        table.add_column("状态", justify="center")
        table.add_column("延迟", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("错误", style="red", max_width=40)

        for result in self.results:
            status = "[green]OK[/green]" if result.success else "[red]FAIL[/red]"
            latency = f"{result.latency_ms:.0f}ms" if result.success else "-"
            tokens = str(result.tokens_used.get("total_tokens", "-")) if result.success else "-"
            error = result.error_message[:40] if result.error_message else ""

            table.add_row(
                result.provider,
                result.model_name,
                status,
                latency,
                tokens,
                error,
            )

        console.print(table)

    def print_summary(self) -> None:
        """打印测试摘要"""
        total = len(self.results)
        success = sum(1 for r in self.results if r.success)
        failed = total - success

        console.print("\n[bold]测试摘要:[/bold]")
        console.print(f"  总数: {total}")
        console.print(f"  [green]成功: {success}[/green]")
        console.print(f"  [red]失败: {failed}[/red]")

        if success > 0:
            avg_latency = sum(r.latency_ms for r in self.results if r.success) / success
            console.print(f"  平均延迟: {avg_latency:.0f}ms")

        # 按提供商分组统计
        console.print("\n[bold]按提供商统计:[/bold]")
        for provider_key in self.providers:
            if provider_key not in PROVIDERS:
                continue
            provider_results = [r for r in self.results if r.provider == provider_key]
            if not provider_results:
                continue
            provider_success = sum(1 for r in provider_results if r.success)
            console.print(
                f"  {PROVIDERS[provider_key].name}: {provider_success}/{len(provider_results)} 成功"
            )

    def save_results(self, output_path: str | None = None) -> str:
        """保存测试结果到 JSON 文件"""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"test_results_{timestamp}.json"

        results_data = [
            {
                "provider": r.provider,
                "model_id": r.model_id,
                "model_name": r.model_name,
                "litellm_model": r.litellm_model,
                "success": r.success,
                "latency_ms": r.latency_ms,
                "response_text": r.response_text[:200] if r.response_text else "",
                "error_message": r.error_message,
                "tokens_used": r.tokens_used,
                "timestamp": r.timestamp,
            }
            for r in self.results
        ]

        output_file = Path(output_path)
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)

        return output_path


def check_api_keys() -> dict[str, bool]:
    """检查已配置的 API Keys"""
    results = {}
    for provider_key, provider in PROVIDERS.items():
        api_key = os.getenv(str(provider.api_key_env))
        results[provider_key] = bool(api_key)
    return results


def print_api_key_status() -> None:
    """打印 API Key 配置状态"""
    console.print("\n[bold]API Key 配置状态:[/bold]")
    api_keys = check_api_keys()

    for provider_key, configured in api_keys.items():
        provider = PROVIDERS[provider_key]
        status = "[green][OK][/green]" if configured else "[red][X][/red]"
        console.print(f"  {provider.name} ({provider.api_key_env}): {status}")

        # 火山引擎额外检查 endpoint_id
        if provider_key == "volcengine" and configured:
            endpoint_id = os.getenv("VOLCENGINE_CHAT_ENDPOINT_ID") or os.getenv(
                "VOLCENGINE_ENDPOINT_ID"
            )
            ep_status = "[green][OK][/green]" if endpoint_id else "[yellow][!][/yellow]"
            console.print(f"    - Endpoint ID: {ep_status}")


async def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(
        description="LiteLLM 模型批量并发测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 测试所有已配置的提供商
  python scripts/test_litellm_models.py

  # 只测试 DeepSeek 和 DashScope
  python scripts/test_litellm_models.py --providers deepseek dashscope

  # 使用较高并发数
  python scripts/test_litellm_models.py --concurrency 5

  # 详细输出并保存结果
  python scripts/test_litellm_models.py --verbose --output results.json
        """,
    )

    parser.add_argument(
        "--providers",
        "-p",
        nargs="+",
        choices=list(PROVIDERS.keys()),
        help="要测试的提供商列表",
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=3,
        help="并发数 (默认: 3)",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=60.0,
        help="单个请求超时时间 (秒, 默认: 60)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="结果输出文件路径 (JSON)",
    )
    parser.add_argument(
        "--check-keys",
        action="store_true",
        help="仅检查 API Key 配置状态",
    )

    args = parser.parse_args()

    console.print("[bold cyan]LiteLLM 模型批量并发测试[/bold cyan]")
    console.print("=" * 50)

    # 显示 API Key 状态
    print_api_key_status()

    if args.check_keys:
        return

    # 过滤已配置的提供商
    api_keys = check_api_keys()
    providers_to_test = args.providers or list(PROVIDERS.keys())

    # 过滤掉未配置 API Key 的提供商
    providers_with_keys = [p for p in providers_to_test if api_keys.get(p)]

    if not providers_with_keys:
        console.print("\n[red]错误: 没有已配置 API Key 的提供商可供测试[/red]")
        console.print("请在 .env 文件中配置至少一个提供商的 API Key")
        return

    skipped = set(providers_to_test) - set(providers_with_keys)
    if skipped:
        console.print(f"\n[yellow]跳过未配置 API Key 的提供商: {', '.join(skipped)}[/yellow]")

    # 创建测试器并运行
    tester = LiteLLMModelTester(
        providers=providers_with_keys,
        concurrency=args.concurrency,
        timeout=args.timeout,
        verbose=args.verbose,
    )

    await tester.run_all_tests()

    # 输出结果
    console.print()
    tester.print_results_table()
    tester.print_summary()

    # 保存结果
    output_path = tester.save_results(args.output)
    console.print(f"\n[dim]结果已保存到: {output_path}[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
