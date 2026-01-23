"""
Image Generator - 图像生成服务

支持的提供商:
- 火山引擎 Seedream (Doubao-Seedream)
- OpenAI DALL-E

文档参考:
- 火山引擎: https://www.volcengine.com/docs/6791/1361741
"""

from typing import TYPE_CHECKING, Any, Literal

import httpx
from pydantic import BaseModel

from utils.logging import get_logger

if TYPE_CHECKING:
    from shared.interfaces import ImageGeneratorConfigProtocol

logger = get_logger(__name__)


class ImageGenerationResult(BaseModel):
    """图像生成结果"""

    success: bool
    images: list[str] = []  # Base64 编码的图片或 URL
    error: str | None = None
    usage: dict[str, Any] | None = None


class ImageGenerator:
    """
    图像生成服务

    统一多个图像生成提供商的接口
    """

    def __init__(self, config: "ImageGeneratorConfigProtocol") -> None:
        """
        初始化图像生成服务

        Args:
            config: 图像生成配置（通过依赖注入传入，避免依赖应用层）
        """
        self.config = config
        self.timeout = 120.0  # 图像生成可能较慢

    async def generate(
        self,
        prompt: str,
        provider: Literal["volcengine", "openai"] = "volcengine",
        model: str | None = None,
        size: str | None = None,  # None 表示使用提供商默认尺寸
        n: int = 1,
        style: str | None = None,
        negative_prompt: str | None = None,
    ) -> ImageGenerationResult:
        """
        生成图像

        Args:
            prompt: 图像描述（支持中英文）
            provider: 提供商 (volcengine, openai)
            model: 模型名称
            size: 图像尺寸 (如 1024x1024)
            n: 生成数量
            style: 风格 (仅部分提供商支持)
            negative_prompt: 负面提示词 (仅部分提供商支持)

        Returns:
            ImageGenerationResult
        """
        if provider == "volcengine":
            # Seedream 要求最小 1920x1920
            actual_size = size or "1920x1920"
            return await self._generate_volcengine(
                prompt=prompt,
                model=model,
                size=actual_size,
                n=n,
                negative_prompt=negative_prompt,
            )
        elif provider == "openai":
            # DALL-E 默认 1024x1024
            actual_size = size or "1024x1024"
            return await self._generate_openai(
                prompt=prompt,
                model=model,
                size=actual_size,
                n=n,
                style=style,
            )
        else:
            return ImageGenerationResult(success=False, error=f"不支持的提供商: {provider}")

    async def _generate_volcengine(
        self,
        prompt: str,
        model: str | None = None,
        size: str = "1024x1024",
        n: int = 1,
        negative_prompt: str | None = None,
    ) -> ImageGenerationResult:
        """
        火山引擎 Seedream 图像生成

        使用 OpenAI 兼容的 API 格式
        文档: https://www.volcengine.com/docs/6791/1361741
        """
        api_key = self.config.volcengine_api_key
        # 优先使用图像专用端点，然后是通用端点
        endpoint_id = self.config.volcengine_image_endpoint_id or self.config.volcengine_endpoint_id

        if not api_key:
            return ImageGenerationResult(success=False, error="VOLCENGINE_API_KEY 未配置")

        if not endpoint_id:
            return ImageGenerationResult(
                success=False, error="VOLCENGINE_IMAGE_ENDPOINT_ID 或 VOLCENGINE_ENDPOINT_ID 未配置"
            )

        try:
            # 验证尺寸格式（解析但不使用，仅用于验证）
            _width, _height = map(int, size.split("x"))

            # 构建请求
            url = f"{self.config.volcengine_api_base}/images/generations"
            headers = {
                "Authorization": f"Bearer {api_key.get_secret_value()}",
                "Content-Type": "application/json",
            }

            payload: dict[str, Any] = {
                "model": endpoint_id,  # 火山引擎使用 endpoint_id 作为模型
                "prompt": prompt,
                "size": size,
                "n": n,
                "response_format": "b64_json",  # 返回 base64
            }

            # 添加负面提示词（如果支持）
            if negative_prompt:
                payload["negative_prompt"] = negative_prompt

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            # 提取图像
            images = []
            for item in data.get("data", []):
                if "b64_json" in item:
                    images.append(item["b64_json"])
                elif "url" in item:
                    images.append(item["url"])

            return ImageGenerationResult(
                success=True,
                images=images,
                usage=data.get("usage"),
            )

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error(f"火山引擎图像生成失败: {error_detail}")
            return ImageGenerationResult(
                success=False, error=f"HTTP 错误 {e.response.status_code}: {error_detail}"
            )
        except Exception as e:
            logger.error(f"火山引擎图像生成异常: {e}")
            return ImageGenerationResult(success=False, error=str(e))

    async def _generate_openai(
        self,
        prompt: str,
        model: str | None = None,
        size: str = "1024x1024",
        n: int = 1,
        style: str | None = None,
    ) -> ImageGenerationResult:
        """
        OpenAI DALL-E 图像生成
        """
        api_key = self.config.openai_api_key

        if not api_key:
            return ImageGenerationResult(success=False, error="OPENAI_API_KEY 未配置")

        try:
            url = f"{self.config.openai_api_base}/images/generations"
            headers = {
                "Authorization": f"Bearer {api_key.get_secret_value()}",
                "Content-Type": "application/json",
            }

            payload: dict[str, Any] = {
                "model": model or "dall-e-3",
                "prompt": prompt,
                "size": size,
                "n": n,
                "response_format": "b64_json",
            }

            if style:
                payload["style"] = style

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            images = [item["b64_json"] for item in data.get("data", [])]

            return ImageGenerationResult(
                success=True,
                images=images,
                usage=data.get("usage"),
            )

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error(f"OpenAI 图像生成失败: {error_detail}")
            return ImageGenerationResult(
                success=False, error=f"HTTP 错误 {e.response.status_code}: {error_detail}"
            )
        except Exception as e:
            logger.error(f"OpenAI 图像生成异常: {e}")
            return ImageGenerationResult(success=False, error=str(e))

    async def test_connection(self, provider: str = "volcengine") -> bool:
        """
        测试连接

        生成一张简单测试图片来验证配置
        """
        result = await self.generate(
            prompt="一只可爱的小猫",
            provider=provider,  # type: ignore
            n=1,
            # 不指定 size，使用提供商默认值
        )
        return result.success
