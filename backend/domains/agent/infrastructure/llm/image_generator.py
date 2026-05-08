"""
Image Generator - 图像生成服务

支持的提供商:
- 火山引擎 Seedream (Doubao-Seedream) - txt2img / img2img
- OpenAI DALL-E - txt2img / img2img (edits)

特性:
- 支持 api_key / api_base 覆写（用户自定义模型）
- 支持异步任务轮询（provider 返回 task_id 时自动轮询）

文档参考:
- 火山引擎: https://www.volcengine.com/docs/6791/1361741
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Literal

import httpx
from pydantic import BaseModel, SecretStr

from utils.logging import get_logger

if TYPE_CHECKING:
    from libs.config.interfaces import ImageGeneratorConfigProtocol

logger = get_logger(__name__)

SUPPORTED_PROVIDERS = ("volcengine", "openai")

PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "volcengine": {"size": "1920x1920", "model": ""},
    "openai": {"size": "1024x1024", "model": "dall-e-3"},
}

PROVIDER_SIZE_OPTIONS: dict[str, list[str]] = {
    "volcengine": ["1920x1920", "1080x1920", "1920x1080"],
    "openai": ["1024x1024", "1024x1792", "1792x1024"],
}

_ASYNC_POLL_INTERVAL = 3.0
_ASYNC_POLL_MAX_ATTEMPTS = 40  # 3s * 40 = 120s


class ImageGenerationResult(BaseModel):
    """图像生成结果"""

    success: bool
    images: list[str] = []
    error: str | None = None
    usage: dict[str, Any] | None = None


class ImageGenerator:
    """图像生成服务 - 统一多提供商接口，支持 txt2img / img2img"""

    def __init__(self, config: "ImageGeneratorConfigProtocol") -> None:
        self.config = config
        self.timeout = 120.0

    async def generate(
        self,
        prompt: str,
        provider: Literal["volcengine", "openai"] = "volcengine",
        model: str | None = None,
        size: str | None = None,
        n: int = 1,
        style: str | None = None,
        negative_prompt: str | None = None,
        reference_image_url: str | None = None,
        strength: float | None = None,
        api_key_override: str | None = None,
        api_base_override: str | None = None,
    ) -> ImageGenerationResult:
        """
        生成图像（txt2img / img2img）

        Args:
            prompt: 图像描述
            provider: 提供商
            model: 模型名称
            size: 图像尺寸
            n: 生成数量
            style: 风格 (仅 openai)
            negative_prompt: 负面提示词 (仅 volcengine)
            reference_image_url: 参考图 URL，提供则走 img2img
            strength: 参考图影响强度 0.0-1.0
            api_key_override: 覆写 API Key（用户自定义模型）
            api_base_override: 覆写 API Base URL（用户自定义模型）
        """
        defaults = PROVIDER_DEFAULTS.get(provider, {})
        actual_size = size or defaults.get("size", "1024x1024")

        if provider == "volcengine":
            return await self._generate_volcengine(
                prompt=prompt,
                model=model,
                size=actual_size,
                n=n,
                negative_prompt=negative_prompt,
                reference_image_url=reference_image_url,
                strength=strength,
                api_key_override=api_key_override,
                api_base_override=api_base_override,
            )
        elif provider == "openai":
            return await self._generate_openai(
                prompt=prompt,
                model=model or defaults.get("model", "dall-e-3"),
                size=actual_size,
                n=n,
                style=style,
                reference_image_url=reference_image_url,
                api_key_override=api_key_override,
                api_base_override=api_base_override,
            )
        else:
            return ImageGenerationResult(success=False, error=f"不支持的提供商: {provider}")

    # -------------------------------------------------------------------------
    # 火山引擎 Seedream
    # -------------------------------------------------------------------------

    def _resolve_volcengine_credentials(
        self,
        api_key_override: str | None,
        api_base_override: str | None,
    ) -> tuple[str | None, str, str | None]:
        """返回 (api_key, api_base, endpoint_id)"""
        if api_key_override:
            api_key = api_key_override
        else:
            raw = self.config.volcengine_api_key
            api_key = raw.get_secret_value() if isinstance(raw, SecretStr) else raw

        api_base = api_base_override or self.config.volcengine_api_base
        endpoint_id = self.config.volcengine_image_endpoint_id or self.config.volcengine_endpoint_id
        return api_key, api_base, endpoint_id

    async def _generate_volcengine(
        self,
        prompt: str,
        model: str | None = None,
        size: str = "1920x1920",
        n: int = 1,
        negative_prompt: str | None = None,
        reference_image_url: str | None = None,
        strength: float | None = None,
        api_key_override: str | None = None,
        api_base_override: str | None = None,
    ) -> ImageGenerationResult:
        """火山引擎 Seedream txt2img / img2img，支持异步轮询"""
        api_key, api_base, endpoint_id = self._resolve_volcengine_credentials(
            api_key_override, api_base_override,
        )

        if not api_key:
            return ImageGenerationResult(success=False, error="VOLCENGINE_API_KEY 未配置")
        if not endpoint_id and not model:
            return ImageGenerationResult(
                success=False, error="VOLCENGINE_IMAGE_ENDPOINT_ID 未配置"
            )

        try:
            _width, _height = map(int, size.split("x"))

            url = f"{api_base}/images/generations"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            payload: dict[str, Any] = {
                "model": model or endpoint_id,
                "prompt": prompt,
                "size": size,
                "n": n,
                "response_format": "b64_json",
            }

            if negative_prompt:
                payload["negative_prompt"] = negative_prompt
            if reference_image_url:
                payload["image_url"] = reference_image_url
                payload["strength"] = strength if strength is not None else 0.7

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            # 异步任务轮询：如果返回 task_id 而非直接结果
            if "task_id" in data and not data.get("data"):
                return await self._poll_volcengine_task(
                    task_id=data["task_id"],
                    api_base=api_base,
                    headers=headers,
                )

            return self._extract_images(data)

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error("火山引擎图像生成失败: %s", error_detail)
            return ImageGenerationResult(
                success=False, error=f"HTTP {e.response.status_code}: {error_detail}"
            )
        except Exception as e:
            logger.error("火山引擎图像生成异常: %s", e)
            return ImageGenerationResult(success=False, error=str(e))

    async def _poll_volcengine_task(
        self,
        task_id: str,
        api_base: str,
        headers: dict[str, str],
    ) -> ImageGenerationResult:
        """轮询火山引擎异步任务直到完成"""
        url = f"{api_base}/images/tasks/{task_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(_ASYNC_POLL_MAX_ATTEMPTS):
                await asyncio.sleep(_ASYNC_POLL_INTERVAL)
                try:
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.warning("Poll attempt %d failed: %s", attempt + 1, e)
                    continue

                status = data.get("status", "")
                if status in ("succeeded", "completed"):
                    return self._extract_images(data)
                if status in ("failed", "error"):
                    return ImageGenerationResult(
                        success=False,
                        error=data.get("error", {}).get("message", f"任务失败: {status}"),
                    )
                logger.debug("Poll %d/%d: status=%s", attempt + 1, _ASYNC_POLL_MAX_ATTEMPTS, status)

        return ImageGenerationResult(success=False, error="图像生成超时（轮询已达上限）")

    # -------------------------------------------------------------------------
    # OpenAI DALL-E
    # -------------------------------------------------------------------------

    def _resolve_openai_credentials(
        self,
        api_key_override: str | None,
        api_base_override: str | None,
    ) -> tuple[str | None, str]:
        """返回 (api_key, api_base)"""
        if api_key_override:
            api_key = api_key_override
        else:
            raw = self.config.openai_api_key
            api_key = raw.get_secret_value() if isinstance(raw, SecretStr) else raw

        api_base = api_base_override or self.config.openai_api_base
        return api_key, api_base

    async def _generate_openai(
        self,
        prompt: str,
        model: str = "dall-e-3",
        size: str = "1024x1024",
        n: int = 1,
        style: str | None = None,
        reference_image_url: str | None = None,
        api_key_override: str | None = None,
        api_base_override: str | None = None,
    ) -> ImageGenerationResult:
        """OpenAI DALL-E txt2img / img2img (edits)"""
        api_key, api_base = self._resolve_openai_credentials(
            api_key_override, api_base_override,
        )
        if not api_key:
            return ImageGenerationResult(success=False, error="OPENAI_API_KEY 未配置")

        try:
            headers = {"Authorization": f"Bearer {api_key}"}

            if reference_image_url:
                return await self._openai_edit(
                    headers=headers,
                    api_base=api_base,
                    prompt=prompt,
                    model=model,
                    size=size,
                    n=n,
                    reference_image_url=reference_image_url,
                )

            url = f"{api_base}/images/generations"
            headers["Content-Type"] = "application/json"
            payload: dict[str, Any] = {
                "model": model,
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

            return self._extract_images(data)

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error("OpenAI 图像生成失败: %s", error_detail)
            return ImageGenerationResult(
                success=False, error=f"HTTP {e.response.status_code}: {error_detail}"
            )
        except Exception as e:
            logger.error("OpenAI 图像生成异常: %s", e)
            return ImageGenerationResult(success=False, error=str(e))

    async def _openai_edit(
        self,
        headers: dict[str, str],
        api_base: str,
        prompt: str,
        model: str,
        size: str,
        n: int,
        reference_image_url: str,
    ) -> ImageGenerationResult:
        """OpenAI /images/edits (img2img)"""
        url = f"{api_base}/images/edits"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                img_resp = await client.get(reference_image_url, timeout=30.0)
                img_resp.raise_for_status()

                files = {"image": ("ref.png", img_resp.content, "image/png")}
                form_data = {
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "n": str(n),
                    "response_format": "b64_json",
                }
                response = await client.post(url, headers=headers, files=files, data=form_data)
                response.raise_for_status()
                data = response.json()

            return self._extract_images(data)

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error("OpenAI edits 失败: %s", error_detail)
            return ImageGenerationResult(
                success=False, error=f"HTTP {e.response.status_code}: {error_detail}"
            )
        except Exception as e:
            logger.error("OpenAI edits 异常: %s", e)
            return ImageGenerationResult(success=False, error=str(e))

    # -------------------------------------------------------------------------
    # 工具方法
    # -------------------------------------------------------------------------

    @staticmethod
    def _extract_images(data: dict[str, Any]) -> ImageGenerationResult:
        """从 API 响应中提取图像"""
        images = []
        for item in data.get("data", []):
            if "b64_json" in item:
                images.append(item["b64_json"])
            elif "url" in item:
                images.append(item["url"])
        return ImageGenerationResult(success=bool(images), images=images, usage=data.get("usage"))

    async def test_connection(self, provider: str = "volcengine") -> bool:
        result = await self.generate(
            prompt="一只可爱的小猫",
            provider=provider,  # type: ignore[arg-type]
            n=1,
        )
        return result.success
